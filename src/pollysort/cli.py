"""Queen — die typer-CLI (§19). Alle Phasen: init, scan/sweep, review, assign, autosort,
sweep-timer, buzz, undertake/bury/resurrect, undo, hive, suggest, export, shell."""

from __future__ import annotations

import sys
from pathlib import Path

# Windows-Konsolen laufen oft mit cp1252 → Emojis würden crashen. UTF-8 erzwingen (§12).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

import typer
from rich.table import Table

from . import __version__, config, i18n
from .console import BeeConsole
from .journal import Journal
from .llm import build_client
from .lock import QueenLock, QueenLockError
from .pipeline import Context, run_cycle

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="🐝 PollySort — konsolenbasierter Dokumenten-Archivar.")
person_app = typer.Typer(help="Personen & Zuständigkeiten (Hintergrund, many-to-many).")
hive_app = typer.Typer(help="Lernendes Gedächtnis: Taxonomie & Kategorie-Vorschläge.")
app.add_typer(person_app, name="person")
app.add_typer(hive_app, name="hive")

_STATE: dict = {"quiet": False, "plain": False, "no_emoji": False, "json": False, "offline": False}


def _con() -> BeeConsole:
    # Dieselbe UI-Sprache wie die Konsole — sonst antwortet `pollysort-cli doctor` einem
    # englischen Nutzer auf Deutsch.
    try:
        i18n.set_language(config.load_config().language)
    except Exception:
        pass
    return BeeConsole(quiet=_STATE["quiet"], plain=_STATE["plain"], no_emoji=_STATE["no_emoji"])


@app.callback()
def main(
    quiet: bool = typer.Option(False, "--quiet", help="Animationen & Statusmeldungen aus."),
    plain: bool = typer.Option(False, "--plain", help="Schmucklos (kein Emoji, keine Animation)."),
    no_emoji: bool = typer.Option(False, "--no-emoji", help="Emojis aus."),
    json_out: bool = typer.Option(False, "--json", help="Maschinen-Ausgabe (wo unterstützt)."),
    offline: bool = typer.Option(False, "--offline", "--spar",
                                 help="Sparmodus: ohne KI (Heuristik, kostenlos)."),
    version: bool = typer.Option(False, "--version", help="Version anzeigen."),
):
    if version:
        typer.echo(f"pollysort {__version__}")
        raise typer.Exit()
    _STATE.update(quiet=quiet, plain=plain, no_emoji=no_emoji, json=json_out, offline=offline)


# ---------------------------------------------------------------------------
# Kontext-Aufbau
# ---------------------------------------------------------------------------
def _resolve_or_exit(con: BeeConsole, hive: str | None) -> Path:
    try:
        return config.resolve_hive(hive)
    except FileNotFoundError as exc:
        con.error(str(exc))
        raise typer.Exit(1)


def _build_ctx(con: BeeConsole, hive: str | None) -> Context:
    hive_path = _resolve_or_exit(con, hive)
    cfg = config.load_config()
    seed = config.load_seed(hive_path)
    if _STATE["offline"]:
        cfg.llm_provider = "offline"
    api_key = None if _STATE["offline"] else config.load_credentials()
    from .feedback import Feedback
    from .wachstafel import Wachstafel
    few_shots = Feedback(hive_path).few_shots()          # Feedback-Loop → Prompt (§14.4)
    wachstafel = Wachstafel(hive_path).text()            # gelernte Projekt-Regeln (ACE)
    client = build_client(cfg, api_key, seed.categories, few_shots, wachstafel=wachstafel)
    return Context.build(hive=hive_path, cfg=cfg, seed=seed, client=client,
                         console=con, journal=Journal(hive_path))


