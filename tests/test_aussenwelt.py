"""Außenwelt-Anbindung (§v0.3): echter Discord-Botenflug (gemockt) + Pollen-Uhr (.ics).

Sichert zu:
- Discord setzt den korrekten httpx.post ab (URL/Header/Payload); Fehler (401/404/Netz) werden
  sauber abgefangen — 🔒 das Bot-Token taucht in KEINER Fehlermeldung auf.
- Baubienen schreiben beim Wabenbau eine gültige .ics-Datei (RFC 5545).
- Der Trigger-Workflow feuert fällige Deadlines genau EINMAL (Anti-Spam via `gemeldet`).
"""

from __future__ import annotations

import types

import httpx
import pytest

from bumble.config import AppConfig, HiveSeed, honig
from bumble.console import BeeConsole
from bumble.journal import Journal
from bumble.llm.client import OfflineClient
from bumble.pipeline import Context
from bumble.swarm import Baubiene, Kalender, Waechterbiene
from bumble.swarm.ics import build_ics
from bumble.swarm.kalender import Termin
from bumble.swarm.kanaele import DiscordKanal, KanalError

TOKEN = "SECRET-BOT-TOKEN-abcd1234"
CHANNEL = "998877665544"


def _resp(status: int):
    return types.SimpleNamespace(status_code=status)


def _ctx(hive):
    hive.mkdir(parents=True, exist_ok=True)
    seed = HiveSeed(categories=["rechnungen"], responsibility={"rechnungen": []})
    return Context.build(hive=hive, cfg=AppConfig(llm_provider="offline"), seed=seed,
                         client=OfflineClient(seed.categories), console=BeeConsole(quiet=True),
                         journal=Journal(hive))


# ---- Echter Discord-POST (gemockt) ---------------------------------------
def test_discord_posts_correctly(monkeypatch):
    captured = {}

    def fake_post(url, **kw):
        captured["url"] = url
        captured["headers"] = kw.get("headers")
        captured["json"] = kw.get("json")
        return _resp(200)

    monkeypatch.setattr(httpx, "post", fake_post)
    DiscordKanal(TOKEN, CHANNEL).senden("Deadline: Rechnungen", "Fällig heute")

    assert captured["url"] == f"https://discord.com/api/v10/channels/{CHANNEL}/messages"
    assert captured["headers"]["Authorization"] == f"Bot {TOKEN}"
    assert "Deadline: Rechnungen" in captured["json"]["content"]
    assert "Fällig heute" in captured["json"]["content"]
    # Token NUR im Header — nie im Payload.
    import json as _json
    assert TOKEN not in _json.dumps(captured["json"])


@pytest.mark.parametrize("status", [401, 403, 404, 500])
def test_discord_http_errors_are_caught_without_token(monkeypatch, status):
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _resp(status))
    with pytest.raises(KanalError) as ei:
        DiscordKanal(TOKEN, CHANNEL).senden("t", "x")
    assert TOKEN not in str(ei.value)          # 🔒 kein Token-Leak in der Fehlermeldung


def test_discord_network_error_is_caught(monkeypatch):
    def boom(url, **kw):
        raise httpx.ConnectError("no route")
    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(KanalError) as ei:
        DiscordKanal(TOKEN, CHANNEL).senden("t", "x")
    assert TOKEN not in str(ei.value)
    assert "no route" not in str(ei.value)     # nur der Fehlertyp, keine Rohdetails


# ---- Pollen-Uhr (.ics / RFC 5545) ----------------------------------------
def test_ics_format():
    termine = [
        Termin(id="a1", titel="Rechnungen, Q1", faellig="2026-07-20", projekt="rechnungen"),
        Termin(id="bad", titel="Kaputt", faellig="kein-datum"),      # wird übersprungen
    ]
    ics = build_ics(termine)
    assert ics.startswith("BEGIN:VCALENDAR\r\n")
    assert ics.rstrip().endswith("END:VCALENDAR")
    assert "BEGIN:VEVENT" in ics and ics.count("BEGIN:VEVENT") == 1   # nur der gültige Termin
    assert "UID:a1@bumble-beebliothek" in ics
    assert "DTSTART;VALUE=DATE:20260720" in ics
    assert "SUMMARY:Deadline: Rechnungen\\, Q1" in ics                # Komma escaped
    assert "\r\n" in ics                                             # CRLF-Zeilenenden


def test_baubiene_writes_ics_on_wabenbau(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    bau = Baubiene(ctx)
    bau.wabenbau("rechnungen", ask=lambda p: ("2026-12-31" if "deadline" in p.lower()
                                              else ("max" if "zuständig" in p.lower() else "Ziel")))
    ics_path = honig(hive) / "kalender.ics"
    assert ics_path.exists()
    text = ics_path.read_text(encoding="utf-8")
    assert "BEGIN:VEVENT" in text and "DTSTART;VALUE=DATE:20261231" in text


# ---- Trigger-Workflow: fällige Deadline → EIN Discord-Versand -------------
class _FakeKanal:
    name = "Discord"
    STOCK = "Discord-Wabe"

    def __init__(self):
        self.calls = 0

    def senden(self, titel, text):
        self.calls += 1


def test_waechter_triggers_once_antispam(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    fake = _FakeKanal()
    w = Waechterbiene(ctx, kanaele=[fake])
    assert w.send_real is True
    w.kalender.eintragen("Miete", "2000-01-01")          # überfällig → fällig

    w.deadlines_pruefen()                                 # feuert echt
    assert fake.calls == 1
    w.deadlines_pruefen()                                 # Anti-Spam: nicht erneut
    assert fake.calls == 1
    # Der Termin ist als gemeldet markiert.
    assert all(t.gemeldet for t in Kalender(hive)._all() if t.titel == "Miete")


def test_waechter_no_secret_in_versand_log(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    w = Waechterbiene(ctx, kanaele=[_FakeKanal()])
    w.kalender.eintragen("Miete", "2000-01-01")
    w.deadlines_pruefen()
    log = (honig(hive) / "log.jsonl").read_text(encoding="utf-8")
    assert TOKEN not in log and "kanal" in log            # nur Metadaten (Kanal-Name)
