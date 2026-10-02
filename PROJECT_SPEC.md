# Friend-Powered Open Model Benchmark: Project Spec (v2)

> Audience: coding agents (GitHub Copilot, Antigravity) and the human owner.
> Work ONE PHASE AT A TIME, on its own branch, merged via pull request. At the end of each phase, stop, summarize what was built, how to verify it, and known issues, then wait for the owner to say "go to next phase". Do not add features that are not in this spec. Ask before adding any dependency not listed.

## Current Implementation Status

| Phase | Description | Status | Verification & Notes |
|---|---|---|---|
| **Phase 1: Foundation & CI** | Architecture, providers, DB schema, config, CI | **Completed** | Full schema in `app/models.py`, OpenAI-compatible (NVIDIA NIM/Groq) & Gemini adapters, 13/13 pytest tests passing. |
| **Phase 2: Queue & Choosing** | Invite auth, prompt submit, background queue, blind voting | **Completed** | Signed cookie session, multi-prompt submission, async background generation worker, randomized blind comparison, model reveals. |
| **Phase 3: Results & Deployment** | Statistics, personal/group results, privacy, Render config | **Completed** | Pairwise stats with sample size flags ($n < 10$), personal summary, group leaderboard, GDPR-style data deletion, `render.yaml` Blueprint & Dockerfile ready. |
| **Phase 4: Live Testing & Write-up** | Render deployment, live friend benchmark, DEV post | **In Progress** | Ready for deployment to Render with credits; live testing with invite codes and drafting challenge post. |


## 1. What this is

Friends keep asking me "which AI model is best for what?" This app answers it with THEIR OWN prompts.

Flow:
1. A friend enters an invite code and pastes 5-15 prompts they actually use AI for, tagging each with a task type.
2. The server generates answers from several models in the background (mostly open-weight models, plus one closed baseline).
3. For each prompt the friend sees 3-4 anonymous answers (model names hidden, order randomized) and picks the best one (or "none are good"). After picking, the models are revealed.
4. At the end they get a personal "best models for you" page, broken down by task type. A group results page combines everyone's picks.

Built for: {FRIEND_NAME} (the friend who asks this most), and my wider friend group.

Purpose of the write-up: give friends an honest "use model X for task Y" guide, and show with their own picks how open models compare to a closed one. Report results honestly, including where open models lose.

## 2. Challenge constraints (must respect)

Submission to the DEV "Hacktoberfest Weekend Challenge: Build for a Friend".

- Project must be NEW and built inside the window: starts Oct 2, 2026 02:00 UTC, ends Oct 5, 2026 06:59 UTC (Mon Oct 5, 12:29 PM IST). Fresh repo. Any commit after the deadline must be noted in the README.
- Open-weight models must be the core of the project; the single closed model is only a comparison baseline.
- Credit any borrowed code or libraries in the README.
- Submission is a DEV post using the official template, with tags `devchallenge`, `weekendchallenge`, `hf26challenge`, in English.
- Possible partner categories (only claim ones genuinely used): Render (hosting), GitHub Copilot (coding agent / CLI / PR review / Actions), Gemma (only if a Gemma model is actually in the benchmark). Backboard only if a model is really routed through it.

## 3. Scope

In scope: invite-only site, prompt submission, background generation, blind choosing, personal and group results, privacy controls, deployment, README, write-up.

Out of scope: passwords or full auth, payments, fine-tuning, admin dashboard, mobile app, user-uploaded files or images.

Stretch (only if time remains after Phase 3): import of a pre-generated "core prompt set" from local Gemma via Ollama, Bradley-Terry ranking, CSV export of opted-in data.

## 4. Architecture

```
Browser (Jinja pages + vanilla JS, polling)
        |
        v
FastAPI app
  - invite code + session cookie
  - prompt submission API
  - results API
  - background generation worker (asyncio, same process)
        |                         |
        v                         v
 Database (Postgres/SQLite)    Model providers
 participants, prompts,         - NVIDIA NIM (OpenAI-compatible)  -> open models
 jobs, answers, picks           - Google Gemini API (adapter)      -> closed baseline
                                - Ollama (OpenAI-compatible)       -> local/dev only
```

Key rules:
- Model access goes through one provider abstraction. Models are defined ONLY in `config/models.yaml`, so adding or swapping a model is a config change.
- Generation is a persistent job queue (a `jobs` table), so a server restart resumes unfinished work.
- The UI never receives model names for an answer until after the participant has picked.

## 5. Tech stack

