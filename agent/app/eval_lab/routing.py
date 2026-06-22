from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException

from app.config import Settings

from .paths import ensure_child_path
from .report import build_report_from_records
from .schemas import EvalReport, EvalRunCreateRequest, EvalRunCreateResponse, EvalRunRecord

if TYPE_CHECKING:
    from .repository import EvalRepository
    from .runner import EvalRunner


router = APIRouter(prefix="/eval-runs", tags=["eval-runs"])


def get_repo() -> EvalRepository:
    from .repository import EvalRepository

    return EvalRepository()


def get_runner() -> EvalRunner:
    from .runner import EvalRunner

    return EvalRunner()


def _project_path(value: str) -> Path:
    root = Path(Settings.eval_lab_host_project_dir)
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        return ensure_child_path(root, candidate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("", response_model=EvalRunCreateResponse)
def create_eval_run(payload: EvalRunCreateRequest) -> EvalRunCreateResponse:
    skill_dir = _project_path(payload.skill_path)
    task_pack_dir = _project_path(payload.task_pack_path)
    network_enabled = (
        Settings.eval_lab_network_enabled if payload.network_enabled is None else payload.network_enabled
    )
    timeout_seconds = (
        Settings.eval_lab_task_timeout_seconds
        if payload.timeout_seconds is None
        else payload.timeout_seconds
    )

    try:
        run = get_runner().run(
            skill_dir=skill_dir,
            task_pack_dir=task_pack_dir,
            network_enabled=network_enabled,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return EvalRunCreateResponse(
        id=run["id"],
        status=run["status"],
        report_url=f"/eval-runs/{run['id']}/report",
    )


@router.get("/{run_id}", response_model=EvalRunRecord)
def get_eval_run(run_id: str) -> EvalRunRecord:
    try:
        return EvalRunRecord.model_validate(get_repo().get_eval_run(run_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Eval run '{run_id}' not found") from exc


@router.get("/{run_id}/report", response_model=EvalReport)
def get_eval_report(run_id: str) -> EvalReport:
    repo = get_repo()
    try:
        run = repo.get_eval_run(run_id)
        skill = repo.get_skill(run["skill_id"])
        task_pack = repo.get_task_pack(run["task_pack_id"])
        scores = repo.list_scores(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Eval resource not found: {exc}") from exc

    return build_report_from_records(run, skill, task_pack, scores)
