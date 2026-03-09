# Security Policy

## Supported Versions

Only the latest release on the `main` branch receives security fixes. Older releases are not patched.

| Version | Supported |
|---------|-----------|
| Latest (`main`) | ✅ |
| Older releases | ❌ |

---

## Reporting a Vulnerability

**Please do not report security vulnerabilities via public GitHub issues.**

If you discover a vulnerability, report it privately using one of the following methods:

1. **GitHub Private Security Advisory (preferred):** Open a private advisory at  
   [https://github.com/SeamusMullan/Jinkies/security/advisories/new](https://github.com/SeamusMullan/Jinkies/security/advisories/new)

2. **Direct message:** Contact the maintainer privately via a GitHub direct message.

### What to include

To help us triage and reproduce the issue quickly, please include:

- A clear description of the vulnerability and its potential impact
- Steps to reproduce (proof-of-concept code or configuration if applicable)
- The version or commit SHA you tested against
- Any relevant logs or screenshots

---

## Response Timeline

| Stage | Target timeframe |
|-------|-----------------|
| Acknowledgement | Within **3 business days** of receipt |
| Initial triage / severity assessment | Within **7 days** |
| Fix or mitigation published | Within **90 days** (critical issues prioritised) |
| Public disclosure | Coordinated with the reporter after a fix is available |

If a fix requires more time, we will notify you and agree on an extended timeline before any public disclosure.

---

## Known Security Limitations

The following limitations are known and are being tracked for future improvement. You do not need to report these again, but improvements and patches are welcome via the standard pull-request process once a private advisory has been opened.

| Issue | Description |
|-------|-------------|
| **Plaintext credential storage** | Feed credentials (username/password) are stored unencrypted in `config.json`. Avoid storing sensitive credentials until this is resolved. |
| **SSRF (Server-Side Request Forgery)** | Feed URLs are fetched without restricting private/internal address ranges. Do not run Jinkies on a network where the polling host can reach sensitive internal services. |
| **XXE (XML External Entity injection)** | The XML parser used for feed parsing may process external entities. Avoid subscribing to untrusted feed URLs from unknown sources. |

---

## Scope

Reports are in scope for:

- The Jinkies Python application (`src/`, `main.py`)
- Feed polling and parsing logic
- Credential handling and configuration storage
- Desktop notification and audio components

Out-of-scope:

- Third-party libraries (report upstream to those projects)
- Vulnerabilities requiring physical access to the machine
- Social-engineering attacks

---

## Disclosure Policy

We follow a **coordinated disclosure** model. We ask that you:

1. Give us a reasonable amount of time to address the issue before any public disclosure.
2. Make a good-faith effort to avoid privacy violations, data destruction, or service interruption during your research.
3. Not disclose the vulnerability to others until a fix has been released.

In return, we will:

- Acknowledge your report promptly
- Keep you informed of progress
- Credit you in the security advisory (unless you prefer to remain anonymous)