- Python 3.11+, FastAPI, Uvicorn
- SQLModel (or SQLAlchemy), SQLite locally, Postgres in production via `DATABASE_URL`
- Jinja2 templates + vanilla JavaScript (no React, no build step)
- `httpx` (async) for provider calls; `PyYAML` for config
- `markdown` + `bleach` for safe rendering of model output (never inject raw model output as HTML)
- `slowapi` or a small custom limiter for rate limiting
- `pytest`, `pytest-asyncio`; GitHub Actions workflow to run tests on every PR
- Hosting: Render web service + Render Postgres

## 6. Providers and models

Three provider kinds in `config/models.yaml`:

1. `openai_compatible`: NVIDIA NIM at `https://integrate.api.nvidia.com/v1` (key env `NVIDIA_API_KEY`, key starts with `nvapi-`). Also used for Ollama at `http://localhost:11434/v1` (dev only, no key).
2. `gemini`: Google Gemini API via REST `generateContent` with header `x-goog-api-key` (key env `GEMINI_API_KEY`). Small adapter that converts the common request (system prompt, user prompt, temperature, max tokens) to Gemini's format and returns text, latency, and token usage if available.

Config shape:

```yaml
generation:
  temperature: 0.3
  max_tokens: 800
  system_prompt: "Answer helpfully and concisely."
models:
  - id: "{short_id}"
    display_name: "{OPEN_MODEL_1}"
    kind: openai_compatible
    base_url: "https://integrate.api.nvidia.com/v1"
    api_key_env: "NVIDIA_API_KEY"
    provider_model_id: "{model id exactly as returned by /v1/models}"
    is_open: true
    license_type: "permissive"   # permissive | custom_open_weights | closed
    license_note: "{e.g. Apache 2.0}"
    live_enabled: true
  # repeat for 3-4 open models
  - id: "{baseline_id}"
    display_name: "{GEMINI_FLASH_MODEL}"
    kind: gemini
    api_key_env: "GEMINI_API_KEY"
    provider_model_id: "{gemini model id}"
    is_open: false
    license_type: "closed"
    is_baseline: true
    live_enabled: true
```

Model selection rules:
- Use plain chat/instruct models. Do NOT use reasoning/"thinking" models for live generation (slow, token-heavy, rate-limit risk). If an output contains `<think>...</think>` blocks, strip them before storing.
- Only use model ids that the NIM `/v1/models` endpoint actually returns for the owner's key. Phase 1 includes a script that lists them.
- Label licenses accurately in the UI and README: Apache 2.0/MIT models are "open source"; Llama, Gemma, Nemotron etc. are "open-weight (custom license)", never "open source".

Fairness rules: same system prompt, temperature and max_tokens for every model; one answer per (prompt, model); failed calls are stored with an `error` and excluded from choosing; log latency and tokens; note answer-length bias as a limitation.

## 7. Data model

- `participants`: id, display_name, invite_code_used, public_profile (bool, default false), consent_third_party (bool), created_at
- `prompts`: id, participant_id, text, category, share_publicly (bool, default false), created_at
  - categories: `coding`, `writing`, `study_help`, `summarizing`, `translation`, `other`
- `models`: id, display_name, provider_model_id, is_open, license_type, is_baseline
- `answers`: id, prompt_id, model_id, text, latency_ms, tokens_in, tokens_out, status (`pending|done|error`), error, created_at; unique (prompt_id, model_id)
- `jobs`: id, prompt_id, model_id, status (`queued|running|done|failed`), attempts, last_error, updated_at
- `picks`: id, prompt_id, participant_id, shown_answer_ids (JSON, in displayed order), chosen_answer_id (nullable), outcome (`picked|none_good`), created_at; unique (prompt_id, participant_id)

## 8. Which models see which prompt

For each submitted prompt:
- Always include the baseline model.
- Add 2-3 randomly chosen open models (from `live_enabled` open models), so each prompt is judged on 3-4 answers.
- Balance selection so each open model appears roughly equally often (choose the least-used models first).
- Only answers with `status=done` are shown; if the baseline failed, show the open answers only and mark the prompt `no_baseline` (excluded from open-vs-closed stats).

---

## PHASE 1: Foundation, providers, and CI

Goal: a repo where every configured model can be called from a script and tests run in CI.

