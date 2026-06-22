import argparse
import json
import sys
from pathlib import Path

import pytest

sys.path.append("/lab")

from skill_lab.cli import build_parser, compare_command
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


def test_compare_command_requires_skill_path_for_external_treatment_repo(tmp_path, capsys):
    baseline = tmp_path / "baseline"
    task_pack = tmp_path / "task-pack"
    baseline.mkdir()
    task_pack.mkdir()
    (baseline / "SKILL.md").write_text("# Baseline\n", encoding="utf-8")
    (task_pack / "taskpack.yaml").write_text("id: demo\n", encoding="utf-8")
    args = argparse.Namespace(
        baseline=str(baseline),
        treatment=None,
        treatment_repo="https://github.com/seasonsolt/ddia-skill",
        treatment_skill_path=None,
        task_pack=str(task_pack),
        api_url="http://localhost:8000",
        runs=1,
        network=False,
        timeout_seconds=300,
        output_dir=None,
    )

    assert compare_command(args) == 2
    assert "--treatment-skill-path is required when --treatment-repo is used" in capsys.readouterr().err


def test_compare_command_exports_artifacts_for_external_repo(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline"
    task_pack = tmp_path / "task-pack"
    external_skill = tmp_path / "external" / "skills" / "ddia-system-design"
    output_dir = tmp_path / "evidence"
    baseline.mkdir()
    task_pack.mkdir()
    external_skill.mkdir(parents=True)
    (baseline / "SKILL.md").write_text("# Baseline\n", encoding="utf-8")
    (task_pack / "taskpack.yaml").write_text("id: demo\n", encoding="utf-8")
    (external_skill / "SKILL.md").write_text("# DDIA\n", encoding="utf-8")
    (external_skill / "manifest.yaml").write_text(
        "id: ddia-system-design\nname: DDIA System Design\nentry: SKILL.md\n",
        encoding="utf-8",
    )

    class FakeExternalRepo:
        repo_url = "https://github.com/seasonsolt/ddia-skill"
        skill_path = "skills/ddia-system-design"
        skill_dir = external_skill
        commit = "0123456789abcdef0123456789abcdef01234567"

    class FakeClone:
        def __enter__(self):
            return FakeExternalRepo()

        def __exit__(self, exc_type, exc, traceback):
            return False

    def fake_clone_external_skill_repo(repo_url, skill_path, clone_root):
        assert repo_url == "https://github.com/seasonsolt/ddia-skill"
        assert skill_path == "skills/ddia-system-design"
        assert clone_root.name == "external-skills"
        return FakeClone()

    reports = iter(
        [
            {
                "eval_run_id": "run-b1",
                "status": "failed",
                "auto_score": 30,
                "final_score": 20,
                "pass_rate": 0,
                "scores": [{"details": {"sandbox_status": "failed"}}],
            },
            {
                "eval_run_id": "run-t1",
                "status": "passed",
                "auto_score": 80,
                "final_score": 60,
                "pass_rate": 1,
                "scores": [{"details": {"sandbox_status": "passed"}}],
            },
        ]
    )

    monkeypatch.setattr("skill_lab.cli.clone_external_skill_repo", fake_clone_external_skill_repo)
    monkeypatch.setattr("skill_lab.cli._run_eval_report", lambda args, skill_path, task_pack_path: next(reports))

    args = argparse.Namespace(
        baseline=str(baseline),
        treatment=None,
        treatment_repo="https://github.com/seasonsolt/ddia-skill",
        treatment_skill_path="skills/ddia-system-design",
        task_pack=str(task_pack),
        api_url="http://localhost:8000",
        runs=1,
        network=False,
        timeout_seconds=300,
        output_dir=str(output_dir),
    )

    assert compare_command(args) == 0
    assert (output_dir / "comparison.json").exists()
    assert (output_dir / "comparison.md").exists()
    payload = json.loads((output_dir / "comparison.json").read_text(encoding="utf-8"))
    assert payload["evidence"]["treatment_repo_url"] == "https://github.com/seasonsolt/ddia-skill"
    assert payload["evidence"]["treatment_repo_commit"] == "0123456789abcdef0123456789abcdef01234567"
    assert payload["evidence"]["treatment_skill_path"] == "skills/ddia-system-design"
    assert payload["verdict"] == "useful"


def test_compare_command_reports_external_repo_validation_error(tmp_path, monkeypatch, capsys):
    baseline = tmp_path / "baseline"
    task_pack = tmp_path / "task-pack"
    baseline.mkdir()
    task_pack.mkdir()
    (baseline / "SKILL.md").write_text("# Baseline\n", encoding="utf-8")
    (task_pack / "taskpack.yaml").write_text("id: demo\n", encoding="utf-8")

    def fake_clone_external_skill_repo(repo_url, skill_path, clone_root):
        raise ValueError("External skill path 'skills/missing' does not contain SKILL.md")

    monkeypatch.setattr("skill_lab.cli.clone_external_skill_repo", fake_clone_external_skill_repo)
    args = argparse.Namespace(
        baseline=str(baseline),
        treatment=None,
        treatment_repo="https://github.com/seasonsolt/ddia-skill",
        treatment_skill_path="skills/missing",
        task_pack=str(task_pack),
        api_url="http://localhost:8000",
        runs=1,
        network=False,
        timeout_seconds=300,
        output_dir=None,
    )

    assert compare_command(args) == 2
    stderr = capsys.readouterr().err
    assert "External skill path 'skills/missing' does not contain SKILL.md" in stderr
    assert "Eval comparison failed" not in stderr


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
