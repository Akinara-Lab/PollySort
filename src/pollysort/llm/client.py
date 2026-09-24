"""Provider-agnostisches LLM-Interface (§15).

Ein Interface, mehrere Backends:
- ``OpenRouterClient`` — Stufe 1 (online), multimodal ``google/gemini-3.1-flash-lite``.
- ``OllamaClient``     — Stufe 2 (lokal), festes Modell ``qwen3.5:9b`` über Ollamas native API.
- ``OfflineClient``    — kostenfreie Heuristik ohne Key (Tests/Erststart-Demo).

Umstieg = Config, kein Code-Change: der Rest der Codebase kennt nur ``LLMClient``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import threading
import time
from pathlib import Path
from typing import Protocol

import httpx

from ..models import BeeAnalysis

# Text-Formate direkt lesbar (markitdown greift zusätzlich, s. extractor)
TEXT_SUFFIXES = {".txt", ".md", ".csv", ".json", ".log", ".html", ".htm", ".xml", ".yaml", ".yml"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

# Lokale KI (Ollama) läuft IMMER mit diesen Modellen — unabhängig von den Online-Defaults
# in der Config. So bleibt der Ollama-Modus reproduzierbar und braucht keine Modellwahl.
OLLAMA_MODEL = "qwen3.5:9b"                    # Chat/Analyse-Modell (multimodal, wo unterstützt)
OLLAMA_EMBED_MODEL = "nomic-embed-text-v2-moe"  # lokales Embedding-Modell für das Gedächtnis
#: Kennung, unter der das Gedächtnis im Ollama-Modus seine Vektoren führt. Der Zusatz
#: benennt die TEXTBASIS: Seit 2026-09-24 bettet der Ollama-Modus den Dokument-Auszug ein
#: statt der Modell-Zusammenfassung (Plan §8.3) — sonst könnte das Gedächtnis nicht vor der
#: KI entscheiden. Ältere Gedächtnisse tragen den blanken Modellnamen; der Unterschied
#: löst die bekannte Wechsel-Erkennung aus ('gedaechtnis neu', F1).
OLLAMA_MEMORY_ID = OLLAMA_EMBED_MODEL + "#auszug"
#: Standard-Adresse des lokalen Ollama-Servers — bewusst IPv4 statt ``localhost``: Unter
#: Windows löst ``localhost`` zuerst auf ``::1`` auf, Ollama lauscht aber nur auf IPv4. Jede
#: neue Verbindung wartete dann ~2 s auf den IPv6-Fehlschlag (gemessen 2026-09-24:
#: ``localhost`` 2,4 s, ``127.0.0.1`` 0,33 s je Anfrage).
OLLAMA_ENDPOINT = "http://127.0.0.1:11434"


class LLMError(RuntimeError):
    """Netz-/Provider-Fehler (Timeout, 5xx, 429) — löst Backoff-Retries aus (§16)."""


class LLMAuthError(LLMError):
    """Schlüssel abgelehnt (HTTP 401/403) — abgelaufen oder ungültig. NICHT retrybar.

    Wird nicht wie ein Netzfehler wiederholt; der Nutzer muss den Schlüssel erneuern
    (REPL: ``schluessel setzen``). Der Schlüssel selbst taucht in keiner Meldung auf.
    """


class LLMRequestError(LLMError):
    """Anfrage vom Provider abgelehnt (HTTP 4xx außer 429/401/403) — NICHT retrybar.

    Z. B. ein Payload-Format, das der Server nicht kennt. Ein Retry mit identischem
    Payload würde identisch scheitern; die Meldung nennt den Grund im Klartext statt
    fälschlich „nicht erreichbar" (QA-Befund: Ollama 400 bei PDF-Datei-Anhängen).
    """


class LLMBackendCrash(LLMError):
    """Das Inferenz-Backend des Providers ist abgestürzt (Ollama: llama-server).

    NICHT retrybar mit identischen Parametern — der Absturz reproduziert sich.
    Der OllamaClient nutzt das als Signal, auf CPU-Inferenz auszuweichen.
    """


def _body_snippet(r: httpx.Response) -> str:
    """Kurzer, menschenlesbarer Auszug aus einer Fehlerantwort (für Meldungen)."""
    try:
        err = r.json().get("error")
        if isinstance(err, dict):
            return str(err.get("message") or err)[:200]
        if err:
            return str(err)[:200]
    except Exception:
        pass
    return (getattr(r, "text", "") or "")[:200]


def verify_openrouter_key(api_key: str, timeout: float = 10.0) -> tuple[bool, str]:
    """Einen OpenRouter-Schlüssel prüfen (``GET /api/v1/key``). Gibt ``(ok, klartext_grund)``.

    Macht einen einzigen, günstigen Request — der Schlüssel wird nie geloggt oder ausgegeben.
    """
    if not (api_key or "").strip():
        return False, "kein Schlüssel hinterlegt"
    try:
        r = httpx.get("https://openrouter.ai/api/v1/key",
                      headers={"Authorization": f"Bearer {api_key.strip()}"}, timeout=timeout)
    except httpx.HTTPError as exc:
        return False, f"OpenRouter nicht erreichbar ({exc.__class__.__name__})"
    if r.status_code == 200:
        return True, "gültig"
    if r.status_code in (401, 403):
        return False, "wird abgelehnt (abgelaufen oder ungültig)"
    return False, f"unerwartete Antwort (HTTP {r.status_code})"


# Zentrale Timeouts für Außen-Calls (§16) — bewusst knapp, damit ein hängender
# Provider nie den ganzen Lauf blockiert. Der Backoff-Retry fängt Transientes ab.
LLM_TIMEOUT = httpx.Timeout(60.0, connect=10.0)   # Analyse/Embedding (PDF-Upload braucht Luft)
PING_TIMEOUT = 1.5                                 # Erreichbarkeits-Checks (Ollama)


def ollama_available(endpoint: str = OLLAMA_ENDPOINT) -> bool:
    """Antwortet lokal ein Ollama-SERVER? (Nur die Installation reicht nicht —
    sonst bietet der Assistent eine lokale KI an, die sofort scheitert; OPT-7.)"""
    try:
        r = httpx.get(f"{endpoint.rstrip('/')}/api/tags", timeout=PING_TIMEOUT)
        return r.status_code == 200
    except Exception:
        return False


def ollama_models(endpoint: str = OLLAMA_ENDPOINT) -> list[str] | None:
    """Welche Modelle hat der lokale Ollama-Server gezogen? ``None`` = nicht erreichbar.

    Die Namen kommen mit Tag zurück (``qwen3.5:9b``, ``nomic-embed-text-v2-moe:latest``);
    :func:`ollama_has_model` vergleicht deshalb tag-tolerant. Gedacht für ``doctor``: Ein
    fehlendes Embedding-Modell fällt sonst nie auf — das Gedächtnis lernt dann einfach
    still nichts dazu.
    """
    try:
        r = httpx.get(f"{endpoint.rstrip('/')}/api/tags", timeout=PING_TIMEOUT)
        if r.status_code != 200:
            return None
        return [str(m.get("name", "")) for m in r.json().get("models", [])]
    except Exception:
        return None


def ollama_version(endpoint: str = OLLAMA_ENDPOINT) -> str | None:
    """Versionsnummer des lokalen Ollama-Servers (``None`` = nicht erreichbar)."""
    try:
        r = httpx.get(f"{endpoint.rstrip('/')}/api/version", timeout=PING_TIMEOUT)
        return str(r.json().get("version")) if r.status_code == 200 else None
    except Exception:
        return None


def ollama_geladen(endpoint: str = OLLAMA_ENDPOINT) -> list[dict] | None:
    """Welche Modelle Ollama gerade im Speicher hat — mit ``size`` (gesamt) und
    ``size_vram`` (davon auf der Grafikkarte). ``None`` = nicht erreichbar.

    Daran erkennt ``doctor``, wenn ein Modell teilweise auf der CPU läuft: am 2026-09-24
    lud Ollama 0.34 das 9B mit 65 536 Tokens Kontext — 42 % landeten auf der CPU, und
    PollySort wurde still langsamer. Seitdem soll so etwas sofort auffallen.
    """
    try:
        r = httpx.get(f"{endpoint.rstrip('/')}/api/ps", timeout=PING_TIMEOUT)
        return list(r.json().get("models", [])) if r.status_code == 200 else None
    except Exception:
        return None


def ollama_has_model(name: str, models: list[str]) -> bool:
    """``nomic-embed-text-v2-moe`` trifft auch ``nomic-embed-text-v2-moe:latest`` —
    ``:latest`` ist Ollamas stiller Standard-Tag. Ein Name ohne Tag passt auf jeden Tag."""
    want = name.lower().removesuffix(":latest")
    for m in (x.lower().removesuffix(":latest") for x in models):
        if m == want or (":" not in want and m.split(":", 1)[0] == want):
            return True
    return False


class Usage:
    """Grobe Kosten-/Token-Buchführung pro Lauf (§16)."""

    def __init__(self) -> None:
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def add(self, prompt: int = 0, completion: int = 0) -> None:
        self.calls += 1
        self.prompt_tokens += prompt
        self.completion_tokens += completion

    def est_cost_eur(self) -> float:
        # sehr grobe Schätzung für gemini-flash-lite-Klasse (~0,10 $/1M In, 0,30 $/1M Out)
        usd = self.prompt_tokens / 1e6 * 0.10 + self.completion_tokens / 1e6 * 0.30
        return round(usd * 0.92, 4)


class LLMClient(Protocol):
    """Was der Rest der Codebase kennt (§15)."""

    usage: Usage
    embed_model: str      # Kennung des Embedding-Modells (für die F1-Wechsel-Erkennung)

    def analyze(self, *, text: str | None = None, file_path: str | None = None) -> BeeAnalysis: ...
    def embed(self, text: str) -> list[float]: ...
    def suggest_subrouting(self, categories: list[str]) -> dict[str, str]: ...


PROMPT = """Du bist ein Dokumenten-Archivar. Analysiere das Dokument und gib NUR gültiges JSON zurück:
{{
  "title":            "<kurzer Titel>",
  "summary":          "<3-5 Saetze Kernaussage>",
  "keywords":         ["<5 Stichworte>"],
  "funktion_aufgabe": "<welche Aufgabe hat dieses Dokument? Wozu dient es? 1 Satz>",
  "kategorie":        "<{kategorie_hint}>"
}}
{regeln}{known_line}{fewshots}
Kein Markdown, keine Erklaerung."""


def _format_fewshots(few_shots: list[dict]) -> str:
    """Korrekturen aus corrections.jsonl als Few-Shot-Hinweise anhängen (§14.4)."""
    if not few_shots:
        return ""
    lines = ["\nBeispiele aus früheren Korrekturen (Titel → richtige Kategorie):"]
    for fs in few_shots:
        lines.append(f'- "{fs.get("title", "")}" → {fs.get("kategorie_neu", "")}')
    return "\n".join(lines)


def _format_regeln(wachstafel: str) -> str:
    """Wachstafel-Regeln als verbindliche Prompt-Erweiterung injizieren (§Meta-Learning/ACE)."""
    text = (wachstafel or "").strip()
    if not text:
        return ""
    return ("Gelernte Projekt-Regeln (UNBEDINGT befolgen; sie schlagen deine Vermutung):\n"
            f"{text}\n\n")


def _apply_wachstafel(blob: str, rules: list[tuple[str, str]]) -> str | None:
    """Erste passende Wachstafel-Regel (Stichwort am Wortanfang) liefert die Zielkategorie."""
    for kw, kat in rules:
        if re.search(r"\b" + re.escape(kw), blob):
            return kat
    return None


def _parse_json(raw: str) -> dict:
    """Robust JSON aus einer Modellantwort ziehen (auch wenn ```json … ``` drumherum steht)."""
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", raw, re.DOTALL)
        if brace:
            raw = brace.group(0)
    return json.loads(raw)


# ---------------------------------------------------------------------------
# OpenRouter (Stufe 1)
# ---------------------------------------------------------------------------
class OpenRouterClient:
    BASE = "https://openrouter.ai/api/v1"
    PROVIDER_NAME = "OpenRouter"      # für Fehlermeldungen (Ollama überschreibt das)

    #: Zusatzfelder, die dieser Provider jedem Chat-Payload mitgibt. Leer für OpenRouter;
    #: Ollama schaltet damit den Denk-Modus ab (s. dort).
    EXTRA_PAYLOAD: dict = {}
    TIMEOUT = LLM_TIMEOUT             # Ollama überschreibt das (CPU-Inferenz braucht Luft)

    def __init__(self, api_key: str, model: str, embed_model: str, categories: list[str],
                 few_shots: list[dict] | None = None, wachstafel: str = "",
                 fallback_model: str | None = None):
        self._key = api_key
        self._model = model
        self._fallback_model = fallback_model
        self._embed_model = embed_model
        self.embed_model = embed_model     # öffentliche Kennung (F1-Wechsel-Erkennung)
        self._categories = categories
        self._few_shots = few_shots or []
        self._wachstafel = wachstafel        # gelernte Projekt-Regeln (ACE), in den Prompt
        self.usage = Usage()
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/Akinara-Lab/PollySort",
            "X-Title": "PollySort",
        }
        # Eine Verbindung für alle Anfragen dieses Clients — erst beim ersten Bedarf
        # aufgebaut (das Anlegen kostet selbst ~0,3 s). Vorher öffnete jede Anfrage eine
        # neue: pro Dokument (Analyse + Embedding) rund 5 s reiner Verbindungsaufbau.
        self._http: httpx.Client | None = None
        self._http_lock = threading.Lock()

    def _client(self) -> httpx.Client:
        """Die gehaltene Verbindung (thread-sicher angelegt — Ultra Swarm teilt sie)."""
        if self._http is None:
            with self._http_lock:
                if self._http is None:
                    self._http = httpx.Client()
        return self._http

    # -- Analyse --------------------------------------------------------------
    def analyze(self, *, text: str | None = None, file_path: str | None = None) -> BeeAnalysis:
        content = self._build_content(text=text, file_path=file_path)
        try:
            return self._analyze_with(self._model, content)
        except (json.JSONDecodeError, ValueError) as exc:
            # Kaputtes/abgeschnittenes JSON vom Hauptmodell → EIN Versuch mit dem
            # konfigurierten Fallback-Modell, statt sofort zum Metadaten-Eintrag (OPT-8).
            if self._fallback_model and self._fallback_model != self._model:
                try:
                    return self._analyze_with(self._fallback_model, content)
                except (json.JSONDecodeError, ValueError):
                    pass
            raise exc

    def _analyze_with(self, model: str, content: list[dict]) -> BeeAnalysis:
        payload = {
            "model": model,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": content}],
            **self.EXTRA_PAYLOAD,
        }
        try:
            data = self._post("/chat/completions", payload)
        except LLMRequestError:
            # Ein Server, der die Zusatzfelder nicht kennt, darf die Analyse nicht kosten.
            if not self.EXTRA_PAYLOAD:
                raise
            for key in self.EXTRA_PAYLOAD:
                payload.pop(key, None)
            data = self._post("/chat/completions", payload)
        usage = data.get("usage", {})
        self.usage.add(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        raw = data["choices"][0]["message"]["content"]
        return BeeAnalysis.model_validate(_parse_json(raw))

    def _build_content(self, *, text: str | None, file_path: str | None) -> list[dict]:
        # Sind Projekt-Kategorien gesetzt (Sortieren), wird das LLM STRENG darauf verpflichtet
        # — so entstehen keine Ordner außerhalb der vorgeschlagenen Menge. Ohne Kategorien
        # (Vorschlags-Pre-Screening) darf es frei ein Label vergeben.
        if self._categories:
            kategorie_hint = ("waehle GENAU EINE der bekannten Kategorien unten, exakt gleiche "
                              "Schreibweise; erfinde KEINE neue Kategorie")
            known_line = ("WICHTIG: Als \"kategorie\" ausschliesslich EINE der bekannten "
                          "Kategorien verwenden (exakt so geschrieben): "
                          f"{', '.join(self._categories)}")
        else:
            # Vorschlags-Modus: Das Modell vergibt das Label frei. Genau hier entstehen
            # sonst die Doppelordner — deshalb bekommt es hier die Benennungs-Regeln.
            from ..taxonomie import SYSTEM_REGELN
            kategorie_hint = ("kurzes, kleingeschriebenes Label nach DOKUMENTTYP, "
                              "Plural, moeglichst ein Wort")
            known_line = "\n" + SYSTEM_REGELN
        prompt = PROMPT.format(kategorie_hint=kategorie_hint, known_line=known_line,
                               fewshots=_format_fewshots(self._few_shots),
                               regeln=_format_regeln(self._wachstafel))
        parts: list[dict] = [{"type": "text", "text": prompt}]
        if text is not None:
            parts.append({"type": "text", "text": f"Dokument:\n<<<\n{text[:60000]}\n>>>"})
            return parts
        # multimodal: Bild/PDF direkt anhängen (§15)
        p = Path(file_path)  # type: ignore[arg-type]
        b64 = base64.b64encode(p.read_bytes()).decode()
        suffix = p.suffix.lower()
        if suffix in IMAGE_SUFFIXES:
            mime = f"image/{'jpeg' if suffix in {'.jpg', '.jpeg'} else suffix.lstrip('.')}"
            parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
        else:  # PDF & andere Binärtypen als file-part
            parts.append({
                "type": "file",
                "file": {"filename": p.name, "file_data": f"data:application/pdf;base64,{b64}"},
            })
        return parts

    # -- Embedding ------------------------------------------------------------
    def embed(self, text: str) -> list[float]:
        data = self._post("/embeddings", {"model": self._embed_model, "input": text})
        return data["data"][0]["embedding"]

    # -- Sub-Routing-Vorschlag (Pre-Screening) --------------------------------
    def suggest_subrouting(self, categories: list[str]) -> dict[str, str]:
        """Fragt das LLM, welche Kategorien nach ``{jahr}/{monat}`` gegliedert werden sollten.

        Ein einziger, günstiger Call. Bei JEDEM Fehler → Rückfall auf die Heuristik, damit
        das Setup nie hängt oder abbricht.
        """
        from ..heuristics import datums_muster as heuristic_muster
        from ..heuristics import suggest_subrouting as heuristic
        if not categories:
            return {}
        prompt = ("Ein Dokumenten-Archiv hat diese Ablage-Kategorien: "
                  f"{', '.join(categories)}.\n"
                  "Welche davon profitieren von Unterordnern nach Jahr und Monat (typisch für "
                  "datierte, laufende Dokumente wie Rechnungen oder Kontoauszüge)? Gib NUR JSON "
                  "zurück: {\"kategorie\": true, ...} mit genau diesen Kategorien als Schlüssel "
                  "(true/false). Kein Markdown.")
        try:
            data = self._post("/chat/completions", {
                "model": self._model, "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": prompt}],
                **self.EXTRA_PAYLOAD,
            })
            flags = _parse_json(data["choices"][0]["message"]["content"])
            known = {c.strip().lower() for c in categories}
            muster = heuristic_muster()
            out = {str(k).strip().lower(): muster
                   for k, v in flags.items() if str(k).strip().lower() in known and bool(v)}
            return out or heuristic(categories)
        except Exception:
            return heuristic(categories)

    # -- HTTP mit Backoff (§16) ----------------------------------------------
    def _post(self, path: str, payload: dict, *, base: str | None = None,
              headers: dict | None = None) -> dict:
        last: Exception | None = None
        for attempt in range(3):
            try:
                r = self._client().post(
                    f"{base or self.BASE}{path}",
                    headers=self._headers if headers is None else headers,
                    json=payload, timeout=self.TIMEOUT,
                )
                # 401/403 ist NICHT transient — sofort abbrechen statt sinnlos zu wiederholen.
                if r.status_code in (401, 403):
                    raise LLMAuthError(
                        f"{self.PROVIDER_NAME}-Schlüssel abgelehnt (HTTP {r.status_code}) — "
                        "abgelaufen oder ungültig; erneuern mit 'schluessel setzen'")
                if r.status_code >= 500 and "llama-server" in (snippet := _body_snippet(r)):
                    # Ollamas Inferenz-Backend ist abgestürzt — reproduziert sich, kein Retry.
                    raise LLMBackendCrash(f"{self.PROVIDER_NAME}-Backend abgestürzt: {snippet}")
                if r.status_code in (429, 500, 502, 503, 504):
                    raise LLMError(f"HTTP {r.status_code}: {_body_snippet(r)}")
                if 400 <= r.status_code < 500:
                    # Payload/Anfrage abgelehnt — ein identischer Retry scheitert identisch.
                    raise LLMRequestError(
                        f"{self.PROVIDER_NAME}: Anfrage abgelehnt (HTTP {r.status_code}) — "
                        f"{_body_snippet(r)}")
                r.raise_for_status()
                return r.json()
            except (LLMAuthError, LLMRequestError, LLMBackendCrash):
                raise                                   # nicht retrybar
            except (httpx.HTTPError, LLMError) as exc:
                last = exc
                time.sleep(2**attempt)  # exponentieller Backoff
        raise LLMError(f"{self.PROVIDER_NAME} nicht erreichbar: {last}")


# ---------------------------------------------------------------------------
# Ollama (Stufe 2) — lokale KI, robust gegen PDF-Payloads und GPU-Abstürze
# ---------------------------------------------------------------------------
def _local_file_text(path: Path) -> str | None:
    """Bester lokaler Text-Extrakt für Binärdateien (v. a. PDF).

    Ollama kennt keine Datei-Anhänge (führte zu HTTP 400) — der Text muss lokal
    gewonnen werden: markitdown, wenn installiert (Extra ``[extract]``), sonst pypdf.
    """
    try:
        from markitdown import MarkItDown
        return MarkItDown().convert(str(path)).text_content
    except Exception:
        pass
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
            return "\n".join((pg.extract_text() or "") for pg in PdfReader(str(path)).pages)
        except Exception:
            return None
    return None


class OllamaClient(OpenRouterClient):
    """Lokale KI über Ollamas **native** API (``/api/chat``, ``/api/embed``).

    Warum nativ statt der OpenAI-kompatiblen ``/v1``-Schnittstelle: Nur hier lassen sich
    Kontextlänge und Sampling setzen. Seit Ollama 0.34 lädt ein Modell ohne Angabe mit
    65 536 Tokens Kontext — das 9B braucht dann 8,5 GB und lief auf einer 8-GB-GPU zu 42 %
    auf der CPU (gemessen 2026-09-24: 20–25 s statt 12–16 s je Dokument). Außerdem bringen
    die Qwen-Modelfiles ``temperature 1`` mit; zum Sortieren gehört ``0``.

    Robustheits-Schichten (QA-Befund 2026-07-14, weiter gültig):
    - **PDF/Binär → lokaler Text:** Ollama akzeptiert keine Datei-Anhänge; der Text wird
      VOR dem Call lokal extrahiert (markitdown/pypdf).
    - **GPU-Crash → CPU:** Stürzt Ollamas llama-server ab, wiederholt der Client die Anfrage
      mit ``num_gpu: 0`` und bleibt für den Rest der Session auf der CPU.
    """

    PROVIDER_NAME = "Ollama"
    # CPU-Inferenz + Modell-Kaltstart brauchen deutlich mehr Luft als ein Online-API-Call.
    TIMEOUT = httpx.Timeout(300.0, connect=5.0)
    #: Kontext jeder Anfrage. Gemessen 2026-09-24 mit dem 9B auf einer 8-GB-GPU: 4096 →
    #: 5,5 GB, 100 % GPU, 6,0 s je Analyse · 8192 → 12 % CPU · 65 536 (Ollama-Standard) →
    #: 42 % CPU, 22 s. Prompt + gekappter Dokumenttext + Antwort passen hinein.
    NUM_CTX = 4096
    #: So viel Dokumenttext geht in die Analyse (≈ 2 Tsd. Tokens; Prompt ~400, Antwort ≤ 800).
    #: Mehr würde Ollama VORNE abschneiden — und mit dem Anfang des Prompts die Anweisungen.
    TEXT_CAP = 7000
    #: Die Entscheidung per Nummer liest nur den Kopf des Dokuments: Der Typ steht fast
    #: immer oben („RECHNUNG", „Kontoauszug Nr. 3"). So gemessen (Plan §8.13).
    AUSZUG = 1500
    #: Textbasis des Gedächtnisses (s. ``OLLAMA_MEMORY_ID``): der Dokument-Auszug.
    memory_basis = "auszug"

    def __init__(self, endpoint: str, categories: list[str] | None,
                 few_shots: list[dict] | None = None, wachstafel: str = ""):
        super().__init__(api_key="ollama", model=OLLAMA_MODEL, embed_model=OLLAMA_EMBED_MODEL,
                         categories=categories, few_shots=few_shots, wachstafel=wachstafel)
        base = endpoint.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3].rstrip("/")
        self._native_base = base
        self.BASE = base + "/v1"          # nur noch für Altpfade; Analyse & Embedding sind nativ
        self.embed_model = OLLAMA_MEMORY_ID
        self._cpu_mode = False            # nach GPU-Crash: dauerhaft CPU-Inferenz

    # -- Inhalte: PDFs/Binär lokal in Text wandeln, Länge kappen ---------------
    def _build_content(self, *, text: str | None, file_path: str | None) -> list[dict]:
        if text is None and file_path is not None:
            p = Path(file_path)
            if p.suffix.lower() not in IMAGE_SUFFIXES:
                text = _local_file_text(p)
                if not (text or "").strip():
                    raise LLMRequestError(
                        f"Ollama kann Dateien nicht direkt lesen und aus '{p.name}' ließ sich "
                        "lokal kein Text extrahieren (Tipp: Extra [extract] installieren oder "
                        "Modus 'online' nutzen).")
        if text is not None:
            return super()._build_content(text=text[:self.TEXT_CAP], file_path=None)
        return super()._build_content(text=None, file_path=file_path)

    # -- Native API -------------------------------------------------------------
    def _options(self, **extra) -> dict:
        opts = {"num_ctx": self.NUM_CTX, "temperature": 0, **extra}
        if self._cpu_mode:
            opts["num_gpu"] = 0
        return opts

    def _chat(self, prompt: str, *, images: list[str] | None = None, fmt: str | None = "json",
              num_predict: int = 800, logprobs: bool = False) -> dict:
        """Eine native Chat-Anfrage. GPU-Crash → einmal auf der CPU wiederholen."""
        msg: dict = {"role": "user", "content": prompt}
        if images:
            msg["images"] = images
        # Denk-Modus AUS: Thinking-Modelle (qwen3.5) grübeln sonst vor jeder Antwort — für
        # ein kurzes JSON oder eine Ziffer bringt das nichts (gemessen: 12,2 s vs. 2,8 s).
        payload: dict = {"model": self._model, "messages": [msg], "stream": False,
                         "think": False}
        if fmt:
            payload["format"] = fmt
        if logprobs:
            payload["logprobs"] = True
            payload["top_logprobs"] = 10
        for _ in range(2):
            payload["options"] = self._options(num_predict=num_predict)
            try:
                return self._post("/api/chat", payload, base=self._native_base, headers={})
            except LLMBackendCrash:
                if self._cpu_mode:
                    raise
                self._cpu_mode = True     # GPU-Backend crasht → ab jetzt CPU
            except LLMRequestError as exc:
                # Manche Modelle kennen den 'think'-Parameter nicht → einmal ohne probieren.
                if "think" not in str(exc).lower() or "think" not in payload:
                    raise
                payload.pop("think", None)
        return self._post("/api/chat", payload, base=self._native_base, headers={})

    # -- Volle Analyse (Titel, Zusammenfassung, Stichworte, Kategorie) ----------
    def analyze(self, *, text: str | None = None, file_path: str | None = None) -> BeeAnalysis:
        content = self._build_content(text=text, file_path=file_path)
        prompt = "\n\n".join(p["text"] for p in content if p.get("type") == "text")
        images = [p["image_url"]["url"].split("base64,", 1)[-1]
                  for p in content if p.get("type") == "image_url"]
        data = self._chat(prompt, images=images)
        self.usage.add(data.get("prompt_eval_count", 0), data.get("eval_count", 0))
        return BeeAnalysis.model_validate(_parse_json(data["message"]["content"]))

    # -- Entscheidung per Nummer (Plan §8.3) ------------------------------------
    def decide(self, text: str, categories: list[str]) -> tuple[str, float] | None:
        """Die Kategorie mit EINEM Token wählen — Konfidenz aus den Logprobs.

        Gemessen 2026-09-24 mit ``qwen3.5:9b``: 99 % Treffer in 0,5 s (GPU) statt 97 % in
        22 s über die volle Analyse; die Konfidenz ist kalibriert (ECE 0,01). Die Wahl
        kommt aus den **Logprobs**, nicht aus dem gezogenen Token: Die Modelfiles setzen
        ``presence_penalty``, und das bestraft Ziffern, die schon im Prompt stehen — also
        jede Optionsnummer.

        Rückgabe ``(kategorie, wahrscheinlichkeit)``; ``_unassigned`` heißt „keine passt".
        ``None``, wenn der Weg nicht trägt (mehr als neun Kategorien, oder der Server liefert
        keine Logprobs) — dann analysiert der Aufrufer wie bisher vollständig.
        """
        names = [c for c in categories if c and c.strip().lower() != "_unassigned"]
        if not names or len(names) > 9 or not (text or "").strip():
            return None
        data = self._chat(entscheid_prompt(names, text[:self.AUSZUG], self._wachstafel),
                          fmt=None, num_predict=1, logprobs=True)
        self.usage.add(data.get("prompt_eval_count", 0), data.get("eval_count", 0))
        return waehle_aus_logprobs(data.get("logprobs"), names)

    # -- Embedding: Task-Prefix (nomic-v2-moe) + CPU-Fallback -------------------
    def embed(self, text: str) -> list[float]:
        payload: dict = {"model": self._embed_model,
                         # das MoE-Embedding erwartet einen Task-Prefix
                         "input": f"search_document: {text}"}
        for _ in range(2):
            if self._cpu_mode:
                payload["options"] = {"num_gpu": 0}
            try:
                data = self._post("/api/embed", payload, base=self._native_base, headers={})
                return data["embeddings"][0]
            except LLMBackendCrash:
                if self._cpu_mode:
                    raise
                self._cpu_mode = True
        raise LLMError("Ollama-Embedding nicht möglich")   # pragma: no cover

    # -- Unterordner-Vorschlag, ebenfalls nativ ---------------------------------
    def suggest_subrouting(self, categories: list[str]) -> dict[str, str]:
        from ..heuristics import datums_muster as heuristic_muster
        from ..heuristics import suggest_subrouting as heuristic
        if not categories:
            return {}
        try:
            data = self._chat(_subrouting_prompt(categories), num_predict=300)
            flags = _parse_json(data["message"]["content"])
            known = {c.strip().lower() for c in categories}
            muster = heuristic_muster()
            out = {str(k).strip().lower(): muster
                   for k, v in flags.items() if str(k).strip().lower() in known and bool(v)}
            return out or heuristic(categories)
        except Exception:
            return heuristic(categories)


def _subrouting_prompt(categories: list[str]) -> str:
    return ("Ein Dokumenten-Archiv hat diese Ablage-Kategorien: "
            f"{', '.join(categories)}.\n"
            "Welche davon profitieren von Unterordnern nach Jahr und Monat (typisch für "
            "datierte, laufende Dokumente wie Rechnungen oder Kontoauszüge)? Gib NUR JSON "
            "zurück: {\"kategorie\": true, ...} mit genau diesen Kategorien als Schlüssel "
            "(true/false). Kein Markdown.")


def entscheid_prompt(names: list[str], auszug: str, wachstafel: str = "") -> str:
    """Der Prompt der Nummer-Entscheidung — genau so gemessen (Plan §8.13).

    Gelernte Wachstafel-Regeln stehen, falls vorhanden, davor: Sie schlagen die Vermutung
    des Modells, wie in der vollen Analyse.
    """
    lines = "\n".join(f"{i} = {n}" for i, n in enumerate(names, 1))
    return (f"{_format_regeln(wachstafel)}"
            "Du sortierst Dokumente in Ordner. Wähle für das Dokument GENAU EINE Kategorie.\n"
            f"Kategorien:\n{lines}\n0 = keine davon passt\n\n"
            f"Dokument:\n<<<\n{auszug}\n>>>\n\nAntworte nur mit der Nummer.")


def waehle_aus_logprobs(logprobs, names: list[str]) -> tuple[str, float] | None:
    """Aus den Top-Logprobs des ersten Tokens die Verteilung über ``0``…``N`` bilden."""
    if not logprobs:
        return None
    valid = {str(i) for i in range(len(names) + 1)}
    lp: dict[str, float] = {}
    for cand in (logprobs[0] or {}).get("top_logprobs", []) or []:
        tok = str(cand.get("token", "")).strip()
        if tok in valid:
            lp[tok] = max(lp.get(tok, -1e9), float(cand.get("logprob", -1e9)))
    if not lp:
        return None
    top = max(lp.values())
    z = sum(math.exp(v - top) for v in lp.values())
    best = max(lp, key=lp.get)
    kategorie = "_unassigned" if best == "0" else names[int(best) - 1].strip().lower()
    return kategorie, round(math.exp(lp[best] - top) / z, 4)


# ---------------------------------------------------------------------------
# Offline (kostenfreie Heuristik, kein Key)
# ---------------------------------------------------------------------------
class OfflineClient:
    """Deterministische Heuristik ohne Netz — für Tests & Erststart ohne Key.

    Ratet Titel/Keywords/Kategorie aus Dateiname + Textanfang. Kein LLM, keine Kosten.
    """

    # Kennung des Offline-Pseudo-Embeddings (Hash, feste Dimension) — s. embed().
    embed_model = "offline:hash-2048"

    def __init__(self, categories: list[str] | None, wachstafel: str = ""):
        from ..wachstafel import parse_rules
        # ``None`` heißt bewusst „alle Regeln" (so klassifiziert der Struktur-Vorschlag,
        # bei dem es noch keine Projekt-Kategorien gibt). Eine LEERE Liste dagegen heißt
        # „keine Kategorie erlaubt" — damit käme für jedes Dokument `_unassigned` heraus.
        self._categories = categories
        self._rules = parse_rules(wachstafel)     # gelernte Regeln (ACE) schlagen die Heuristik
        self.usage = Usage()

    def analyze(self, *, text: str | None = None, file_path: str | None = None) -> BeeAnalysis:
        from ..heuristics import classify, keywords
        p = Path(file_path) if file_path else None
        name = p.stem if p else "dokument"
        ext = p.suffix.lower() if p else ""
        self.usage.add(0, 0)  # kostenfrei, aber als 'Call' gezählt

        # Gelernte Wachstafel-Regeln zuerst: ein Treffer schlägt die generische Heuristik.
        blob = f"{name} {text or ''}".lower()
        kategorie = _apply_wachstafel(blob, self._rules)
        if kategorie is None:
            # Gleiche Regeln wie der Onboarding-Vorschlag, beschränkt auf die Projekt-Kategorien.
            kategorie = classify(name, text or "", ext, allowed=self._categories)
        seen = keywords(f"{name} {text or ''}", limit=5)
        title = name.replace("_", " ").replace("-", " ").strip().title() or "Dokument"
        summary = (text or "").strip().replace("\n", " ")[:280]
        # Bewusst OHNE generischen Boilerplate: identische Floskeln in jedem Eintrag würden
        # sonst die Cosine-Ähnlichkeit unverwandter Dokumente künstlich anheben.
        return BeeAnalysis(
            title=title,
            summary=summary,
            keywords=seen,
            funktion_aufgabe=(kategorie if kategorie != "_unassigned" else ""),
            kategorie=kategorie,
        )

    def embed(self, text: str) -> list[float]:
        """Deterministisches Pseudo-Embedding — nur für lokale Tests der kNN-Logik.

        Breite Dimension (2048), um Hash-Kollisionen zwischen unverwandten Tokens klein zu
        halten; sonst wirken thematisch fremde Dokumente fälschlich ähnlich.
        """
        dim = 2048
        vec = [0.0] * dim
        for tok in re.findall(r"\w+", text.lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            vec[h % dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def suggest_subrouting(self, categories: list[str]) -> dict[str, str]:
        """Offline: rein heuristischer Unterordner-Vorschlag (kein Netz)."""
        from ..heuristics import suggest_subrouting as heuristic
        return heuristic(categories)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def build_client(cfg, api_key: str | None, categories: list[str] | None,
                 few_shots: list[dict] | None = None, wachstafel: str = "") -> LLMClient:
    """Wählt das Backend anhand der Config (§15). Ohne Key → Offline-Fallback.

    ``wachstafel`` (gelernte Projekt-Regeln, ACE) wird durchgereicht: online in den Prompt
    injiziert, offline direkt angewandt. Es ist Projekt-Text, nie ein Geheimnis.
    """
    provider = cfg.llm_provider
    if provider == "offline" or (provider == "openrouter" and not api_key):
        return OfflineClient(categories, wachstafel=wachstafel)
    if provider == "ollama":
        # Modell ist bewusst fixiert (qwen3.5:9b) — nicht aus cfg, das sind Online-Defaults.
        return OllamaClient(cfg.llm_endpoint or OLLAMA_ENDPOINT,
                            categories, few_shots, wachstafel=wachstafel)
    return OpenRouterClient(api_key, cfg.llm_model, cfg.embed_model, categories,  # type: ignore[arg-type]
                            few_shots, wachstafel=wachstafel,
                            fallback_model=getattr(cfg, "llm_fallback", None))


def embed_model_for(cfg, api_key: str | None) -> str:
    """Kennung des Embedding-Modells, das ``build_client`` für diese Config wählen würde —
    ohne einen echten Client zu bauen (für ``doctor`` / F1-Wechsel-Erkennung)."""
    provider = cfg.llm_provider
    if provider == "offline" or (provider == "openrouter" and not api_key):
        return OfflineClient.embed_model
    if provider == "ollama":
        return OLLAMA_MEMORY_ID
    return cfg.embed_model
