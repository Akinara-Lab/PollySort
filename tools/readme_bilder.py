#!/usr/bin/env python3
"""Die Bilder für die README: Demo-Ablage anlegen, Flugbrett starten, mit Edge fotografieren.

    python tools/readme_bilder.py                    # nach docs/bilder/
    python tools/readme_bilder.py --nur-hell         # nur das helle Thema
    python tools/readme_bilder.py --modell <ordner>  # BeeNara von woanders (Standard: ~/.pollysort)

Braucht Playwright (``pip install playwright``) und ein installiertes Edge oder Chrome — einen
eigenen Browser lädt das Skript nicht herunter. Für die BeeNara-Bilder außerdem das Extra
``[beenara]`` und ein geladenes Modell; fehlt es, sortiert die Demo ohne BeeNara.

Alles läuft in einem eigenen, temporären ``POLLYSORT_HOME``: Deine echte Ablage, deine Projekte
und dein Gedächtnis bleiben unberührt. Die Dokumente sind erfunden und englisch, wie die README.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

WABEN = ["invoices", "contracts", "insurance", "taxes", "payslips", "bank statements"]

# So stehen die Pfade auf den Bildern — statt des temporären Ordners (und deines Benutzernamens).
DEMO_ORDNER = r"C:\Users\alex\Documents"
DEMO_ABLAGE = r"C:\Users\alex\.pollysort"

# Bewusst gemischt: sprechende Namen und nichtssagende Scans — sortiert wird nach dem Inhalt.
DOKUMENTE = {
    "northwind-energy-bill.txt": """Northwind Energy Ltd
Customer no. 448 201 · Meter 7Q-31877

ELECTRICITY BILL · Invoice no. NE-2026-09-4471
Billing period: 1 Aug 2026 – 31 Aug 2026

Consumption 312 kWh × 0.29 EUR          90.48 EUR
Standing charge                         12.00 EUR
VAT 19 %                                19.47 EUR
Total due                              121.95 EUR

Payable by direct debit on 15 Sep 2026.
""",
    "scan_0912.txt": """Bluewave Mobile
Invoice 2026/09 · Account 0176-2290

Monthly plan "Unlimited 30"             29.99 EUR
Roaming EU                               0.00 EUR
Total incl. VAT                         29.99 EUR

Thank you for paying on time. Amount will be collected on 05 Oct 2026.
""",
    "Plumber Weber - invoice.txt": """Weber Plumbing & Heating
Invoice no. 2026-118 · Date: 22 Sep 2026

Replaced kitchen tap, sealed drain       180.00 EUR
Call-out fee                              45.00 EUR
VAT 19 %                                  42.75 EUR
Invoice total                            267.75 EUR

Please transfer within 14 days quoting the invoice number.
""",
    "tenancy agreement flat.txt": """TENANCY AGREEMENT

between Maple Court Properties (landlord) and Alex Morgan (tenant)
for the flat at 12 Linden Street, 3rd floor left.

§1 The tenancy begins on 1 March 2026 and runs for an indefinite period.
§2 Monthly rent: 980.00 EUR plus 210.00 EUR service charges.
§3 Deposit: three months' basic rent.
§4 Either party may terminate with three months' notice.

Signed, Berlin, 14 February 2026
""",
    "gym-membership.txt": """FitHive Studios — Membership contract

Member: Alex Morgan · Membership no. FH-20931
Plan: Premium, 24 months minimum term, 39.90 EUR per month
Start date: 1 October 2026

The contract renews automatically for 12 months unless cancelled
four weeks before the end of the minimum term.
""",
    "Document (3).txt": """Car insurance — renewal of your policy

Policy no. KFZ-5521-8830 · Vehicle: B-AM 2207
Cover: fully comprehensive, excess 300 EUR
New annual premium from 1 Jan 2027: 612.40 EUR
No-claims class SF 9

Please check the enclosed insurance certificate.
""",
    "home-contents-policy.txt": """Household contents insurance — policy schedule

Policyholder: Alex Morgan, 12 Linden Street
Sum insured: 45,000 EUR · includes bicycle theft up to 1,500 EUR
Premium: 9.80 EUR per month

Insurance period 1 Mar 2026 – 1 Mar 2027, renews annually.
""",
    "tax-assessment-2025.txt": """Tax Office Berlin-Mitte
Tax number 13/245/67890

NOTICE OF ASSESSMENT — Income tax 2025

Taxable income                         48,312 EUR
Income tax assessed                     8,941 EUR
Tax already withheld                    9,655 EUR
Refund                                    714 EUR

The refund will be paid into your account ending 4471.
""",
    "scan_0917.txt": """Payslip September 2026

Employer: Lumen Data GmbH · Employee: Alex Morgan · Personnel no. 1187

Gross salary                            4,350.00 EUR
Income tax                               -612.33 EUR
Social security contributions            -893.18 EUR
Net pay                                 2,844.49 EUR

Paid to account ending 4471 on 30 Sep 2026.
""",
    "payslip_2026-08.txt": """Payslip August 2026

