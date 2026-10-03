"""Der Flugbrett-Server — nur Standardbibliothek, nur ``127.0.0.1``, nur mit Token.

Der Server läuft auf dem eigenen Rechner und ist für genau einen Menschen da. Trotzdem
gilt: Ein Browser besucht nebenbei auch fremde Seiten, und die dürfen nicht an den Stock.

- Gebunden wird **ausschließlich an 127.0.0.1** — aus dem Netz ist nichts erreichbar.
- Jede API-Anfrage braucht das **Sitzungs-Token** (Header ``X-Flugbrett-Token``). Es wird
  beim Start zufällig erzeugt und reist nur im Fragment der geöffneten Adresse (``#t=…``)
  zur Seite — Fragmente schickt der Browser nie an einen Server.
- Der ``Host``-Header muss ``127.0.0.1``/``localhost`` mit dem richtigen Port sein
  (gegen DNS-Rebinding); eine fremde ``Origin`` wird abgewiesen.
- Schreibende Aktionen nur als ``POST`` mit JSON-Körper, höchstens 1 MB.
- Strenge Content-Security-Policy: kein Fremd-Code, keine Inline-Skripte, kein Einbetten.

Es wird nichts mitgeschrieben, was ein Token, einen Pfad-Inhalt oder ein Dokument enthält.
"""

from __future__ import annotations

import argparse
import hmac
import inspect
import json
import queue
import secrets
import select
import socket
import sys
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .. import config, i18n
from .dienst import Beschaeftigt, Dienst, Gesperrt, Ungueltig

STATIC = Path(__file__).parent / "static"
MAX_KOERPER = 1 << 20

TYPEN = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml",
    ".png": "image/png", ".ico": "image/x-icon", ".json": "application/json",
}

CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
       "form-action 'self'; frame-ancestors 'none'")


def _aktionen(dienst: Dienst) -> tuple[dict, dict]:
    """Erlaubte Ansichten (GET) und Aktionen (POST) — nur, was ausdrücklich markiert ist."""
    ansichten, aktionen = {}, {}
    for name in dir(type(dienst)):
        fn = getattr(type(dienst), name)
        if getattr(fn, "ansicht", None):
            ansichten[name] = getattr(dienst, name)
        if getattr(fn, "auftrag", None):
            aktionen[name] = getattr(dienst, name)
    return ansichten, aktionen


def _argumente(fn, daten: dict) -> dict:
    """Nur Parameter durchlassen, die die Methode kennt — alles andere ist ein Fehler."""
    erlaubt = {n for n, p in inspect.signature(fn).parameters.items()
               if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)}
    fremd = set(daten) - erlaubt
    if fremd:
        raise Ungueltig(i18n.t("web.err.params"))
    return dict(daten)


class Flugbrett(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, adresse, dienst: Dienst, token: str):
        self.dienst = dienst
        self.token = token
        self.ansichten, self.aktionen = _aktionen(dienst)
        super().__init__(adresse, Handler)

    @property
    def port(self) -> int:
        return self.server_address[1]

    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/#t={self.token}"