Tasks
1. Create the repo layout:
```
   open-model-bench/
     README.md  PROJECT_SPEC.md  requirements.txt  .env.example  .gitignore
     config/models.yaml
     app/{main.py,db.py,models.py,config.py}
     app/providers/{base.py,openai_compat.py,gemini.py}
     app/services/{generation.py,selection.py,stats.py}
     app/routes/{auth.py,prompts.py,pick.py,results.py}
     app/templates/  app/static/
     scripts/{list_nim_models.py,smoke_test_models.py}
     tests/
     docs/agent-log.md
     .github/workflows/ci.yml
```
2. `.env.example` with: `DATABASE_URL`, `NVIDIA_API_KEY`, `GEMINI_API_KEY`, `INVITE_CODES` (comma-separated), `SESSION_SECRET`, `DAILY_CALL_CAP`, `GENERATION_ENABLED`. Never commit real keys; `.gitignore` covers `.env` and local DB files.
3. `app/config.py`: load `config/models.yaml` and env vars; validate at startup (fail clearly if a required key is missing for a `live_enabled` model).
4. `app/db.py` + `app/models.py`: tables from section 7, created on startup; SQLite default, `DATABASE_URL` override.
5. Provider layer: a common interface `async generate(system, prompt, temperature, max_tokens) -> {text, latency_ms, tokens_in, tokens_out}`. Implement `openai_compat.py` and `gemini.py`. Both need timeout (60s), retry with exponential backoff and jitter on 429/5xx (max 3 attempts), and clear error messages. Strip `<think>` blocks.
6. `scripts/list_nim_models.py`: prints model ids available to the owner's NVIDIA key via `/v1/models`, so the owner can fill `models.yaml`.
7. `scripts/smoke_test_models.py`: sends one short prompt to every `live_enabled` model and prints text, latency, and tokens, or the error.
8. Tests with mocked HTTP: provider success, 429 retry, timeout, think-tag stripping, config validation.
9. GitHub Actions `ci.yml`: install deps and run pytest on pull requests.

Acceptance criteria
- `python scripts/smoke_test_models.py` gets an answer from every configured model (or a clear error per model).
- Tests pass locally and in CI.
- No secrets in the repo.

---

## PHASE 2: Prompt submission, generation queue, and blind choosing

Goal: a friend can paste prompts and choose answers end to end, locally.

Tasks
1. Invite-only entry: `GET /` landing page explains the project and the privacy notice; the visitor enters an invite code (from `INVITE_CODES`) and a display name. Create a `participants` row and set a signed session cookie. No passwords.
2. Consent: required checkbox "I understand my prompts are sent to third-party AI providers (NVIDIA-hosted endpoints and Google) and may be processed under their terms." Optional unchecked-by-default checkbox "Allow my anonymized prompts and picks to appear in public results." Store both.
3. `GET /submit`: form for 5-15 prompts (min 5, max 15), each up to 1500 characters, each with a category dropdown. Validate server-side. Remind users not to include personal or sensitive information.
4. `POST /api/prompts`: store prompts, run model selection (section 8), create `answers` (pending) and `jobs` rows.
5. Background worker (asyncio task started on app startup):
   - pulls queued jobs, runs them with a per-provider concurrency limit (NIM: 3, Gemini: 2), retries with backoff, updates statuses
   - persistent: on startup, re-queue jobs left `running`
   - respects `GENERATION_ENABLED` (kill switch) and `DAILY_CALL_CAP` (stop and mark jobs `queued` when reached; show a friendly "come back later" message)
6. `GET /api/session/status`: progress (answers ready per prompt) for polling every 2 seconds.
7. Choosing UI (`pick.html` + `app.js`): one prompt at a time, 3-4 answers in randomized order labeled A/B/C/D, buttons "Pick this one" per answer and "None are good". A prompt becomes available as soon as its answers are ready; show a waiting state otherwise. Progress indicator ("4 of 12"). After picking, reveal model names (and whether each is open or closed) and show a "Next" button.
8. `POST /api/pick`: validate that the prompt belongs to the participant, the answer ids were shown, and no earlier pick exists; store the pick. The `GET /api/next` response must NOT contain model names or license info.
9. Safe rendering of answers (sanitized markdown, code blocks styled, long answers scroll inside their card).
10. Abuse controls: per-IP rate limit on submit and pick endpoints, max 15 prompts per participant, invite code can be limited by uses (optional).
11. Tests: selection logic (always includes baseline, balances models, handles baseline failure), pick validation, job resume after restart, no model name leakage before picking.

Acceptance criteria
- A participant can submit prompts, wait while answers appear, pick for every prompt, and see reveals.
- Model names never appear in the page source or `/api/next` before a pick.
- A failed model call does not block the prompt; the participant is never asked to judge an errored answer.
- Restarting the server mid-generation resumes pending jobs.
- Works on a phone-sized screen.