# ---------------------------------------------------------------------------
# init & person
# ---------------------------------------------------------------------------
@app.command()
def init(
    hive: str = typer.Option(..., "--hive", help="Pfad des Bienenstocks (Wurzel-Storage)."),
    offline: bool = typer.Option(False, "--offline", help="Ohne OpenRouter-Key starten."),
):
    """Stock einrichten: Ordnerbaum, hive.toml, Key-Abfrage (§10, §15)."""
    con = _con()
    hive_path = Path(hive).expanduser().resolve()
    con.info(f"Königin erwacht – Bienenstock: {hive_path}", "🐝")
    for sub in config.STOCK_DIRS:
        (hive_path / sub).mkdir(parents=True, exist_ok=True)

    seed = config.HiveSeed(responsibility={c: [] for c in config.DEFAULT_CATEGORIES})
    if not (hive_path / "hive.toml").exists():
        config.write_seed(hive_path, seed)

    cfg = config.load_config()
    cfg.hive = str(hive_path)
    if offline or _STATE["offline"]:
        cfg.llm_provider = "offline"

    if cfg.llm_provider == "openrouter" and not config.load_credentials():
        con.info("Kein OpenRouter-Key gefunden.", "🔑")
        key = typer.prompt("Bitte OpenRouter API-Key eingeben (leer = Sparmodus)",
                           default="", hide_input=True)
        if key.strip():
            config.save_credentials(key)
            con.honey(f"Key gespeichert unter {config.CREDENTIALS_PATH} (chmod 600)", "✅")
        else:
            cfg.llm_provider = "offline"
            con.info("Kein Key → Sparmodus (heuristische Analyse, keine Kosten).", "🐝")

    config.save_config(cfg)
    Journal(hive_path).init_header(hive_path)
    con.honey("Ordner bereit. Dateien hineinlegen und 'pollysort-cli scan --mode move' ausführen.", "🍯")
    if cfg.llm_provider == "openrouter":
        con.ask("Hinweis: In Stufe 1 werden Dokumentinhalte zur Analyse an OpenRouter "
                "übertragen (§17). Vertrauliches via .beeignore/exclude ausnehmen.", "⚠️")


@person_app.command("add")
def person_add(
    name: str = typer.Argument(..., help="Personenkürzel, z. B. nik"),
    categories: str = typer.Option("", "--categories", help="Kategorien, kommagetrennt."),
    hive: str | None = typer.Option(None, "--hive"),
):
    """Person einer/mehreren Kategorien zuordnen (Hintergrund, many-to-many)."""
    con = _con()
    ctx = _build_ctx(con, hive)
    cats = [c.strip().lower() for c in categories.split(",") if c.strip()]
    for cat in cats:
        persons = set(ctx.taxonomy.persons_for(cat)) | {name}
        ctx.taxonomy.set_persons(cat, sorted(persons))
    con.honey(f"{name} → {', '.join(cats) or '(keine Kategorie)'}", "🐝")


@person_app.command("list")
def person_list(hive: str | None = typer.Option(None, "--hive")):
    """Zuständigkeiten anzeigen."""
    con = _con()
    ctx = _build_ctx(con, hive)
    for cat, persons in ctx.taxonomy.responsibility.items():
        con.raw(f"  {cat:<16} {', '.join(persons) or '—'}")


