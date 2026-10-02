import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlmodel import Session, select

from app.config import load_config
from app.db import engine
from app.models import Answer, Model, Pick, Prompt
from app.rate_limit import allowed
from app.security import verify_session

router = APIRouter()
config = load_config()


def participant_id(request: Request) -> int | None:
    return verify_session(request.cookies.get("whichmodel_session"), config.session_secret)


@router.get("/pick", response_class=HTMLResponse)
def pick_page(request: Request):
    if not participant_id(request):
        return RedirectResponse("/", status_code=303)
    return request.app.state.templates.TemplateResponse("pick.html", {"request": request})


@router.get("/api/next")
def next_prompt(request: Request):
    pid = participant_id(request)
    if not pid:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    with Session(engine) as session:
        prompts = session.exec(select(Prompt).where(Prompt.participant_id == pid)).all()
        picked_ids = {
            pick.prompt_id
            for pick in session.exec(select(Pick).where(Pick.participant_id == pid))
        }
        completed = len(picked_ids)
        for prompt in prompts:
            if prompt.id in picked_ids:
                continue
            answers = session.exec(
                select(Answer)
                .where(Answer.prompt_id == prompt.id, Answer.status == "done")
                .order_by(Answer.id)
            ).all()
            if len(answers) < 2:
                continue
            answers = answers[:4]
            return {
                "prompt_id": prompt.id,
                "prompt": prompt.text,
                "category": prompt.category,
                "answers": [
                    {"id": answer.id, "label": chr(65 + index), "text": answer.text}
                    for index, answer in enumerate(answers)
                ],
                "progress": {"current": completed + 1, "total": len(prompts)},
            }
    return {"complete": completed == len(prompts), "waiting": completed != len(prompts)}


@router.post("/api/pick")
async def create_pick(request: Request):
    if not allowed(request, "pick", limit=30, window=60):
        return JSONResponse({"error": "Too many picks. Try again shortly."}, status_code=429)
    pid = participant_id(request)
    if not pid:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    body = await request.json()
    prompt_id = body.get("prompt_id")
    shown_ids = body.get("shown_answer_ids", [])
    chosen_id = body.get("chosen_answer_id")
    outcome = body.get("outcome")
    if not isinstance(shown_ids, list) or outcome not in {"picked", "none_good"}:
        return JSONResponse({"error": "Invalid pick."}, status_code=400)
    with Session(engine) as session:
        prompt = session.get(Prompt, prompt_id)
        if not prompt or prompt.participant_id != pid:
            return JSONResponse({"error": "Prompt does not belong to this participant."}, status_code=403)
        if session.exec(
            select(Pick).where(Pick.prompt_id == prompt_id, Pick.participant_id == pid)
        ).first():
            return JSONResponse({"error": "This prompt was already picked."}, status_code=409)
        available = {
            answer.id
            for answer in session.exec(
                select(Answer).where(Answer.prompt_id == prompt_id, Answer.status == "done")
            )
        }
        if not shown_ids or any(answer_id not in available for answer_id in shown_ids):
            return JSONResponse({"error": "Answers shown to the participant are invalid."}, status_code=400)
        if outcome == "picked" and chosen_id not in shown_ids:
            return JSONResponse({"error": "Chosen answer was not shown."}, status_code=400)
        session.add(
            Pick(
                prompt_id=prompt_id,
                participant_id=pid,
                shown_answer_ids=json.dumps(shown_ids),
                chosen_answer_id=chosen_id if outcome == "picked" else None,
                outcome=outcome,
            )
        )
        session.commit()
        reveals = session.exec(
            select(Answer, Model)
            .join(Model, Model.id == Answer.model_id)
            .where(Answer.id.in_(shown_ids))
        ).all()
    return {
        "reveals": [
            {
                "answer_id": answer.id,
                "model_id": model.id,
                "display_name": model.display_name,
                "is_open": model.is_open,
            }
            for answer, model in reveals
        ]
    }
