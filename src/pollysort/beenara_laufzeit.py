"""BeeNara-Laufzeit — ONNX Runtime, kein torch, kein Trainingscode.

Kopie von ``beenara.py`` aus https://huggingface.co/Kwokou/BeeNara (Stand der v0.3-Laufzeit;
auf dem v0.2-Modell entscheidet sie Zeile für Zeile wie die ausgelieferte Fassung, geprüft am
2026-10-02 mit Stufe-0: 420/420; auf dem v0.3-Modell am 2026-10-08 dieselben Treffer wie die
Bewertung im Trainingspaket, Stufe-0 C1/C2/C3 100 / 92,9–94,3 / 100 %; v0.4 am 2026-10-27:
Buckets aus der Kalibrierdatei, ONNX und PyTorch-Bewertung wählen 199/200 gleich). Änderungen gehören
zuerst dorthin, mit Paritätstest, und werden dann hierher übernommen. PollySort lädt bewusst
keinen Code vom Hub; deshalb liegt die Laufzeit hier im Paket. Zwei Abweichungen vom Original:

* ``numpy`` wird erst beim Laden importiert — PollySort muss ohne das Extra ``[beenara]``
  starten.
* ``from_pretrained`` fehlt; das Herunterladen übernimmt :mod:`pollysort.beenara`.

Input format: [CLS] question [SEP] [MASK] option 1 [MASK] option 2 … [SEP] document [SEP].
Each option is scored at its own [MASK]; one extra head gives p("none fits").

Optional, read from ``calibration.json`` when a model ships them (older models behave as before):
``truncation`` keeps the start AND the end of long documents; ``risk`` holds per-bucket confidence thresholds
for ``decide(..., rule="risk")``, which files automatically only when the calibrated confidence reaches the
threshold certified for "at most x % of auto-filed documents wrong".
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

NONE = "__none__"
QUESTION = {"de": "In welchen Ordner gehört dieses Dokument?",
            "en": "Which folder does this document belong in?"}
MAX_LEN = 512          # tokens in total
HEAD_MAX = 192         # tokens for the question and all options
OPTION_MAX = 40        # tokens per option, name plus short description
BUCKETS = ((3, 9), (10, 24), (25, 49), (50, 99), (100, 199), (200, 299), (300, None))


def bucket(n: int, buckets=None) -> str:
    """Option-count bucket of the risk thresholds: "3-9", "10-24" … "300+" (fewer than 3 counts as "3-9").
    ``buckets``: the calibration file's own buckets (v0.4 writes them, e.g. ending in "200+")."""
    bs = [(int(lo), None if hi is None else int(hi)) for lo, hi in buckets] if buckets else BUCKETS
    for lo, hi in bs:
        if hi is None or n <= hi:
            return f"{lo}+" if hi is None else f"{lo}-{hi}"
    lo, hi = bs[-1]
    return f"{lo}+" if hi is None else f"{lo}-{hi}"


@dataclass
class Decision:
    category: str | None            # set only when the prediction set is exactly one category
    confidence: float               # calibrated probability of the top answer
    ask: bool                       # True: let the user decide
    distribution: dict[str, float] = field(default_factory=dict)
    prediction_set: list[str] = field(default_factory=list)


