# CLAUDE.md — PhishGuard AI (Project Root)

This file gives AI coding assistants (Claude, Copilot, Cursor, etc.) the context they need to work on this project. Read this first before editing any code.

---

## 1. Project Summary

**PhishGuard AI** is a web tool that checks URLs and email content for phishing indicators and returns a clear verdict (Safe / Suspicious / Dangerous) with human-readable reasons.

**Core principle: be useful to non-technical users.** Every output should explain *why*, not just *what*.

---

## 2. Repository Layout

```
phishguard/
├── backend/         # Python + FastAPI API
│   └── CLAUDE.md    # Python-specific rules
├── frontend/        # HTML + JS + Tailwind
│   └── CLAUDE.md    # Frontend-specific rules
├── docs/            # Additional docs
├── .github/         # CI/CD workflows
├── .env.example     # Template for env vars
└── CLAUDE.md        # This file
```

When working inside `backend/` or `frontend/`, **also read the CLAUDE.md in that folder** — it overrides anything here.

---

## 3. Tech Stack (Quick Reference)

| Layer | Choice |
|-------|--------|
| Backend | Python 3.11+, FastAPI, httpx, Pydantic |
| Frontend | HTML5, vanilla JS (ES modules), Tailwind CSS |
| Database | PostgreSQL (via Supabase) — only for rate limiting in v1 |
| External APIs | Google Safe Browsing, VirusTotal, PhishTank, WHOIS, Anthropic Claude API |
| Hosting | Railway/Render (backend), Vercel/Netlify (frontend) |
| CI | GitHub Actions |

---

## 4. Cross-Cutting Rules (apply everywhere)

### 4.1 Security
- **Never commit secrets.** API keys, tokens, DB URLs go in `.env`, never in code.
- **Never log user-submitted email content.** It may contain personal data.
- **Validate every external input.** URLs, email text, headers — all of it.
- **Rate-limit every public endpoint.** No exceptions.

### 4.2 Privacy
- We do not store submitted URLs or email content by default.
- Only hashed IPs are stored, and only for rate-limit counters (24h TTL).
- If a feature needs persistence, flag it in the PR description.

### 4.3 Clarity over cleverness
- Prefer boring, readable code over clever one-liners.
- Give variables descriptive names. `url_age_days` beats `uad`.
- Comments explain *why*, not *what*. The code shows the what.

### 4.4 Error messages
- User-facing errors must be plain English, not stack traces.
- Log the technical detail; show the user something like "We couldn't check that URL right now. Please try again."

### 4.5 Testing
- Every new endpoint needs at least one happy-path test and one error-path test.
- Every detection rule needs a positive and negative test case.

---

## 5. How to Run Locally

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in API keys
uvicorn app.main:app --reload

# Frontend
cd frontend
# Just open index.html in a browser, or:
npx serve .
```

---

## 6. Git and PR Rules

- Branch naming: `feat/`, `fix/`, `docs/`, `chore/` prefix. Example: `feat/url-checker-whois`.
- Commit messages: short imperative summary. "Add WHOIS domain-age check" not "Added stuff".
- PRs describe *what changed* and *why*, and list any new env vars or dependencies.

---

## 7. What NOT to Do

- Do not add new external API dependencies without updating this doc and `.env.example`.
- Do not bypass rate limiting "just for testing" — use the test fixtures.
- Do not reproduce email content in logs, error messages, or analytics events.
- Do not silently change scoring weights — scoring changes need a PR review.
- Do not add heavy frontend frameworks (React, Vue) until v1.5 — keep the MVP lean.

---

## 8. When in Doubt

1. Check the CLAUDE.md in the subdirectory you're working in.
2. Check `docs/` for deeper context.
3. Ask before adding a new dependency, a new env var, or a new external API call.
