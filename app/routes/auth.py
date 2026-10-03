from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.config import load_config
from app.db import engine
from app.models import Participant, Prompt
from app.security import sign_session, verify_session

router = APIRouter()
config = load_config()


@router.get("/", response_class=HTMLResponse)
def landing(request: Request):
    participant = None
    has_prompts = False
    pid = verify_session(request.cookies.get("whichmodel_session"), config.session_secret)
    if pid:
        with Session(engine) as session:
            participant = session.get(Participant, pid)
            if participant:
                has_prompts = (
                    session.exec(select(Prompt).where(Prompt.participant_id == pid)).first()
                    is not None
                )

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"participant": participant, "has_prompts": has_prompts},
    )


@router.post("/enter")
def enter(
    request: Request,
    invite_code: str = Form(...),
    display_name: str = Form(...),
    consent_third_party: str | None = Form(None),
    public_profile: str | None = Form(None),
):
    if invite_code not in config.invite_codes:
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"error": "Invalid invite code. Benchmark participation is currently invite-only due to free API tier limits."},
            status_code=400,
        )
    if not display_name.strip() or consent_third_party != "on":
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"error": "Name and third-party provider consent are required."},
            status_code=400,
        )
    with Session(engine) as session:
        participant = Participant(
            display_name=display_name.strip(),
            invite_code_used=invite_code,
            consent_third_party=True,
            public_profile=public_profile == "on",
        )
        session.add(participant)
        session.commit()
        session.refresh(participant)

    response = RedirectResponse("/submit", status_code=303)
    response.set_cookie(
        "whichmodel_session",
        sign_session(participant.id, config.session_secret),
        max_age=30 * 86400,  # 30-day persistent session
        httponly=True,
        samesite="lax",
    )
    return response
