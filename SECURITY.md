# Security Policy

## Reporting a vulnerability

Please do **not** open a public issue.

Use GitHub's private reporting instead:
[**Report a vulnerability**](https://github.com/Akinara-Lab/PollySort/security/advisories/new).
Only the maintainers can see it.

Please include: what you found, how to reproduce it, which version (`pollysort doctor` prints
it), and what you think the impact is.

We aim to acknowledge within a few working days and to keep you updated while we work on a
fix. If you would like credit in the advisory, say so — we are happy to give it.

## Supported versions

PollySort is in beta. Only the latest release on `main` receives security fixes.

| Version | Supported |
|---|---|
| 0.4.x (beta) | ✅ |
| earlier | ❌ |

## What we consider a vulnerability

PollySort runs locally on your own machine and handles your own documents. The things that
matter most to us:

- **Data loss.** Any path where a user file is deleted or overwritten. PollySort only ever
  moves files — a bug that breaks this is treated as a security issue, not a normal bug.
- **Secret leakage.** API keys, SMTP or Discord credentials, or licence keys appearing in
  `log.jsonl`, in the console, in an LLM prompt, or in a file inside the project folder.
  These are supposed to stay in `~/.beehive/` (chmod 600), masked wherever they surface.
- **Unintended data egress.** Document content leaving the machine in `offline` or `ollama`
  mode. In those modes nothing may be sent anywhere. Only `openrouter` mode transmits
  content for analysis, and only after the user has chosen it.
- **Path traversal.** A crafted filename, category or subfolder pattern that causes writes
  outside the project folder.
- **Code execution** from parsing an untrusted document.

## What is out of scope

- Vulnerabilities in third-party AI providers (OpenRouter, Ollama) — report those to them.
- Issues that require an attacker to already have write access to your `~/.beehive/`
  directory or to the project folder.
- The fact that `openrouter` mode sends document content to a third party. That is the
  documented purpose of the mode, disclosed during setup, and `offline`/`ollama` exist
  precisely for confidential material.

## Our side of the deal

- Secrets live only in `~/.beehive/` with restrictive permissions, never in the project
  folder, never in a repository, never in an LLM prompt.
- `log.jsonl` contains metadata only — never document content.
- No key or secret is baked into the source or the published wheel.
