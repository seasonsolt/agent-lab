from __future__ import annotations

import logging

from fastapi import FastAPI

from .config import Settings
from .eval_lab.db import init_schema
from .routing import router


logger = logging.getLogger(__name__)

app = FastAPI(title="Coding Agent", version="0.1.1")
app.include_router(router)


@app.on_event("startup")
def startup() -> None:
    try:
        init_schema()
    except Exception:
        logger.exception("Failed to initialize eval lab schema")


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "coding-agent",
        "version": "0.1.1",
        "workspace": Settings.workspace,
    }
