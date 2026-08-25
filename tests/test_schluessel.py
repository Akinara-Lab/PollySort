"""OpenRouter-Schlüssel: Ablauf-Erkennung (401/403 nicht retrybar) + Key-Prüfung.

Deckt die Lücke ab, dass ein abgelaufener Schlüssel bisher als „nicht erreichbar" fehlgedeutet
und 3× wiederholt wurde — und dass es keinen Prüf-/Erneuerungsweg gab.
"""

from __future__ import annotations

import types

import httpx
import pytest

from bumble.llm.client import (
    LLMAuthError,
    LLMError,
    OpenRouterClient,
    verify_openrouter_key,
)

KEY = "sk-or-SECRET-abcd1234"


def _resp(status: int, body: dict | None = None):
    return types.SimpleNamespace(status_code=status,
                                 json=lambda: body or {},
                                 raise_for_status=lambda: None)


# ---- verify_openrouter_key (GET /api/v1/key, gemockt) --------------------
@pytest.mark.parametrize("status,ok,needle", [
    (200, True, "gültig"),
    (401, False, "abgelehnt"),
    (403, False, "abgelehnt"),
    (500, False, "unerwartete"),
])
def test_verify_key_status(monkeypatch, status, ok, needle):
    monkeypatch.setattr(httpx, "get", lambda url, **kw: _resp(status))
    got_ok, grund = verify_openrouter_key(KEY)
    assert got_ok is ok
    assert needle in grund


def test_verify_key_empty():
    ok, grund = verify_openrouter_key("")
    assert ok is False and "kein Schlüssel" in grund


def test_verify_key_network_error(monkeypatch):
    def boom(url, **kw):
        raise httpx.ConnectError("dns")
    monkeypatch.setattr(httpx, "get", boom)
    ok, grund = verify_openrouter_key(KEY)
    assert ok is False and "nicht erreichbar" in grund


# ---- Abgelaufener Schlüssel: 401 wird NICHT wiederholt -------------------
def test_expired_key_raises_autherror_without_retry(monkeypatch):
    calls = {"post": 0, "sleep": 0}

    def fake_post(url, **kw):
        calls["post"] += 1
        return _resp(401)

    def count_sleep(_s):
        calls["sleep"] += 1

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr("bumble.llm.client.time.sleep", count_sleep)

    client = OpenRouterClient(api_key=KEY, model="m", embed_model="e", categories=["x"])
    with pytest.raises(LLMAuthError) as ei:
        client.analyze(text="doc", file_path=None)

    assert calls["post"] == 1                 # KEIN Retry bei 401
    assert calls["sleep"] == 0                 # kein Backoff-Schlaf
    assert KEY not in str(ei.value)            # 🔒 Schlüssel nie in der Meldung
    assert "abgelaufen oder ungültig" in str(ei.value)
    assert isinstance(ei.value, LLMError)      # bleibt ein LLMError (Extractor fängt es)


def test_transient_500_is_retried(monkeypatch):
    calls = {"post": 0}

    def fake_post(url, **kw):
        calls["post"] += 1
        return _resp(500)

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr("bumble.llm.client.time.sleep", lambda s: None)

    client = OpenRouterClient(api_key=KEY, model="m", embed_model="e", categories=["x"])
    with pytest.raises(LLMError) as ei:
        client.analyze(text="doc", file_path=None)
    assert not isinstance(ei.value, LLMAuthError)   # 5xx ist KEIN Auth-Fehler
    assert calls["post"] == 3                        # transient → 3 Versuche
