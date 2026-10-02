from fastapi import FastAPI

from app.db import create_db_and_tables


app = FastAPI(title="WhichModel?")


@app.on_event("startup")
def startup() -> None:
    create_db_and_tables()


@app.get("/health")
def health():
    return {"status": "ok"}
