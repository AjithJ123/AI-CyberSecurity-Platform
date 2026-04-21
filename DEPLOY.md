# Deploying Helix to Vercel

The HTML / JS / CSS live at the repo **root** so Vercel serves them
automatically — no build step, no `outputDirectory`, no framework preset.
The FastAPI backend runs as a single Python serverless function at
`api/index.py` and reuses the server code under `backend/` (bundled with the
function via `vercel.json → includeFiles`).

## One-time setup

1. Push the repo to GitHub (already done — [AjithJ123/AI-CyberSecurity-Platform](https://github.com/AjithJ123/AI-CyberSecurity-Platform)).
2. Go to <https://vercel.com/new> and **Import** the GitHub repo.
3. On the Vercel import screen leave every field at its **default** — the
   settings come from `vercel.json`.
4. Add the environment variables below (Project → Settings → Environment
   Variables → Add for **Production, Preview, Development**):

   | Name | Value | Required? |
   |---|---|---|
   | `GROQ_API_KEY` | your Groq key (starts `gsk_…`) | **yes** — every AI tool |
   | `GOOGLE_SAFE_BROWSING_API_KEY` | your GCP Safe Browsing key | for Scanner |
   | `VIRUSTOTAL_API_KEY` | your VT API key | for Scanner |
   | `PHISHTANK_API_KEY` | only if you have one | optional |
   | `CORS_ORIGINS` | `https://<your-vercel-domain>.vercel.app` | only if you later add a separate frontend origin |

5. Click **Deploy**.

Vercel will install `api/requirements.txt`, package the `backend/` folder
alongside the function (configured in `vercel.json → includeFiles`), and serve
everything in `frontend/` as static assets.

## How requests flow

| URL | Served by |
|---|---|
| `https://your-app.vercel.app/` | `frontend/index.html` |
| `https://your-app.vercel.app/scanner.html` | `frontend/scanner.html` |
| `https://your-app.vercel.app/assets/js/*.js` | `frontend/assets/js/*.js` |
| `https://your-app.vercel.app/api/v1/check/url` | rewritten to `api/index.py` → FastAPI router |

## Local development

```bash
# Backend (FastAPI on :8000)
cd backend
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
uvicorn app.main:app --reload --port 8000

# Frontend (static files served from the repo root on :5173)
cd ..
npx serve . -l 5173
```

The frontend [API client](frontend/assets/js/api.js) auto-detects:

* Local (`localhost` / `127.0.0.1` on port ≠ 8000) → `http://127.0.0.1:8000/api/v1`
* Production (any other host) → same-origin `/api/v1`

## Known limitations on Vercel

* **Rate limiting is best-effort.** `slowapi` uses in-process memory so limits
  apply *per function instance*, not per user across the fleet. Good enough to
  stop obvious abuse. For real multi-tenant rate limiting, swap to
  [Upstash Redis](https://upstash.com/) and point `slowapi` at it.
* **Cold starts are ~1–3s.** The first request after idle time pays the Python
  + FastAPI import cost. Subsequent requests run in ~50–300ms plus the Groq
  latency.
* **30s function timeout** (set in `vercel.json → maxDuration`). All Helix
  endpoints finish well under this.
* **50 MB zipped function size.** We're comfortably under — the full Python
  dep tree weighs ~12 MB zipped.

## Troubleshooting

### `503 Service Unavailable` from AI tools

Check that `GROQ_API_KEY` is set in Vercel. Under Project → Settings →
Environment Variables, tick all three environments (Production, Preview,
Development) or the key won't show up on preview URLs.

### `500 Internal Server Error` on any `/api/*` route

Open the deployment's **Logs** tab in Vercel. The traceback is printed there.
Most common cause: missing env var.

### Frontend calls still go to `http://127.0.0.1:8000`

That means you're visiting a local file (`file://`). The auto-detector in
`api.js` requires the page to be served from `http(s)://`. Use `npx serve` or
deploy.

### You want a custom domain

Vercel → Project → Settings → Domains → Add. Then (optional) update
`CORS_ORIGINS` in env vars so the backend still trusts it.
