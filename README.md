# WhichModel?

WhichModel? is a friend-powered benchmark for finding the best AI model for real tasks. Friends submit prompts, compare anonymous answers from open-weight models and one closed baseline, and receive results tailored to their work.

## Phase 1 status

The foundation and Phase 2 benchmark flow include invite access, consent, prompt submission, persistent generation jobs, polling, anonymous answer selection, answer reveals, rate limits, and automated tests. Results analytics are planned for Phase 3.

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
