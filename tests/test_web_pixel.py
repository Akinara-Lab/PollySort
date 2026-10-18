"""Pixel statt Emoji — und ein Hintergrund, der wirklich eine Wabe ist.

Die Konsole schmückt ihre Meldungen mit Emojis; das Flugbrett zeigt an ihrer Stelle die
eigenen Pixel-Icons. Diese Tests halten das fest: Die Oberfläche selbst enthält keine Emojis,
jedes Symbol, das der Kern schickt, hat ein Pixel-Icon, jedes benutzte Icon existiert und ist
sauber gerastert — und das Hintergrundmuster schließt nahtlos an.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "pollysort" / "web" / "static"

#: Bildzeichen, die als Emoji dargestellt werden (Variation Selector 16 eingeschlossen). Das
#: typografische Häkchen ✓ (U+2713) und Pfeile (U+2190 ff.) sind Schriftzeichen und dürfen bleiben.
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-✒✔-➿⬀-⯿️]")


def _js(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def _sprites() -> dict[str, list[str]]:
    js = _js("pixel.js")
    block = js[js.index("const S = {"):js.index("\n  };", js.index("const S = {"))]
    out: dict[str, list[str]] = {}
    name = None
    for zeile in block.splitlines():
        m = re.match(r"^\s*([a-z0-9]+): \[\s*$", zeile)
        if m:
            name = m.group(1)
            out[name] = []
            continue
        m = re.match(r"^\s*'([^']*)',?\s*$", zeile)
        if m and name:
            out[name].append(m.group(1))
    return out


def _symbol_tabelle() -> dict[str, str]:
    """Die Zuordnung Emoji → Sprite aus app.js (Schlüssel stehen dort als JS-Escapes)."""
    js = _js("app.js")
    block = js[js.index("const SYMBOL = {"):js.index("const ART_SYMBOL")]
    out = {}
    for code, sprite in re.findall(r"'((?:\\u\{[0-9A-F]+\}|\\u[0-9A-F]{4}))': '([a-z0-9]+)'", block):
        out[chr(int(code.strip("\\u{}"), 16))] = sprite
    return out


def test_die_oberflaeche_selbst_enthaelt_keine_emojis():
    for datei in ("app.js", "index.html", "musterbuch.html", "musterbuch.js", "pixel.js"):
        funde = sorted(set(EMOJI.findall(_js(datei))))
        assert not funde, f"{datei} enthält Emojis {funde} — bitte ein Pixel-Icon verwenden"


def test_jedes_benutzte_icon_existiert_und_ist_sauber_gerastert():
    sprites = _sprites()
    for name, raster in sprites.items():
        assert len({len(z) for z in raster}) == 1, f"Sprite {name}: Zeilen unterschiedlich breit"
    benutzt = set(re.findall(r"P\.sprite\('([a-z0-9]+)'", _js("app.js")))
    benutzt |= set(_symbol_tabelle().values())
    benutzt |= set(re.findall(r"\['([a-z0-9]+)', '[^']+', '[^']*'\]", _js("musterbuch.js")))
    fehlt = sorted(benutzt - set(sprites))
    assert not fehlt, f"Diese Icons gibt es in pixel.js nicht: {fehlt}"


def test_jedes_symbol_des_kerns_hat_ein_pixel_icon():
    """Was Konsole, Dienst und BeeNara als Symbol mitschicken, wird im Browser zu einem Pixel-Icon
    — kommt ein neues Emoji dazu, fällt es hier auf statt als Ersatz-Biene im Protokoll."""
    tabelle = _symbol_tabelle()
    gesendet: set[str] = set()
    for datei in (ROOT / "src" / "pollysort").rglob("*.py"):
        text = datei.read_text(encoding="utf-8")
        # Symbol-Argumente sind kurze Zeichenketten aus 1–2 Zeichen (Emoji ggf. mit FE0F)
        for kurz in re.findall(r"""["']([^"'\n]{1,2})["']""", text):
            for zeichen in EMOJI.findall(kurz):
                if zeichen != "️":
                    gesendet.add(zeichen)
    ohne = sorted(z for z in gesendet if z not in tabelle and z not in {"⚪"})   # ⚪ = neutral
    assert not ohne, f"Symbole ohne Pixel-Icon: {ohne} — in app.js SYMBOL ergänzen"


def test_hintergrund_ist_eine_nahtlose_wabe():
    """Flache Sechsecke 28 × 24: Die Kachel muss 3/2 Sechseck-Breiten (42) breit und eine
    Sechseck-Höhe (24) hoch sein, sonst schließt das Muster nicht an (vorher: 56 × 48 → lose
    Striche zwischen einzelnen Sechsecken)."""
    css = _js("app.css")
    kacheln = re.findall(r"url\(\"data:image/svg\+xml,[^\"]*\"\)", css)
    assert len(kacheln) == 3, "hell, dunkel und Systemdunkelmodus"
    for k in kacheln:
        assert "width='42' height='24'" in k and "viewBox='0 0 42 24'" in k
        assert "d='M0 12L7 0H21L28 12L21 24H7ZM28 12H42'" in k
