from __future__ import annotations

from collections import Counter
from typing import Any


def summarize_comparison(
    baseline_skill: str,
    treatment_skill: str,
    task_pack: str,
    baseline_reports: list[dict[str, Any]],
    treatment_reports: list[dict[str, Any]],
) -> dict[str, Any]:
    baseline = _summarize_arm(baseline_reports)
    treatment = _summarize_arm(treatment_reports)
    auto_lift = round(treatment["mean_auto_score"] - baseline["mean_auto_score"], 2)
    final_lift = round(treatment["mean_final_score"] - baseline["mean_final_score"], 2)
    pass_rate_delta = round(treatment["mean_pass_rate"] - baseline["mean_pass_rate"], 2)

    return {
        "baseline_skill": baseline_skill,
        "treatment_skill": treatment_skill,
        "task_pack": task_pack,
        "run_count": {
            "baseline": len(baseline_reports),
            "treatment": len(treatment_reports),
        },
        "baseline": baseline,
        "treatment": treatment,
        "score_lift": {
            "auto_score": auto_lift,
            "final_score": final_lift,
        },
        "pass_rate_delta": pass_rate_delta,
        "verdict": _comparison_verdict(final_lift, auto_lift, baseline, treatment),
    }


def _summarize_arm(reports: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "run_ids": [report["eval_run_id"] for report in reports],
        "mean_auto_score": _mean([report.get("auto_score", 0) for report in reports]),
        "mean_final_score": _mean([report.get("final_score", 0) for report in reports]),
        "mean_pass_rate": _mean([report.get("pass_rate", 0) for report in reports]),
        "status_counts": dict(Counter(report.get("status", "unknown") for report in reports)),
        "error_rate": _rate(reports, _report_has_error),
        "timeout_rate": _rate(reports, _report_has_timeout),
    }


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(float(value) for value in values) / len(values), 2)


def _rate(reports: list[dict[str, Any]], predicate) -> float:
    if not reports:
        return 0.0
    return round(sum(1 for report in reports if predicate(report)) / len(reports), 2)


def _report_has_error(report: dict[str, Any]) -> bool:
    if report.get("status") == "error":
        return True
    return any(score.get("details", {}).get("sandbox_status") == "error" for score in report.get("scores", []))


def _report_has_timeout(report: dict[str, Any]) -> bool:
    if "timed out" in str(report.get("error", "")).lower():
        return True
    return any(
        "timed out" in str(score.get("details", {}).get("sandbox_error", "")).lower()
        for score in report.get("scores", [])
    )


def _comparison_verdict(
    final_lift: float,
    auto_lift: float,
    baseline: dict[str, Any],
    treatment: dict[str, Any],
) -> str:
    if final_lift <= -5 or treatment["timeout_rate"] > baseline["timeout_rate"] + 0.2:
        return "harmful"
    if final_lift >= 10 and auto_lift >= 10 and treatment["timeout_rate"] <= baseline["timeout_rate"]:
        return "useful"
    if final_lift > 0 or auto_lift > 0:
        return "weak"
    return "inconclusive"
