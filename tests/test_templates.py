from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import load_config
from app.db import engine
from app.main import app
from app.models import Participant
from app.security import sign_session


def test_pages_and_static_render():
    config = load_config()
    with TestClient(app) as client:
        # Static CSS
        css_res = client.get("/static/style.css")
        assert css_res.status_code == 200
        assert "WhichModel?" in css_res.text

        # Landing page
        landing_res = client.get("/")
        assert landing_res.status_code == 200
        assert "WhichModel?" in landing_res.text

        # Results page (public)
        results_res = client.get("/results")
        assert results_res.status_code == 200
        assert "Model Benchmark Leaderboard" in results_res.text

        # Create dummy participant to test authed pages
        with Session(engine) as session:
            participant = Participant(
                display_name="Tester",
                invite_code_used="test",
                consent_third_party=True,
                public_profile=True,
            )
            session.add(participant)
            session.commit()
            session.refresh(participant)
            pid = participant.id

        client.cookies.set("whichmodel_session", sign_session(pid, config.session_secret))

        # Submit page
        submit_res = client.get("/submit")
        assert submit_res.status_code == 200
        assert "Submit Your Prompts" in submit_res.text

        # Pick page
        pick_res = client.get("/pick")
        assert pick_res.status_code == 200
        assert "Which Answer is Best?" in pick_res.text

        # Results Me page
        me_res = client.get("/results/me")
        assert me_res.status_code == 200
        assert "Your Benchmark Results" in me_res.text
