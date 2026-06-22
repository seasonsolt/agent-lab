from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import orchestrator
from .eval_lab.routing import router as eval_lab_router


router = APIRouter()
router.include_router(eval_lab_router)


class RunRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4000)


class RunResponse(BaseModel):
    success: bool
    output: str
    raw: Dict[str, Any]


@router.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@router.post("/runs", response_model=RunResponse)
def run_agent(payload: RunRequest) -> RunResponse:
    try:
        from .orchestrator import _build_langfuse_callbacks

        result = orchestrator.get_agent().invoke(
            {"messages": [{"role": "user", "content": payload.task}]},
            config={"callbacks": _build_langfuse_callbacks()},
        )
        return RunResponse(success=True, output=orchestrator.extract_response(result), raw={"result": result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
