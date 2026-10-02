from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from app.config import load_config
from app.db import create_db_and_tables
from app.routes import auth, pick, prompts, results
from app.services.generation import GenerationWorker
from app.services.markdown_safe import render_safe_markdown

app = FastAPI(title="WhichModel?")

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))
templates.env.filters["markdown"] = lambda s: Markup(render_safe_markdown(s))
templates.env.filters["clean_category"] = lambda s: s.replace("_", " ").title() if s else ""
app.state.templates = templates
app.state.rate_limits = {}
config = load_config()


@app.on_event("startup")
async def startup() -> None:
    create_db_and_tables()
    app.state.worker = GenerationWorker(config)
    await app.state.worker.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await app.state.worker.stop()


app.include_router(auth.router)
app.include_router(prompts.router)
app.include_router(pick.router)
app.include_router(results.router)


@app.get("/health")
def health():
    return {"status": "ok"}