class BeeNara:
    def __init__(self, path: str | Path, *, threads: int = 4):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        p = Path(path)
        self.tok = Tokenizer.from_file(str(p / "tokenizer" / "tokenizer.json"))
        cfg = json.loads((p / "tokenizer" / "tokenizer_config.json").read_text(encoding="utf-8"))
        self.mask = cfg["mask_token"]
        self.mask_id, self.cls_id, self.sep_id, self.pad_id = (
            self.tok.token_to_id(cfg[k]) for k in ("mask_token", "cls_token", "sep_token", "pad_token"))
        self.cal = json.loads((p / "onnx" / "calibration.json").read_text(encoding="utf-8"))
        self.truncation = self.cal.get("truncation") or {"mode": "end"}
        opt = ort.SessionOptions()
        opt.intra_op_num_threads = threads
        opt.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(p / "onnx" / "beenara.onnx"), opt,
                                            providers=["CPUExecutionProvider"])

    # -- input ----------------------------------------------------------------
    def _ids(self, text: str) -> list[int]:
        return self.tok.encode(text.replace(self.mask, " "), add_special_tokens=False).ids

    def _truncate(self, ids: list[int], room: int) -> list[int]:
        """Cut the document to ``room`` tokens: from the end ("end"), or keeping start and end
        ("head_tail")."""
        if len(ids) <= room:
            return ids
        mode = self.truncation.get("mode", "end")
        if mode == "end" or room < 8:
            return ids[:room]
        if mode != "head_tail":
            raise ValueError(f"unknown truncation mode: {mode}")
        tail = int(room * self.truncation.get("tail_share", 0.3))
        return ids[:room - tail] + (ids[-tail:] if tail else [])

    def sequence(self, question: str, options: list[str], text: str) -> tuple[list[int], list[int]]:
        """Token ids and the positions of the option markers."""
        head = self._ids(question)
        opts = [[self.mask_id] + self._ids(" " + o)[:OPTION_MAX] for o in options]
        budget = HEAD_MAX - sum(len(o) for o in opts)
        if budget < 8:                                  # many or long options: shorten them evenly
            each = max(4, (HEAD_MAX - 8) // max(1, len(opts)))
            opts = [o[:each] for o in opts]
            budget = HEAD_MAX - sum(len(o) for o in opts)
        ids = [self.cls_id] + head[:max(4, budget)] + [self.sep_id]
        markers = []
        for o in opts:
            markers.append(len(ids))
            ids.extend(o)
        ids.append(self.sep_id)
        room = max(0, MAX_LEN - len(ids) - 1)
        ids += self._truncate(self._ids(text), room) + [self.sep_id]
        return ids[:MAX_LEN], [m for m in markers if m < MAX_LEN]

    # -- model ----------------------------------------------------------------
    def scores(self, question: str, options: list[str], text: str) -> tuple[list[float], float]:
        """Raw option logits and the raw "none" logit, before calibration."""
        import numpy as np

        ids, markers = self.sequence(question, options, text)
        out = self.session.run(None, {
            "input_ids": np.array([ids], dtype=np.int64),
            "attention_mask": np.ones((1, len(ids)), dtype=np.int64),
            "marker_pos": np.array([markers], dtype=np.int64),
            "marker_mask": np.ones((1, len(markers)), dtype=np.bool_),
        })
        return out[0][0, :len(markers)].astype(float).tolist(), float(out[1][0])

    def distribution(self, logits: list[float], none_logit: float) -> list[float]:
        """Calibrated [p(option 1) … p(option K), p(none)]."""
        t, tn = self.cal["option_temperature"], self.cal["none_temperature"]
        z = none_logit / tn
        p_none = 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))
        m = max(logits)
        e = [math.exp((x - m) / t) for x in logits]
        s = sum(e)
        return [v / s * (1 - p_none) for v in e] + [p_none]

    def decide(self, text: str, categories: list[str], *, descriptions: dict[str, str] | None = None,
               language: str = "de", question: str | None = None, rule: str = "conformal") -> Decision:
        """Pick one of ``categories`` or "none". ``rule="conformal"`` (default): sort automatically
        only when the conformal prediction set holds exactly one category. ``rule="risk"``: sort
        automatically only when the top category (not "none") reaches the risk threshold of its
        bucket; no threshold → ask."""
        if rule not in ("conformal", "risk"):
            raise ValueError(f"unknown rule: {rule}")
        options = [f"{c} — {descriptions[c]}" if descriptions and descriptions.get(c) else c
                   for c in categories]
        logits, none_logit = self.scores(question or QUESTION.get(language, QUESTION["en"]), options, text)
        vert = self.distribution(logits, none_logit)
        names = categories[:len(logits)] + [NONE]
        qhat = self.cal["conformal"]["qhat"]
        pset = [names[i] for i, p in enumerate(vert) if 1 - p <= qhat]
        best = max(range(len(vert)), key=vert.__getitem__)
        sure = len(pset) == 1 and pset[0] != NONE
        if rule == "risk":
            b = bucket(len(logits), self.cal.get("buckets"))
            lam = (self.cal.get("risk", {}).get(b) or {}).get("lambda")
            sure = lam is not None and names[best] != NONE and vert[best] >= lam
        return Decision(category=names[best] if sure else None, confidence=vert[best], ask=not sure,
                        distribution=dict(zip(names, vert)), prediction_set=pset)
