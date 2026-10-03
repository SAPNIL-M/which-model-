# WhichModel?

> A friend-powered benchmark for finding the best AI model for real tasks.

Friends submit prompts they actually use for work or study, compare anonymous answers from open-weight models against a closed baseline, and receive benchmark results tailored to their specific needs.

---

## Current Status

| Phase | Milestone | Status | Details |
|---|---|---|---|
| **Phase 1** | Foundation, Providers & CI | **Completed** | Database schemas, OpenAI-compatible (NVIDIA NIM/Groq) & Gemini providers, 13 automated tests passing. |
| **Phase 2** | Queue & Blind Choosing | **Completed** | Invite-gate auth, session management, multi-prompt submission, in-process background worker, randomized blind comparison, model reveals. |
| **Phase 3** | Results, Privacy & Deployment | **Completed** | Personal `/results/me` breakdown, group `/results` leaderboard, pairwise win rates, sample size warnings ($n < 10$), self-service "Delete my data", `render.yaml` Blueprint & Dockerfile. |
| **Phase 4** | Live Deployment & Write-up | **In Progress** | Deploying to Render using Render credits, collecting live friend evaluations, and preparing the DEV challenge submission. |

---

## How It Works

1. **Invite-Gated Access:** Visitors enter with an invite code and grant privacy consent. Signed session cookies handle authentication without passwords.
2. **Prompt Submission:** Users submit 5–15 prompts categorized by task type (`coding`, `writing`, `study_help`, `summarizing`, `translation`, `other`).
3. **Background Generation:** An in-process `asyncio` background worker queries the configured models in parallel with concurrency controls and retry backoffs.
4. **Blind Voting:** Answers are presented with randomized order and neutral labels (Answer A, B, C) to eliminate brand bias. Users pick the best answer or mark "None are good".
5. **The Reveal:** Model identities, latencies, and token counts are revealed immediately after voting.
6. **Leaderboards & Insights:** Pairwise win rates, category performance charts, and an open-vs-closed showdown are updated in real time.
7. **Privacy by Design:** Users can delete their prompts, answers, and pick history at any time with immediate stats recalculation.

---

## Configured Models

Models are configured via `config/models.yaml`:

| Model | Kind | Provider | License Type | Role |
|---|---|---|---|---|
| **Llama 3.2 11B Vision Instruct** | OpenAI-compatible | NVIDIA NIM | Open-weight (Community) | Open Candidate |
| **Qwen 3.8 27B** | OpenAI-compatible | Groq | Open-weight | Open Candidate |
| **GPT-OSS 20B** | OpenAI-compatible | Groq | Open-weight (Apache 2.0) | Open Candidate |
| **Gemini 3.5 Flash Lite** | Gemini API | Google | Closed | Comparison Baseline |

---

## Deployment on Render

The repository includes a ready-to-use `render.yaml` Blueprint that automatically provisions:
1. **Web Service (`whichmodel`):** FastAPI running on Uvicorn with a health check at `/health` (Starter plan, Singapore).
2. **Managed Database (`whichmodel-db`):** Render PostgreSQL (`basic-256mb`) automatically wired into `DATABASE_URL`.

Paid plans are used on purpose: free web services sleep when idle (which stops the background generation worker) and free Postgres databases expire after 30 days. Expect roughly $7 + $6 per month.

### Steps to Deploy:
1. Push this repository to GitHub.
2. In the [Render Dashboard](https://dashboard.render.com), click **New** → **Blueprint**.
3. Connect your repository. Render will automatically parse `render.yaml`.
4. Fill in the required environment variables:
   * `INVITE_CODES`: Comma-separated list of access codes (e.g. `friends2026,team-access`).
   * `GEMINI_API_KEY`: Google Gemini API key.
   * `GROQ_API_KEY`: Groq API key.
   * `NVIDIA_API_KEY`: NVIDIA NIM API key.
5. Apply the Blueprint. Render will provision both resources and launch your live app.

> **Note:** Run a single web service instance because the generation worker runs in-memory within the web process.

---

## Local Development Setup

### 1. Environment & Dependencies

```powershell
# Create and activate virtual environment
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt

# Copy environment template
Copy-Item .env.example .env
```

### 2. Configure Environment

Fill in `.env` with your API keys:
```env
DATABASE_URL=sqlite:///./whichmodel.db
SESSION_SECRET=local-dev-secret-key-change-me
INVITE_CODES=testcode
DAILY_CALL_CAP=100
GENERATION_ENABLED=true
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
NVIDIA_API_KEY=your_nvidia_key
```

### 3. Verify Setup & Run Tests

```powershell
# Run the test suite
pytest

# Smoke test model endpoints (optional)
python scripts/smoke_test_models.py
```

### 4. Start the Application

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Open `http://localhost:8000` in your browser.

---

## Security & Privacy

* **Input & Output Sanitization:** All model outputs are rendered with `markdown` + `bleach` to prevent XSS.
* **Model Privacy:** Model identities are stripped from all API endpoints until voting is complete.
* **Rate Limiting:** IP-level throttling protects against automated abuse.
* **Data Deletion:** The `/results/me` page provides a self-service deletion option that purges all user data and adjusts stats.

---

## License

MIT License. See individual model documentation for respective model weights licenses.
