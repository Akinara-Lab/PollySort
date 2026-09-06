## What does this change?

<!-- Briefly: what and why. Link the issue if there is one. -->

## Checklist

- [ ] `pytest -q` is green
- [ ] `ruff check src Beehive.py tests` is clean
- [ ] No code path can delete or overwrite a user file
- [ ] New user-facing strings go through `i18n.t()` and have both `de` and `en`
- [ ] No secret (API key, password, licence key) can reach a log, the console or an LLM prompt
- [ ] Behaviour I changed is covered by a test
