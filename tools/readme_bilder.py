#!/usr/bin/env python3
"""Die Bilder für die README: Demo-Ablage anlegen, Flugbrett starten, mit Edge fotografieren.

    python tools/readme_bilder.py                    # nach docs/bilder/
    python tools/readme_bilder.py --nur-hell         # nur das helle Thema
    python tools/readme_bilder.py --modell <ordner>  # BeeNara von woanders (Standard: ~/.pollysort)
    python tools/readme_bilder.py --big <ordner>     # BeeNara Big von woanders (dito)

Braucht Playwright (``pip install playwright``) und ein installiertes Edge oder Chrome — einen
eigenen Browser lädt das Skript nicht herunter. Für die BeeNara-Bilder außerdem das Extra
``[beenara]`` und ein geladenes Modell; fehlt es, sortiert die Demo ohne BeeNara. Damit die
Karte BeeNara Big als bereit zeigt, braucht diese Python-Umgebung auch dessen Laufzeit (Extra
``[beenara-big]``, torch mit CUDA) und das geladene Modell — sonst steht dort, was fehlt.

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
    "northwind-energy-bill.txt": """Northwind Energy Ltd · Harbour Road 18 · 20457 Hamburg
Customer service: +49 40 555 0182 · service@northwind-energy.example

Alex Morgan
12 Linden Street
10115 Berlin

ELECTRICITY BILL
Invoice no. NE-2026-09-4471 · Invoice date 2 Sep 2026
Customer no. 448 201 · Contract: Green Basic 12 · Meter no. 7Q-31877

Billing period: 1 Aug 2026 – 31 Aug 2026
Meter reading 1 Aug 2026                 18,402 kWh
Meter reading 31 Aug 2026                18,714 kWh
Consumption                                 312 kWh

Energy charge 312 kWh × 0.2900 EUR          90.48 EUR
Standing charge (1 month)                   12.00 EUR
Net amount                                 102.48 EUR
VAT 19 %                                    19.47 EUR
Total due                                  121.95 EUR

The amount of 121.95 EUR will be collected by direct debit on 15 Sep 2026
under mandate reference NE-448201-01. Your next monthly payment remains 115.00 EUR.

Northwind Energy Ltd · Registered in Hamburg HRB 99812 · VAT ID DE 000 111 222
""",
    "scan_0912.txt": """Bluewave Mobile GmbH                                          Page 1 of 1
P.O. Box 4410 · 80331 Munich

Alex Morgan · 12 Linden Street · 10115 Berlin

INVOICE 2026/09
Invoice no. BW-0176-2290-0926 · Date 1 Oct 2026
Customer account 0176-2290 · Phone number 0176 ••• 2290
Billing period 1 Sep 2026 – 30 Sep 2026

Monthly plan "Unlimited 30"                         25.20 EUR
Roaming EU (regulated, included)                     0.00 EUR
Third-party services                                 0.00 EUR
Net amount                                          25.20 EUR
VAT 19 %                                             4.79 EUR
Total incl. VAT                                     29.99 EUR

Thank you for paying on time. The total will be collected from your account
ending 4471 on 5 Oct 2026 (SEPA mandate BW-77120).

Questions about your invoice? bluewave-mobile.example/help · Hotline 0800 555 0110
Bluewave Mobile GmbH · Munich Local Court HRB 230017 · VAT ID DE 000 333 444
""",
    "Plumber Weber - invoice.txt": """Weber Plumbing & Heating · Master Plumber Jonas Weber
Kastanienallee 41 · 10435 Berlin · Tel. 030 555 4410

Ms Alex Morgan
12 Linden Street, 3rd floor left
10115 Berlin

INVOICE
Invoice no. 2026-118 · Date: 22 Sep 2026 · Customer no. 3307
Job: kitchen, leaking tap and blocked drain · Work carried out on 19 Sep 2026

Pos  Description                                   Qty    Price      Total
1    Call-out charge, Berlin city zone              1      45.00      45.00
2    Labour, plumber                              1.5 h    68.00     102.00
3    Single-lever kitchen tap, chrome               1      64.00      64.00
4    Drain cleaning, sealing material               1      14.00      14.00
                                             Net amount            225.00 EUR
                                             VAT 19 %               42.75 EUR
                                             Invoice total         267.75 EUR

Please transfer the invoice total within 14 days, quoting invoice number 2026-118.
Of this, 102.00 EUR labour costs can be claimed as household services.