# ---------------------------------------------------------------------------
# scan / sweep
# ---------------------------------------------------------------------------
@app.command()
def scan(
    mode: str = typer.Option("index", "--mode", help="index | move."),
    hive: str | None = typer.Option(None, "--hive"),
    limit: int | None = typer.Option(None, "--limit", help="Nur die ersten N Dateien."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Geplante Moves zeigen, nichts anfassen."),
    report_only: bool = typer.Option(False, "--report-only", help="Nur Drift-Bericht, nichts tun."),
    all_stock: bool = typer.Option(False, "--all", help="Ganzen Stock (Sweep) statt nur Flugloch."),
):
    """Rundflug: Flugloch (Default) oder ganzer Stock; mit Drift-Bericht (§9–§11)."""
    con = _con()
    ctx = _build_ctx(con, hive)
    con.info(f"LLM-Provider: {ctx.cfg.llm_provider} · Modell: "
             f"{config.effective_model(ctx.cfg)}", "🧠")
    try:
        with QueenLock(ctx.hive):
            if all_stock or report_only:
                from .sweeper import sweep as run_sweep
                rep = run_sweep(ctx, mode=mode, report_only=report_only, dry_run=dry_run)
                code = rep.exit_code()
                payload = rep.__dict__
            else:
                s = run_cycle(ctx, mode=mode, limit=limit, dry_run=dry_run)
                code, payload = s.exit_code(), s.__dict__
    except QueenLockError as exc:
        con.error(str(exc))
        raise typer.Exit(1)
    if _STATE["json"]:
        import json as _json
        typer.echo(_json.dumps(payload, ensure_ascii=False, default=str))
    raise typer.Exit(code)


@app.command()
def sweep(hive: str | None = typer.Option(None, "--hive"),
          mode: str = typer.Option("index", "--mode")):
    """Voller Rundflug über den ganzen Stock + Drift-Bericht (Alias für scan --all)."""
    scan(mode=mode, hive=hive, limit=None, dry_run=False, report_only=False, all_stock=True)


# ---------------------------------------------------------------------------
# status / list / find
# ---------------------------------------------------------------------------
@app.command()
def status(hive: str | None = typer.Option(None, "--hive")):
    """Überblick: Stock, Provider, Status-Zähler, Betriebsmodi (§19)."""
    con = _con()
    hive_path = _resolve_or_exit(con, hive)
    cfg = config.load_config()
    # Der Provider ist pro Projekt (seed), nicht global — den auch anzeigen.
    cfg.llm_provider = config.load_seed(hive_path).provider
    from .store import Store
    counts = Store(hive_path).status_counts()
    con.info(f"Bienenstock: {hive_path}", "🐝")
    con.info(f"Provider: {cfg.llm_provider} · Modell: {config.effective_model(cfg)}", "🧠")
    con.info(f"Autosort: {'AN' if cfg.autosort else 'AUS'} · Sweep-Timer: "
             f"{'AN' if cfg.sweep_auto else 'AUS'} ({cfg.sweep_interval_minutes} min)", "🟢")
    con.raw(f"📦  {sum(counts.values())} Einträge im Index")
    for st, n in sorted(counts.items()):
        con.raw(f"    {st:<13} {n}")
    if counts.get("needs_review"):
        con.ask(f"{counts['needs_review']} offene Rückfrage(n) → 'pollysort-cli review'")


@app.command("list")
def list_cmd(
    status: str | None = typer.Option(None, "--status"),
    kategorie: str | None = typer.Option(None, "--kategorie"),
    hive: str | None = typer.Option(None, "--hive"),
):
    """Einträge auflisten/filtern (SQL-Index)."""
    con = _con()
    hive_path = _resolve_or_exit(con, hive)
    from .store import Store
    _print_rows(con, Store(hive_path).query(status=status, kategorie=kategorie))


@app.command()
def find(
    keyword: str | None = typer.Option(None, "--keyword"),
    person: str | None = typer.Option(None, "--person"),
    kategorie: str | None = typer.Option(None, "--kategorie"),
    hive: str | None = typer.Option(None, "--hive"),
):
    """Suchen & Filtern nach Metadaten."""
    con = _con()
    hive_path = _resolve_or_exit(con, hive)
    from .store import Store
    _print_rows(con, Store(hive_path).query(keyword=keyword, person=person, kategorie=kategorie))


# ---------------------------------------------------------------------------
# review / assign
# ---------------------------------------------------------------------------
@app.command()
def review(hive: str | None = typer.Option(None, "--hive"),
           mode: str = typer.Option("move", "--mode")):
    """Rückfragen (< 75 %) gebündelt & interaktiv abarbeiten (§9)."""
    con = _con()
    ctx = _build_ctx(con, hive)
    from .review import review as run_review
    try:
        with QueenLock(ctx.hive):
            run_review(ctx, mode=mode)
    except QueenLockError as exc:
        con.error(str(exc))
        raise typer.Exit(1)


@app.command()
def assign(
    ident: str = typer.Argument(..., help="Eintrags-ID (oder Dateiname)."),
    kategorie: str = typer.Option(..., "--kategorie", help="Zielkategorie."),
    hive: str | None = typer.Option(None, "--hive"),
    mode: str = typer.Option("move", "--mode"),
):
    """Zuordnung korrigieren → Feedback ins Gedächtnis (§14.4)."""
    con = _con()
    ctx = _build_ctx(con, hive)
    from .review import apply_correction
    old = apply_correction(ctx, ident, kategorie, mode=mode, source="assign")
    if old is None:
        con.error(f"Kein Eintrag für '{ident}' gefunden.")
        raise typer.Exit(1)
    con.honey(f"{ident}: {old} → {kategorie.lower()} (Gedächtnis aktualisiert)", "🍯")


# ---------------------------------------------------------------------------
# autosort / sweep-timer (Config-Schalter, wirken auch auf laufenden Daemon)
# ---------------------------------------------------------------------------
@app.command()
def autosort(state: str = typer.Argument(..., help="on | off | status"),
             hive: str | None = typer.Option(None, "--hive")):
    """Flugloch-Autosort an-/abschalten (§10.1)."""
    con = _con()
    cfg = config.load_config()
    if state == "status":
        con.info(f"Autosort: {'AN' if cfg.autosort else 'AUS'} "
                 f"(Poll alle {cfg.flugloch_poll_seconds} s)", "🟢")
        return
    cfg.autosort = (state == "on")
    config.save_config(cfg)
    con.honey(f"Autosort {'AN' if cfg.autosort else 'AUS'}", "🟢" if cfg.autosort else "⚪")


@app.command("sweep-timer")
def sweep_timer(
    state: str = typer.Argument("status", help="on | off | status"),
    every: str | None = typer.Option(None, "--every", help="Intervall, z. B. 20m | 2h | 12h."),
    hive: str | None = typer.Option(None, "--hive"),
):
    """Intervall-Sweep an/aus + Intervall setzen (§10.2)."""
    con = _con()
    cfg = config.load_config()
    if every:
        cfg.sweep_interval_minutes = _parse_every(every)
    if state == "on":
        cfg.sweep_auto = True
    elif state == "off":
        cfg.sweep_auto = False
    config.save_config(cfg)
    con.info(f"Sweep-Timer: {'AN' if cfg.sweep_auto else 'AUS'} "
             f"(alle {cfg.sweep_interval_minutes} min)", "⏱️")


def _parse_every(s: str) -> int:
    s = s.strip().lower()
    if s.endswith("h"):
        return int(float(s[:-1]) * 60)
    if s.endswith("m"):
        return int(s[:-1])
    return int(s)


# ---------------------------------------------------------------------------
# buzz (Daemon)
# ---------------------------------------------------------------------------
@app.command()
def buzz(
    hive: str | None = typer.Option(None, "--hive"),
    mode: str = typer.Option("move", "--mode"),
    no_autosort: bool = typer.Option(False, "--no-autosort", help="Nur Sweeps, kein Autosort."),
    no_sweep: bool = typer.Option(False, "--no-sweep", help="Nur Autosort, kein Intervall-Sweep."),
    max_cycles: int | None = typer.Option(None, "--max-cycles", help="Runden begrenzen (Test)."),
):
    """Dauerbetrieb: Flugloch-Watcher + Sweep-Timer in einem Prozess (§10.3)."""
    con = _con()
    hive_path = _resolve_or_exit(con, hive)
    from .daemon import run_daemon
    run_daemon(lambda: _build_ctx(_con(), str(hive_path)), hive_path, mode=mode,
               use_autosort=not no_autosort, use_sweep=not no_sweep, max_cycles=max_cycles)


# ---------------------------------------------------------------------------
# Undertaker: undertake / resurrect / bury  +  undo
# ---------------------------------------------------------------------------
@app.command()
def undertake(ident: str = typer.Argument(...), hive: str | None = typer.Option(None, "--hive")):
    """Eintrag in die Quarantäne (friedhof/) verschieben — löscht nichts (§13)."""
    con = _con()
    ctx = _build_ctx(con, hive)
    from .undertaker import undertake as do
    dest = do(ctx.hive, ctx.store, ident)
    if not dest:
        con.error(f"Kein Eintrag für '{ident}'.")
        raise typer.Exit(1)
    ctx.mind.forget(ctx.store.by_id(ident)["id"] if ctx.store.by_id(ident) else ident)
    con.info(f"→ friedhof/ (Quarantäne, nicht gelöscht): {dest.name}", "⚰️")


@app.command()
def resurrect(ident: str = typer.Argument(...), hive: str | None = typer.Option(None, "--hive")):
    """Datei aus dem Friedhof zurückholen (§13)."""
    con = _con()
    ctx = _build_ctx(con, hive)
    from .undertaker import resurrect as do
    dest = do(ctx.hive, ctx.store, ident)
    if not dest:
        con.error(f"Nichts zum Zurückholen für '{ident}'.")
        raise typer.Exit(1)
    con.honey(f"Zurück im Stock: {dest.name}", "🐝")


@app.command()
def bury(
    confirm: bool = typer.Option(False, "--confirm", help="Pflicht: endgültiges Löschen bestätigen."),
    hive: str | None = typer.Option(None, "--hive"),
):
    """friedhof/ ENDGÜLTIG leeren — getrennter, bestätigungspflichtiger Schritt (§13)."""
    con = _con()
    hive_path = _resolve_or_exit(con, hive)
    from .undertaker import buried_candidates
    from .undertaker import bury as do
    candidates = buried_candidates(hive_path)
    if not candidates:
        con.info("Friedhof ist leer.", "🐝")
        return
    con.raw("Würde endgültig löschen:")
    for p in candidates:
        con.raw(f"    🗑️ {p.name}")
    if not confirm:
        con.ask("Nichts gelöscht. Zum Ausführen: 'pollysort-cli bury --confirm'.")
        raise typer.Exit(0)
    answer = typer.prompt(f'Wirklich {len(candidates)} Dateien endgültig löschen? Tippe "'
                          f'{len(candidates)}"')
    if answer.strip() != str(len(candidates)):
        con.info("Abgebrochen.", "🐝")
        raise typer.Exit(0)
    removed = do(hive_path, None)  # type: ignore[arg-type]
    con.honey(f"{len(removed)} Datei(en) endgültig gelöscht.", "⚰️")


@app.command()
def undo(hive: str | None = typer.Option(None, "--hive")):
    """'Rückflug': die letzte vom System durchgeführte Verschiebung rückgängig machen (§19)."""
    con = _con()
    ctx = _build_ctx(con, hive)
    import shutil

    from .movelog import MoveLog
    last = MoveLog(ctx.hive).pop_last()
    if not last:
        con.info("Nichts rückgängig zu machen.", "🐝")
        return
    src, dst = Path(last["dst"]), Path(last["src"])
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        ctx.store.update_path(last["bee_id"], str(dst))
    con.honey(f"Rückgängig: {src.name} → {dst}", "↩️")


# ---------------------------------------------------------------------------
# hive: show / review / approve  +  suggest
# ---------------------------------------------------------------------------
@hive_app.command("show")
def hive_show(hive: str | None = typer.Option(None, "--hive")):
    """Aktuelle Taxonomie + Zuständigkeiten (§19)."""
    con = _con()
    ctx = _build_ctx(con, hive)
    con.info(f"Kategorien: {', '.join(ctx.taxonomy.categories)}", "🧠")
    for cat, persons in ctx.taxonomy.responsibility.items():
        con.raw(f"    {cat:<16} {', '.join(persons) or '—'}  "
                f"({ctx.mind.count(cat)} im Gedächtnis)")


@hive_app.command("review")
def hive_review(hive: str | None = typer.Option(None, "--hive")):
    """Kategorie-Vorschläge (neu/merge) erzeugen & anzeigen (Human-in-the-Loop, §14.3)."""
    con = _con()
    ctx = _build_ctx(con, hive)
    from .hive_mind.reflection import Reflection
    refl = Reflection(ctx.hive)
    proposals = refl.reflect(ctx.store, ctx.mind) or refl.pending()
    if not proposals:
        con.info("Keine Vorschläge. Das Gedächtnis ist zufrieden. 🐝", "🐣")
        return
    for p in proposals:
        con.raw(f"    [{p.slug}] {p.describe()}")
    con.info("Übernehmen mit: pollysort-cli hive approve <slug>", "🐣")


@hive_app.command("approve")
def hive_approve(slug: str = typer.Argument(...), hive: str | None = typer.Option(None, "--hive")):
    """Einen Vorschlag übernehmen inkl. Migration (Ordner + DB + Zentroide) (§6, §14.3)."""
    con = _con()
    ctx = _build_ctx(con, hive)
    from .hive_mind.reflection import Reflection
    from .migrate import approve as do_approve
    refl = Reflection(ctx.hive)
    p = refl.get(slug)
    if not p:
        con.error(f"Kein Vorschlag '{slug}'.")
        raise typer.Exit(1)
    try:
        with QueenLock(ctx.hive):
            msg = do_approve(ctx, p)
            refl.resolve(slug)
    except QueenLockError as exc:
        con.error(str(exc))
        raise typer.Exit(1)
    con.honey(msg, "🍯")


@app.command()
def suggest(
    strategy: str = typer.Option("para", "--strategy", help="para | johnny | dewey"),
    hive: str | None = typer.Option(None, "--hive"),
):
    """Empfehlungen: Strategie-Preset + dynamische Vorschläge (§18)."""
    con = _con()
    ctx = _build_ctx(con, hive)
    from .recommender import suggest as do
    do(ctx, strategy)


# ---------------------------------------------------------------------------
# export / shell
# ---------------------------------------------------------------------------
@app.command()
def export(
    format: str = typer.Option("md", "--format", help="md | json"),
    out: str = typer.Option(..., "--out", help="Zieldatei."),
    hive: str | None = typer.Option(None, "--hive"),
):
    """Gesamten Index als MD-Bericht oder JSON exportieren (§19)."""
    con = _con()
    hive_path = _resolve_or_exit(con, hive)
    from .store import Store
    rows = Store(hive_path).query()
    outp = Path(out)
    if format == "json":
        import json as _json
        outp.write_text(_json.dumps(rows, ensure_ascii=False, indent=2, default=str),
                        encoding="utf-8")
    else:
        lines = ["# 🐝 PollySort — Export", ""]
        for r in rows:
            lines += [f"## {r.get('title') or r['filename']}",
                      f"- Kategorie: {r.get('kategorie')}  |  Status: {r.get('status')}  "
                      f"|  Confidence: {r.get('confidence')}",
                      f"- Funktion: {r.get('funktion')}",
                      f"- Pfad: {r.get('path')}", ""]
        outp.write_text("\n".join(lines), encoding="utf-8")
    con.honey(f"{len(rows)} Einträge → {outp} ({format})", "🍯")


@app.command()
def doctor(hive: str | None = typer.Option(None, "--hive")):
    """Health-Check: Interpreter, KI-Provider, Datenbank, Extras, Gedächtnis."""
    con = _con()
    try:
        hive_path = config.resolve_hive(hive)
    except FileNotFoundError:
        hive_path = None
    from .doctor import run_checks
    icon = {"ok": "✅", "warn": "⚠️", "fail": "❌"}
    con.info(i18n.t("doctor.cli_title"), "🩺")
    worst = 0
    for label, status, detail in run_checks(hive_path):
        con.raw(f"  {icon.get(status, '•')}  {label:<12} {detail}")
        worst = max(worst, {"ok": 0, "warn": 1, "fail": 2}.get(status, 0))
    raise typer.Exit(worst)


@app.command("beenara")
def beenara_cmd(aktion: str = typer.Argument("status", help="status | pull")):
    """BeeNara (lokales Entscheider-Modell) samt Laufzeit laden oder den Stand zeigen.
    Exit 0 = BeeNara sortiert mit."""
    con = _con()
    from . import beenara
    a = aktion.strip().lower()
    if a in ("pull", "laden", "download", "update"):
        raise typer.Exit(0 if beenara.einrichten(con) else 1)
    if a not in ("status", ""):
        con.error("pollysort-cli beenara <status|pull>")
        raise typer.Exit(2)
    cfg = config.load_config()
    for art, emoji, text in beenara.bericht(cfg):
        getattr(con, art)(text, emoji)
    raise typer.Exit(0 if beenara.warum_nicht(cfg) is None else 1)


@app.command()
def shell(hive: str | None = typer.Option(None, "--hive")):
    """Interaktive Bienenstock-Konsole (REPL) — Befehle ohne 'pollysort'-Präfix (§19.1)."""
    con = _con()
    _resolve_or_exit(con, hive)
    con.honey("🐝 pollysort-Shell. Befehle direkt eingeben ('help', 'exit').", "🐝")
    import shlex
    while True:
        try:
            raw = input("🐝 pollysort> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if raw in ("exit", "quit", "q"):
            break
        if not raw:
            continue
        if raw in ("help", "?"):
            typer.echo("scan | sweep | status | list | find | review | suggest | hive show | exit")
            continue
        try:
            app(shlex.split(raw), standalone_mode=False)
        except SystemExit:
            pass
        except Exception as exc:  # REPL soll nicht sterben
            con.error(str(exc))
    con.info("Shell verlassen.", "🐝")


# ---------------------------------------------------------------------------
def _print_rows(con: BeeConsole, rows: list[dict]) -> None:
    if _STATE["json"]:
        import json as _json
        typer.echo(_json.dumps(rows, ensure_ascii=False, default=str))
        return
    if not rows:
        con.info("Keine Treffer.", "🕸️")
        return
    table = Table(show_header=True, header_style="bold gold1")
    for col in ("id", "kategorie", "status", "conf", "titel", "datei"):
        table.add_column(col)
    for r in rows:
        table.add_row(r["id"], r.get("kategorie") or "", r.get("status") or "",
                      f"{r.get('confidence') or 0:.2f}", (r.get("title") or "")[:40],
                      (r.get("filename") or "")[:36])
    con.raw(table)


if __name__ == "__main__":
    app()
