from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from app.config import load_config
from app.db import engine
from app.models import Participant
from app.security import sign_session

router = APIRouter()
config = load_config()


@router.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return request.app.state.templates.TemplateResponse("index.html", {"request": request})


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
            "index.html", {"request": request, "error": "Invalid invite code."}, status_code=400
        )
    if not display_name.strip() or consent_third_party != "on":
        return request.app.state.templates.TemplateResponse(
            "index.html",
            {"request": request, "error": "Name and third-party consent are required."},
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
        httponly=True,
        samesite="lax",
    )
    return response
