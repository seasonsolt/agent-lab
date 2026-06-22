from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvidenceMetadata:
    evaluator: str
    treatment_repo_url: str | None
    treatment_repo_commit: str | None
    treatment_skill_path: str | None
    baseline_skill_path: str
    task_pack_path: str
    reproduction_command: str


def write_comparison_artifacts(
    summary: dict[str, Any],
    metadata: EvidenceMetadata,
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {**summary, "evidence": asdict(metadata)}
    json_path = output_dir / "comparison.json"
    markdown_path = output_dir / "comparison.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_comparison_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_comparison_markdown(payload: dict[str, Any]) -> str:
    evidence = payload["evidence"]
    generated_at = datetime.now(timezone.utc).isoformat()
    baseline = payload["baseline"]
    treatment = payload["treatment"]
    score_lift = payload["score_lift"]
    lines = [
        "# Agent Lab Skill Comparison Evidence",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Evaluator: `{evidence['evaluator']}`",
        f"- Treatment repo: `{evidence['treatment_repo_url']}`",
        f"- Treatment commit: `{evidence['treatment_repo_commit']}`",
        f"- Treatment skill path: `{evidence['treatment_skill_path']}`",
        f"- Baseline skill path: `{evidence['baseline_skill_path']}`",
        f"- Task pack path: `{evidence['task_pack_path']}`",
        f"- Verdict: `{payload['verdict']}`",
        "",
        "## Summary",
        "",
        "| Metric | Baseline | Treatment | Delta |",
        "| --- | ---: | ---: | ---: |",
        f"| Mean auto score | {baseline['mean_auto_score']} | {treatment['mean_auto_score']} | {score_lift['auto_score']} |",
        f"| Mean final score | {baseline['mean_final_score']} | {treatment['mean_final_score']} | {score_lift['final_score']} |",
        f"| Mean pass rate | {baseline['mean_pass_rate']} | {treatment['mean_pass_rate']} | {payload['pass_rate_delta']} |",
        f"| Error rate | {baseline['error_rate']} | {treatment['error_rate']} |  |",
        f"| Timeout rate | {baseline['timeout_rate']} | {treatment['timeout_rate']} |  |",
        "",
        "## Run IDs",
        "",
        f"- Baseline: `{', '.join(baseline['run_ids'])}`",
        f"- Treatment: `{', '.join(treatment['run_ids'])}`",
        "",
        "## Reproduction",
        "",
        "```bash",
        evidence["reproduction_command"],
        "```",
        "",
        "## Limitations",
        "",
        "This is repeated Agent Lab comparison evidence, not statistical proof. Model output variance, model/provider configuration, task-pack coverage, and sandbox timeouts can affect the result.",
        "",
    ]
    return "\n".join(lines)
