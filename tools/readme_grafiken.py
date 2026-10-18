#!/usr/bin/env python3
"""Die Pixel-Grafiken des Flugbretts als eigenständige SVGs für die README.

    python tools/readme_grafiken.py            # nach docs/bilder/

Liest die Raster aus ``web/static/pixel.js`` (Sprites und Wabenschrift) und die Farben aus
``web/static/app.css``. Im Flugbrett kommen die Farben aus CSS-Variablen; GitHub zeigt SVGs aber
als Bild ohne fremdes CSS, deshalb stehen die Farben hier fest im SVG:

* ``logo.svg`` / ``logo-dark.svg``: Biene und Schriftzug, je in den Farben des hellen bzw.
  dunklen Themas (die README wählt per ``<picture>``).
* ``icons/<name>.svg``: ein Sprite auf einer hellen Wabenkachel — auf GitHub hell wie dunkel
  lesbar, ohne zwei Fassungen.

Kein Browser, keine Abhängigkeit: nur die Standardbibliothek.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATIC = REPO / "src" / "pollysort" / "web" / "static"

#: Die Sprites, die die README als Kachel zeigt.
ICONS = ("haus", "ordner", "biene", "chip", "gehirn", "frage", "auge", "lupe", "blitz", "wabe",
         "tafel", "kiste", "rueckflug", "hammer", "glocke", "weiche", "zahnrad", "schluessel",
         "laden", "topf", "route")

KACHEL_GRUND, KACHEL_RAND = "#FBF4E2", "#E3CF9E"     # --bg des hellen Themas, warmer Rand


def sprites(js: str) -> dict[str, list[str]]:
    block = js[js.index("const S = {"):js.index("function spriteSvg")]
    out = {}
    for name, zeilen in re.findall(r"^\s{4}(\w+): \[\n(.*?)\n\s{4}\],", block, re.S | re.M):
        out[name] = re.findall(r"'([^']*)'", zeilen)
    return out


def glyphen(js: str) -> dict[str, list[str]]:
    block = js[js.index("const G = {"):js.index("const GLYPHEN")]
    out = {}
    for quote, wort, raster in re.findall(r"^\s{4}(?:'(.)'|(\w)): '([.#|]+)',?\s*$", block, re.M):
        out[quote or wort] = raster.split("|")
    return out


def farben(css: str) -> tuple[dict[str, str], dict[str, str]]:
    """``(hell, dunkel)``: Sprite-Farben ``k``/``y``/… plus ``text`` — dunkel überschreibt nur,
    was das dunkle Thema anders setzt."""
    def variablen(block: str) -> dict[str, str]:
        return dict(re.findall(r"--([\w-]+):\s*(#[0-9A-Fa-f]{3,8})", block))
    hell = variablen(css[css.index(":root {"):css.index("@media (prefers-color-scheme: dark)")])
    dunkel_block = css[css.index(':root[data-theme="dark"] {'):]
    dunkel = hell | variablen(dunkel_block[:dunkel_block.index("}")])
    def palette(v: dict[str, str]) -> dict[str, str]:
        p = {k[3:]: wert for k, wert in v.items() if k.startswith("sp-")}
        p["text"] = v["text"]
        return p
    return palette(hell), palette(dunkel)


def _pfade(raster: list[str], dx: int = 0, dy: int = 0) -> dict[str, str]:
    pfade: dict[str, str] = {}
    for y, zeile in enumerate(raster):
        for x, c in enumerate(zeile):
            if c not in ". ":
                pfade[c] = pfade.get(c, "") + f"M{x + dx} {y + dy}h1v1h-1z"
    return pfade


def _svg(w: int, h: int, px: int, inhalt: str, titel: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w * px}" '
            f'height="{h * px}" shape-rendering="crispEdges" role="img" aria-label="{titel}">'
            f"<title>{titel}</title>{inhalt}</svg>\n")


def logo(spr: dict[str, list[str]], gl: dict[str, list[str]], p: dict[str, str]) -> str:
    biene = spr["biene"]
    bw, bh = max(map(len, biene)), len(biene)
    teile = [f'<path fill="{p[c]}" d="{d}"/>' for c, d in _pfade(biene).items()]
    x, oben = bw + 4, (bh - 7) // 2 + 1
    schrift = ""
    for ch in "POLLYSORT":
        g = gl[ch]
        schrift += "".join(_pfade(g, x, oben).values())
        x += len(g[0]) + 1
    teile.append(f'<path fill="{p["text"]}" d="{schrift}"/>')
    return _svg(x - 1, bh, 6, "".join(teile), "PollySort")


def kachel(raster: list[str], p: dict[str, str], name: str) -> str:
    w, h = max(map(len, raster)), len(raster)
    seite = max(w, h) + 4
    dx, dy = (seite - w) // 2, (seite - h) // 2
    grund = (f'<rect x="0.5" y="0.5" width="{seite - 1}" height="{seite - 1}" rx="2" '
             f'fill="{KACHEL_GRUND}" stroke="{KACHEL_RAND}" shape-rendering="geometricPrecision"/>')
    teile = [f'<path fill="{p[c]}" d="{d}"/>' for c, d in _pfade(raster, dx, dy).items()]
    return _svg(seite, seite, 2, grund + "".join(teile), name)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ziel", default=str(REPO / "docs" / "bilder"))
    ziel = Path(ap.parse_args().ziel)
    js = (STATIC / "pixel.js").read_text(encoding="utf-8")
    spr, gl = sprites(js), glyphen(js)
    hell, dunkel = farben((STATIC / "app.css").read_text(encoding="utf-8"))
    fehlt = [n for n in (*ICONS, "biene") if n not in spr] + [c for c in "POLLYSORT" if c not in gl]
    if fehlt:
        raise SystemExit(f"✗  Nicht in pixel.js gefunden: {', '.join(fehlt)}")
    (ziel / "icons").mkdir(parents=True, exist_ok=True)
    geschrieben = []
    for name, p in (("logo.svg", hell), ("logo-dark.svg", dunkel)):
        (ziel / name).write_text(logo(spr, gl, p), encoding="utf-8", newline="\n")
        geschrieben.append(name)
    for n in ICONS:
        (ziel / "icons" / f"{n}.svg").write_text(kachel(spr[n], hell, n), encoding="utf-8", newline="\n")
        geschrieben.append(f"icons/{n}.svg")
    ort = ziel.relative_to(REPO) if ziel.is_relative_to(REPO) else ziel
    print(f"✓  {len(geschrieben)} Grafiken nach {ort}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
