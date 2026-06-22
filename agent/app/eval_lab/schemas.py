from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


RunStatus = Literal["queued", "running", "passed", "failed", "error"]
ScoreType = Literal["auto", "rubric", "llm_judge", "human"]
Verdict = Literal["useful", "weak", "harmful", "inconclusive"]


class SkillManifest(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    entry: str = "SKILL.md"
    tags: list[str] = Field(default_factory=list)


class TaskSpec(BaseModel):
    id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    fixture: str = Field(min_length=1)
    expected: str = Field(min_length=1)
    scorer: str = Field(min_length=1)
    max_score: float = Field(gt=0)


class TaskPackManifest(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    tasks: list[TaskSpec] = Field(min_length=1)


class EvalRunCreateRequest(BaseModel):
    skill_path: str = Field(min_length=1)
    task_pack_path: str = Field(min_length=1)
    network_enabled: bool | None = None
    timeout_seconds: int | None = Field(default=None, gt=0)


class EvalRunCreateResponse(BaseModel):
    id: str
    status: RunStatus
    report_url: str


class ScoreRecord(BaseModel):
    task_id: str
    score_type: ScoreType
    score: float
    max_score: float = Field(gt=0)
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_score_bounds(self) -> "ScoreRecord":
        if self.score < 0:
            raise ValueError("score must be greater than or equal to 0")
        if self.score > self.max_score:
            raise ValueError("score must be less than or equal to max_score")
        return self


class EvalRunRecord(BaseModel):
    id: str
    skill_id: str
    task_pack_id: str
    status: RunStatus
    sandbox_container_id: str | None = None
    langfuse_trace_ids: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


class EvalReport(BaseModel):
    eval_run_id: str
    skill: dict[str, Any]
    task_pack: dict[str, Any]
    status: RunStatus
    pass_rate: float
    final_score: float
    auto_score: float
    value_score: float
    scores: list[ScoreRecord]
    trace_ids: list[str]
    verdict: Verdict
    error: str | None = None
