"""Provider-agnostisches LLM-Interface (§15).

Ein Interface, mehrere Backends:
- ``OpenRouterClient`` — Stufe 1 (online), multimodal ``google/gemini-3.1-flash-lite``.
- ``OllamaClient``     — Stufe 2 (lokal), festes Modell ``qwen3.5:9b`` über Ollamas ``/v1``-API.
- ``OfflineClient``    — kostenfreie Heuristik ohne Key (Tests/Erststart-Demo).

Umstieg = Config, kein Code-Change: der Rest der Codebase kennt nur ``LLMClient``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
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


def ollama_available(endpoint: str = "http://localhost:11434") -> bool:
    """Antwortet lokal ein Ollama-SERVER? (Nur die Installation reicht nicht —
    sonst bietet der Assistent eine lokale KI an, die sofort scheitert; OPT-7.)"""
    try:
        r = httpx.get(f"{endpoint.rstrip('/')}/api/tags", timeout=PING_TIMEOUT)
        return r.status_code == 200
    except Exception:
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
            "HTTP-Referer": "https://github.com/nik/bumble-beebliothek",
            "X-Title": "Bumble Beebliothek",
        }

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
        }
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
            kategorie_hint = "kurzes, kleingeschriebenes Label (moeglichst ein Wort)"
            known_line = ""
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
            })
            flags = _parse_json(data["choices"][0]["message"]["content"])
            known = {c.strip().lower() for c in categories}
            out = {str(k).strip().lower(): "{jahr}/{monat}"
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
                r = httpx.post(
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
    """Lokale KI über Ollamas OpenAI-kompatible API (``/v1``).

    Zwei Robustheits-Schichten (QA-Befund 2026-07-14):
    - **PDF/Binär → lokaler Text:** Ollama akzeptiert keine ``file``-Parts (HTTP 400);
      der Dokumenttext wird deshalb VOR dem Call lokal extrahiert (markitdown/pypdf).
    - **GPU-Crash → CPU-Fallback:** Stürzt Ollamas llama-server ab (z. B. Treiberproblem,
      0xc0000005), wechselt der Client automatisch auf die native API mit ``num_gpu: 0``
      (reine CPU-Inferenz — langsamer, aber funktionsfähig) und bleibt für den Rest der
      Session dabei.
    """

    PROVIDER_NAME = "Ollama"
    # CPU-Inferenz + Modell-Kaltstart brauchen deutlich mehr Luft als ein Online-API-Call.
    TIMEOUT = httpx.Timeout(300.0, connect=5.0)

    def __init__(self, endpoint: str, categories: list[str],
                 few_shots: list[dict] | None = None, wachstafel: str = ""):
        super().__init__(api_key="ollama", model=OLLAMA_MODEL, embed_model=OLLAMA_EMBED_MODEL,
                         categories=categories, few_shots=few_shots, wachstafel=wachstafel)
        base = endpoint.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3].rstrip("/")
        self._native_base = base          # native API: /api/chat, /api/embed
        self.BASE = base + "/v1"          # OpenAI-kompatible API
        self._cpu_mode = False            # nach GPU-Crash: dauerhaft native CPU-Inferenz

    # -- Inhalte: PDFs/Binär lokal in Text wandeln (kein file-Part → kein 400) ----
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
                return super()._build_content(text=text, file_path=None)
        return super()._build_content(text=text, file_path=file_path)

    # -- Analyse mit CPU-Fallback ---------------------------------------------
    def analyze(self, *, text: str | None = None, file_path: str | None = None) -> BeeAnalysis:
        content = self._build_content(text=text, file_path=file_path)
        if not self._cpu_mode:
            try:
                return self._analyze_with(self._model, content)
            except LLMBackendCrash:
                self._cpu_mode = True     # GPU-Backend crasht → ab jetzt CPU (native API)
        return self._native_analyze(content)

    def _native_analyze(self, content: list[dict]) -> BeeAnalysis:
        prompt = "\n\n".join(p["text"] for p in content if p.get("type") == "text")
        images = [p["image_url"]["url"].split("base64,", 1)[-1]
                  for p in content if p.get("type") == "image_url"]
        msg: dict = {"role": "user", "content": prompt}
        if images:
            msg["images"] = images
        payload: dict = {
            "model": self._model, "messages": [msg], "stream": False, "format": "json",
            # Denk-Modus AUS: Thinking-Modelle (qwen3.5) grübeln auf CPU sonst minutenlang,
            # bevor das kleine JSON kommt — für die Extraktion bringt das nichts.
            "think": False,
            # num_predict kappt die Antwort: das Analyse-JSON ist kurz, Ausreißer kosten
            # auf CPU nur Zeit. num_gpu 0 = der eigentliche CPU-Fallback.
            "options": {"num_gpu": 0, "num_predict": 800},
        }
        try:
            data = self._post("/api/chat", payload, base=self._native_base, headers={})
        except LLMRequestError as exc:
            # Manche Modelle kennen den 'think'-Parameter nicht → einmal ohne probieren.
            if "think" not in str(exc).lower():
                raise
            payload.pop("think", None)
            data = self._post("/api/chat", payload, base=self._native_base, headers={})
        self.usage.add(data.get("prompt_eval_count", 0), data.get("eval_count", 0))
        return BeeAnalysis.model_validate(_parse_json(data["message"]["content"]))

    # -- Embedding: Task-Prefix (nomic-v2-moe) + CPU-Fallback -------------------
    def embed(self, text: str) -> list[float]:
        text = f"search_document: {text}"   # das MoE-Embedding erwartet einen Task-Prefix
        if not self._cpu_mode:
            try:
                return super().embed(text)
            except LLMBackendCrash:
                self._cpu_mode = True
        data = self._post("/api/embed", {
            "model": self._embed_model, "input": text, "options": {"num_gpu": 0},
        }, base=self._native_base, headers={})
        return data["embeddings"][0]


# ---------------------------------------------------------------------------
# Offline (kostenfreie Heuristik, kein Key)
# ---------------------------------------------------------------------------
class OfflineClient:
    """Deterministische Heuristik ohne Netz — für Tests & Erststart ohne Key.

    Ratet Titel/Keywords/Kategorie aus Dateiname + Textanfang. Kein LLM, keine Kosten.
    """

    # Kennung des Offline-Pseudo-Embeddings (Hash, feste Dimension) — s. embed().
    embed_model = "offline:hash-2048"

    def __init__(self, categories: list[str], wachstafel: str = ""):
        from ..wachstafel import parse_rules
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
def build_client(cfg, api_key: str | None, categories: list[str],
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
        return OllamaClient(cfg.llm_endpoint or "http://localhost:11434",
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
        return OLLAMA_EMBED_MODEL
    return cfg.embed_model
