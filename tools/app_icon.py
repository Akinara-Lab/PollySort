"""Das App-Symbol von PollySort erzeugen — aus derselben Pixel-Biene wie im Flugbrett.

    python tools/app_icon.py

Schreibt ``src/pollysort/web/static/pollysort.ico`` (16–256 px, für Windows-Verknüpfungen,
Fenster und Taskleiste) und ``pollysort.png`` (256 px, für Linux-Starter und macOS).
Reines Python (zlib + struct), keine Bildbibliothek: Das Raster wird pixelgenau
vergrößert, so bleibt die Biene in jeder Größe scharf.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ZIEL = Path(__file__).resolve().parents[1] / "src" / "pollysort" / "web" / "static"

#: Dieselbe Biene wie ``biene`` in static/pixel.js (d = Streifen, h = Augenlicht).
BIENE = [
    "....ll.ll.....",
    "...lwwlwwl....",
    "...lwwlwwl....",
    "....lllll.....",
    "...kkkkkkkk...",
    "..kyydyydyykk.",
    "kkyyydyydyykhk",
    "..koodyodyokk.",
    "...kkkkkkkk...",
    "....k..k......",
]
FARBEN = {
    "k": (0x2B, 0x1D, 0x0E), "d": (0x3A, 0x26, 0x10), "y": (0xFF, 0xC8, 0x3D),
    "o": (0xE3, 0x9B, 0x1B), "w": (0xEE, 0xF8, 0xFF), "l": (0x7F, 0xA9, 0xC9),
    "h": (0xFF, 0xFF, 0xFF),
}
#: Heller Rand um die Biene — damit sie auf dunkler Taskleiste genauso lesbar ist.
RAND = (0xFB, 0xF4, 0xE2)
GROESSEN = (16, 32, 48, 64, 128, 256)


def raster16() -> list[list[tuple[int, int, int, int]]]:
    """16×16-Bild: Biene mittig, darum ein 1-px-Rand in Wachs-Creme (wie ein Aufkleber)."""
    n = 16
    bild = [[(0, 0, 0, 0)] * n for _ in range(n)]
    ox, oy = 1, 3
    for y, zeile in enumerate(BIENE):
        for x, c in enumerate(zeile):
            if c in FARBEN:
                bild[oy + y][ox + x] = (*FARBEN[c], 255)
    belegt = {(x, y) for y in range(n) for x in range(n) if bild[y][x][3]}
    for y in range(n):
        for x in range(n):
            if (x, y) in belegt:
                continue
            nachbarn = {(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
            if nachbarn & belegt:
                bild[y][x] = (*RAND, 255)
    return bild


def png(bild: list[list[tuple[int, int, int, int]]], faktor: int) -> bytes:
    """Das Raster ``faktor``-fach (Nearest Neighbour) als RGBA-PNG."""
    zeilen = []
    for reihe in bild:
        z = b"".join(bytes(px) * faktor for px in reihe)
        zeilen.extend([b"\x00" + z] * faktor)
    roh = b"".join(zeilen)
    seite = len(bild) * faktor

    def block(art: bytes, daten: bytes) -> bytes:
        return (struct.pack(">I", len(daten)) + art + daten
                + struct.pack(">I", zlib.crc32(art + daten) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + block(b"IHDR", struct.pack(">IIBBBBB", seite, seite, 8, 6, 0, 0, 0))
            + block(b"IDAT", zlib.compress(roh, 9)) + block(b"IEND", b""))


def ico(bilder: list[tuple[int, bytes]]) -> bytes:
    """ICO-Container mit PNG-Einträgen (ab Windows Vista für alle Größen erlaubt)."""
    kopf = struct.pack("<HHH", 0, 1, len(bilder))
    versatz = 6 + 16 * len(bilder)
    eintraege, daten = b"", b""
    for seite, inhalt in bilder:
        s = 0 if seite >= 256 else seite
        eintraege += struct.pack("<BBBBHHII", s, s, 0, 0, 1, 32, len(inhalt), versatz + len(daten))
        daten += inhalt
    return kopf + eintraege + daten


#: macOS-Symboltypen mit PNG-Inhalt → Kantenlänge.
ICNS_TYPEN = {b"icp4": 16, b"icp5": 32, b"icp6": 64, b"ic07": 128, b"ic08": 256, b"ic09": 512}


def icns(bild: list[list[tuple[int, int, int, int]]]) -> bytes:
    """ICNS-Container für das macOS-Programmpaket (PollySort.app)."""
    eintraege = b""
    for typ, seite in ICNS_TYPEN.items():
        inhalt = png(bild, seite // 16)
        eintraege += typ + struct.pack(">I", 8 + len(inhalt)) + inhalt
    return b"icns" + struct.pack(">I", 8 + len(eintraege)) + eintraege


def main() -> None:
    bild = raster16()
    pngs = [(g, png(bild, g // 16)) for g in GROESSEN]
    (ZIEL / "pollysort.ico").write_bytes(ico(pngs))
    (ZIEL / "pollysort.png").write_bytes(dict(pngs)[256])
    (ZIEL / "pollysort.icns").write_bytes(icns(bild))
    print(f"geschrieben: pollysort.ico ({len(pngs)} Groessen), pollysort.png, pollysort.icns -> {ZIEL}")


if __name__ == "__main__":
    main()