class Handler(BaseHTTPRequestHandler):
    server: Flugbrett
    protocol_version = "HTTP/1.1"
    server_version = "PollySort-Flugbrett"
    sys_version = ""

    # -- Kein Zugriffsprotokoll auf die Konsole (Pfade, Token, Inhalte bleiben privat) --
    def log_message(self, format, *args) -> None:
        pass

    # -- Antworten -------------------------------------------------------------
    def _kopf(self, status: int, typ: str, laenge: int | None = None, *, cache: bool = False) -> None:
        self.send_response(status)
        self.send_header("Content-Type", typ)
        if laenge is not None:
            self.send_header("Content-Length", str(laenge))
        self.send_header("Cache-Control", "no-cache" if cache else "no-store")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.end_headers()

    def _json(self, status: int, daten) -> None:
        body = json.dumps(daten, ensure_ascii=False, default=str).encode("utf-8")
        self._kopf(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def _fehler(self, status: int, text: str) -> None:
        self._json(status, {"fehler": text})

    # -- Schutz ------------------------------------------------------------------
    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").strip().lower()
        return host in {f"127.0.0.1:{self.server.port}", f"localhost:{self.server.port}"}

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        return origin.lower() in {f"http://127.0.0.1:{self.server.port}",
                                  f"http://localhost:{self.server.port}"}

    def _token_ok(self) -> bool:
        gesendet = self.headers.get("X-Flugbrett-Token") or ""
        return hmac.compare_digest(gesendet.encode(), self.server.token.encode())

    def _api_erlaubt(self) -> bool:
        if not self._host_ok() or not self._origin_ok():
            self._fehler(HTTPStatus.FORBIDDEN, "forbidden")
            return False
        if not self._token_ok():
            self._fehler(HTTPStatus.UNAUTHORIZED, i18n.t("web.err.token"))
            return False
        return True

    # -- GET ----------------------------------------------------------------------
    def do_GET(self) -> None:
        teile = urlsplit(self.path)
        if teile.path.startswith("/api/"):
            if not self._api_erlaubt():
                return
            name = teile.path[len("/api/"):]
            if name == "ereignisse":
                self._ereignisse()
                return
            fn = self.server.ansichten.get(name)
            if fn is None:
                self._fehler(HTTPStatus.NOT_FOUND, "?")
                return
            params = {k: v[-1] for k, v in parse_qs(teile.query).items()}
            self._ausfuehren(fn, params)
            return
        if not self._host_ok():
            self._fehler(HTTPStatus.FORBIDDEN, "forbidden")
            return
        self._datei(teile.path)

    def _datei(self, pfad: str) -> None:
        name = "index.html" if pfad in ("", "/") else pfad.lstrip("/")
        ziel = (STATIC / name).resolve()
        try:
            ziel.relative_to(STATIC.resolve())
        except ValueError:
            self._fehler(HTTPStatus.NOT_FOUND, "?")
            return
        if not ziel.is_file() or ziel.suffix not in TYPEN:
            self._fehler(HTTPStatus.NOT_FOUND, "?")
            return
        body = ziel.read_bytes()
        self._kopf(HTTPStatus.OK, TYPEN[ziel.suffix], len(body), cache=True)
        self.wfile.write(body)

    def _ereignisse(self) -> None:
        """Server-Sent Events: Fortschritt & Meldungen live. Gelesen per fetch (mit Token)."""
        q = self.server.dienst.bus.abonnieren()
        try:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            self.close_connection = True
            self.wfile.write(b": flugbrett offen\n\n")
            self.wfile.flush()
            zuletzt = time.monotonic()
            while True:
                try:
                    e = q.get(timeout=1.0)
                except queue.Empty:
                    # Jede Sekunde nachsehen, ob das Fenster zu ist — die App beendet sich
                    # danach (web/app.py), und das soll nicht erst beim nächsten Lebenszeichen
                    # auffallen.
                    if self._getrennt():
                        break
                    if time.monotonic() - zuletzt < 15:
                        continue
                    self.wfile.write(b": summ\n\n")          # Lebenszeichen
                else:
                    zeile = "data: " + json.dumps(e, ensure_ascii=False, default=str) + "\n\n"
                    self.wfile.write(zeile.encode("utf-8"))
                self.wfile.flush()
                zuletzt = time.monotonic()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            self.server.dienst.bus.abbestellen(q)

    def _getrennt(self) -> bool:
        """Hat die Gegenseite die Verbindung geschlossen? Lesbar und 0 Bytes = zu.

        Ein Ereignis-Abonnent sendet nach seiner Anfrage nichts mehr; wird der Socket
        trotzdem lesbar, ist das nur das Ende der Verbindung.
        """
        try:
            lesbar, _, _ = select.select([self.connection], [], [], 0)
            return bool(lesbar) and self.connection.recv(1, socket.MSG_PEEK) == b""
        except (OSError, ValueError):
            return True

    # -- POST ---------------------------------------------------------------------
    def do_POST(self) -> None:
        teile = urlsplit(self.path)
        if not teile.path.startswith("/api/"):
            self._fehler(HTTPStatus.NOT_FOUND, "?")
            return
        if not self._api_erlaubt():
            return
        fn = self.server.aktionen.get(teile.path[len("/api/"):])
        if fn is None:
            self._fehler(HTTPStatus.NOT_FOUND, "?")
            return
        typ = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if typ != "application/json":
            self._fehler(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, i18n.t("web.err.params"))
            return
        try:
            laenge = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            laenge = -1
        if laenge < 0 or laenge > MAX_KOERPER:
            self._fehler(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, i18n.t("web.err.params"))
            return
        try:
            daten = json.loads(self.rfile.read(laenge) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            daten = None
        if not isinstance(daten, dict):
            self._fehler(HTTPStatus.BAD_REQUEST, i18n.t("web.err.params"))
            return
        self._ausfuehren(fn, daten)

    def _ausfuehren(self, fn, daten: dict) -> None:
        try:
            gebunden = inspect.signature(fn).bind(**_argumente(fn, daten))
        except (TypeError, Ungueltig):
            self._fehler(HTTPStatus.BAD_REQUEST, i18n.t("web.err.params"))
            return
        try:
            self._json(HTTPStatus.OK, fn(*gebunden.args, **gebunden.kwargs))
        except Ungueltig as exc:
            self._fehler(HTTPStatus.BAD_REQUEST, str(exc))
        except Beschaeftigt as exc:
            self._fehler(HTTPStatus.CONFLICT, str(exc))
        except Gesperrt as exc:
            self._fehler(HTTPStatus.LOCKED, str(exc))
        except Exception as exc:          # ein Fehler beendet nie den Server (§16)
            self._fehler(HTTPStatus.INTERNAL_SERVER_ERROR, i18n.t("r.failed", err=exc))


# --------------------------------------------------------------------------- #
#  Start
# --------------------------------------------------------------------------- #
def startziel() -> Path | None:
    """Welches Projekt? Zuletzt genutztes > erstes bekanntes > keins (dann Assistent)."""
    cfg = config.load_config()
    if cfg.hive:
        p = Path(cfg.hive)
        if p.exists() and config.is_setup(p):
            return p.resolve()
    for p in config.list_projects():
        if config.is_setup(p):
            return p.resolve()
    return None


def starten(hive: Path | None, *, port: int | None = None, browser: bool = True
            ) -> tuple[Flugbrett, str, Dienst]:
    """Server bauen (noch nicht laufen lassen). Ist der Wunsch-Port belegt, nimmt er einen freien."""
    dienst = Dienst(hive)
    token = secrets.token_urlsafe(24)
    wunsch = config.load_config().web_port if port is None else port
    try:
        httpd = Flugbrett(("127.0.0.1", wunsch), dienst, token)
    except OSError:
        httpd = Flugbrett(("127.0.0.1", 0), dienst, token)
    url = httpd.url()
    if browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    return httpd, url, dienst


def main(argv: list[str] | None = None) -> int:
    """Einstiegspunkt von ``pollysort-web``."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass
    i18n.set_language(getattr(config.load_config(), "language", "de"))
    parser = argparse.ArgumentParser(prog="pollysort-web", description=i18n.t("web.cli.desc"))
    parser.add_argument("pfad", nargs="?", help=i18n.t("web.cli.arg_path"))
    parser.add_argument("--port", type=int, default=None, help=i18n.t("web.cli.arg_port"))
    parser.add_argument("--kein-browser", "--no-browser", dest="kein_browser",
                        action="store_true", help=i18n.t("web.cli.arg_nobrowser"))
    args = parser.parse_args(argv)
    hive = Path(args.pfad).expanduser().resolve() if args.pfad else startziel()
    httpd, url, dienst = starten(hive, port=args.port, browser=not args.kein_browser)
    print(f"🐝  {i18n.t('web.cli.open', url=url)}", flush=True)
    print(f"🐝  {i18n.t('web.cli.stop')}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        dienst.wache.stoppen()
        httpd.server_close()
        print(f"🐝  {i18n.t('web.cli.closed')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
