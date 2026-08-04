# Security Policy

## Supported Versions

GraphCoder is currently in early development (v0.x). Security fixes will be
backported to the latest minor release when applicable.

| Version | Supported          |
|---------|--------------------|
| 0.2.x   | ✅ Yes             |
| < 0.2   | ❌ No              |

---

## Reporting a Vulnerability

If you discover a security vulnerability in GraphCoder, **please do NOT open
a public GitHub issue.** Instead, report it privately so we can fix it before
disclosure.

### How to Report

1. Send an email to **dajucoder@users.noreply.github.com** (or open a
   [private security advisory](https://github.com/Dajucoder/GraphCoder/security/advisories/new)
   on GitHub)
2. Include:
   - A description of the vulnerability
   - Steps to reproduce (if applicable)
   - The affected version(s)
   - Your contact information (optional)

### What to Expect

- **Acknowledgment:** within 48 hours
- **Initial assessment:** within 7 days
- **Fix timeline:** depends on severity, typically within 30 days
- **Credit:** you will be credited in the security advisory (unless you prefer anonymity)

---

## Security Considerations for Users

### API Keys

- **Never** commit `.env` or any file containing API keys to version control
- Use environment variables or a secrets manager
- Rotate keys regularly, especially if a key is exposed

### Untrusted Input

GraphCoder processes user-provided requirements and generates code. **Do NOT**
feed untrusted or sensitive input (PII, proprietary code, credentials) into
GraphCoder unless you understand the implications:

- User input is sent to the configured LLM provider
- Generated code may contain LLM-introduced artifacts
- No sandboxing is currently implemented

### LLM Provider Security

- Review your LLM provider's data handling and retention policies
- Consider using a local or self-hosted LLM for sensitive workloads
- Enable API key restrictions (IP allowlists, rate limits) where possible

---

## Known Limitations (v0.x)

| Area | Status |
|------|--------|
| Input sanitization | ⚠️ Minimal — user input is passed directly to prompts |
| Output sandboxing | ⚠️ None — generated code is not executed in isolation |
| Secret scanning | ⚠️ Not implemented |
| Dependency pinning | ⚠️ Loose — see `requirements.txt` |
| Authentication/Authorization | ⚠️ Not applicable (local CLI only) |

These will be addressed in future releases as the project matures.
