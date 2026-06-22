from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator


class ScorerResult(BaseModel):
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_score_bounds(self) -> "ScorerResult":
        if self.score > self.max_score:
            raise ValueError("score must be less than or equal to max_score")
        return self


def _error_result(details: dict[str, Any]) -> ScorerResult:
    return ScorerResult(score=0, max_score=100, details=details)


def run_scorer(
    scorer_path: Path,
    workspace_path: Path,
    expected_path: Path,
    agent_output_path: Path,
    timeout_seconds: int,
) -> ScorerResult:
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(scorer_path),
                "--workspace",
                str(workspace_path),
                "--expected",
                str(expected_path),
                "--agent-output",
                str(agent_output_path),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return _error_result(
            {
                "scorer_error": f"Scorer timed out after {timeout_seconds} seconds",
                "timeout": True,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
            }
        )

    if completed.returncode != 0:
        return _error_result(
            {
                "scorer_error": completed.stderr.strip() or completed.stdout.strip(),
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )

    try:
        payload = json.loads(completed.stdout)
        return ScorerResult.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        return _error_result(
            {
                "scorer_error": str(exc),
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
