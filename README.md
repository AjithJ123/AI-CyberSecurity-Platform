# Helix — a suite of AI tools

Helix is a small, focused web application that hosts several AI-powered utilities behind
one UI. Every tool returns structured, explained results — no black boxes.

## Tools

| Tool | Endpoint | What it does |
|---|---|---|
| **Threat Scanner** | `POST /api/v1/check/url`, `/check/email`, `/check/email-address` | URL, email address, and email body phishing detection using Google Safe Browsing, VirusTotal, PhishTank, WHOIS, URL-heuristics (punycode, shorteners), and AI analysis. |
| **Writing Assistant** | `POST /api/v1/writing/rewrite` | Paste a draft, get a cleaner rewrite in one of 4 tones (natural / professional / concise / friendly). |
| **Code Reviewer** | `POST /api/v1/code/review` | Paste a snippet, get a focused review: bugs, security, readability, style, with an overall quality score. |
| **Image Analyzer** | `POST /api/v1/image/analyze` | Upload an image, get a description, OCR, and an AI-generated likelihood score. |
| **Data Summarizer** | `POST /api/v1/data/summarize` | Paste a CSV/TSV, get a one-line story, highlights, outliers, and per-column stats. |
| **Translator+** | `POST /api/v1/translate` | Context-aware translation that preserves tone, idioms, and intent. |

## Stack

- **Backend:** Python 3.11+, FastAPI, httpx, Pydantic v2, slowapi (rate limiting).
- **Frontend:** HTML5, vanilla ES modules, Tailwind (Play CDN), plain CSS tokens,
  Three.js for the hero animation, Canvas 2D for the text scenes.
- **AI:** Groq (Llama 3.1 8B for text tools; Llama 4 Scout for vision).
- **Threat intelligence:** Google Safe Browsing, VirusTotal, PhishTank.

## Running locally

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # or .venv/Scripts/activate on Windows
pip install -r requirements.txt
cp .env.example .env                                # fill in API keys
uvicorn app.main:app --reload --port 8000

# Frontend (static files served from the repo root)
cd ..
npx serve . -l 5173
```

Then open http://localhost:5173.

## Project layout

```
AI-CyberSecurity/
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI app
│   │   ├── config.py                 # pydantic-settings (reads backend/.env)
│   │   ├── rate_limit.py             # shared slowapi limiter
│   │   ├── api/v1/                   # one file per endpoint group
│   │   ├── ai/                       # one file per model-backed tool
│   │   ├── checkers/                 # URL/email heuristic modules
│   │   ├── models/schemas.py         # pydantic request/response models
│   │   ├── scoring/aggregator.py     # signal aggregation
│   │   └── utils/
│   ├── tests/unit/
│   ├── requirements.txt
│   └── .env.example
├── index.html                        # home page (Three.js hero + service grid)
├── scanner.html                      # URL / email threat scanner
├── writing.html                      # writing rewriter
├── code.html                         # code review
├── image.html                        # image analysis
├── data.html                         # data summary
├── translate.html                    # translator
├── about.html / privacy.html / developers.html
├── assets/
│   ├── css/custom.css                # design tokens + components
│   └── js/                           # one module per page
├── api/
│   ├── index.py                      # Vercel serverless entry → imports backend
│   └── requirements.txt
├── vercel.json                       # rewrites + function config
└── README.md
```

## API keys

All external APIs can be run on free tiers.

| Provider | Env var | Get it at |
|---|---|---|
| Google Safe Browsing | `GOOGLE_SAFE_BROWSING_API_KEY` | https://console.cloud.google.com/ (enable Safe Browsing API) |
| VirusTotal | `VIRUSTOTAL_API_KEY` | https://www.virustotal.com/gui/join-us |
| PhishTank | `PHISHTANK_API_KEY` | Optional; new registrations no longer issued |
| Groq (all AI tools) | `GROQ_API_KEY` | https://console.groq.com/keys |

Copy `backend/.env.example` to `backend/.env` and paste the keys.

## Privacy

- URLs and email content are **never stored**.
- IP addresses are hashed before any persistence (used for rate-limiting only, 24h TTL).
- Images and pasted text are sent to the model provider for inference and discarded
  after the response is returned.

## License

MIT.
