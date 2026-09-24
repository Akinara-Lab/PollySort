"""Konfiguration & Pfade.

Grundprinzip: **Das Arbeitsverzeichnis bleibt sauber.** Alles, was das Tool generiert
(Datenbank, Logs, Gedächtnis, Einträge, Quarantäne, Config), liegt in genau EINEM
versteckten Ordner ``<hive>/.honig/``. Sichtbar entstehen nur die Kategorie-Ordner.

- ``~/.beehive/credentials``  — OpenRouter-Key (chmod 600), außerhalb des Arbeitsordners
- ``<hive>/.honig/hive.toml`` — Einstellungen (Kategorien, Schwelle, Zuständigkeit)
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Pfade
# ---------------------------------------------------------------------------
#: Die alte Ablage vor dem Rename auf PollySort. Wird einmalig übernommen (s. u.).
LEGACY_HOME = Path.home() / ".beehive"


def _migrate_legacy_home(old: Path, new: Path) -> None:
    """Die alte ``~/.beehive``-Ablage nach ``~/.pollysort`` übernehmen.

    Es wird **kopiert**, nie verschoben und nie gelöscht — die alte Ablage bleibt
    unberührt liegen. Das folgt dem Grundprinzip des Projekts: kein Code-Pfad entfernt
    Daten des Nutzers. Geht die Übernahme schief (Rechte, volle Platte), startet das
    Tool mit einer leeren neuen Ablage weiter, statt abzubrechen.
    """
    import shutil
    from datetime import UTC, datetime
    try:
        shutil.copytree(old, new)
    except OSError:
        try:
            new.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return
    try:
        (new / "UEBERNOMMEN.txt").write_text(
            f"Übernommen aus {old} am "
            f"{datetime.now(UTC).replace(microsecond=0).isoformat()}.\n"
            "Der alte Ordner wurde bewusst NICHT gelöscht — du kannst ihn entfernen, "
            "sobald du geprüft hast, dass hier alles vollständig ist.\n",
            encoding="utf-8")
    except OSError:
        pass


def _resolve_home() -> Path:
    """Wo die globale Ablage liegt.

    Vorrang hat ``POLLYSORT_HOME``; der Altname ``BEEHIVE_HOME`` wird weiter akzeptiert,
    damit bestehende Skripte und CI-Aufrufe nicht brechen. Ohne Env liegt sie in
    ``~/.pollysort`` — gibt es die noch nicht, wohl aber eine alte ``~/.beehive``, wird
    diese einmalig übernommen.
    """
    env = os.environ.get("POLLYSORT_HOME") or os.environ.get("BEEHIVE_HOME")
    if env:
        return Path(env)
    home = Path.home() / ".pollysort"
    if not home.exists() and LEGACY_HOME.is_dir():
        _migrate_legacy_home(LEGACY_HOME, home)
    return home


POLLYSORT_HOME = _resolve_home()
#: Altname — noch als Alias erhalten, damit externe Skripte nicht brechen.
BEEHIVE_HOME = POLLYSORT_HOME
CONFIG_PATH = POLLYSORT_HOME / "config.toml"
CREDENTIALS_PATH = POLLYSORT_HOME / "credentials"

#: Der EINE versteckte Ordner, in dem alles Generierte landet.
HONIG = ".honig"

# Was in .honig angelegt wird (Kategorie-Ordner entstehen erst bei Bedarf, direkt im Root).
STOCK_DIRS = [HONIG, f"{HONIG}/eintraege", f"{HONIG}/papierkorb", f"{HONIG}/vorschlaege"]

DEFAULT_CATEGORIES = ["rechnungen", "vertraege", "protokolle", "recherche"]

# Nektar-Sorten (§v0.3): Kurznamen → OpenRouter-Modell-IDs für den schnellen 'modell'-Wechsel.
# Beliebige OpenRouter-IDs sind zusätzlich direkt erlaubt: `modell <provider/modell-id>`.
NEKTAR_SORTEN: dict[str, str] = {
    "flash-lite": "google/gemini-3.1-flash-lite",
    "flash": "google/gemini-3.5-flash",
}


def honig(hive: Path) -> Path:
    """Der versteckte Metadaten-Ordner eines Stocks: ``<hive>/.honig``."""
    return hive / HONIG


def effective_model(cfg) -> str:
    """Das Modell, das für diesen Provider WIRKLICH läuft (nicht der Online-Default).

    Der Ollama-Modus ist auf ein festes lokales Modell fixiert; ``cfg.llm_model`` gilt nur online.
    """
    if getattr(cfg, "llm_provider", None) == "ollama":
        from .llm.client import OLLAMA_MODEL
        return OLLAMA_MODEL
    if getattr(cfg, "llm_provider", None) == "offline":
        return "heuristik (offline)"
    return cfg.llm_model


def pretty_category(kat: str) -> str:
    """Kleingeschriebenes Label → sichtbarer Ordnername (``rechnungen`` → ``Rechnungen``)."""
    if not kat or kat == "_unassigned":
        return "_Unsortiert"
    return kat[:1].upper() + kat[1:]


class AppConfig(BaseModel):
    """Globale Config aus ``~/.beehive/config.toml`` (§10, §15)."""

    hive: str | None = None                                   # aktiver Stock-Pfad
    onboarded: bool = False                                   # globales Erst-Setup erledigt?
    llm_provider: str = "openrouter"                          # openrouter | ollama | offline
    llm_model: str = "google/gemini-3.1-flash-lite"
    embed_model: str = "perplexity/pplx-embed-v1-4b"
    llm_fallback: str = "google/gemini-3.5-flash"
    llm_endpoint: str | None = None                           # nur Ollama/TEI (Stufe 2)
    embed_endpoint: str | None = None

    # Betriebsmodi (§10)
    autosort: bool = True
    flugloch_poll_seconds: int = 20
    sweep_auto: bool = True
    sweep_interval_minutes: int = 30
    scan_mode: str = "index"                                  # index | move

    # Konsole (§12)
    animations: bool = True
    theme: str = "dark"                                      # dark | light (Terminal-Hintergrund)
    static_view: bool = True                                 # statische Ansicht statt Log-Scrolling
    tutorial_seen: bool = False                              # 3-Schritt-Erststart-Tutorial gezeigt?
    language: str = "de"                                     # de | en (UI-Sprache)


@dataclass
class HiveSeed:
    """Die pro-Projekt-Konfiguration in ``<hive>/.honig/hive.toml``.

    Jeder Bienenstock hat seine eigene — so laufen mehrere Projekte mit unterschiedlichen
    Kategorien, Modus und Update-Verhalten unabhängig nebeneinander.
    """

    categories: list[str] = field(default_factory=lambda: list(DEFAULT_CATEGORIES))
    responsibility: dict[str, list[str]] = field(default_factory=dict)
    # Dynamische Unterordner je Kategorie, z. B. {"rechnung": "{jahr}/{monat}"} →
    # sortiert Rechnungen nach Jahr/Monat. Platzhalter: {jahr}/{monat}/{tag} (dt./engl.).
    subrouting: dict[str, str] = field(default_factory=dict)
    threshold_assign: float = 0.75
    max_file_mb: int = 100
    pollen_retention_days: int = 30
    exclude: list[str] = field(default_factory=list)

    # Projekt-Metadaten (aus dem Einrichtungs-Assistenten)
    name: str = ""
    provider: str = "offline"            # offline | openrouter | ollama  (Modus je Projekt)
    watch: str = "off"                   # off | notify | move  (Verhalten bei neuen Dateien)
    watch_seconds: int = 10              # wie oft der Eingang geprüft wird
    # Nach dem Sortieren verfeinert die KI Titel & Zusammenfassung (nur Ollama, Plan §8.3).
    nacherfassung: bool = True


def is_setup(hive: Path) -> bool:
    """Ist dieser Ordner bereits als Projekt eingerichtet?"""
    return (honig(hive) / "hive.toml").exists()


# ---------------------------------------------------------------------------
# Laden / Speichern
# ---------------------------------------------------------------------------
def _read_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except (tomllib.TOMLDecodeError, OSError):
        # Defektes/halbfertiges Config-File soll den Start nie blockieren → Defaults.
        return {}


def load_config() -> AppConfig:
    data = _read_toml(CONFIG_PATH)
    return AppConfig(**data)


def save_config(cfg: AppConfig) -> None:
    POLLYSORT_HOME.mkdir(parents=True, exist_ok=True)
    lines = ["# PollySort — globale Config (KEIN API-Key hier!)", ""]
    for key, val in cfg.model_dump().items():
        if val is None:
            continue
        lines.append(f"{key} = {_toml_val(val)}")
    CONFIG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_credentials() -> str | None:
    """Key aus Env (Vorrang, für CI/Container) oder ``~/.beehive/credentials`` (§15)."""
    env = os.environ.get("OPENROUTER_API_KEY")
    if env:
        return env.strip()
    if CREDENTIALS_PATH.exists():
        return CREDENTIALS_PATH.read_text(encoding="utf-8").strip() or None
    return None


def save_credentials(key: str) -> None:
    POLLYSORT_HOME.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_PATH.write_text(key.strip(), encoding="utf-8")
    try:
        os.chmod(CREDENTIALS_PATH, 0o600)  # best effort; auf Windows teils No-Op
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Hive-Seed (hive.toml)
# ---------------------------------------------------------------------------
def load_seed(hive: Path) -> HiveSeed:
    data = _read_toml(honig(hive) / "hive.toml")
    proj = data.get("project", {})
    return HiveSeed(
        categories=data.get("categories", list(DEFAULT_CATEGORIES)),
        responsibility=data.get("responsibility", {}),
        subrouting={str(k).strip().lower(): str(v)
                    for k, v in data.get("subrouting", {}).items()},
        threshold_assign=float(data.get("threshold", {}).get("assign", 0.75)),
        max_file_mb=int(data.get("limits", {}).get("max_file_mb", 100)),
        pollen_retention_days=int(data.get("limits", {}).get("pollen_retention_days", 30)),
        exclude=data.get("exclude", []),
        name=proj.get("name", ""),
        provider=proj.get("provider", "offline"),
        # Rückwärtskompatibel: altes auto_sort_on_start → watch="move".
        watch=proj.get("watch", "move" if proj.get("auto_sort_on_start") else "off"),
        watch_seconds=int(proj.get("watch_seconds", 10)),
        nacherfassung=bool(proj.get("nacherfassung", True)),
    )


def write_seed(hive: Path, seed: HiveSeed) -> None:
    # Kategorienamen können Leerzeichen enthalten → als quotierte TOML-Schlüssel schreiben.
    resp_lines = "\n".join(f"{_toml_val(k)} = {_toml_val(v)}"
                           for k, v in seed.responsibility.items())
    # WICHTIG: In TOML müssen bare Top-Level-Keys (categories, exclude) VOR jedem
    # [table]-Header stehen — sonst würden sie der Tabelle zugeordnet.
    content = f"""# PollySort — Projekt-Konfiguration (human-editierbar)
