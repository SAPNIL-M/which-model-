from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlmodel import Session, select

from app.config import load_config
from app.db import engine
from app.models import Answer, Participant, Prompt, Model
from app.rate_limit import allowed
from app.security import verify_session
from app.services.selection import queue_prompt

router = APIRouter()
config = load_config()
CATEGORIES = {"coding", "writing", "study_help", "summarizing", "translation", "other"}


def participant_id(request: Request) -> int | None:
    return verify_session(request.cookies.get("whichmodel_session"), config.session_secret)


@router.get("/submit", response_class=HTMLResponse)
def submit_page(request: Request):
    pid = participant_id(request)
    if not pid:
        return RedirectResponse("/", status_code=303)
    with Session(engine) as session:
        has_prompts = session.exec(select(Prompt).where(Prompt.participant_id == pid)).first() is not None
        if has_prompts:
            return RedirectResponse("/pick", status_code=303)
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="submit.html",
        context={"categories": sorted(CATEGORIES)},
    )


@router.post("/api/prompts")
async def submit_prompts(request: Request):
    if not allowed(request, "submit", limit=3, window=60):
        return JSONResponse({"error": "Too many submissions. Try again shortly."}, status_code=429)
    pid = participant_id(request)
    if not pid:
        return JSONResponse({"error": "Sign in with an invite code first."}, status_code=401)
    body = await request.json()
    prompts = body.get("prompts", [])
    if not 5 <= len(prompts) <= 15:
        return JSONResponse({"error": "Submit between 5 and 15 prompts."}, status_code=400)
    with Session(engine) as session:
        participant = session.get(Participant, pid)
        if not participant or not participant.consent_third_party:
            return JSONResponse({"error": "Consent is required."}, status_code=403)
        if session.exec(select(Prompt).where(Prompt.participant_id == pid)).first():
            return JSONResponse({"error": "Prompts have already been submitted."}, status_code=409)
        configured_ids = {model.id for model in config.models if model.live_enabled}
        models = [
            model
            for model in session.exec(select(Model)).all()
            if model.id in configured_ids
        ]
        try:
            for item in prompts:
                text = str(item.get("text", "")).strip()
                category = item.get("category")
                if not text or len(text) > 1500 or category not in CATEGORIES:
                    return JSONResponse({"error": "Each prompt needs valid text and category."}, status_code=400)
                prompt = Prompt(
                    participant_id=pid,
                    text=text,
                    category=category,
                    share_publicly=bool(item.get("share_publicly", False)),
                )
                session.add(prompt)
                session.flush()
                queue_prompt(session, prompt, models)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)
        session.commit()
    return {"status": "queued", "count": len(prompts)}


@router.get("/api/session/status")
def session_status(request: Request):
    pid = participant_id(request)
    if not pid:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    with Session(engine) as session:
        prompts = session.exec(select(Prompt).where(Prompt.participant_id == pid)).all()
        result = []
        for prompt in prompts:
            answers = session.exec(select(Answer).where(Answer.prompt_id == prompt.id)).all()
            result.append(
                {
                    "prompt_id": prompt.id,
                    "ready": sum(answer.status == "done" for answer in answers),
                    "total": len(answers),
                }
            )
    return {"prompts": result}
