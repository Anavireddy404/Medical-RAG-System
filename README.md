# 🏥 Medical Literature RAG System

Evidence-based medical Q&A grounded in live PubMed literature, with a personal health profile, medication safety checks, and emergency triage — built as a FastAPI backend and a single-file React frontend.

## What it does

- **Signup/login** — JWT-based auth (bcrypt password hashing), one health profile per account
- **Health profile** — name, age, gender, height/weight, medical conditions, medications, allergies, family history, lifestyle; autocomplete on condition/medication/allergy fields via NIH Clinical Tables and RxTerms
- **BMI + TDEE** — calculated from the profile using the Mifflin-St Jeor equation
- **Medical Q&A (RAG)** — retrieves live PubMed abstracts for a question, then has an LLM (Llama 3.3 70B via Groq) write a cited answer from them. A relevance filter runs before generation so the model can't cite a paper that doesn't actually support the claim it's attached to
- **Fallback to general knowledge** — if no retrieved paper is genuinely relevant, the answer is generated from the model's general medical knowledge instead, and clearly labeled as such
- **Safety checker** — cross-references the profile's medications and allergies against RxNorm/RxClass drug classifications and openFDA's structured "Drug Interactions" label text, to flag real interactions/conflicts (not LLM guesses)
- **Emergency triage** — every query is checked against a red-flag keyword list plus an LLM classification pass; a likely emergency short-circuits the normal answer with an urgent "seek care now" message (deliberately biased toward false alarms over missed emergencies)
- **Free/low-cost care locator** — looks up Federally Qualified Health Centers near a ZIP code via CMS's NPPES registry, plus static national hotlines (988, Poison Control, SAMHSA)
- **Multi-language answers** — 12 languages, including translated emergency messages (with the English original always shown alongside as a safety backup)
- **Voice input/output** — browser-native speech-to-text and text-to-speech
- **Query interpreter** — cleans up a rambling/unclear question (e.g. a raw voice transcript) into a clear one before searching

## Architecture

```
frontend/index.html   React 18 (CDN + Babel standalone, no build step) + Axios
backend/main.py        FastAPI, single file
  ├─ Auth              JWT (PyJWT) + bcrypt, scoped per account
  ├─ Storage           Postgres (Neon) — profiles keyed 1:1 by account
  ├─ Retrieval         PubMed E-utilities (esearch/efetch) — live, no local corpus
  ├─ Generation        Groq API, Llama 3.3 70B (OpenAI-compatible SDK)
  ├─ Safety data       RxNorm / RxClass / openFDA (NIH + FDA, free, no key)
  └─ Care locator      CMS NPPES provider registry (free, no key)
```

No vector database, no embeddings, no local document corpus — retrieval is a live PubMed search per query, and every external data source (NIH, FDA, CMS) is free and requires no API key except Groq's.

## Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file at the project root (see `.env.example`) with:
- `GROQ_API_KEY` — free at [console.groq.com](https://console.groq.com/keys)
- `DATABASE_URL` — a Postgres connection string (e.g. a free [Neon](https://neon.tech) project)
- `SECRET_KEY` — a random secret for JWT signing (e.g. `python3 -c "import secrets; print(secrets.token_hex(32))"`)

Run the backend from the project root:
```bash
python backend/main.py
```

Open `frontend/index.html` directly in a browser — no build step, no dev server required. It talks to `http://localhost:8000` locally and auto-switches to the deployed backend URL when not on `localhost`.

## Deployment

`render.yaml` at the repo root configures the backend as a Render Blueprint web service. The frontend deploys separately as a Render Static Site pointed at `frontend/`. Database is Postgres (Neon), not SQLite, since most free hosting tiers wipe local disk on every redeploy.

## API overview

| Method | Endpoint | Auth |
|---|---|---|
| POST | `/api/auth/signup`, `/api/auth/login` | — |
| GET/PUT/DELETE | `/api/my-profile` | ✓ |
| GET | `/api/my-profile/safety-check`, `/api/my-profile/metrics` | ✓ |
| POST | `/api/query` | ✓ |
| POST | `/api/interpret-query` | — |
| GET | `/api/autocomplete/{conditions\|medications\|allergies}` | — |
| GET | `/api/care-locator` | — |
| GET | `/api/health-info`, `/api/stats`, `/health` | — |

## Disclaimer

This system is for informational purposes only and is not a substitute for professional medical advice, diagnosis, or treatment. It includes an automated emergency-symptom check, but that check can miss things — always seek emergency care directly for anything urgent rather than relying on this tool.
