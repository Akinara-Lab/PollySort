"""Regressionstests: Ollama-Anbindung robust (QA-Nachtrag 2026-07-14, report.txt R4).

Befund im Feld: 'sortiere' im Ollama-Modus schlug mit „HTTP 400" fehl (PDF als
file-Part — kennt Ollama nicht) und wurde 3× sinnlos wiederholt und als „nicht
erreichbar" gemeldet. Darunter: llama-server-GPU-Crash (0xc0000005) auf der Maschine.

Deckt ab:
- 4xx wird NICHT wiederholt und klar gemeldet (LLMRequestError).
- llama-server-Crash (5xx) wird erkannt, NICHT wiederholt (LLMBackendCrash).
- PDFs werden für Ollama lokal in Text gewandelt (kein file-Part mehr im Payload).
- GPU-Crash → automatischer CPU-Fallback (num_gpu: 0), seit 2026-09-24 auf der nativen API.
- Embedding bekommt den nomic-v2-moe-Task-Prefix.
- Extractor: LLMRequestError → Rückfrage (Metadaten-Eintrag), keine error-Retry-Schleife.
"""

from __future__ import annotations

import copy

import httpx
import pytest

import pollysort.llm.client as client_mod
from pollysort.llm.client import (
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
    """Den Transport ersetzen. Seit 2026-09-24 hält jeder Client EINE Verbindung
    (``httpx.Client``) — ein Patch auf ``httpx.post`` griffe ins Leere, und der Test ginge
    ungebremst ins Netz."""
    calls: list[dict] = []

    def fake_post(self, url, headers=None, json=None, timeout=None):
        # Payload kopieren: Der Client verändert ihn zwischen zwei Versuchen weiter.
        calls.append({"url": url, "payload": copy.deepcopy(json)})
        return handler(url, json)

    monkeypatch.setattr(client_mod.httpx.Client, "post", fake_post)
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


# ---- GPU-Crash → CPU-Fallback ----------------------------------------------
_ANALYSE_OK = {
    "message": {"content": '{"title": "Angebot 3", "summary": "s", "keywords": [], '
                           '"funktion_aufgabe": "f", "kategorie": "angebot"}'},
    "prompt_eval_count": 5, "eval_count": 7,
}


def test_cpu_fallback_after_backend_crash(monkeypatch):
    def handler(url, payload):
        assert url.endswith("/api/chat")                    # nur noch die native API
        if "num_gpu" not in payload["options"]:             # GPU crasht
            return FakeResponse(500, {"error": {"message": "llama-server process has terminated"}})
        assert payload["options"]["num_gpu"] == 0           # CPU-Inferenz antwortet
        assert payload.get("think") is False                # kein Grübeln (Thinking-Modelle)
        return FakeResponse(200, _ANALYSE_OK)

    calls = _patch_post(monkeypatch, handler)
    c = OllamaClient("http://localhost:11434", ["angebot"])
    a = c.analyze(text="Angebot Nr. 3")
    assert a.kategorie == "angebot"
    assert c._cpu_mode is True
    # Zweiter Call geht DIREKT auf die CPU (kein erneuter GPU-Crash-Versuch).
    n_before = len(calls)
    c.analyze(text="Angebot Nr. 4")
    assert len(calls) == n_before + 1
    assert calls[-1]["payload"]["options"]["num_gpu"] == 0


# ---- Kontext & Sampling werden gesetzt (Befund 2026-09-24) -----------------
def test_analysis_sets_context_temperature_and_caps_text(monkeypatch):
    """Ohne ``num_ctx`` lädt Ollama 0.34 mit 65 536 Tokens — das 9B passt dann nicht mehr
    in 8 GB VRAM. Und ohne Kappung schnitte Ollama den Prompt VORNE ab, samt Anweisungen."""
    calls = _patch_post(monkeypatch, lambda url, p: FakeResponse(200, _ANALYSE_OK))
    c = OllamaClient("http://localhost:11434", ["angebot"])
    c.analyze(text="Angebot " + "x" * 50_000)
    payload = calls[0]["payload"]
    assert payload["options"]["num_ctx"] == OllamaClient.NUM_CTX
    assert payload["options"]["temperature"] == 0
    assert payload["format"] == "json" and payload["think"] is False
    assert len(payload["messages"][0]["content"]) < OllamaClient.TEXT_CAP + 3000


def test_default_endpoint_is_ipv4():
    """``localhost`` kostete unter Windows ~2 s je Verbindung (erst ``::1``, dann IPv4)."""
    from pollysort.config import AppConfig
    from pollysort.llm.client import OLLAMA_ENDPOINT, build_client
    assert OLLAMA_ENDPOINT.startswith("http://127.0.0.1")
    c = build_client(AppConfig(llm_provider="ollama"), None, ["a"])
    assert c._native_base == OLLAMA_ENDPOINT


def test_client_keeps_one_connection(monkeypatch):
    seen: list[int] = []

    def fake_post(self, url, headers=None, json=None, timeout=None):
        seen.append(id(self))
        return FakeResponse(200, {"embeddings": [[0.5]]})

    monkeypatch.setattr(client_mod.httpx.Client, "post", fake_post)
    c = OllamaClient("http://localhost:11434", [])
    c.embed("a")
    c.embed("b")
    assert len(seen) == 2 and seen[0] == seen[1], "jede Anfrage muss dieselbe Verbindung nutzen"


# ---- Entscheidung per Nummer (Plan §8.3) -----------------------------------
def _lp(*paare):
    return [{"token": "2", "logprob": -0.1,
             "top_logprobs": [{"token": tok, "logprob": lp} for tok, lp in paare]}]


def test_decide_reads_the_logprobs_not_the_sampled_token(monkeypatch):
    def handler(url, payload):
        assert payload["logprobs"] is True and payload["options"]["num_predict"] == 1
        assert "1 = rechnungen" in payload["messages"][0]["content"]
        assert "0 = keine davon passt" in payload["messages"][0]["content"]
        # Gezogen wurde "2" — die Logprobs sagen aber klar "1".
        return FakeResponse(200, {"message": {"content": "2"},
                                  "logprobs": _lp(("1", -0.05), ("2", -3.0), ("0", -4.0))})

    _patch_post(monkeypatch, handler)
    c = OllamaClient("http://localhost:11434", ["rechnungen", "spesen"])
    kat, p = c.decide("RECHNUNG Nr. 4", ["rechnungen", "spesen"])
    assert kat == "rechnungen" and p > 0.9


def test_decide_zero_means_nothing_fits(monkeypatch):
    _patch_post(monkeypatch, lambda url, p: FakeResponse(
        200, {"message": {"content": "0"}, "logprobs": _lp(("0", -0.01), ("1", -5.0))}))
    c = OllamaClient("http://localhost:11434", ["rechnungen"])
    assert c.decide("Kochrezept", ["rechnungen"])[0] == "_unassigned"


def test_decide_falls_back_without_logprobs_or_with_too_many_categories(monkeypatch):
    _patch_post(monkeypatch, lambda url, p: FakeResponse(200, {"message": {"content": "1"}}))
    c = OllamaClient("http://localhost:11434", [])
    assert c.decide("Text", ["a", "b"]) is None                       # ältere Ollama-Version
    assert c.decide("Text", [f"k{i}" for i in range(10)]) is None     # zweistellige Nummern
    assert c.decide("   ", ["a"]) is None


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
    from pollysort.extractor import extract
    from pollysort.guards import IgnoreMatcher
    from pollysort.llm.client import Usage
    from pollysort.models import Status
    from pollysort.scout import scout, walk

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
