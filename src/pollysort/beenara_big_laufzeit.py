"""BeeNara-Big-Laufzeit — torch + transformers + peft, kein Trainingscode.

Kopie von ``beenara_big.py`` aus https://huggingface.co/Kwokou/BeeNara-Big (v0.3; geprüft am
2026-10-08: auf denselben Eingaben bitgleich mit dem Trainingscode, CPU fp32). Änderungen gehören
zuerst dorthin, mit Paritätstest, und werden dann hierher übernommen. PollySort lädt bewusst
keinen Code vom Hub. Abweichungen vom Original:

* ``from_pretrained`` fehlt; das Herunterladen übernimmt :mod:`pollysort.beenara_big`, und das
  Basismodell kommt aus dem lokalen Ordner (``base=``), nie still aus dem Netz.
* :meth:`BeeNaraBig.decide` liefert eine :class:`~pollysort.beenara_laufzeit.Decision` wie das
  kleine BeeNara — so entscheidet :mod:`pollysort.entscheidung` mit beiden gleich.
* Ein Schloss reiht parallele Aufrufe (Ultra Swarm): das Modell merkt sich zwischen zwei
  Aufrufen Zustand (``rope_deltas``), und auf einer GPU bringt Parallelität nichts.
"""

from __future__ import annotations

import json
import math
import threading
from dataclasses import dataclass
from pathlib import Path

from .beenara_laufzeit import Decision

MARKER_OPTION, MARKER_NONE = "<|box_start|>", "<|box_end|>"
IMAGE_START, IMAGE_PAD, IMAGE_END = "<|vision_start|>", "<|image_pad|>", "<|vision_end|>"
TEXTS = {"de": {"task": "Aufgabe: ", "doc": "\nDokument:\n", "folders": "\nOrdner:\n",
                "score": "\nBewertung je Ordner:\n", "none": "\nKeiner dieser Ordner passt"},
         "en": {"task": "Task: ", "doc": "\nDocument:\n", "folders": "\nFolders:\n",
                "score": "\nScore each folder:\n", "none": "\nNone of these folders fits"}}
QUESTION = {"de": "In welchen Ordner gehört dieses Dokument?", "en": "Which folder does this document belong in?"}
NONE = "__none__"
LOG_K_MAX = math.log(300)
BUCKETS = ((3, 9), (10, 24), (25, 49), (50, 99), (100, 199), (200, 299), (300, None))


def bucket(n: int) -> str:
    """List-size bucket of the risk thresholds: "3-9", "10-24" … "300+"."""
    for lo, hi in BUCKETS:
        if hi is None or n <= hi:
            return f"{lo}+" if hi is None else f"{lo}-{hi}"
    return "300+"


@dataclass
class Suggestion:
    suggestions: list[tuple[str, float]]     # folders, best first, with calibrated probabilities
    none: float                              # p("none of these folders fits")
    distribution: dict[str, float]           # every folder plus "__none__"
    category: str | None                     # only set when a risk threshold allows automatic filing
    ask: bool                                # True: show the suggestions and let the user decide
    truncated_tokens: int = 0                # document tokens that did not fit


class _Head:
    """Decision head: folder scorer at the option markers, none scorer at the none marker (plus three features
    of the folder distribution)."""

    def __init__(self, d: int, state: dict):
        import torch
        from torch import nn
        self.bewerter = nn.Sequential(nn.LayerNorm(d), nn.Dropout(0.0), nn.Linear(d, d), nn.GELU(), nn.Linear(d, 1))
        self.keine = nn.Sequential(nn.LayerNorm(d + 3), nn.Linear(d + 3, 256), nn.GELU(), nn.Linear(256, 1))
        mods = nn.ModuleDict({"bewerter": self.bewerter, "keine": self.keine})
        missing, unexpected = mods.load_state_dict(state, strict=False)
        if missing or unexpected:
            raise ValueError(f"head weights do not match: missing={missing[:4]} unexpected={unexpected[:4]}")
        self.mods = mods.eval()
        self.torch = torch

    def to(self, device, dtype):
        self.mods.to(device=device, dtype=dtype)
        return self

    def __call__(self, h_opt, h_none):
        torch = self.torch
        logits = self.bewerter(h_opt).squeeze(-1).float()
        p = torch.softmax(logits, -1)
        k = torch.tensor(float(max(2, logits.numel())), device=logits.device)
        entropy = -(p * torch.log(p.clamp_min(1e-9))).sum() / torch.log(k)
        top = p.topk(min(2, p.numel())).values
        gap = top[0] - (top[1] if top.numel() > 1 else 0)
        feats = torch.stack([entropy, gap, torch.log(k) / LOG_K_MAX]).to(h_none.device)
        none = self.keine(torch.cat([h_none.float(), feats]).to(next(self.keine.parameters()).dtype)).squeeze(-1)
        return logits.tolist(), float(none)


