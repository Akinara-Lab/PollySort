"""Die BeeNara-Laufzeit (beenara_laufzeit.py) — Eingabefolge, Kalibrierung, Entscheidungsregel.

Ohne ONNX Runtime: Tokenizer und Modell-Ausgabe sind ersetzt, geprüft wird die Logik drumherum.
Der Live-Test am Ende rechnet mit dem echten Modell, wenn ``BEENARA_MODELL`` auf einen
geladenen Ordner zeigt und die Laufzeit installiert ist (in der CI also nicht):

    BEENARA_MODELL=~/.pollysort/modelle/BeeNara pytest tests/test_beenara_laufzeit.py
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from pollysort import entscheidung
from pollysort.beenara_laufzeit import HEAD_MAX, MAX_LEN, NONE, BeeNara

KAL = {"option_temperature": 0.5783, "none_temperature": 1.0114,
       "conformal": {"alpha": 0.1, "qhat": 0.030514784147349983}}


class Tok:
    """Ein Wort = ein Token; Sonderzeichen haben feste IDs."""

    SPEZIAL = {"[MASK]": 4, "[CLS]": 1, "[SEP]": 2, "[PAD]": 0}

    def encode(self, text, add_special_tokens=False):
        return SimpleNamespace(ids=[10 + (sum(map(ord, w)) % 1000) for w in text.split()])

    def token_to_id(self, t):
        return self.SPEZIAL[t]


def _bee(scores=None) -> BeeNara:
    bee = BeeNara.__new__(BeeNara)
    bee.tok = Tok()
    bee.mask = "[MASK]"
    bee.mask_id, bee.cls_id, bee.sep_id, bee.pad_id = 4, 1, 2, 0
    bee.cal = dict(KAL)
    bee.truncation = {"mode": "end"}
    if scores is not None:
        bee.scores = lambda _q, _o, _t: scores
    return bee


def test_folge_markiert_jede_option_und_bleibt_unter_512():
    bee = _bee()
    ids, marker = bee.sequence("Welcher Ordner?", ["rechnungen", "spesen", "steuer"],
                               "wort " * 2000)
    assert len(ids) == MAX_LEN and ids[0] == bee.cls_id and ids[-1] == bee.sep_id
    assert len(marker) == 3 and all(ids[m] == bee.mask_id for m in marker)


def test_maske_im_dokument_wird_neutralisiert():
    """Ein „[MASK]" im Dokumenttext darf keinen falschen Options-Marker erzeugen."""
    ids, marker = _bee().sequence("Frage", ["a", "b", "c"], "Text [MASK] Text")
    assert ids.count(4) == len(marker) == 3


def test_viele_lange_optionen_werden_gleichmaessig_gekuerzt():
    lang = " ".join(["wort"] * 60)
    ids, marker = _bee().sequence("Frage", [lang] * 9, "Dokument")
    assert len(marker) == 9 and marker[-1] < HEAD_MAX + 8


def test_verteilung_ist_kalibriert_und_summiert_auf_eins():
    vert = _bee().distribution([2.0, 0.0, -1.0], -3.0)
    assert math.isclose(sum(vert), 1.0)
    assert math.isclose(vert[-1], 1 / (1 + math.exp(3.0 / KAL["none_temperature"])))
    assert vert[0] > vert[1] > vert[2]


def test_eindeutig_wird_sortiert():
    d = _bee(([12.0, 0.0, 0.0], -10.0)).decide("x", ["rechnungen", "spesen", "steuer"])
    assert d.category == "rechnungen" and not d.ask and d.prediction_set == ["rechnungen"]
    assert d.confidence >= 1 - KAL["conformal"]["qhat"]


def test_keiner_passt_wird_gefragt():
    d = _bee(([0.0, 0.0, 0.0], 8.0)).decide("x", ["rechnungen", "spesen", "steuer"])
    assert d.category is None and d.ask
    assert max(d.distribution, key=d.distribution.get) == NONE


def test_zwei_gleich_gute_ordner_werden_gefragt():
    d = _bee(([3.0, 3.0, -5.0], -8.0)).decide("x", ["rechnungen", "spesen", "steuer"])
    assert d.category is None and d.ask


def test_risiko_regel_aus_der_kalibrierung():
    bee = _bee(([3.0, 0.0, 0.0], -6.0))
    bee.cal["risk"] = {"3-9": {"lambda": 0.9}}
    d = bee.decide("x", ["a", "b", "c"], rule="risk")
    assert d.category == "a"
    bee.cal["risk"] = {}
    assert bee.decide("x", ["a", "b", "c"], rule="risk").ask, "ohne Schwelle → fragen"


def test_import_braucht_kein_numpy():
    """PollySort startet ohne das Extra [beenara] — numpy kommt erst beim Rechnen."""
    import ast
    src = (Path(__file__).resolve().parent.parent / "src" / "pollysort"
           / "beenara_laufzeit.py").read_text(encoding="utf-8")
    oben = [n for n in ast.parse(src).body if isinstance(n, (ast.Import, ast.ImportFrom))]
    namen = {a.name for n in oben for a in n.names} | {getattr(n, "module", "") for n in oben}
    assert not namen & {"numpy", "onnxruntime", "tokenizers"}


# --------------------------------------------------------------------------- #
#  Live — das echte Modell, wenn vorhanden
# --------------------------------------------------------------------------- #
MODELL = os.environ.get("BEENARA_MODELL")


@pytest.mark.skipif(not MODELL, reason="BEENARA_MODELL nicht gesetzt")
def test_live_entscheidungen_mit_dem_echten_modell():
    pytest.importorskip("onnxruntime")
    pytest.importorskip("tokenizers")
    bee = BeeNara(Path(MODELL).expanduser())
    kats = ["rechnungen", "vertraege", "kontoauszuege", "protokolle"]
    w = entscheidung.beenara_waehlen
    assert w(bee, "RECHNUNG Nr. 4711\nBetrag 119,00 EUR, zahlbar bis 30.10.2026.", kats, {})[0] \
        == "rechnungen"
    assert w(bee, "Apfelkuchen: 500 g Mehl, 3 Eier, 200 g Zucker. Bei 180 Grad backen.",
             kats, {}) == ("_unassigned", 0.0)
    kat, conf = w(bee, "Kontoauszug Nr. 9\nAlter Saldo 1.204,50 EUR\nNeuer Saldo 980,10 EUR",
                  kats, {})
    assert kat == "kontoauszuege" and conf >= 0.97
