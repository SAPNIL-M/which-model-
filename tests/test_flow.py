import json
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import load_config
from app.db import engine
from app.main import app
from app.models import Answer, Job, Model, Participant, Pick, Prompt
from app.security import sign_session
from app.services.generation import count_calls_today


def test_cookie_persistence_and_landing_resumption():
    config = load_config()
    with TestClient(app) as client:
        code = config.invite_codes[0] if config.invite_codes else "SAM123"

        res = client.post(
            "/enter",
            data={
                "invite_code": code,
                "display_name": "AliceFlowTester",
                "consent_third_party": "on",
                "public_profile": "on",
            },
            follow_redirects=False,
        )
        assert res.status_code == 303
        cookie = res.cookies.get("whichmodel_session")
        assert cookie is not None

        # Check raw Set-Cookie header for Max-Age (30 days = 2592000s)
        set_cookie_header = res.headers.get("set-cookie", "")
        assert "max-age=2592000" in set_cookie_header.lower()

        # Check landing page shows returning participant resumption banner
        client.cookies.set("whichmodel_session", cookie)
        landing_res = client.get("/")
        assert landing_res.status_code == 200
        assert "AliceFlowTester" in landing_res.text
        assert "Welcome back" in landing_res.text


def test_submit_redirects_if_prompts_already_submitted():
    config = load_config()
    with Session(engine) as session:
        participant = Participant(
            display_name="BobAlreadySubmitted",
            invite_code_used="test",
            consent_third_party=True,
        )
        session.add(participant)
        session.commit()
        session.refresh(participant)
        pid = participant.id

        prompt = Prompt(
            participant_id=pid,
            text="Existing prompt for bob",
            category="coding",
        )
        session.add(prompt)
        session.commit()

    with TestClient(app) as client:
        client.cookies.set(
            "whichmodel_session", sign_session(pid, config.session_secret)
        )
        res = client.get("/submit", follow_redirects=False)
        assert res.status_code == 303
        assert res.headers["location"] == "/pick"


def test_explore_page_shows_only_shared_and_picked_prompts():
    config = load_config()
    with Session(engine) as session:
        participant = Participant(
            display_name="CharlieExplorer",
            invite_code_used="test",
            consent_third_party=True,
            public_profile=True,
        )
        session.add(participant)
        session.commit()
        session.refresh(participant)
        pid = participant.id

        # Public shared prompt with pick
        prompt_shared = Prompt(
            participant_id=pid,
            text="Public shared secret idea 12345",
            category="coding",
            share_publicly=True,
        )
        # Private unshared prompt with pick
        prompt_private = Prompt(
            participant_id=pid,
            text="Private secret prompt 99999",
            category="writing",
            share_publicly=False,
        )
        session.add(prompt_shared)
        session.add(prompt_private)
        session.commit()
        session.refresh(prompt_shared)
        session.refresh(prompt_private)

        # Add dummy answers
        ans_shared = Answer(
            prompt_id=prompt_shared.id,
            model_id=config.models[0].id,
            text="Shared model answer text",
            status="done",
        )
        ans_private = Answer(
            prompt_id=prompt_private.id,
            model_id=config.models[0].id,
            text="Private answer text",
            status="done",
        )
        session.add(ans_shared)
        session.add(ans_private)
        session.commit()
        session.refresh(ans_shared)
        session.refresh(ans_private)

        # Add picks
        pick_shared = Pick(
            prompt_id=prompt_shared.id,
            participant_id=pid,
            shown_answer_ids=json.dumps([ans_shared.id]),
            chosen_answer_id=ans_shared.id,
            outcome="picked",
        )
        pick_private = Pick(
            prompt_id=prompt_private.id,
            participant_id=pid,
            shown_answer_ids=json.dumps([ans_private.id]),
            chosen_answer_id=ans_private.id,
            outcome="picked",
        )
        session.add(pick_shared)
        session.add(pick_private)
        session.commit()

    with TestClient(app) as client:
        res = client.get("/explore")
        assert res.status_code == 200
        assert "Explore Community Prompts" in res.text
        assert "Public shared secret idea 12345" in res.text
        assert "Shared model answer text" in res.text
        # Private prompt text must NOT leak
        assert "Private secret prompt 99999" not in res.text


def test_count_calls_today():
    with Session(engine) as session:
        participant = Participant(
            display_name="DaveJobTester",
            invite_code_used="test",
            consent_third_party=True,
        )
        session.add(participant)
        session.commit()
        session.refresh(participant)
        pid = participant.id

        prompt = Prompt(participant_id=pid, text="Job test prompt", category="other")
        session.add(prompt)
        session.commit()
        session.refresh(prompt)
        prompt_id = prompt.id

        # Job done today
        job_today = Job(
            prompt_id=prompt_id,
            model_id="gemini-3-5-flash-lite",
            status="done",
            updated_at=datetime.now(timezone.utc),
        )
        # Job done yesterday
        yesterday = datetime.now(timezone.utc) - timedelta(days=1, hours=2)
        job_yesterday = Job(
            prompt_id=prompt_id,
            model_id="gemini-3-5-flash-lite",
            status="done",
            updated_at=yesterday,
        )
        session.add(job_today)
        session.add(job_yesterday)
        session.commit()

    count = count_calls_today()
    assert count >= 1


def test_api_pick_reveals_license_type():
    config = load_config()
    with Session(engine) as session:
        participant = Participant(
            display_name="EvePickTester",
            invite_code_used="test",
            consent_third_party=True,
        )
        session.add(participant)
        session.commit()
        session.refresh(participant)
        pid = participant.id

        prompt = Prompt(participant_id=pid, text="Pick test prompt", category="coding")
        session.add(prompt)
        session.commit()
        session.refresh(prompt)
        prompt_id = prompt.id

        ans1 = Answer(
            prompt_id=prompt_id,
            model_id="gpt-oss-20b",
            text="GPT OSS answer",
            status="done",
        )
        ans2 = Answer(
            prompt_id=prompt_id,
            model_id="gemini-3-5-flash-lite",
            text="Gemini answer",
            status="done",
        )
        session.add(ans1)
        session.add(ans2)
        session.commit()
        session.refresh(ans1)
        session.refresh(ans2)
        ans1_id, ans2_id = ans1.id, ans2.id

    with TestClient(app) as client:
        client.cookies.set(
            "whichmodel_session", sign_session(pid, config.session_secret)
        )
        pick_payload = {
            "prompt_id": prompt_id,
            "shown_answer_ids": [ans1_id, ans2_id],
            "chosen_answer_id": ans1_id,
            "outcome": "picked",
        }
        res = client.post("/api/pick", json=pick_payload)
        assert res.status_code == 200
        data = res.json()
        assert "reveals" in data
        reveals = data["reveals"]
        assert len(reveals) == 2
        # Check license_type is returned
        gpt_reveal = next(r for r in reveals if r["model_id"] == "gpt-oss-20b")
        assert gpt_reveal["license_type"] == "permissive"
