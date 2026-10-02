from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlmodel import Session, delete, select

from app.config import load_config
from app.db import engine
from app.models import Answer, Job, Participant, Pick, Prompt
from app.security import verify_session
from app.services.stats import calculate_stats

router = APIRouter()
config = load_config()


def participant_id(request: Request) -> int | None:
    return verify_session(request.cookies.get("whichmodel_session"), config.session_secret)


@router.get("/results/me", response_class=HTMLResponse)
def personal_results(request: Request):
    pid = participant_id(request)
    if not pid:
        return RedirectResponse("/", status_code=303)
    with Session(engine) as session:
        stats = calculate_stats(session, pid)
        participant = session.get(Participant, pid)
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="results_me.html",
        context={"stats": stats, "participant": participant},
    )


@router.get("/results", response_class=HTMLResponse)
def group_results(request: Request):
    with Session(engine) as session:
        stats = calculate_stats(session)
        profiles = session.exec(
            select(Participant).where(Participant.public_profile)
        ).all()
        public_profiles = []
        for profile in profiles:
            profile_stats = calculate_stats(session, profile.id)
            top_by_category = {}
            for category, rows in profile_stats["categories"].items():
                top = max(rows.items(), key=lambda item: item[1]["win_rate"], default=None)
                if top:
                    top_by_category[category] = profile_stats["models"][top[0]]["display_name"]
            public_profiles.append({"display_name": profile.display_name, "top_by_category": top_by_category})
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="results.html",
        context={"stats": stats, "public_profiles": public_profiles},
    )


@router.get("/results.json")
def group_results_json():
    with Session(engine) as session:
        return calculate_stats(session)


@router.delete("/api/me")
def delete_my_data(request: Request):
    pid = participant_id(request)
    if not pid:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    with Session(engine) as session:
        prompt_ids = [
            prompt.id for prompt in session.exec(select(Prompt).where(Prompt.participant_id == pid))
        ]
        if prompt_ids:
            session.exec(delete(Pick).where(Pick.prompt_id.in_(prompt_ids)))
            session.exec(delete(Answer).where(Answer.prompt_id.in_(prompt_ids)))
            session.exec(delete(Job).where(Job.prompt_id.in_(prompt_ids)))
            session.exec(delete(Prompt).where(Prompt.id.in_(prompt_ids)))
        session.delete(session.get(Participant, pid))
        session.commit()
    response = JSONResponse({"status": "deleted"})
    response.delete_cookie("whichmodel_session")
    return response
