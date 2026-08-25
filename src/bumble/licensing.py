"""Fair-Code-Lizenzierung (PollySort) — lokale Verwaltung, keine Cloud im Normalbetrieb.

Modell (siehe LICENSE-KONZEPT.md): Personal/Free ist bis **5 Projekte** frei; darüber bzw.
für zahlende Kundenprojekte greift eine Jahreslizenz (Freelancer/Agency). Ultra Swarm ist
ein lizenzpflichtiges Leistungs-Feature.

🔒 Wachssiegel: Der Lizenzschlüssel wird NIE in Logs oder LLM-Prompts geschrieben. Die
Aktivierung legt ein lokales Zertifikat (`~/.beehive/license.json`) ab, sodass das Tool
offline läuft. Die Online-Validierung gegen den Merchant of Record (Lemon Squeezy/Gumroad)
ist als klar markierter Platzhalter angelegt — hier wird später der echte API-Call verdrahtet.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime

from . import config

FREE_PROJECT_LIMIT = 5
_LICENSE_PATH = config.BEEHIVE_HOME / "license.json"

# Grobes Schlüsselformat (Platzhalter): 4 Blöcke à 4 alphanumerische Zeichen, per '-' getrennt.
_KEY_RE = re.compile(r"^[A-Za-z0-9]{4}(-[A-Za-z0-9]{4}){3}$")

# 🔑 Master-/Entwickler-Schlüssel: schaltet ALLE Features frei (Tier „developer").
# 🔒 BEWUSST LEER im Code — ein hier hinterlegter Schlüssel würde mit dem Repo/Wheel
# ausgeliefert und wäre ein unwiderrufliches Backdoor-Geheimnis. Für die eigene
# Entwicklung optional per Umgebungsvariable POLLYSORT_MASTER_KEY=<key[,key…]> setzen
# (bleibt lokal, nie im Repo). Einfacher/datei-los: POLLYSORT_DEV_LICENSE=1 (siehe unten).
# Vergleich case-insensitiv.
_MASTER_KEYS = {
    k.strip().upper()
    for k in os.environ.get("POLLYSORT_MASTER_KEY", "").split(",")
    if k.strip()
}

# Env-Variablen, die den Dev-Modus ohne Datei einschalten (truthy = an).
# PollySort ist der aktuelle Name; die alten Varianten bleiben als Alias erhalten.
_DEV_ENV_VARS = ("POLLYSORT_DEV_LICENSE", "BUMBLENARA_DEV_LICENSE", "BUMBLE_DEV_LICENSE")

_TIER_LABEL = {
    "personal": "Personal/Free (bis 5 Projekte, keine Kundenprojekte)",
    "freelancer": "Freelancer & Commercial (1 Platz)",
    "agency": "Agency & Enterprise (Multi-Seat)",
    "developer": "Developer/Master (Entwicklung — alle Features frei)",
}


def _dev_env() -> bool:
    """Entwickler-Modus per Umgebungsvariable (schaltet ohne Datei alles frei)."""
    return any(str(os.environ.get(v, "")).strip() not in ("", "0", "false", "False")
               for v in _DEV_ENV_VARS)


def _mask(key: str) -> str:
    key = key.strip()
    return f"{key[:4]}…{key[-2:]}" if len(key) >= 6 else "****"


def load_license() -> dict | None:
    """Lokales Lizenz-Zertifikat lesen (oder None). Nie den Klarschlüssel zurückgeben."""
    try:
        if _LICENSE_PATH.exists():
            data = json.loads(_LICENSE_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None
    return None


def tier() -> str:
    if _dev_env():
        return "developer"
    lic = load_license()
    t = (lic or {}).get("tier", "personal")
    return t if t in _TIER_LABEL else "personal"


def is_licensed() -> bool:
    """Gibt es eine gültige (nicht abgelaufene) bezahlte Lizenz (oder Dev-Modus)?"""
    if _dev_env():
        return True
    lic = load_license()
    if not lic or lic.get("tier", "personal") == "personal":
        return False
    expires = lic.get("expires")
    if expires:
        try:
            if datetime.fromisoformat(expires) < datetime.now(UTC):
                return False
        except ValueError:
            pass
    return True


def ultra_swarm_allowed() -> bool:
    """Ultra Swarm ist ein lizenzpflichtiges Leistungs-Feature."""
    return is_licensed()


def project_count() -> int:
    try:
        return len(config.list_projects())
    except Exception:
        return 0


def free_limit_reached() -> bool:
    """Freie Stufe ausgeschöpft (≥ 5 Projekte) und keine bezahlte Lizenz aktiv?"""
    return project_count() >= FREE_PROJECT_LIMIT and not is_licensed()


def _verify_remote(key: str) -> tuple[bool, str, str]:
    """PLATZHALTER für die Online-Validierung beim Merchant of Record.

    Später: ein einziger HTTPS-Call an die License-API von Lemon Squeezy/Gumroad
    (Key → gültig? Tarif? Ablaufdatum?). Bis dahin akzeptieren wir ein wohlgeformtes
    Schlüsselformat lokal und leiten den Tarif aus dem Präfix ab. Gibt (ok, tier, grund).
    """
    k = key.strip()
    # Master-/Entwickler-Schlüssel: schaltet alles frei (nur für die eigene Entwicklung).
    if k.upper() in _MASTER_KEYS:
        return True, "developer", "Master-Schlüssel erkannt — alle Features frei (Dev)"
    if not _KEY_RE.match(k):
        return False, "", "ungültiges Schlüsselformat (erwartet XXXX-XXXX-XXXX-XXXX)"
    prefix = k[:1].upper()
    tarif = "agency" if prefix in ("A", "E") else "freelancer"
    return True, tarif, "akzeptiert (lokale Prüfung — Online-Validierung folgt)"


def activate(key: str) -> tuple[bool, str]:
    """Einen Schlüssel aktivieren und ein lokales Zertifikat ablegen. Gibt (ok, meldung).

    Der Klarschlüssel wird NUR maskiert gespeichert (kein Leak in Logs/Prompts).
    """
    ok, tarif, grund = _verify_remote(key)
    if not ok:
        return False, grund
    cert = {
        "tier": tarif,
        "key_masked": _mask(key),
        "activated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "expires": None,          # später aus der License-API (Jahreslizenz)
    }
    config.BEEHIVE_HOME.mkdir(parents=True, exist_ok=True)
    _LICENSE_PATH.write_text(json.dumps(cert, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        import os
        os.chmod(_LICENSE_PATH, 0o600)      # best effort (wie Credentials)
    except OSError:
        pass
    return True, f"{_TIER_LABEL[tarif]} aktiviert"


def deactivate() -> bool:
    if _LICENSE_PATH.exists():
        _LICENSE_PATH.unlink()
        return True
    return False


def status_line() -> str:
    """Einzeiler für `doctor`/`lizenz`: Tarif + Projektauslastung."""
    n = project_count()
    if is_licensed():
        return f"{_TIER_LABEL[tier()]} · {n} Projekt(e)"
    rest = max(0, FREE_PROJECT_LIMIT - n)
    return (f"{_TIER_LABEL['personal']} · {n}/{FREE_PROJECT_LIMIT} genutzt"
            + (f", {rest} frei" if rest else " — Limit erreicht"))
