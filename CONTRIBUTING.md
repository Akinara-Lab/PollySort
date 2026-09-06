# Contributing to PollySort

Thanks for taking the time. PollySort is developed by [Akinara](https://akinara.de) and
released under the Apache License 2.0. Issues and pull requests are genuinely welcome.

## The one rule that is not negotiable

**No code path may ever delete or overwrite a user's file.**

PollySort only ever *moves* files. Name collisions get a unique suffix. Deleting happens
exclusively through `papierkorb` (quarantine) followed by an explicitly confirmed `leeren`.
A dry run (`vorschau`) stays free of side effects until the user says yes.

Any change that could lose user data will be rejected, however elegant it is. If you are
unsure whether your change touches this, open an issue first and we will work it out.

## Before you open a pull request

```bash
uv venv --python 3.12
uv pip install -e ".[extract,dev]"

.venv/Scripts/python.exe -m pytest -q            # must be green
.venv/Scripts/python.exe -m ruff check src Beehive.py tests   # must be clean
```

Both run in CI across {Windows, macOS, Linux} x {Python 3.12, 3.13}. A red build will not
be merged.

## What good contributions look like

- **Match the surrounding code.** Same comment density, same naming, same idioms. The
  codebase uses German identifiers in the domain layer (bees, combs, honey) on purpose —
  keep that consistent rather than half-translating it.
- **Add a test for behaviour you change.** Especially for anything that touches the move,
  delete or persistence paths.
- **Both languages, always.** Every user-facing string goes through `i18n.t()` and needs a
  `de` *and* an `en` entry. There is a test that enforces this.
- **Never log secrets.** API keys, passwords and licence keys stay local and masked. They
  must never appear in `log.jsonl`, in the console, or in an LLM prompt. This is enforced
  by tests and it is not a style preference.
- **Errors are isolated.** A broken document or an unreachable AI provider must never
  abort a whole run. Fail that one file, log it, keep going.

## Commit messages

Short imperative subject, body explaining *why* if it is not obvious. English or German,
either is fine.

## Contributor License Agreement

PollySort follows an open-core model: the core in this repository is Apache-2.0, while
Akinara also builds commercial components on top of it. So that contributed code can be
used across both, we ask contributors to sign a CLA. The CLA bot will comment on your
first pull request with a link — it takes one click.

If you would rather not sign, we can usually still take the *idea*: open an issue
describing it and we will implement it independently.

## Reporting security problems

Please do **not** open a public issue. See [SECURITY.md](SECURITY.md).

## Code of conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