Employer: Lumen Data GmbH · Employee: Alex Morgan · Personnel no. 1187

Gross salary                            4,350.00 EUR
Income tax                               -612.33 EUR
Social security contributions            -893.18 EUR
Net pay                                 2,844.49 EUR
""",
    "statement-sep-2026.txt": """Riverbank · Current account statement no. 9/2026
Account ending 4471 · 1 Sep – 30 Sep 2026

Opening balance                         3,112.40 EUR
01.09. Rent Maple Court               -1,190.00 EUR
05.09. Bluewave Mobile                   -29.99 EUR
15.09. Northwind Energy                 -121.95 EUR
30.09. Salary Lumen Data              +2,844.49 EUR
Closing balance                         4,614.95 EUR
""",
    "credit card october.txt": """Riverbank Visa — monthly statement
Card ending 9902 · Statement date 3 Oct 2026

Online bookstore                         34.90 EUR
Train tickets                           118.00 EUR
Restaurant Olive                         62.50 EUR
New balance                             215.40 EUR

The amount will be debited from your current account on 10 Oct 2026.
""",
    "letter-landlord-heating.txt": """Maple Court Properties
Dear Ms Morgan,

we would like to inform you that the heating system in your building
will be serviced on 14 October 2026 between 8 am and 1 pm. Please
make sure the radiators in your flat are accessible.

Kind regards,
Facility Management
""",
    "packing list.txt": """Packing list — Lisbon, long weekend

- passport, charger, sunglasses
- 2 shirts, light jacket, trainers
- book for the flight
- don't forget: plant watering (ask Sam)
""",
}


def demo_anlegen(wurzel: Path, modell: Path | None, thema: str) -> Path:
    """Ablage + Projekt „Home office" mit losen Dokumenten. Gibt den Projektordner zurück."""
    from pollysort import beenara, config
    from pollysort.web.dienst import Dienst

    if modell and modell.is_dir():
        shutil.copytree(modell, beenara.ordner())
    else:
        print("!  BeeNara nicht gefunden — die Demo sortiert ohne.", file=sys.stderr)

    cfg = config.load_config()
    cfg.language = "en"
    cfg.theme = thema
    cfg.onboarded = True
    cfg.tutorial_seen = True
    cfg.llm_provider = "offline"
    cfg.web_animationen = "aus"        # Kein Bild mitten in einer Bewegung
    config.save_config(cfg)

    projekt = wurzel / "Home office"
    projekt.mkdir()
    for name, text in DOKUMENTE.items():
        (projekt / name).write_text(text, encoding="utf-8")
    Dienst().einrichten(pfad=str(projekt), name="Home office", modus="offline",
                        kategorien=WABEN, wache="off")
    return projekt


# Vor jedem Bild: echte Pfade gegen die Demo-Pfade tauschen (Texte und Attribute), Hinweise
# (Toasts) weg, ganz nach oben scrollen.
_AUFRAEUMEN = """([ersetzen]) => {
  const tausch = (s) => ersetzen.reduce((a, [alt, neu]) => a.split(alt).join(neu), s);
  const gang = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = gang.nextNode(); n; n = gang.nextNode()) n.nodeValue = tausch(n.nodeValue);
  for (const el of document.querySelectorAll('*')) {
    for (const a of [...el.attributes]) a.value = tausch(a.value);
    if (el.scrollTop) el.scrollTop = 0;
  }
  for (const el of document.querySelectorAll('input, textarea')) el.value = tausch(el.value);
  document.querySelectorAll('.toast').forEach((t) => t.remove());
  window.scrollTo(0, 0);
}"""


