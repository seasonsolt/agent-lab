from __future__ import annotations

from typing import Any

from .schemas import EvalReport, ScoreRecord, Verdict, WorkflowNodeRecord


VALUE_SCORE_TYPES = ("rubric", "llm_judge", "human")


def _normalized_average(scores: list[ScoreRecord], score_type: str) -> float:
    typed_scores = [score for score in scores if score.score_type == score_type]
    if not typed_scores:
        return 0.0
    normalized = [score.score / score.max_score * 100 for score in typed_scores]
    return round(sum(normalized) / len(normalized), 2)


def _value_score(scores: list[ScoreRecord]) -> float:
    value_components = [
        _normalized_average(scores, score_type)
        for score_type in VALUE_SCORE_TYPES
        if any(score.score_type == score_type for score in scores)
    ]
    if not value_components:
        return 0.0
    return round(sum(value_components) / len(value_components), 2)


def _verdict(status: str, auto_score: float, value_score: float) -> Verdict:
    if status == "error":
        return "harmful"
    if auto_score >= 80 and value_score >= 60:
        return "useful"
    if auto_score >= 60 and value_score < 60:
        return "weak"
    if auto_score < 40:
        return "harmful"
    return "inconclusive"


def build_report_from_records(
    eval_run: dict[str, Any],
    skill: dict[str, Any],
    task_pack: dict[str, Any],
    scores: list[dict[str, Any]],
) -> EvalReport:
    score_records = [ScoreRecord.model_validate(score) for score in scores]
    workflow_nodes = [
        WorkflowNodeRecord.model_validate({**node, "task_id": score.get("task_id")})
        for score in scores
        for node in score.get("details", {}).get("workflow_nodes", [])
    ]
    auto_score = _normalized_average(score_records, "auto")
    value_score = _value_score(score_records)
    final_score = round(auto_score * 0.7 + value_score * 0.3, 2)
    auto_task_ids = {score.task_id for score in score_records if score.score_type == "auto"}
    passed_task_ids = {
        score.task_id
        for score in score_records
        if score.score_type == "auto" and score.score / score.max_score >= 0.6
    }
    pass_rate = round(len(passed_task_ids) / len(auto_task_ids), 2) if auto_task_ids else 0.0

    return EvalReport(
        eval_run_id=eval_run["id"],
        skill={
            "id": skill["id"],
            "name": skill["name"],
            "hash": skill["version_hash"],
            "tags": skill.get("manifest", {}).get("tags", []),
        },
        task_pack={
            "id": task_pack["id"],
            "name": task_pack["name"],
            "domain": task_pack["domain"],
            "hash": task_pack["version_hash"],
        },
        status=eval_run["status"],
        pass_rate=pass_rate,
        final_score=final_score,
        auto_score=auto_score,
        value_score=value_score,
        scores=score_records,
        workflow_nodes=workflow_nodes,
        trace_ids=eval_run.get("langfuse_trace_ids", []),
        verdict=_verdict(eval_run["status"], auto_score, value_score),
        error=eval_run.get("error"),
    )