Bank: Berliner Handwerksbank · IBAN DE00 1000 0000 0000 2026 18
Tax no. 21/555/01234 · Thank you for your order!
""",
    "tenancy agreement flat.txt": """RESIDENTIAL TENANCY AGREEMENT

between
Maple Court Properties GmbH, Am Wasserturm 3, 10405 Berlin (the "Landlord")
and
Alex Morgan, born 3 May 1991 (the "Tenant")

§1 Rented premises
The Landlord lets to the Tenant the flat at 12 Linden Street, 10115 Berlin,
3rd floor left, consisting of 2 rooms, kitchen, bathroom and balcony,
approx. 64 m², together with cellar compartment no. 7.

§2 Term
The tenancy begins on 1 March 2026 and runs for an indefinite period.
Either party may terminate it in writing with three months' notice.

§3 Rent and service charges
The monthly basic rent is 980.00 EUR. In addition, the Tenant pays an advance
of 210.00 EUR per month for heating and service charges, settled annually.
Rent is payable in advance by the third working day of each month.

§4 Deposit
The Tenant pays a deposit of three months' basic rent (2,940.00 EUR), which the
Landlord keeps separate from its own assets in an interest-bearing account.

§5 Repairs and alterations
Minor repairs up to 100 EUR per case are borne by the Tenant, at most 8 % of the
annual basic rent. Structural alterations require the Landlord's written consent.

Berlin, 14 February 2026

________________________            ________________________
Landlord                            Tenant
""",
    "gym-membership.txt": """FitHive Studios GmbH · Torstraße 120 · 10119 Berlin

MEMBERSHIP CONTRACT

Member: Alex Morgan · Date of birth 3 May 1991 · Membership no. FH-20931
Studio: FitHive Mitte · Contract date 24 Sep 2026

Plan: Premium (all studios, courses, sauna)
Monthly fee: 39.90 EUR · One-off joining fee: 29.00 EUR
Minimum term: 24 months, starting 1 October 2026

Terms
1. Fees are collected monthly in advance by direct debit from the account
   ending 4471.
2. After the minimum term the contract renews for an indefinite period and can
   then be cancelled with one month's notice.
3. Cancellation during the minimum term must be received in writing at least
   four weeks before the end of the minimum term.
4. Membership can be paused for illness or pregnancy on presentation of a
   certificate.

By signing, the member accepts the studio rules and the general terms and
conditions, which form part of this contract.

________________________            ________________________
FitHive Studios                     Member
""",
    "Document (3).txt": """Harbourline Insurance AG · Motor Division · Postfach 1180 · 50667 Cologne

Ms Alex Morgan
12 Linden Street
10115 Berlin

Cologne, 18 November 2026

Your car insurance — renewal for 2027
Policy no. KFZ-5521-8830 · Vehicle registration B-AM 2207 · VW Golf, 2019

Dear Ms Morgan,

your car insurance renews on 1 January 2027. Here is an overview of your cover
for the new insurance year:

Third-party liability, sum insured 100 million EUR          318.20 EUR
Fully comprehensive cover, excess 300 EUR                    251.60 EUR
Partial cover (theft, glass, storm), excess 150 EUR          included
Roadside assistance                                           42.60 EUR
New annual premium from 1 Jan 2027                           612.40 EUR

Your no-claims class improves to SF 9 because you made no claim this year.
The premium will be collected on 2 January 2027 from your account ending 4471.

Please keep the enclosed insurance certificate in your vehicle.

Kind regards
Your Harbourline Insurance team
""",
    "home-contents-policy.txt": """Harbourline Insurance AG · Home & Property

POLICY SCHEDULE — HOUSEHOLD CONTENTS INSURANCE
Policy no. HR-77-410293 · Date of issue 20 Feb 2026

Policyholder: Alex Morgan
Insured location: 12 Linden Street, 10115 Berlin, 3rd floor left (64 m²)

Insurance period: 1 Mar 2026 – 1 Mar 2027, renews annually unless cancelled
three months before expiry.

Cover                                           Sum insured
Household contents (fire, burglary, water,
storm and hail)                                   45,000 EUR
Bicycle theft, around the clock                    1,500 EUR
Overvoltage from lightning                         included
Valuables (jewellery, cash) in the home           up to 20 % of the sum insured

Excess per claim: 150 EUR
Premium: 9.80 EUR per month, including 19 % insurance tax

This schedule, together with the general insurance conditions HR-2026 and the
product information sheet, forms your insurance contract.
""",
    "tax-assessment-2025.txt": """Tax Office Lindenfeld · Steuerallee 5 · 10117 Berlin