class BeeNaraBig:
    #: Für so viele Ordner ist Big trainiert (3–300, in 5 % der Aufgaben bis 500).
    ordner_bereich = (3, 500)
    #: So viel Dokumenttext bekommt Big aus PollySort (es kürzt selbst auf 2.048 Token, Anfang + Ende).
    text_zeichen = 12_000

    def __init__(self, path: str | Path, *, base: str | None = None, device: str | None = None, dtype=None,
                 threads: int | None = None):
        """``path``: folder with ``big_config.json``, ``lora.safetensors``, ``kopf.safetensors``, ``tokenizer/``.
        ``base``: local path or Hub id of Qwen3.5-2B-Base (default: the id and revision in ``big_config.json``)."""
        import torch
        from peft import LoraConfig, inject_adapter_in_model
        from safetensors.torch import load
        from transformers import AutoModel, AutoTokenizer
        p = Path(path)
        self.cfg = json.loads((p / "big_config.json").read_text(encoding="utf-8"))
        if self.cfg.get("variante") != "L2":
            raise ValueError(f"this loader supports variant L2, not {self.cfg.get('variante')}")
        self.cal = json.loads((p / "kalibrierung.json").read_text(encoding="utf-8"))
        if threads:
            torch.set_num_threads(threads)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.dtype = dtype or (torch.bfloat16 if self.device.startswith("cuda") else torch.float32)
        self.tok = AutoTokenizer.from_pretrained(p / "tokenizer")
        kw = {"dtype": self.dtype}
        if base is None and self.cfg.get("basis_revision"):
            kw["revision"] = self.cfg["basis_revision"]
        if base is not None and Path(base).is_dir():
            kw["local_files_only"] = True          # PollySort: das Basismodell nie still aus dem Netz
        self.base = AutoModel.from_pretrained(base or self.cfg["basis"], **kw)
        lc = self.cfg["lora"]
        inject_adapter_in_model(LoraConfig(r=lc["r"], lora_alpha=lc["alpha"], lora_dropout=0.0,
                                           target_modules=lc["ziele"], bias="none"), self.base)
        res = self.base.load_state_dict(load((p / "lora.safetensors").read_bytes()), strict=False)
        if res.unexpected_keys or not any("lora_" in k for k in self.base.state_dict()):
            raise ValueError(f"LoRA weights do not match the base model: {res.unexpected_keys[:4]}")
        self.base.to(self.device).eval()
        d = self.base.config.text_config.hidden_size
        self.head = _Head(d, load((p / "kopf.safetensors").read_bytes())).to(self.device, self.dtype)
        self.image_processor = None
        if (p / "bildprozessor").exists():
            try:
                from transformers import Qwen2VLImageProcessorPil as IP
            except ImportError:
                from transformers import Qwen2VLImageProcessor as IP
            self.image_processor = IP.from_pretrained(p / "bildprozessor")
        self.max_context, self.text_max = self.cfg.get("max_kontext", 16384), self.cfg.get("text_max", 2048)
        self.option_max = self.cfg.get("option_max", 32)
        ids = {t: self.tok.convert_tokens_to_ids(t) for t in (MARKER_OPTION, MARKER_NONE, IMAGE_START, IMAGE_PAD,
                                                              IMAGE_END)}
        self.id_opt, self.id_none = ids[MARKER_OPTION], ids[MARKER_NONE]
        self.id_img_start, self.id_img, self.id_img_end = ids[IMAGE_START], ids[IMAGE_PAD], ids[IMAGE_END]
        self._special = [t for t in (getattr(self.tok, "all_special_tokens", None) or []) if t] + list(ids)
        self._schloss = threading.Lock()

    # -- input --------------------------------------------------------------------
    def _t(self, text: str) -> list[int]:
        for s in self._special:
            if s and s in text:
                text = text.replace(s, " ")
        return self.tok(text, add_special_tokens=False)["input_ids"] if text else []

    @staticmethod
    def _cut(ids: list[int], room: int, tail_share: float = 0.3) -> list[int]:
        """Keep the start and the last 30 % of a long document (as in training)."""
        if len(ids) <= room:
            return ids
        tail = int(room * tail_share)
        return ids[:room - tail] + (ids[-tail:] if tail else [])

    def _images(self, images):
        if not images or self.image_processor is None:
            return None, None, []
        from PIL import Image
        imgs = [im if hasattr(im, "convert") else Image.open(im) for im in images]
        b = self.image_processor(images=[im.convert("RGB") for im in imgs], return_tensors="pt")
        grid = b["image_grid_thw"]
        return b["pixel_values"], grid, [int(g.prod()) // 4 for g in grid]

    def encode(self, question: str, options: list[str], text: str, language: str, images=None):
        tx = TEXTS["en" if language == "en" else "de"]
        pixel, grid, n_img = self._images(images)
        head = self._t(tx["task"] + question)
        for n in n_img:
            head += [self.id_img_start] + [self.id_img] * n + [self.id_img_end]
        doc_full = self._t(text)
        opts_full = [self._t("- " + o) for o in options]
        nl, text_max, option_max = self._t("\n"), self.text_max, self.option_max
        while True:
            doc = self._cut(doc_full, text_max)
            opts = [o[:option_max] for o in opts_full]
            ids = head + self._t(tx["doc"]) + doc
            img_pos = [i for i, t in enumerate(ids) if t == self.id_img]
            listing = self._t(tx["folders"])
            for o in opts:
                listing += o + nl
            ids += listing + self._t(tx["score"])
            markers = []
            for o in opts:
                ids += o
                markers.append(len(ids))
                ids += [self.id_opt] + nl
            ids += self._t(tx["none"]) + [self.id_none]
            if len(ids) <= self.max_context:
                return ids, markers, len(ids) - 1, img_pos, pixel, grid, len(doc_full) - len(doc)
            if text_max > 256:
                text_max = max(256, text_max // 2)
            elif option_max > 10:
                option_max = max(10, option_max - 6)
            else:
                raise ValueError(f"{len(ids)} tokens do not fit into {self.max_context} ({len(options)} folders)")

    # -- scoring ------------------------------------------------------------------
    def scores(self, text: str, folders: list[str], *, language: str = "de", question: str | None = None,
               images=None) -> tuple[list[float], float, int]:
        """Raw folder logits and the raw none logit, before calibration."""
        import torch
        ids, markers, none_pos, img_pos, pixel, grid, cut = self.encode(
            question or QUESTION.get(language, QUESTION["en"]), folders, text, language, images)
        t = torch.tensor([ids], device=self.device)
        mask = torch.ones_like(t)
        mm = torch.zeros_like(t, dtype=torch.int32)
        if img_pos:
            mm[0, torch.tensor(img_pos, device=self.device)] = 1
        kw = {}
        if pixel is not None:
            kw = {"pixel_values": pixel.to(self.device, self.dtype), "image_grid_thw": grid.to(self.device)}
        with self._schloss, torch.no_grad():
            self.base.rope_deltas = None
            pos, _ = self.base.get_rope_index(t, mm_token_type_ids=mm, image_grid_thw=kw.get("image_grid_thw"),
                                              attention_mask=mask)
            h = self.base(input_ids=t, attention_mask=mask, position_ids=pos, mm_token_type_ids=mm, **kw
                          ).last_hidden_state[0]
            logits, none = self.head(h[torch.tensor(markers, device=self.device)], h[none_pos])
        return logits, none, cut

    def distribution(self, logits: list[float], none_logit: float) -> list[float]:
        table = self.cal.get("temperatur_je_k") or {}
        if self.cal.get("modus") == "global" and table:
            t = next(iter(table.values()))
        else:
            k = str(len(logits))
            t = table.get(k) or (table[min(table, key=lambda s: abs(int(s) - len(logits)))] if table else 1.0)
        tn = self.cal.get("temperatur_keine", 1.0)
        z = none_logit / tn
        p_none = 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))
        m = max(logits)
        e = [math.exp((x - m) / t) for x in logits]
        s = sum(e)
        return [v / s * (1 - p_none) for v in e] + [p_none]

    def suggest(self, text: str, folders: list[str], *, descriptions: dict[str, str] | None = None,
                language: str = "de", question: str | None = None, images=None, top_k: int = 3) -> Suggestion:
        """Rank ``folders`` for this document. ``images``: page images (paths or PIL images), optional."""
        if len(folders) < 1:
            raise ValueError("need at least one folder")
        options = [f"{f} — {descriptions[f]}" if descriptions and descriptions.get(f) else f for f in folders]
        logits, none, cut = self.scores(text, options, language=language, question=question, images=images)
        vert = self.distribution(logits, none)
        dist = dict(zip(folders, vert[:-1])) | {NONE: vert[-1]}
        ranking = sorted(zip(folders, vert[:-1]), key=lambda x: -x[1])
        lam = (self.cal.get("risiko", {}).get(bucket(len(folders))) or {}).get("lambda")
        best, p_best = ranking[0]
        sure = lam is not None and p_best >= lam and p_best > vert[-1]
        return Suggestion(suggestions=ranking[:top_k], none=vert[-1], distribution=dist,
                          category=best if sure else None, ask=not sure, truncated_tokens=cut)

    def decide(self, text: str, categories: list[str], *, descriptions: dict[str, str] | None = None,
               language: str = "de", question: str | None = None, rule: str = "risk") -> Decision:
        """Wie ``BeeNara.decide``: ``category`` nur, wenn eine Risiko-Schwelle das erlaubt — in
        v0.3 nie, Big macht nur Vorschläge (``ask`` immer ``True``). ``rule`` ist der
        Gleichförmigkeit halber da; Big kennt nur die Risiko-Regel."""
        s = self.suggest(text, categories, descriptions=descriptions, language=language, question=question)
        best = max(s.distribution, key=s.distribution.get)
        return Decision(category=s.category, confidence=s.distribution[best], ask=s.ask,
                        distribution=s.distribution, prediction_set=[f for f, _ in s.suggestions])