# Das Gedächtnis (taxonomie.toml) lernt darüber hinaus; diese Datei bleibt der Startpunkt.

# Start-Kategorien (das Gedächtnis darf später neue vorschlagen)
categories = {_toml_val(seed.categories)}

# Analog zu .gitignore: Pfad-Muster, die vom Scan ausgenommen werden
exclude = {_toml_val(seed.exclude)}

[project]
name          = {_toml_val(seed.name or hive.name)}
provider      = {_toml_val(seed.provider)}
watch         = {_toml_val(seed.watch)}          # off | notify | move
watch_seconds = {_toml_val(seed.watch_seconds)}
nacherfassung = {_toml_val(seed.nacherfassung)}   # KI verfeinert Titel/Zusammenfassung nach dem Sortieren

# Zuständigkeit ist many-to-many und liegt im Hintergrund
[responsibility]
{resp_lines}

[threshold]
assign = {seed.threshold_assign}   # >= automatisch, darunter wird extra gefragt

[limits]
max_file_mb = {seed.max_file_mb}          # groesser -> Metadaten-Eintrag + needs_review
pollen_retention_days = {seed.pollen_retention_days}
"""
    # Dynamische Unterordner je Kategorie (optional) — nur schreiben, wenn gesetzt.
    if seed.subrouting:
        sub_lines = "\n".join(f"{_toml_val(k)} = {_toml_val(v)}"
                              for k, v in seed.subrouting.items())
        content += ("\n# Dynamische Unterordner je Kategorie. Platzhalter: "
                    "{jahr}/{monat}/{tag}\n"
                    "# z. B.  \"rechnung\" = \"{jahr}/{monat}\"\n"
                    f"[subrouting]\n{sub_lines}\n")
    honig(hive).mkdir(parents=True, exist_ok=True)
    (honig(hive) / "hive.toml").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Mini-TOML-Serializer (nur die hier genutzten Typen; spart eine Abhängigkeit)
# ---------------------------------------------------------------------------
def _toml_val(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        # TOML-Basic-String: Backslash & Quote escapen (wichtig für Windows-Pfade)
        escaped = v.replace("\\", "\\\\").replace('"', '\\"')
        return '"' + escaped + '"'
    if isinstance(v, list):
        return "[" + ", ".join(_toml_val(x) for x in v) + "]"
    raise TypeError(f"Nicht serialisierbar: {v!r}")


def resolve_hive(explicit: str | None = None) -> Path:
    """Aktiven Ordner bestimmen: expliziter Pfad > zuletzt genutzter > aktuelles Verzeichnis."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    cfg = load_config()
    if cfg.hive and Path(cfg.hive).exists():
        return Path(cfg.hive).expanduser().resolve()
    return Path.cwd().resolve()


# ---------------------------------------------------------------------------
# Projekt-Registry (mehrere Bienenstöcke nebeneinander)
# ---------------------------------------------------------------------------
PROJECTS_PATH = POLLYSORT_HOME / "projects.txt"


def register_project(hive: Path) -> None:
    """Einen Stock in die globale Projektliste aufnehmen (für 'projekte')."""
    hive = hive.resolve()
    known = list_projects()
    if hive not in known:
        POLLYSORT_HOME.mkdir(parents=True, exist_ok=True)
        with PROJECTS_PATH.open("a", encoding="utf-8") as fh:
            fh.write(str(hive) + "\n")


def list_projects() -> list[Path]:
    """Bekannte, noch existierende Projekt-Ordner."""
    if not PROJECTS_PATH.exists():
        return []
    out: list[Path] = []
    for line in PROJECTS_PATH.read_text(encoding="utf-8").splitlines():
        p = Path(line.strip())
        if line.strip() and p.exists() and p not in out:
            out.append(p)
    return out


def remember_last_hive(hive: Path) -> None:
    """Zuletzt genutzten Stock global merken (nur ein kleiner Zeiger)."""
    cfg = load_config()
    cfg.hive = str(hive.resolve())
    save_config(cfg)
