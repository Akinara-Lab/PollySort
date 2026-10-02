# 🐝 PollySort

> **A learning, console-based document archivist.** Point it at a folder full of loose
> files, type **`sort`** — and it files them into clean category folders, getting smarter
> with every correction.
>
> _Developed by **Akinara** · **public beta** · Apache-2.0_

PollySort watches a folder, reads each document, figures out **what it is** and **what it's
for**, assigns it to a **learning category**, and moves it into a visible category folder
("comb"). Unsure cases are collected into a quick batch review. **Nothing is ever deleted or
overwritten — only moved, with undo.** Everything the tool generates (index, memory, logs,
entries, quarantine) lives in **one hidden folder, `.honig/`**, so your directory stays clean —
only the category folders appear.

> ⚠️ **Beta.** The core is well-tested and stable, but APIs, command names and file layout may
> still change before 1.0. Your files are safe by design (move-only, never delete), but treat
> this as pre-release software.

> 🌍 **Language.** The first-run wizard asks for your language and **defaults to English**;
> German is fully equivalent (`language de`). This README uses the English command aliases; the
> original German names are shown in parentheses.
>
> Note: the *setup* is fully translated, but some runtime messages during a sort run are still
> German. Full coverage is in progress.

---

## Table of contents

- [Why PollySort](#why-pollysort)
- [Key features](#key-features)
- [Installation](#installation)
- [First run](#first-run)
- [Everyday workflow](#everyday-workflow)
- [Command reference](#command-reference)
- [How it works](#how-it-works)
- [What lives where](#what-lives-where)
- [Modes: low-power · local · cloud](#modes)
- [Learning: the Wachstafel (meta-learning)](#learning-the-wachstafel)
- [Stage 2: projects, deadlines & notifications](#stage-2-projects)
- [Licence](#licence)
- [Privacy & security](#privacy--security)
- [Development & testing](#development--testing)
- [Roadmap](#roadmap)
- [FAQ](#faq)

---

## Why PollySort

Most "auto-sorters" force a rigid folder scheme on you and break the moment your documents
don't fit. PollySort is different:

- **It adapts to you, not the other way around.** Categories are not fixed — a vector memory
  grows with every document, and the tool learns your habits from the corrections you make.
- **It respects what you already have.** During setup it looks at your loose files *and* your
  existing subfolders and proposes a structure that extends what you started, instead of
  starting from zero.
- **It is safe by construction.** There is no code path that deletes or overwrites a user
  file. Name clashes get a unique suffix; deletion only ever happens through an explicit,
  confirmed quarantine step.
- **It works without the cloud.** A free offline heuristic sorts without any network or API
  key. Add a local **Ollama** model or an **OpenRouter** key for higher quality — your choice,
  per project.
- **It stays out of your way.** One hidden `.honig/` folder holds everything generated; your
  working directory only ever shows the clean category folders.

---

## Key features

| | Feature |
|---|---|
| 🗂️ | **Content-aware sorting** — title, summary, keywords, function and category per document |
| 🧠 | **Learning memory (Hive Mind)** — kNN vector memory + a living taxonomy that grows with use |
| ❓ | **Confidence & batch review** — sure files are filed automatically, unsure ones are queued |
| 👁️ | **Real-time watch** — a `watchdog` observer sorts/announces new files the instant they land |
| 👀 | **Preview & apply** — dry-run first, then apply from cache with **no second AI calls** |
| ⚡ | **Ultra Swarm** — parallel AI analysis for large batches, free and unrestricted |
| 📁 | **Dynamic subfolders** — e.g. file invoices into `Invoices/{year}/{month}` automatically |
| 🔁 | **Learns from manual moves** — drag a file between folders, `scan` turns it into a rule |
| 🧹 | **Duplicate detection** — SHA-256 dedupe; a second run makes **zero** new AI calls |
| ↩️ | **Undo & quarantine** — move-only, unique-suffix collisions, reversible, never auto-deletes |
| 🐝 | **Stage 2 project management** — turn a category into a project with charter & deadlines |
| 🔔 | **Notifications** — optional Discord / e-mail alerts for due deadlines; `.ics` calendar sync |
| 🔌 | **Three modes** — low-power (heuristics, any PC) · local (AI via Ollama) · cloud (AI via API), switchable per project |
| 🩺 | **`doctor` health-check**, 🌍 **DE/EN UI**, 🎨 **dark/light themes**, 🛟 **abort any prompt** |
| 🔓 | **Apache-2.0** — real open source: no feature gates, no project limit, commercial use OK |

---

## Installation

**Requirement: Python 3.12+.** PollySort is a pure console tool. An isolated install via
[`pipx`](https://pipx.pypa.io) or [`uv`](https://docs.astral.sh/uv/) is recommended — it puts
the **`pollysort`** command on your PATH on Windows, macOS and Linux without you having to manage
virtual environments.

> 💡 **Two commands.** **`pollysort`** opens the interactive console (that is the one you
> want). **`pollysort-cli`** is the scripting CLI for automation — `pollysort-cli doctor`,
> `pollysort-cli scan --mode move`, and so on.

### Easiest: the installer script

The repo ships installers that **check the prerequisites** (project files present, a real
Python 3.12+ — not the Microsoft Store placeholder), pick the best available tool
(`uv` → `pipx` → `pip --user`), install PollySort including the text-extraction extra, **and
put the command on your PATH** so that afterwards you only ever type `pollysort`:

| Platform | Command |
|---|---|
| **Windows** | double-click **`install.bat`**, or `.\install.ps1` in PowerShell |
| **Linux / macOS** | **`bash install.sh`** |
| **Git-Bash on Windows** | **`bash install.sh`** |

The PATH entry is written **for your user only** — never system-wide, and no administrator
rights are needed. On Windows it goes into the user `Path` environment variable; on Linux and
macOS into the startup file your shell actually reads (`~/.zshrc`, `~/.bashrc`,
`~/.bash_profile` on macOS, or `~/.config/fish/config.fish`), inside a marked block so a second
run does not duplicate it.

Both installers accept:

- `--dry-run` — show what would happen and change nothing.
- `--no-path` — install but leave PATH alone (PowerShell: `-DryRun` / `-NoPath`).

Open a new terminal afterwards so the PATH entry takes effect — or `source` the file the
installer names.

### Manual install

```bash
# 1) Get the code
git clone https://github.com/Akinara-Lab/PollySort.git pollysort
cd pollysort

# 2) Install (recommended: with better text extraction)
pipx install ".[extract]"      # or:  uv tool install ".[extract]"

# 3) Verify & launch
pollysort-cli doctor           # health-check: Python, AI provider, DB, memory
pollysort                      # open the interactive console
```

The **`[extract]`** extra (DOCX/CSV/HTML → Markdown, MIME detection via libmagic) is
**optional** — deliberately not in the core so installs succeed everywhere. Core only:

```bash
pipx install .                 # or:  uv tool install .
```

> Without `[extract]` the tool falls back to `mimetypes` + raw text reading — it still works,
> just recognizes file types / Office formats more coarsely. PDFs are always read by the core
> (`pypdf`), which matters for **local AI (Ollama)** since it can't take file attachments.

> 🦙 **Robust local AI:** if Ollama's GPU backend crashes (driver issues), PollySort
> automatically falls back to CPU inference (`num_gpu: 0`) — slower, but it keeps working.

**Update** (after `git pull`): `pipx install --force ".[extract]"` (or `uv tool install --force`).

### Uninstalling

| Platform | Command |
|---|---|
| **Windows** | double-click **`uninstall.bat`**, or `.\uninstall.ps1` in PowerShell |
| **Linux / macOS / Git-Bash** | **`bash uninstall.sh`** |

By default this removes only the **application**: the `pollysort` and `pollysort-cli`
commands, plus the PATH entry the installer added (and only if nothing else lives in that
folder). Add **`--alles`** (PowerShell: `-Alles`) to also delete the global store
`~/.pollysort` — settings, your OpenRouter key, the project list, notification routes and
the input history. That step asks for confirmation.

**Your documents are never touched**, under any option. Neither are the hidden `.honig`
folders inside your projects: they hold the catalogue, the learned memory — and
`papierkorb/`, the quarantine, which may still contain real files you sorted out but never
purged. The uninstaller lists those folders instead, so you can decide yourself. A
deinstaller that quietly takes user data with it is data loss with a clean conscience, and
PollySort's first principle is that nothing is ever deleted.

Both scripts accept `--dry-run` to show what would happen without changing anything.

### Run without installing

From the cloned repo you can always run `python polly.py [path]`. If it's launched under an
old Python by mistake, it re-launches itself into the project's own `.venv`.

---

## First run

```bash
pollysort                    # opens the most recently used project
pollysort "C:\path\to\dir"   # opens/creates a project at this path
```

A **project** is just a folder whose documents get sorted; the loose files in it are your
inbox. PollySort does **not** assume the current directory — it remembers your projects.

On the **very first launch** a one-time setup clarifies the AI backend (it detects a local
**Ollama** and offers to store an **OpenRouter** key), then a short **3-step tutorial** appears
(**pick a folder → `preview` → `sort`**), and the wizard walks you through the project setup.
The setup also offers to download **BeeNara**, the local decider model from Hugging Face
(~370 MB). Pressing Enter means "later" — `beenara pull` (`beenara laden`) fetches it any time,
and `pollysort-cli beenara pull` does the same from a script.

**Setup order: Name → AI mode → Categories → Subfolders → Watch.** For categories there's a
**proposal mode** that looks at both your loose files *and* your existing folder structure
(existing subfolders count as categories you already use — adaptive, not rigid) and suggests a
structure. In local and cloud mode the **AI** analyzes the documents; in low-power mode a
heuristic does. Each project
stores its config in `.honig/hive.toml`, so **multiple projects run independently** side by side.

```text
🐝  PollySort
──────── First-time setup ────────
🦙  Local Ollama detected — AI can run for free & privately on your machine.
🔑  Store an OpenRouter API key? [y/N]: n

🐝  Welcome! No project yet.
  📂 Path to the project folder: C:\Users\me\Documents\office
──────── Set up project ────────
  1) Project name [office]: Law firm
  2) AI mode — how should documents be classified?
       [1] Low-power — heuristics only: instant, free, runs on any PC
       [2] Local — AI on your machine (Ollama), free & private
     Choice [2]: 2
  3) Categories — how should filing work?
       [1] Proposal — look at files & existing folders (the AI reads them)  (recommended)
       [2] Standard  ·  [3] Custom
     Choice [1]: 1
  📁  14 file(s) examined (AI analysis, 2 of them existing folders) — proposal:
       Tax 2023     ██████████ 4 · existing
       Invoices     ███████ 3
       Photos       █████ 2 · existing
       Contracts    █████ 2
       …
     Accept? [Y/n]: y
  4) New files in the inbox (check every ~10 s)?
       [1] off  ·  [2] announce only  ·  [3] sort immediately
     Choice [1]: 3
✅  'Law firm' · 6 categories · mode ollama · inbox: auto-sort

🐝 office ▸ sort
🍯  10 file(s) sorted: 3 → Invoices, 2 → Contracts, 2 → Photos, …
🎉  Cleanly sorted — nothing left behind!
```

Re-opening the same folder loads the config (no wizard). `setup` reconfigures, `projects` lists
all projects, `switch <n>` changes project.

> 🛟 **Abort anytime.** Any interactive prompt (setup, review, …) can be left cleanly by typing
> `abort` / `bye` / `exit` (German: `abbruch`) or pressing **Ctrl-C** — the action is **not**
> executed and nothing is lost.

---

## Everyday workflow

1. **Drop** loose files into your project folder.
2. **`preview`** (`v`) to see where they'd go, then confirm **"apply? [Y/n]"** — applying costs
   no extra AI calls.
3. Or **`sort`** (`s`) directly. Sure files move into category folders; unsure ones stay put.
4. **`review`** (`r`) to quickly assign the unsure ones — each answer trains the memory.
5. **`watch`** to keep the inbox monitored in real time.
6. Correct a mistake with **`assign <id> <category>`** — PollySort learns a rule from it.

---

## Command reference

`help` groups commands into three tiers: **🐝 Daily**, **🎯 Situational**, **🛠️ Pro**. Commands
below list the **English alias** first and the original **German** name in parentheses.

### 🐝 Daily

| Command | What it does |
|---|---|
| `home` (`start`) | Back to the **home screen** (banner + overview): current project (mode, inbox, open reviews, due deadlines) + all projects. Works from anywhere. |
| `sort` (`sortiere`, `s`) | File the loose documents into category folders |
| `preview` (`vorschau`, `v`) | Show the plan, then **"apply now? [Y/n]"** — applying reuses the cache, **no second AI calls** |
| `review` (`rueckfragen`, `r`) | Assign the unsure cases quickly yourself |
| `status` | What's here, what's already sorted? |
| `list [category]` (`liste`) | List sorted entries |
| `find <word>` (`suche`) | Search titles / keywords / summaries |

### 🎯 Situational

| Command | What it does |
|---|---|
| `watch` (`wache`) | Monitor the inbox in **real time** (watchdog); announce or sort new files instantly. Ctrl-C stops. |
| `sort turbo [N]` | **Ultra Swarm**: analyze many files in parallel (default 10 workers) — same result, much faster |
| `scan` (`sweep`) | Check the whole folder for manual changes (moved/changed/new/gone) and **learn from hand-moves** — free, no AI call |
| `import <folder>` (`importiere`) | Sort files from another folder into here |
| `assign <id> <cat>` (`zuordnen`) | Correct an assignment (memory learns) |
| `reanalyze <id>` (`analysiere`) | Re-analyse one entry — asks before re-filing it |
| `subfolder <cat> <pattern\|off>` (`unterordner`) | Dynamic subfolders per category, e.g. `{year}/{month}` — dated by the document's own date (e.g. invoice date), not by a due date |
| `duplicates [cleanup]` (`dubletten [aufraeumen]`) | Show detected duplicates · move them to quarantine |
| `trash <id>` / `empty` (`papierkorb` / `leeren`) | Quarantine / permanently delete (with confirmation) |
| `restore <id>` (`zurueckholen`) | Bring a file back from quarantine (into its category) |
| `undo` (`rueckflug`) | Reverse the last move |
| `charter [category]` (`wabenbau`) | Turn a category into a **project**: charter, stakeholders, deadlines |
| `calendar [notify]` (`kalender [melden]`) | Show deadlines · send due reminders via the notification routes |
| `swarm` (`schwarm`) | Overview: Queen & bees (combs, open cases, projects, deadlines) |
| `recommend [para\|johnny\|dewey]` (`empfehlung`) | Filing-strategy suggestions + dynamic hints |

### 🛠️ Pro

| Command | What it does |
|---|---|
| `new [path]` (`neu`) · `switch [n]` (`wechsel`) | Create a project · switch to another |
| `projects` (`projekte`) · `setup` | List all projects · reconfigure the current one |
| `mode <low\|local\|cloud>` (`modus`) | Low-power (heuristics) · local (Ollama) · cloud (API) for this project — the old names `offline`/`ollama`/`online` still work |
| `model [name\|list]` (`modell`) | Switch the OpenRouter model at runtime |
| `key [test\|set\|remove]` (`schluessel`) | Check / renew / remove the OpenRouter key |
| `routes [setup\|test]` (`flugrouten`) | Discord / e-mail notifications (opt-in) |
| `reflect` (`reflektiere`) · `rules [clear]` (`wachstafel [leeren]`) | Derive rules from your corrections · show/clear them |
| `memory [approve\|rebuild]` (`gedaechtnis`) | Learned categories + merge/new proposals · `rebuild` re-embeds after a model change |
| `enrich [on\|off\|now]` (`nacherfassen`) | Local mode: let the AI refine titles & summaries after sorting |
| `person <name> <cat,..>` | Set responsibility in the background |
| `doctor` | Health-check: Python, AI provider, local models, database, extraction extras, memory |
| `beenara [pull\|remove]` (`beenara [laden\|entfernen]`) | Download [BeeNara](https://huggingface.co/Kwokou/BeeNara), the local decider model (~370 MB, checksum-verified, resumes after an interruption) · remove it again. Not used for sorting yet |
| `language <de\|en>` (`sprache`, `lang`) | Switch UI language |
| `theme` (`thema`) · `view` (`ansicht`) | Dark/light mode · static view or classic log |
| `help` (`hilfe`) / `exit` | This help / leave the console |

---

## How it works

### The sorting pipeline (per file, isolated — one bad file never aborts a run)

1. **Scout / Guard** — landing check, MIME, size limit, **SHA-256**; duplicate & crash-recovery
   via the hash. The `.honig/` and category folders are **not** re-scanned. A second run over
   the same set makes **zero** new AI calls.
2. **Extractor** — a multimodal LLM call (or the heuristic in low-power mode) returns title, summary,
   keywords, function and a category. The prompt requires the model to pick **exactly one of the
   known categories**; a returned label is then **snapped** onto the known set
   (`snap_category`). Broken JSON → repair-retry → fallback model → otherwise a metadata-only
   entry flagged for review.
3. **Assign + Inspector (confidence)** — the memory (kNN) confirms or contradicts the label.
   **Confidence ≥ threshold (0.75)** → filed automatically; below → **review**.
4. **Persist & move** — the entry is written **first** (crash-recovery), then **only surely
   assigned** files move into `<Category>/[{year}/{month}/…]` (collision-safe, logged for undo).
   Unsure and error cases **stay put**, so the only loose files left are the ones needing you.
5. **Memory** — every successful assignment is embedded; category centroids grow over time.

If the AI fails repeatedly mid-run (≥ 3 in a row), the run **falls back to low-power mode**
(heuristics) for the rest instead of producing a pile of errors.

### Local mode: memory → one-token decision → review

Writing a title and summary is the slow part of an AI analysis — the category itself is a
handful of tokens. In **local mode**, PollySort therefore decides first and describes later:

1. **Memory.** The start of the document is embedded and compared with everything already
   filed. If the closest known document is very similar *and* clearly closer than any other
   category, memory decides alone — no AI call.
2. **One-token decision.** Otherwise the model picks the category by number, answering with a
   single token; the confidence comes from its token probabilities.
3. **Review**, if the model says "none of these fit" or isn't sure.

Afterwards the AI **refines titles and summaries** of the files it just filed (`enrich`,
Ctrl-C skips, the next run continues). The files are already in the right folder by then.

Measured on 70 test documents with `qwen3.5:9b` (57 unique, 13 exact duplicates):

| | per document, GPU | per document, **CPU only** | correct |
|---|---|---|---|
| before (full analysis per file) | 22.2 s | 48.7 s | 97 % |
| now | **0.21 s** | **4.0 s** | 56 of 57 |

About half of the documents were decided by memory alone. Low-power and cloud mode are
unchanged.

### Preview → apply

`preview` runs a dry-run that **fills an analysis cache** (no persisting, no moving), then asks
**"apply? [Y/n]"**. Answering yes runs the real pass **from the cache** — so applying costs
**no second AI calls**, and the preview stays side-effect-free until you confirm.

### Ultra Swarm

`sort turbo [N]` warms the expensive AI analyses **in parallel** into that same cache; the
actual filing (DB, move, memory) stays **single-threaded**, so there are no race conditions and
the result is identical to a sequential run — just much faster for big batches. Fully
included, no activation needed.

---

## What lives where

```
<your folder>/
├── Invoices/          ← visible category folders (the result)
├── Contracts/
├── Minutes/
├── note.txt           ← loose files still awaiting your go-ahead ('review')
└── .honig/            ← ONE hidden folder with everything generated:
    ├── katalog.db         · searchable index
    ├── eintraege/         · one Markdown + JSON entry per file (PKM-ready)
    ├── gedaechtnis.db     · the learning category memory
    ├── taxonomie.toml     · learned categories + responsibilities
    ├── korrekturen.jsonl  · feedback from your assignments
    ├── wachstafel.md      · learned, human-readable project rules
    ├── papierkorb/        · quarantine (never auto-emptied)
    ├── journal.md         · what happened when
    └── log.jsonl          · structured log (metadata only, never contents)
```

The Markdown entries start with YAML front-matter and open straight in Obsidian, Logseq or
Notion. Global settings (last project, credentials, project registry) live under
`~/.pollysort/`, outside your working folders (relocatable via `POLLYSORT_HOME`); a downloaded
BeeNara sits in `~/.pollysort/modelle/BeeNara/` (`HF_ENDPOINT` points the download at a mirror). An old
`~/.beehive/` from earlier versions is migrated automatically — copied, never deleted.

> The hidden folder is named `.honig` ("honey") and categories are internally called "combs"
> (`Waben`) — part of the tool's bee theme. You never need to touch these names.

---

## Modes

One interface, three modes — chosen per project (`mode low | local | cloud`):

- **Low-power** — pure heuristics from filename, text start, file type and category names
  (self-named/discovered categories work without hard-coded rules). Instant, free, no network,
  no model — runs on any PC.
- **Local** — AI on your own machine via Ollama (free & private); automatic CPU fallback if
  the GPU backend crashes. Decides in **three stages** (see *How it works*) — fast enough for a
  laptop without a GPU.
- **Cloud** — AI via an API (OpenRouter, multimodal, best quality); the key is stored globally.

Switching is config, not code. Without a key, cloud mode degrades cleanly to low-power mode.
The old mode names (`offline`, `ollama`, `online`) keep working.

---

## Learning: the Wachstafel

When you correct an assignment (`assign <id> <category>`) — or when `scan` notices you moved a
file **from one category folder to another by hand** — the Queen studies the corrections and
**inscribes rules in plain language** into `.honig/wachstafel.md` (e.g. *"telekom → Invoices"*).
`reflect` shows the derived rules and only writes them after you confirm.

On the next `sort`, those rules are applied — online they're injected into the LLM prompt as
"learned project rules", offline they're applied directly. So each project adapts specifically
to you.

> 🔒 **Safe & project-scoped:** **no code is ever generated** — learning happens purely through
> the `wachstafel.md` text file. Rules apply **only** within their project and never leak into
> another. `rules` shows them, `rules clear` discards them.

---

## Stage 2: projects

`sort` brings loose files into combs (categories). **`wabenbau`** turns a comb into a real
project:

- Generates a **charter** (`Bienenstock.md`) in the category folder: goal, status, stakeholders,
  contents, open tasks and deadlines; missing info is asked for interactively.
- Records deadlines in the swarm calendar and writes a real **`.ics` file** you can subscribe to
  in Apple Calendar, Outlook or Google.
- **Notification routes (opt-in):** via `routes setup` you can give the guard bees **Discord**
  (bot token + channel) and/or **e-mail** (SMTP presets for Gmail/Outlook or custom). When a
  deadline is due they actually notify you (`calendar notify`, or automatically in the `watch`
  service; anti-spam included).

> 🔒 **Credential seal:** notification credentials live **only** locally in
> `~/.pollysort/flugrouten.toml` (chmod 600, env override possible), **never** in the project and
> **never** in an LLM prompt. Discord/SMTP calls run completely independently of the AI;
> sensitive fields are masked in `log.jsonl`. No notifications are sent without your setup.

---

## Licence

PollySort is licensed under the **[Apache License 2.0](LICENSE)** — real, OSI-approved open
source.

- ✅ **Everything is included.** No project limit, no feature behind a gate, no licence key.
  **Ultra Swarm** runs free.
- ✅ **Commercial use is allowed** — your own data and paid client work alike.
- ✅ **Fork it, change it, ship it.**
- ✅ **Patent grant included** (Apache-2.0 §3) — that is why Apache rather than MIT.

What the licence does *not* cover is the name and logo: "PollySort" and "Akinara" are
trademarks of Akinara. See **[`TRADEMARK.md`](TRADEMARK.md)** for what needs no permission —
short version: do anything you like with the code, but please fork under your own name.

**So how is this funded?** Akinara is building a commercial **web cockpit** for teams on top of
it (project management in the browser, multiple users, server deployment) — a separate package
that this repository does not need. The local terminal tool here stays complete and free.

Contributions welcome: **[`CONTRIBUTING.md`](CONTRIBUTING.md)** ·
Report vulnerabilities privately: **[`SECURITY.md`](SECURITY.md)**.

---

## Privacy & security

- **Low-power / local:** no document content ever leaves your machine.
- **Cloud:** document content is sent for analysis (shown at onboarding) — exclude
  confidential files via `.beeignore`/`exclude` or use low-power or local mode.
- **No document content is ever logged** (`log.jsonl` holds metadata only).
- **Move-only guarantee:** no code path deletes or overwrites a user file; deletion happens only
  through the confirmed `trash` → `empty` flow.
- API keys and credentials are stored locally only and never enter an AI prompt.

---

## Development & testing

```bash
# editable install with test & lint tools
uv pip install -e ".[extract,dev]"    # or: python -m venv .venv && pip install -e ".[extract,dev]"

pytest -q
ruff check src polly.py tests
```

Stack: Python ≥ 3.12 · `cmd` REPL + `pyreadline3` · `rich` output · `pydantic v2` models ·
`SQLAlchemy 2 Core`/SQLite index · `httpx` (OpenRouter/Ollama) · `watchdog` · `pypdf` (core) +
`markitdown` (extra) · `pytest` + `ruff`.

For contributors and AI assistants, `Pollysort_projektbrief.md` is an onboarding brief
(architecture, process order, design intentions), `TODO.md` is the roadmap, and `CHANGELOG.md`
tracks releases.

---

## Roadmap

Planned for upcoming releases (see `TODO.md`):

- **Wabenbau contacts & milestones** — enter one or more e-mail addresses when building a
  project so the guard bees mail deadline/milestone reminders (multiple milestones per project).
- **Project from the parent folder** — create a project directly from the top-level files
  (two levels: an overarching project + category sub-projects), not only from a sorted category.
- **Full English UI** — English command names shown in help and all runtime messages in EN mode
  (English aliases already work today).
- **An open model of our own** for local mode — small enough for low-power PCs, trained on
  open synthetic data (research phase).

---

## FAQ

**Does it delete my files?**
No. It only moves them, with collision-safe names and undo. Deletion is a separate, confirmed
quarantine step.

**Do I need an API key or the internet?**
No — low-power mode works with no key, no network and no model. Local mode (Ollama) and
cloud mode (OpenRouter) are optional upgrades for higher quality.

**What's the bee theme about (`.honig`, "combs", "the Queen")?**
Flavor. Internally the tool uses a beehive metaphor; it doesn't affect how you use it.

---

_PollySort — Developed by Akinara · Apache-2.0 · public beta. Feedback and issues welcome._