---

## PHASE 3: Results, privacy controls, and deployment

Goal: personal and group results live on a public URL, with friends using it.

Tasks
1. Stats (`app/services/stats.py`). For each prompt with a pick, treat the chosen answer as beating every other shown answer (pairwise). `none_good` picks are counted separately and excluded from win rates.
   - pairwise win rate per model = pairwise wins / pairwise comparisons, overall and per category, always with n (number of comparisons)
   - pick rate = times chosen / times shown, with the chance baseline (1/k) noted
   - open-vs-closed: among prompts that include the baseline and at least one open answer, the share where an open answer was picked over the baseline (report n)
   - median latency and tokens per model
2. `GET /results/me`: the participant's personal ranking per category: "your best models" with counts, plus a plain-language summary. Label small samples ("based on {n} picks, treat as a hint").
3. `GET /results`: group results: models x categories with win rate and n, a simple bar chart per category (plain HTML/CSS), the open-vs-closed number, and "none are good" rate. Flag any cell with n < 10 as "not enough picks yet". Also `GET /results.json`.
4. "Friends' picks" section: shown only for participants with `public_profile = true`: display name, top model per category.
5. Privacy features: a "Delete my data" button that removes the participant's prompts, answers, and picks (and recomputes stats); public results only ever use prompts with `share_publicly = true` for any prompt text shown (aggregate stats may include all picks without text).
6. Deployment on Render: web service start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, Render Postgres via `DATABASE_URL`, environment variables from `.env.example`, `/health` endpoint. Run a single instance only (the background worker lives in the web process). Confirm data survives a restart (no reliance on local disk).
7. Add a basic usage note and spend protection: `DAILY_CALL_CAP` enforced, and a visible message if generation is paused.
8. Tests for stats calculations (pairwise logic, small-sample flags, open-vs-closed), delete-my-data, and public-profile filtering.

Acceptance criteria
- Public URL works end to end: invite code, submit, pick, personal results, group results.
- Every statistic shows its n and warns on small samples.
- Deleting data removes it from results.
- The owner hands the link to {FRIEND_NAME} and at least several friends complete a session.

---

## PHASE 4: Analysis, README, and write-up

Goal: a valid, high-quality submission.

Tasks
1. Pull final numbers from `/results.json`. Identify: the best model per category, where open models matched or beat the baseline, where the baseline clearly won, and the most surprising result. Report losses honestly.
2. README: what it is and who it's for, screenshots, local setup, how to get NVIDIA and Gemini keys, how to edit `models.yaml`, how to deploy on Render, model list with licenses (permissive vs custom open-weight vs closed), privacy notice, limitations (small sample, answer-length bias, one answer per prompt per model, one closed baseline from one vendor, friend-group prompts, free-tier rate limits), credits, and a note on any post-deadline commits.
3. `docs/agent-log.md`: short record of which tasks used Copilot (coding agent, CLI, PR review, Actions) and which used Antigravity, and what had to be fixed by hand.
4. Draft the DEV post using the official template:
   - What I Built: who {FRIEND_NAME} is, the question they kept asking, what the app does
   - Demo: live link and a short screen recording
   - Code: GitHub repo embed
   - How I Built It: architecture, models used, how fairness and privacy were handled
   - Why Does Open Innovation Matter?: concrete points only (swap models by editing one YAML file, one key to many open models, no per-token cost on the open side, comparing open models on friends' own tasks, accurate license distinctions), plus honest limits
   - My Agent Session: optional link/embed
   - Prize Categories: only those genuinely used
   - What {FRIEND_NAME} said when they used it
5. Final checks: tags present, post in English, repo public, live link works, no secrets committed, post published with a buffer before the deadline (aim for Mon Oct 5, 9:00 AM IST).

Acceptance criteria
- README lets a stranger run the project locally.
- Post covers every template section with real numbers from real picks.
- Limitations are stated plainly, and "closed model" is described as one specific model, not "the big models" in general.

---

## 9. Working agreement for agents

- One phase at a time, one branch per phase, one pull request per phase; do not start the next phase without owner approval.
- Small, reviewable commits; clear messages.
- Never commit API keys or real participant data.
- Keep it simple: no extra frameworks, no abstractions "for later".
- Write tests for selection, pick validation, job resume, and stats; run them before finishing each phase.
- At the end of each phase output: what was built, how to verify it, known issues, and what the owner must provide for the next phase.