def fotografieren(url: str, ziel: Path, thema: str, ersetzen: list[tuple[str, str]],
                  verboten: str) -> list[Path]:
    from playwright.sync_api import sync_playwright

    endung = "" if thema == "light" else "-dark"
    bilder: list[Path] = []

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="msedge")
        except Exception:
            browser = pw.chromium.launch(channel="chrome")
        seite = browser.new_page(viewport={"width": 1280, "height": 820}, device_scale_factor=1,
                                 color_scheme=thema)
        seite.goto(url)
        seite.wait_for_selector("nav a, nav button")

        def gehe(route: str) -> None:
            seite.evaluate(f"location.hash = '#/{route}'")
            seite.wait_for_timeout(700)

        def klick(wahl: str) -> None:
            # Per Skript statt per Maus: Playwrights Stabilitätsprüfung wartet sonst auf
            # Knöpfe, die während eines Laufs neu gezeichnet werden.
            seite.locator(wahl).first.evaluate("(el) => el.click()")

        def foto(name: str, *, bis: str | None = None, karte: str | None = None) -> None:
            """``bis``: diese Karte nach oben scrollen · ``karte``: nur diese Karte fotografieren."""
            seite.evaluate(_AUFRAEUMEN, [ersetzen])
            if bis:
                seite.locator(bis).first.evaluate(
                    "(el) => { const s = el.closest('section'); s.style.scrollMarginTop = '96px';"
                    " s.scrollIntoView({block: 'start'}); }")
            seite.wait_for_timeout(150)
            # Lieber kein Bild als eins mit deinem Benutzernamen darin.
            if verboten and verboten.lower() in seite.content().lower():
                raise SystemExit(f"✗  '{verboten}' steht noch auf der Seite '{name}' — kein Bild.")
            pfad = ziel / f"{name}{endung}.png"
            if karte:
                # Mit etwas Rand, sonst fehlt der Pixel-Schatten der Karte.
                k = seite.locator(karte).first
                k.scroll_into_view_if_needed()
                b = k.bounding_box()
                rand = 16
                seite.screenshot(path=str(pfad), clip={
                    "x": b["x"] - rand, "y": b["y"] - rand,
                    "width": b["width"] + 2 * rand, "height": b["height"] + 2 * rand})
            else:
                seite.screenshot(path=str(pfad))
            bilder.append(pfad)

        # 1) Flugloch: Vorschau mit Plan — wer hat je Datei entschieden?
        gehe("flugloch")
        klick('[data-tun="vorschau"]')
        seite.wait_for_selector('[data-tun="anwenden"]', timeout=180_000)
        seite.wait_for_timeout(400)
        foto("vorschau", bis="table")

        # 2) Anwenden (kein eigenes Bild — Zuhause zeigt das Ergebnis)
        klick('[data-tun="anwenden"]')
        seite.wait_for_selector('[data-tun="anwenden"]', state="detached", timeout=180_000)
        seite.wait_for_timeout(800)

        # 3) Rückfragen — ein Fall, zu dem BeeNara einen Vorschlag hat
        gehe("rueckfragen")
        for _ in range(len(DOKUMENTE)):
            if seite.locator('[data-tun="rueck-ok"]:not([disabled])').count():
                break
            klick('[data-tun="rueck-skip"]')
            seite.wait_for_timeout(300)
        foto("rueckfragen")

        # 4) Zuhause
        gehe("zuhause")
        foto("zuhause")

        # 5) Waben
        gehe("waben")
        foto("waben")

        # 6) Die BeeNara-Karte aus der Werkstatt
        gehe("werkstatt")
        foto("beenara", karte='section[aria-labelledby="bn-titel"]')

        browser.close()
    return bilder


def lauf(thema: str, wurzel: Path, ziel: Path, modell: Path) -> int:
    """Ein Thema in einem eigenen Prozess — erst nach dessen Ende sind Datenbank und Modell zu."""
    # Vor dem ersten Import: config liest den Ablage-Ort beim Laden.
    os.environ["POLLYSORT_HOME"] = str(wurzel / "home")
    sys.path.insert(0, str(REPO / "src"))
    from pollysort.web.server import starten

    projekt = demo_anlegen(wurzel, modell, thema)
    httpd, url, dienst = starten(projekt, port=0, browser=False)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    ersetzen = []
    for echt, demo in [(wurzel / "home", DEMO_ABLAGE), (wurzel, DEMO_ORDNER)]:
        for form in {str(echt), str(echt.resolve())}:
            ersetzen += [(form, demo), (form.replace("\\", "/"), demo)]
    # Heißt du selbst „alex", wäre jedes Bild ein Fehlalarm — dann ohne diese Prüfung.
    ich = Path.home().name
    verboten = "" if len(ich) < 3 or ich.lower() in DEMO_ORDNER.lower() else ich
    try:
        for bild in fotografieren(url, ziel, thema, ersetzen, verboten):
            print(f"✓  {bild.relative_to(REPO) if bild.is_relative_to(REPO) else bild}", flush=True)
    finally:
        httpd.shutdown()
        dienst.wache.stoppen()
        httpd.server_close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ziel", default=str(REPO / "docs" / "bilder"))
    ap.add_argument("--modell", default=str(Path.home() / ".pollysort" / "modelle" / "BeeNara"))
    ap.add_argument("--nur-hell", action="store_true")
    ap.add_argument("--lauf", nargs=2, metavar=("THEMA", "WURZEL"), help=argparse.SUPPRESS)
    args = ap.parse_args()
    ziel = Path(args.ziel)
    ziel.mkdir(parents=True, exist_ok=True)
    if args.lauf:
        return lauf(args.lauf[0], Path(args.lauf[1]), ziel, Path(args.modell))

    for thema in ["light"] if args.nur_hell else ["light", "dark"]:
        wurzel = Path(tempfile.mkdtemp(prefix="pollysort-bilder-"))
        try:
            code = subprocess.call([sys.executable, __file__, "--lauf", thema, str(wurzel),
                                    "--ziel", str(ziel), "--modell", args.modell])
        finally:
            # Der Prozess ist beendet, also ist nichts mehr geöffnet. Scheitert es trotzdem,
            # wenigstens sagen, wo die Demo (mit Modell-Kopie) noch liegt.
            try:
                shutil.rmtree(wurzel)
            except OSError as exc:
                print(f"!  Konnte {wurzel} nicht aufräumen: {exc}", file=sys.stderr)
        if code:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
