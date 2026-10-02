from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from app.config import load_config
from app.db import create_db_and_tables
from app.routes import auth, pick, prompts, results
from app.services.generation import GenerationWorker

app = FastAPI(title="WhichModel?")
app.state.templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
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
