import sys
from pathlib import Path

import pytest

sys.path.append("/lab")

from skill_lab.cli import build_parser
from skill_lab.comparison import summarize_comparison


def test_cli_parser_accepts_run_command():
    parser = build_parser()
    args = parser.parse_args(
        ["run", "--skill", "./skills/demo", "--task-pack", "./task_packs/basic", "--api-url", "http://localhost:8000"]
    )

    assert args.command == "run"
    assert args.skill == "./skills/demo"
    assert args.task_pack == "./task_packs/basic"
    assert args.api_url == "http://localhost:8000"


def test_cli_parser_accepts_compare_command():
    parser = build_parser()
    args = parser.parse_args(
        [
            "compare",
            "--baseline",
            "./skills/basic",
            "--treatment",
            "./skills/ddia",
            "--task-pack",
            "./task_packs/ddia",
            "--runs",
            "3",
        ]
    )

    assert args.command == "compare"
    assert args.baseline == "./skills/basic"
    assert args.treatment == "./skills/ddia"
    assert args.task_pack == "./task_packs/ddia"
    assert args.runs == 3


def test_cli_parser_accepts_external_treatment_repo_compare_command():
    parser = build_parser()
    args = parser.parse_args(
        [
            "compare",
            "--baseline",
            "./skills/example-coding-skill",
            "--treatment-repo",
            "https://github.com/seasonsolt/ddia-skill",
            "--treatment-skill-path",
            "skills/ddia-system-design",
            "--task-pack",
            "./task_packs/ddia-coding-real",
            "--output-dir",
            "./evaluation-results/ddia-skill",
            "--runs",
            "3",
        ]
    )

    assert args.command == "compare"
    assert args.baseline == "./skills/example-coding-skill"
    assert args.treatment_repo == "https://github.com/seasonsolt/ddia-skill"
    assert args.treatment_skill_path == "skills/ddia-system-design"
    assert args.treatment is None
    assert args.output_dir == "./evaluation-results/ddia-skill"
    assert args.runs == 3


def test_cli_parser_rejects_local_and_external_treatment_together():
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "compare",
                "--baseline",
                "./skills/example-coding-skill",
                "--treatment",
                "./skills/ddia-system-design",
                "--treatment-repo",
                "https://github.com/seasonsolt/ddia-skill",
                "--treatment-skill-path",
                "skills/ddia-system-design",
                "--task-pack",
                "./task_packs/ddia-coding-real",
            ]
        )


def test_summarize_comparison_reports_lift_and_verdict():
    baseline = [
        {
            "eval_run_id": "run-b1",
            "status": "failed",
            "auto_score": 30,
            "final_score": 21,
            "pass_rate": 0,
            "scores": [
                {
                    "details": {
                        "sandbox_status": "error",
                        "sandbox_error": "timed out",
                    }
                }
            ],
        },
        {
            "eval_run_id": "run-b2",
            "status": "failed",
            "auto_score": 40,
            "final_score": 28,
            "pass_rate": 0,
            "scores": [{"details": {"sandbox_status": "failed"}}],
        },
    ]
    treatment = [
        {
            "eval_run_id": "run-t1",
            "status": "passed",
            "auto_score": 80,
            "final_score": 56,
            "pass_rate": 1,
            "scores": [{"details": {"sandbox_status": "passed"}}],
        },
        {
            "eval_run_id": "run-t2",
            "status": "failed",
            "auto_score": 70,
            "final_score": 49,
            "pass_rate": 1,
            "scores": [{"details": {"sandbox_status": "passed"}}],
        },
    ]

    summary = summarize_comparison(
        baseline_skill="example-coding-skill",
        treatment_skill="ddia-system-design",
        task_pack="ddia-coding-real",
        baseline_reports=baseline,
        treatment_reports=treatment,
    )

    assert summary["score_lift"]["auto_score"] == 40
    assert summary["score_lift"]["final_score"] == 28
    assert summary["pass_rate_delta"] == 1
    assert summary["baseline"]["timeout_rate"] == 0.5
    assert summary["treatment"]["timeout_rate"] == 0
    assert summary["verdict"] == "useful"