Tax number 13/245/67890 · Date 9 Sep 2026

Alex Morgan
12 Linden Street
10115 Berlin

NOTICE OF ASSESSMENT for 2025
Income tax and solidarity surcharge

The assessment is based on your income tax return received on 28 May 2026.

Income from employment                                  52,200 EUR
less work-related expenses (lump sum exceeded)          -2,688 EUR
less special expenses and insurance contributions       -1,200 EUR
Taxable income                                          48,312 EUR

Income tax assessed                                      8,941 EUR
Solidarity surcharge                                         0 EUR
Tax withheld from wages                                 -9,655 EUR
Refund                                                     714 EUR

The refund of 714 EUR will be paid into your account ending 4471.

Notice of rights: You may appeal against this notice within one month of its
announcement. The appeal must be submitted in writing or electronically to the
tax office named above.
""",
    "scan_0917.txt": """Lumen Data GmbH · Payroll · Invalidenstraße 90 · 10115 Berlin

PAYSLIP · September 2026
Employee: Alex Morgan · Personnel no. 1187 · Tax class 1 · Church tax: none
Entry date 1 Apr 2022 · Position: Data Analyst · Weekly hours: 40

Earnings                                              Amount
Basic salary                                       4,200.00 EUR
Capital-forming benefits                              40.00 EUR
Public transport allowance                           110.00 EUR
Gross salary                                       4,350.00 EUR

Deductions
Income tax                                          -612.33 EUR
Health insurance (incl. supplementary rate)         -369.75 EUR
Pension insurance                                   -404.55 EUR
Unemployment insurance                               -56.55 EUR
Long-term care insurance                             -62.33 EUR
Net pay                                            2,844.49 EUR

Year to date: gross 39,150.00 EUR · income tax 5,510.97 EUR
Paid to account ending 4471 on 30 Sep 2026.
""",
    "payslip_2026-08.txt": """Lumen Data GmbH · Payroll · Invalidenstraße 90 · 10115 Berlin

PAYSLIP · August 2026
Employee: Alex Morgan · Personnel no. 1187 · Tax class 1 · Church tax: none
Entry date 1 Apr 2022 · Position: Data Analyst · Weekly hours: 40

Earnings                                              Amount
Basic salary                                       4,200.00 EUR
Capital-forming benefits                              40.00 EUR
Public transport allowance                           110.00 EUR
Gross salary                                       4,350.00 EUR

Deductions
Income tax                                          -612.33 EUR
Health insurance (incl. supplementary rate)         -369.75 EUR
Pension insurance                                   -404.55 EUR
Unemployment insurance                               -56.55 EUR
Long-term care insurance                             -62.33 EUR
Net pay                                            2,844.49 EUR

Year to date: gross 34,800.00 EUR · income tax 4,898.64 EUR
Paid to account ending 4471 on 29 Aug 2026.
""",
    "statement-sep-2026.txt": """Riverbank AG · Current account statement
Statement no. 9/2026 · Page 1 of 1 · Date 1 Oct 2026

Account holder: Alex Morgan
Account ending 4471 · Giro Plus · Statement period 1 Sep – 30 Sep 2026

Opening balance                                       3,112.40 EUR

Date    Transaction                                         Amount
01.09.  Standing order rent, Maple Court Properties      -1,190.00
01.09.  Direct debit FitHive Studios                         -39.90
05.09.  Direct debit Bluewave Mobile                         -29.99
08.09.  Card payment supermarket                             -64.21
12.09.  Cash withdrawal ATM Alexanderplatz                  -100.00
15.09.  Direct debit Northwind Energy                       -121.95
22.09.  Transfer received, refund                            +45.00
30.09.  Salary Lumen Data GmbH                            +2,844.49

Closing balance                                       4,455.84 EUR

Overdraft limit 1,000.00 EUR · Interest on overdraft 11.9 % p.a.
Please check this statement. Objections must be raised within six weeks.
""",
    "credit card october.txt": """Riverbank Visa Classic · Monthly statement
Card ending 9902 · Cardholder Alex Morgan · Statement date 3 Oct 2026

Statement period 4 Sep – 3 Oct 2026
Previous balance                                         188.30 EUR
Payment received, thank you                             -188.30 EUR

Date    Merchant                                            Amount
09.09.  Online bookstore                                     34.90
17.09.  Rail tickets, online booking                        118.00
26.09.  Restaurant Olive, Berlin                             62.50
New balance                                              215.40 EUR

