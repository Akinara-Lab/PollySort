"""Sicherheit (🔒 Wachssiegel) + Flugrouten der Wächterbienen (§v0.3).

Harte Zusicherungen:
- API-Keys/Passwörter landen NIE im LLM-Payload.
- Secrets tauchen NIE im Klartext-Log (log.jsonl) auf.
- Credentials liegen global, NICHT im Projekt-.honig/.
Plus: SMTP-Presets, Sender-Payloads (ohne Netz), Kanal-Aufbau.
"""

from __future__ import annotations

import json

from bumble.config import AppConfig, HiveSeed
from bumble.console import BeeConsole
from bumble.flugrouten import (
    EMAIL_PRESETS,
    DiscordConfig,
    EmailConfig,
    Flugrouten,
    load_flugrouten,
    mask,
    save_flugrouten,
)
from bumble.journal import Journal
from bumble.llm.client import OfflineClient, OpenRouterClient
from bumble.pipeline import Context
from bumble.swarm.kanaele import DiscordKanal, EmailKanal, build_kanaele
from bumble.swarm.waechterbiene import Waechterbiene

SECRET_TOKEN = "discord-SUPERSECRET-abcd1234"
SECRET_PASS = "app-PASSWORT-xyz789"


def _flugrouten() -> Flugrouten:
    fr = Flugrouten()
    fr.discord = DiscordConfig(enabled=True, bot_token=SECRET_TOKEN, channel_id="42")
    fr.email = EmailConfig(enabled=True, provider="gmail", address="ich@example.com",
                           password=SECRET_PASS, smtp_host="smtp.gmail.com", smtp_port=587)
    return fr


# ---- 🔒 Secrets NIE im LLM-Payload ---------------------------------------
def test_secrets_never_in_llm_payload():
    fr = _flugrouten()                      # Flugrouten mit Secrets sind konfiguriert …
    # … der LLM-Client kennt sie strukturell nicht. Payload für ein Dokument bauen:
    client = OpenRouterClient(api_key="sk-irrelevant", model="m", embed_model="e",
                              categories=["rechnungen", "vertraege"],
                              few_shots=[{"title": "x", "kategorie_neu": "rechnungen"}])
    parts = client._build_content(text="Rechnung ACME Betrag 100 EUR", file_path=None)
    blob = json.dumps(parts, ensure_ascii=False)
    assert SECRET_TOKEN not in blob
    assert SECRET_PASS not in blob
    assert fr.email.address not in blob     # auch die E-Mail-Adresse (PII) nicht

    # Offline-Client ebenso wenig.
    off = OfflineClient(["rechnungen"])
    a = off.analyze(text="Rechnung ACME", file_path=None)
    assert SECRET_TOKEN not in json.dumps(a.model_dump(), ensure_ascii=False)


# ---- 🔒 Secrets NIE im Log (log.jsonl) -----------------------------------
def test_secrets_never_in_logs(tmp_path):
    hive = tmp_path / "hive"
    hive.mkdir()
    j = Journal(hive)
    # Selbst wenn versehentlich ein Secret durchgereicht würde: es wird maskiert.
    j.event("test", bot_token=SECRET_TOKEN, password=SECRET_PASS, kanal="Discord", ok=True)
    log = (hive / ".honig" / "log.jsonl").read_text(encoding="utf-8")
    assert SECRET_TOKEN not in log
    assert SECRET_PASS not in log
    assert '"kanal": "Discord"' in log      # Metadaten bleiben erhalten
    assert '"bot_token": "***"' in log      # sensibles Feld maskiert


def test_waechterbiene_reminder_log_has_no_secret(tmp_path):
    hive = tmp_path / "hive"
    ctx = Context.build(hive=hive, cfg=AppConfig(llm_provider="offline"),
                        seed=HiveSeed(), client=OfflineClient([]),
                        console=BeeConsole(quiet=True), journal=Journal(hive))
    w = Waechterbiene(ctx, flugrouten=_flugrouten(), kanaele=[])   # keine echten Sends
    w.kalender.eintragen("Miete zahlen", "2000-01-01")            # überfällig → fällig
    w.deadlines_pruefen(senden=False)
    log = (hive / ".honig" / "log.jsonl").read_text(encoding="utf-8")
    assert SECRET_TOKEN not in log and SECRET_PASS not in log


# ---- 🔒 Global gespeichert, NICHT im Projekt -----------------------------
def test_flugrouten_stored_globally(tmp_path):
    p = tmp_path / "beehive" / "flugrouten.toml"
    save_flugrouten(_flugrouten(), path=p)
    assert p.exists()
    fr2 = load_flugrouten(path=p)
    assert fr2.discord.bot_token == SECRET_TOKEN
    assert fr2.email.password == SECRET_PASS
    # Kein Bezug zu einem Projekt-.honig/
    assert ".honig" not in str(p)


def test_env_overrides_and_never_written(tmp_path, monkeypatch):
    p = tmp_path / "flugrouten.toml"
    fr = Flugrouten()
    fr.discord = DiscordConfig(enabled=True, bot_token="", channel_id="1")
    save_flugrouten(fr, path=p)             # ohne Token gespeichert
    assert 'bot_token  = ""' in p.read_text(encoding="utf-8")   # leer auf Platte
    monkeypatch.setenv("BEEHIVE_DISCORD_TOKEN", "env-secret-9999")
    from bumble.flugrouten import discord_token
    assert discord_token(load_flugrouten(path=p)) == "env-secret-9999"   # Env hat Vorrang
    assert "env-secret-9999" not in p.read_text(encoding="utf-8")        # nie persistiert


# ---- Sender-Payloads (ohne Netz) & Presets -------------------------------
def test_discord_payload_carries_message():
    k = DiscordKanal(SECRET_TOKEN, "42")
    payload = k._payload("Deadline", "Fällig heute")
    assert "Deadline" in payload["content"] and "Fällig heute" in payload["content"]
    assert SECRET_TOKEN not in json.dumps(payload)      # Token nur im Header, nie im Body


def test_email_message_build():
    k = EmailKanal("ich@example.com", SECRET_PASS, "smtp.gmail.com", 587, True, "du@example.com")
    msg = k._message("Deadline", "Fällig heute")
    assert msg["To"] == "du@example.com" and msg["From"] == "ich@example.com"
    assert "Deadline" in msg["Subject"]
    assert SECRET_PASS not in msg.as_string()           # Passwort nie in der Nachricht


def test_email_presets():
    assert EMAIL_PRESETS["gmail"] == ("smtp.gmail.com", 587, True)
    assert EMAIL_PRESETS["outlook"] == ("smtp-mail.outlook.com", 587, True)


def test_build_kanaele_from_config():
    kanaele = build_kanaele(_flugrouten())
    namen = {k.name for k in kanaele}
    assert namen == {"Discord", "E-Mail"}
    # Nichts aktiv → keine Kanäle.
    assert build_kanaele(Flugrouten()) == []


def test_mask_hides_secret():
    assert mask(SECRET_TOKEN).endswith("1234") and SECRET_TOKEN not in mask(SECRET_TOKEN)
    assert mask("") == "—"
