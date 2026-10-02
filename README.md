# WhichModel?

WhichModel? is a friend-powered benchmark for finding the best AI model for real tasks. Friends submit prompts, compare anonymous answers from open-weight models and one closed baseline, and receive results tailored to their work.

## Phase 1 status

The foundation, benchmark flow, and Phase 3 results flow include invite access, consent, prompt submission, persistent generation jobs, polling, anonymous answer selection, answer reveals, statistics, privacy deletion, group results, and automated tests.

## Deployment

Render can use `render.yaml` with the start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set the variables from `.env.example` in the Render dashboard and use a Render PostgreSQL connection string for `DATABASE_URL`. Run a single web instance because the generation worker lives in the web process.

## Local setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
pytest
```

Set provider keys in `.env` before running the smoke-test scripts. Never commit `.env` or real keys.

## License

Project licensing and model licensing details will be finalized before deployment.
