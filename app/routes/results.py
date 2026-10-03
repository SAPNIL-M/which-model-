from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlmodel import Session, delete, select

from app.config import load_config
from app.db import engine
from app.models import Answer, Job, Model, Participant, Pick, Prompt
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


@router.get("/explore", response_class=HTMLResponse)
def explore_page(request: Request):
    with Session(engine) as session:
        picks = session.exec(select(Pick)).all()
        picked_prompt_ids = {pick.prompt_id: pick for pick in picks}

        shared_prompts = session.exec(
            select(Prompt)
            .where(Prompt.share_publicly == True, Prompt.id.in_(list(picked_prompt_ids.keys())))
            .order_by(Prompt.id.desc())
        ).all() if picked_prompt_ids else []

        models_map = {m.id: m for m in session.exec(select(Model)).all()}
        participants_map = {p.id: p for p in session.exec(select(Participant)).all()}

        items = []
        for prompt in shared_prompts:
            pick = picked_prompt_ids.get(prompt.id)
            if not pick:
                continue
            answers = session.exec(
                select(Answer).where(Answer.prompt_id == prompt.id, Answer.status == "done")
            ).all()
            if not answers:
                continue

            author = participants_map.get(prompt.participant_id)
            author_name = (
                author.display_name
                if (author and author.public_profile)
                else "Community Participant"
            )

            answer_data = []
            for ans in answers:
                model = models_map.get(ans.model_id)
                answer_data.append(
                    {
                        "id": ans.id,
                        "text": ans.text,
                        "model_name": model.display_name if model else ans.model_id,
                        "is_open": model.is_open if model else False,
                        "license_type": model.license_type if model else "custom_open_weights",
                        "latency_ms": ans.latency_ms,
                        "tokens_out": ans.tokens_out,
                        "is_chosen": (pick.outcome == "picked" and pick.chosen_answer_id == ans.id),
                    }
                )

            items.append(
                {
                    "prompt": prompt,
                    "author_name": author_name,
                    "outcome": pick.outcome,
                    "answers": answer_data,
                }
            )

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="explore.html",
        context={"items": items},
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