Credit limit 2,500.00 EUR · Available 2,284.60 EUR
The new balance will be debited in full from your current account ending
4471 on 10 Oct 2026. No interest is charged on full repayment.
""",
    "letter-landlord-heating.txt": """Maple Court Properties GmbH · Facility Management
Am Wasserturm 3 · 10405 Berlin

To all tenants of 12 Linden Street

Berlin, 30 September 2026

Annual maintenance of the heating system

Dear tenants,

we would like to inform you that the heating system in your building will be
serviced on 14 October 2026 between 8 am and 1 pm. During this time the hot
water supply may be interrupted for up to two hours.

Please make sure the radiators in your flat are accessible. If you will not be
at home, you can leave a key with the caretaker, Mr Brandt (ground floor).

Thank you for your understanding.

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


def _verlinken(quelle: Path, ziel: Path) -> None:
    """Große Dateien als Hardlink (BeeNara Big hat 4,7 GB), kleine als Kopie — so kann die Demo
    an ``herkunft.json`` & Co. nie das echte Modell verändern. Ohne Hardlinks: kopieren."""
    for f in quelle.rglob("*"):
        if not f.is_file():
            continue
        z = ziel / f.relative_to(quelle)
        z.parent.mkdir(parents=True, exist_ok=True)
        if f.stat().st_size > 10_000_000:
            try:
                os.link(f, z)
                continue
            except OSError:
                pass
        shutil.copy2(f, z)


def demo_anlegen(wurzel: Path, modell: Path | None, big: Path | None, thema: str) -> Path:
    """Ablage + Projekt „Home office" mit losen Dokumenten. Gibt den Projektordner zurück."""
    from pollysort import beenara, beenara_big, config
    from pollysort.web.dienst import Dienst

    if modell and modell.is_dir():
        shutil.copytree(modell, beenara.ordner())
    else:
        print("!  BeeNara nicht gefunden — die Demo sortiert ohne.", file=sys.stderr)
    if big and big.is_dir():
        _verlinken(big, beenara_big.ordner())
    else:
        print("!  BeeNara Big nicht gefunden — die Karte zeigt es als nicht geladen.", file=sys.stderr)

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
                # Mit etwas Rand, sonst fehlt der Pixel-Schatten der Karte. Die BeeNara-Karte ist
                # mit Big höher als das Fenster: kurz ein hohes Fenster, Karte unter die Kopfleiste.
                k = seite.locator(karte).first
                seite.set_viewport_size({"width": 1280, "height": 2400})
                k.evaluate("(el) => { el.style.scrollMarginTop = '96px';"
                           " el.scrollIntoView({block: 'start'}); }")
                seite.wait_for_timeout(200)
                b = k.bounding_box()
                rand = 16
                seite.screenshot(path=str(pfad), clip={
                    "x": b["x"] - rand, "y": b["y"] - rand,
                    "width": b["width"] + 2 * rand, "height": b["height"] + 2 * rand})
                seite.set_viewport_size({"width": 1280, "height": 820})
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


def lauf(thema: str, wurzel: Path, ziel: Path, modell: Path, big: Path) -> int:
    """Ein Thema in einem eigenen Prozess — erst nach dessen Ende sind Datenbank und Modell zu."""
    # Vor dem ersten Import: config liest den Ablage-Ort beim Laden.
    os.environ["POLLYSORT_HOME"] = str(wurzel / "home")
    sys.path.insert(0, str(REPO / "src"))
    from pollysort.web.server import starten

    projekt = demo_anlegen(wurzel, modell, big, thema)
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
    ap.add_argument("--big", default=str(Path.home() / ".pollysort" / "modelle" / "BeeNara-Big"))
    ap.add_argument("--nur-hell", action="store_true")
    ap.add_argument("--lauf", nargs=2, metavar=("THEMA", "WURZEL"), help=argparse.SUPPRESS)
    args = ap.parse_args()
    ziel = Path(args.ziel)
    ziel.mkdir(parents=True, exist_ok=True)
    if args.lauf:
        return lauf(args.lauf[0], Path(args.lauf[1]), ziel, Path(args.modell), Path(args.big))

    for thema in ["light"] if args.nur_hell else ["light", "dark"]:
        wurzel = Path(tempfile.mkdtemp(prefix="pollysort-bilder-"))
        try:
            code = subprocess.call([sys.executable, __file__, "--lauf", thema, str(wurzel),
                                    "--ziel", str(ziel), "--modell", args.modell, "--big", args.big])
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
