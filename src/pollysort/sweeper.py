"""Sweep — der große Rundflug + Drift-Bericht (§11).

Vergleicht DB ↔ Dateisystem über ``content_hash`` und Pfad. Vier Fälle:
  🆕 neu · ✏️ geändert · 🔀 verschoben/umbenannt · 🗑️ verschwunden (nur bemerkt, nie gelöscht).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import i18n
from .guards import IgnoreMatcher
from .models import Status
from .pipeline import Context, CycleSummary, ingest
from .scout import scout, walk


@dataclass
class SweepReport:
    new: int = 0
    changed: int = 0
    moved: int = 0
    missing: int = 0
    errors: int = 0
    learned: int = 0                 # aus manuellen Moves zwischen Waben gelernte Korrekturen
    llm_calls: int = 0
    est_cost_eur: float = 0.0
    details: list[str] = field(default_factory=list)

    def exit_code(self) -> int:
        # §19: 3 Fehler · 4 verschwundene Dateien bemerkt · 0 ok
        if self.errors:
            return 3
        if self.missing:
            return 4
        return 0


def _category_of_path(ctx: Context, path) -> str | None:
    """Zu welcher bekannten Wabe gehört dieser Pfad? (Ordnername = Kategorie, sonst None.)"""
    parent = Path(path).parent
    if parent.resolve() == Path(ctx.hive).resolve():
        return None                  # liegt lose im Root, keine Wabe
    name = parent.name.strip().lower()
    known = {c.strip().lower() for c in ctx.taxonomy.categories}
    return name if name in known else None


def sweep(ctx: Context, *, mode: str = "index", report_only: bool = False,
          dry_run: bool = False) -> SweepReport:
    """Einen vollständigen Rundflug fliegen und den Sweep-Bericht erzeugen."""
    con = ctx.console
    store = ctx.store
    matcher = IgnoreMatcher(ctx.hive, extra=ctx.seed.exclude)

    con.info(i18n.t("sw.checking"), "🧹")
    findings = scout(walk([ctx.hive], matcher, recursive=True))
    cur_by_path = {str(f.path): f for f in findings}
    cur_by_hash: dict[str, list] = {}
    for f in findings:
        cur_by_hash.setdefault(f.content_hash, []).append(f)

    rows = store.query()
    active = [r for r in rows if r["status"] not in
              (Status.SUPERSEDED.value, Status.MISSING.value, Status.QUARANTINED.value)]
    db_hashes = {r["content_hash"] for r in rows}
    db_paths = {r["path"] for r in rows} | {r.get("original_path") for r in rows}

    report = SweepReport()
    summary = CycleSummary()

    # 1) Bekannte Einträge prüfen: geändert / verschoben / verschwunden
    for r in active:
        p = r["path"]
        if Path(p).exists():
            cur = cur_by_path.get(p)
            if cur and cur.content_hash != r["content_hash"]:
                _handle_changed(ctx, r, cur, mode, report_only, dry_run, report, summary)
        else:
            _handle_gone(ctx, r, cur_by_hash, db_paths, report_only, report)

    # 2) Neue Dateien (unbekannter Hash UND unbekannter Pfad)
    seen_new: set[str] = set()
    for f in findings:
        if f.content_hash in db_hashes or str(f.path) in db_paths:
            continue
        if f.content_hash in seen_new:
            store.add_duplicate_path(f.content_hash.split(":")[-1][:8], str(f.path))
            continue
        seen_new.add(f.content_hash)
        report.new += 1
        report.details.append(f"🆕 {f.path.relative_to(ctx.hive)}")
        if not report_only:
            ingest(ctx, f, mode=mode, dry_run=dry_run, summary=summary)

    report.errors = summary.errors
    report.llm_calls = ctx.client.usage.calls
    report.est_cost_eur = ctx.client.usage.est_cost_eur()
    _print_report(ctx, report)
    return report


def _handle_changed(ctx, r, cur, mode, report_only, dry_run, report, summary) -> None:
    """Bekannter Pfad, neuer Hash → neue Version, alte → superseded (§11)."""
    report.changed += 1
    report.details.append(f"✏️ {Path(r['path']).name} → neue Version (alt: superseded)")
    if report_only:
        return
    ctx.store.set_status(r["id"], Status.SUPERSEDED)
    ctx.mind.forget(r["id"])
    ingest(ctx, cur, mode=mode, dry_run=dry_run, summary=summary, supersedes=r["id"])


def _handle_gone(ctx, r, cur_by_hash, db_paths, report_only, report) -> None:
    """Pfad weg. Taucht der Hash woanders auf → verschoben; sonst → verschwunden (§11)."""
    candidates = [f for f in cur_by_hash.get(r["content_hash"], [])
                  if str(f.path) not in db_paths]
    if candidates:
        report.moved += 1
        new_path = str(candidates[0].path)
        report.details.append(f"🔀 {Path(r['path']).name} → {candidates[0].path.name}")
        if not report_only:
            ctx.store.update_path(r["id"], new_path)
            _learn_from_move(ctx, r, new_path, report)
    else:
        report.missing += 1
        report.details.append(f"🗑️ {Path(r['path']).name} → status: missing")
        if not report_only:
            ctx.store.set_status(r["id"], Status.MISSING)


def _learn_from_move(ctx, r, new_path, report) -> None:
    """Manuellen Move ZWISCHEN Waben als Korrektur werten (Self-Learning-Loop).

    Hat der Nutzer eine Datei von Hand aus Wabe A in Wabe B gezogen, ist das eine
    Zuordnungs-Korrektur A→B: Kategorie/Status nachziehen und als Nektar-Feedback
    (`quelle: manuell`) festhalten, damit die Königin daraus Wachstafel-Regeln ableiten
    kann. Bewusst OHNE Embedding-Call — ein Scan bleibt so kostenfrei & vorhersehbar.
    """
    old_cat = _category_of_path(ctx, r["path"])
    new_cat = _category_of_path(ctx, new_path)
    if not new_cat or new_cat == old_cat or new_cat == r.get("kategorie"):
        return
    from .store import bees
    with ctx.store.engine.begin() as c:
        c.execute(bees.update().where(bees.c.id == r["id"]).values(
            kategorie=new_cat, status=Status.ASSIGNED.value))
    ctx.feedback.record(bee_id=r["id"], title=r.get("title") or "",
                        funktion=r.get("funktion") or "",
                        kategorie_alt=old_cat or r.get("kategorie") or "",
                        kategorie_neu=new_cat, quelle="manuell")
    report.learned += 1
    report.details.append(
        i18n.t("sw.learned_one", name=Path(new_path).name, old=old_cat or "—", new=new_cat))


def _print_report(ctx: Context, r: SweepReport) -> None:
    con = ctx.console
    con.rule(i18n.t("sw.title"))
    line = i18n.t("sw.line", new=r.new, changed=r.changed, moved=r.moved, missing=r.missing,
                  errors=r.errors)
    if r.learned:
        line += i18n.t("sw.learned", n=r.learned)
    con.raw(line)
    for d in r.details[:40]:
        con.raw(f"    {d}")
    # Ehrlich bleiben wie im Sortierlauf: Kosten nur, wo es welche gibt (Cloud).
    schluss = i18n.t("sw.safe")
    if r.llm_calls and getattr(ctx.cfg, "llm_provider", "") == "openrouter":
        schluss += i18n.t("sw.calls_cost", n=r.llm_calls, cost=f"{r.est_cost_eur:.4f}")
    elif r.llm_calls:
        schluss += i18n.t("sw.calls", n=r.llm_calls)
    con.info(schluss, "🐝")
    ctx.journal.entry("Sweep-Bericht", [
        f"neu: {r.new}", f"geändert: {r.changed}", f"verschoben: {r.moved}",
        f"verschwunden: {r.missing}", f"fehler: {r.errors}",
    ] + r.details[:40])
    ctx.journal.event("sweep", new=r.new, changed=r.changed, moved=r.moved,
                      missing=r.missing, errors=r.errors)
