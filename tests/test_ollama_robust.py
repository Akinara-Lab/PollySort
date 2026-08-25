"""Regressionstests: Ollama-Anbindung robust (QA-Nachtrag 2026-07-14, report.txt R4).

Befund im Feld: 'sortiere' im Ollama-Modus schlug mit „HTTP 400" fehl (PDF als
file-Part — kennt Ollama nicht) und wurde 3× sinnlos wiederholt und als „nicht
erreichbar" gemeldet. Darunter: llama-server-GPU-Crash (0xc0000005) auf der Maschine.

Deckt ab:
- 4xx wird NICHT wiederholt und klar gemeldet (LLMRequestError).
- llama-server-Crash (5xx) wird erkannt, NICHT wiederholt (LLMBackendCrash).
- PDFs werden für Ollama lokal in Text gewandelt (kein file-Part mehr im Payload).
- GPU-Crash → automatischer CPU-Fallback über die native API (num_gpu: 0).
- Embedding bekommt den nomic-v2-moe-Task-Prefix.
- Extractor: LLMRequestError → Rückfrage (Metadaten-Eintrag), keine error-Retry-Schleife.
"""

from __future__ import annotations

import httpx
import pytest

import bumble.llm.client as client_mod
from bumble.llm.client import (
    LLMBackendCrash,
    LLMRequestError,
    OllamaClient,
    OpenRouterClient,
)


class FakeResponse:
    def __init__(self, status_code: int, body: dict | None = None):
        self.status_code = status_code
        self._body = body or {}
        self.text = str(body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)  # type: ignore[arg-type]


def _patch_post(monkeypatch, handler):
    calls: list[dict] = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "payload": json})
        return handler(url, json)

    monkeypatch.setattr(client_mod.httpx, "post", fake_post)
    return calls


# ---- 4xx: kein Retry, klare Meldung ---------------------------------------
def test_bad_request_is_not_retried(monkeypatch):
    calls = _patch_post(monkeypatch, lambda url, p: FakeResponse(
        400, {"error": {"message": "invalid content part: file"}}))
    c = OpenRouterClient("key", "m", "e", [])
    with pytest.raises(LLMRequestError, match="HTTP 400.*invalid content part"):
        c._post("/chat/completions", {})
    assert len(calls) == 1                       # exakt EIN Versuch, kein Backoff


# ---- llama-server-Crash: erkannt, kein Retry ------------------------------
def test_backend_crash_detected_without_retry(monkeypatch):
    calls = _patch_post(monkeypatch, lambda url, p: FakeResponse(
        500, {"error": {"message": "llama-server process has terminated: 0xc0000005"}}))
    c = OllamaClient("http://localhost:11434", [])
    with pytest.raises(LLMBackendCrash):
        c._post("/chat/completions", {})
    assert len(calls) == 1


# ---- PDF → lokaler Text statt file-Part -----------------------------------
def test_pdf_becomes_local_text(monkeypatch, tmp_path):
    monkeypatch.setattr(client_mod, "_local_file_text", lambda p: "Angebot Nr. 3 über 100 EUR")
    pdf = tmp_path / "angebot.pdf"
    pdf.write_bytes(b"%PDF-fake")
    c = OllamaClient("http://localhost:11434", ["angebot"])
    parts = c._build_content(text=None, file_path=str(pdf))
    assert all(p["type"] == "text" for p in parts)          # KEIN file-Part mehr
    assert any("Angebot Nr. 3" in p["text"] for p in parts)


def test_pdf_without_text_raises_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(client_mod, "_local_file_text", lambda p: None)
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-fake")
    c = OllamaClient("http://localhost:11434", [])
    with pytest.raises(LLMRequestError, match="kein Text extrahieren"):
        c._build_content(text=None, file_path=str(pdf))


# ---- GPU-Crash → CPU-Fallback über die native API -------------------------
def test_cpu_fallback_after_backend_crash(monkeypatch):
    def handler(url, payload):
        if "/v1/" in url:                                   # OpenAI-Pfad: GPU crasht
            return FakeResponse(500, {"error": {"message": "llama-server process has terminated"}})
        # native API: CPU-Inferenz antwortet
        assert url.endswith("/api/chat")
        assert payload["options"]["num_gpu"] == 0
        assert payload.get("think") is False            # kein CPU-Grübeln (Thinking-Modelle)
        return FakeResponse(200, {
            "message": {"content": '{"title": "Angebot 3", "summary": "s", "keywords": [], '
                                   '"funktion_aufgabe": "f", "kategorie": "angebot"}'},
            "prompt_eval_count": 5, "eval_count": 7,
        })

    calls = _patch_post(monkeypatch, handler)
    c = OllamaClient("http://localhost:11434", ["angebot"])
    a = c.analyze(text="Angebot Nr. 3")
    assert a.kategorie == "angebot"
    assert c._cpu_mode is True
    # Zweiter Call geht DIREKT auf die native API (kein erneuter GPU-Crash-Versuch).
    n_before = len(calls)
    c.analyze(text="Angebot Nr. 4")
    assert all("/v1/" not in rec["url"] for rec in calls[n_before:])


# ---- Embedding: Task-Prefix + CPU-Pfad ------------------------------------
def test_embed_prefix_and_cpu_payload(monkeypatch):
    def handler(url, payload):
        assert url.endswith("/api/embed")
        assert payload["input"].startswith("search_document: ")
        assert payload["options"] == {"num_gpu": 0}
        return FakeResponse(200, {"embeddings": [[0.1, 0.2]]})

    _patch_post(monkeypatch, handler)
    c = OllamaClient("http://localhost:11434", [])
    c._cpu_mode = True
    assert c.embed("hallo") == [0.1, 0.2]


# ---- Extractor: dauerhafte Ablehnung → Rückfrage statt error-Schleife -----
def test_extractor_turns_request_error_into_review(tmp_path):
    from bumble.extractor import extract
    from bumble.guards import IgnoreMatcher
    from bumble.llm.client import Usage
    from bumble.models import Status
    from bumble.scout import scout, walk

    class RejectingClient:
        usage = Usage()

        def analyze(self, **kw):
            raise LLMRequestError("Ollama: Anfrage abgelehnt (HTTP 400) — file part")

        def embed(self, text):
            return [0.0]

    hive = tmp_path / "hive"
    hive.mkdir()
    (hive / "scan.pdf").write_bytes(b"%PDF-fake")
    finding = scout(walk([hive], IgnoreMatcher(hive), recursive=False))[0]
    _analysis, status, reason = extract(finding, RejectingClient(), max_file_mb=100)
    assert status == Status.NEEDS_REVIEW                    # Rückfrage, nicht error
    assert "abgelehnt" in (reason or "")
