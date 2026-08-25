# 🐝 BumbleNara — Lizenzkonzept (Fair-Code, Entwurf)

> **Status: ENTWURF.** Dieses Dokument beschreibt das geplante Lizenzmodell von
> BumbleNara (Developed by Akinara). Es ist noch kein rechtsverbindlicher Lizenztext —
> der finale englische `LICENSE.md`-Text folgt nach juristischer Prüfung.
> Preise stehen bewusst nicht hier; sie werden auf der Produktseite veröffentlicht.

---

## Grundidee: Fair-Code

BumbleNara ist **Fair-Code** (Vorbild: „Sustainable Use License", wie sie z. B. n8n
nutzt) — kein klassisches Open Source, aber auch kein Blackbox-Produkt:

- **Der Quellcode ist öffentlich einsehbar.** Jeder kann ihn lesen, prüfen, lernen,
  Issues und Pull Requests beisteuern.
- **Private und interne Nutzung ist frei.** Wer seine eigenen Dokumente sortiert,
  zahlt nichts.
- **Wer mit BumbleNara Geld verdient, beteiligt das Projekt.** Kommerzielle Nutzung
  für zahlende Kunden erfordert eine Lizenz — das finanziert Weiterentwicklung,
  Server und Support nachhaltig.

## Die drei Stufen

### 1) Personal & Internal Use — kostenlos
Für Privatpersonen sowie interne Nutzung (eigene Daten, eigenes Team-Archiv):

- ✅ Nutzung für **bis zu 5 eigene, interne oder private Projekte**.
- ✅ Alle Kern-Funktionen (Sortieren, Lernen/Wachstafel, Projekte, Kalender).
- ❌ **Keine Nutzung für kommerzielle Kundenprojekte** (Sortieren/Verwalten von
  Daten Dritter gegen Entgelt).

### 2) Freelancer & Commercial License — Jahreslizenz, 1 Arbeitsplatz
Pflicht, sobald **eine** der beiden Grenzen überschritten wird:

- ab dem **6. eigenen Projekt**, oder
- sobald BumbleNara verwendet wird, um **Daten für zahlende Kunden** zu sortieren.

Enthalten:

- ✅ 1 Arbeitsplatz / 1 Entwickler:in.
- ✅ Nag-freier Modus.
- ✅ Volle **Offline-Lizenz-Validierung** (lokal signiertes Zertifikat — das Tool
  telefoniert im Normalbetrieb nicht nach Hause).
- ✅ Lizenzpflichtige Leistungs-Features (z. B. **Ultra Swarm Mode**, parallele
  Massenverarbeitung).

### 3) Agency & Enterprise License — Jahreslizenz, Multi-Seat
Für Agenturen und IT-Dienstleister im regulären Workflow:

- ✅ Team-Lizenz (z. B. bis zu 5 Arbeitsplätze/Keys; größere Kontingente auf Anfrage).
- ✅ Unbegrenzt viele Kundenprojekte, volle kommerzielle Nutzung.
- ✅ Alles aus Stufe 2.

## Was IMMER gilt (alle Stufen)

- 🔒 **Wachssiegel:** API-Keys, Passwörter und Lizenzschlüssel bleiben lokal, landen
  nie in Logs und nie in KI-Prompts. Offline verlässt kein Dokumentinhalt den Rechner.
- 🛡️ **Nie löschen, nie überschreiben:** BumbleNara verschiebt nur; endgültiges
  Löschen erfordert immer eine explizite, bestätigte Nutzeraktion.
- 📦 **Deine Daten gehören dir:** Index und Einträge liegen als SQLite/Markdown/JSON
  im Projektordner — jederzeit ohne das Tool lesbar.
- ⏳ **Lizenz-Ablauf sperrt keine Daten:** Läuft eine Lizenz aus, bleiben alle bereits
  sortierten Bestände und Kernfunktionen für Bestandsprojekte nutzbar (Fair-Code,
  kein Ransom-Modell); nur lizenzpflichtige Features und neue Projekte jenseits der
  Freigrenze erfordern eine Verlängerung.

## Verbote (alle Stufen)

- ❌ BumbleNara selbst (oder abgeleitete Versionen) als kommerzielles Produkt/SaaS
  anbieten oder weiterverkaufen.
- ❌ Lizenz-Mechanismen entfernen oder umgehen.
- ❌ Branding („BumbleNara", „Developed by Akinara") entfernen und als Eigenleistung
  ausgeben.

## Umsetzung im Tool (geplant, siehe TODO Phase 6)

- Lokaler Projektzähler: Stufe 1 endet nach 5 Projekten — das Tool weist freundlich
  auf die Lizenzpflicht hin.
- `bumblenara --activate <KEY>`: einmalige Online-Validierung (Merchant of Record),
  danach lokal signiertes Zertifikat für den Offline-Betrieb.
- `lizenz`: zeigt Stufe, Projekte und Ablaufdatum.

---

_Entwurf v0.1 · 2026-07-14 · Feedback willkommen — Ziel ist ein Modell, das für
Privatnutzer großzügig und für kommerzielle Nutzer fair ist._
