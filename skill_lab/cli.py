from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .comparison import summarize_comparison
from .evidence import EvidenceMetadata, write_comparison_artifacts
from .repo_ingestion import ExternalSkillRepo, clone_external_skill_repo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skill-lab")
    subcommands = parser.add_subparsers(dest="command", required=True)
    run = subcommands.add_parser("run")
    run.add_argument("--skill", required=True)
    run.add_argument("--task-pack", required=True)
    run.add_argument("--api-url", default="http://localhost:8000")
    run.add_argument("--network", action="store_true")
    run.add_argument("--timeout-seconds", type=int, default=None)
    compare = subcommands.add_parser("compare")
    compare.add_argument("--baseline", required=True)
    treatment = compare.add_mutually_exclusive_group(required=True)
    treatment.add_argument("--treatment")
    treatment.add_argument("--treatment-repo")
    compare.add_argument("--treatment-skill-path")
    compare.add_argument("--task-pack", required=True)
    compare.add_argument("--api-url", default="http://localhost:8000")
    compare.add_argument("--runs", type=int, default=3)
    compare.add_argument("--network", action="store_true")
    compare.add_argument("--timeout-seconds", type=int, default=None)
    compare.add_argument("--output-dir")
    return parser


def _request_json(url: str, payload: dict | None = None, timeout: int = 30) -> dict:
    request = Request(
        url,
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _build_url(api_url: str, path: str) -> str:
    return f"{api_url.rstrip('/')}{path}"


def run_command(args: argparse.Namespace) -> int:
    skill_path = Path(args.skill).resolve()
    task_pack_path = Path(args.task_pack).resolve()
    validation_error = _validate_skill_and_task_pack(skill_path, task_pack_path)
    if validation_error is not None:
        print(validation_error, file=sys.stderr)
        return 2

    try:
        created = _create_eval_run(args, skill_path, task_pack_path)
        report = _request_json(_build_url(args.api_url, created["report_url"]))
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"Eval request failed: {exc}", file=sys.stderr)
        return 1


def compare_command(args: argparse.Namespace) -> int:
    baseline_path = Path(args.baseline).resolve()
    task_pack_path = Path(args.task_pack).resolve()
    validation_error = _validate_skill_and_task_pack(baseline_path, task_pack_path)
    if validation_error is not None:
        print(validation_error, file=sys.stderr)
        return 2
    if args.runs < 1:
        print("--runs must be greater than or equal to 1", file=sys.stderr)
        return 2

    try:
        if args.treatment_repo:
            if not args.treatment_skill_path:
                print("--treatment-skill-path is required when --treatment-repo is used", file=sys.stderr)
                return 2
            with clone_external_skill_repo(
                args.treatment_repo,
                args.treatment_skill_path,
                clone_root=_external_clone_root(),
            ) as external:
                summary = _compare_with_treatment_path(args, baseline_path, external.skill_dir, task_pack_path)
                metadata = _build_evidence_metadata(args, baseline_path, task_pack_path, external=external)
                _write_artifacts_if_requested(args, summary, metadata)
        else:
            treatment_path = Path(args.treatment).resolve()
            validation_error = _validate_skill_and_task_pack(treatment_path, task_pack_path)
            if validation_error is not None:
                print(validation_error, file=sys.stderr)
                return 2
            summary = _compare_with_treatment_path(args, baseline_path, treatment_path, task_pack_path)
            metadata = _build_evidence_metadata(
                args,
                baseline_path,
                task_pack_path,
                treatment_skill_path=str(treatment_path),
            )
            _write_artifacts_if_requested(args, summary, metadata)
    except (HTTPError, URLError, TimeoutError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"Eval comparison failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _compare_with_treatment_path(
    args: argparse.Namespace,
    baseline_path: Path,
    treatment_path: Path,
    task_pack_path: Path,
) -> dict[str, Any]:
    baseline_reports = [
        _run_eval_report(args, baseline_path, task_pack_path)
        for _ in range(args.runs)
    ]
    treatment_reports = [
        _run_eval_report(args, treatment_path, task_pack_path)
        for _ in range(args.runs)
    ]
    summary = summarize_comparison(
        baseline_skill=baseline_path.name,
        treatment_skill=treatment_path.name,
        task_pack=task_pack_path.name,
        baseline_reports=baseline_reports,
        treatment_reports=treatment_reports,
    )
    return summary


def _write_artifacts_if_requested(
    args: argparse.Namespace,
    summary: dict[str, Any],
    metadata: EvidenceMetadata,
) -> None:
    if args.output_dir:
        write_comparison_artifacts(summary, metadata, Path(args.output_dir))


def _build_evidence_metadata(
    args: argparse.Namespace,
    baseline_path: Path,
    task_pack_path: Path,
    treatment_skill_path: str | None = None,
    external: ExternalSkillRepo | None = None,
) -> EvidenceMetadata:
    if external is not None:
        treatment_repo_url = external.repo_url
        treatment_repo_commit = external.commit
        evidence_treatment_skill_path = external.skill_path
    else:
        treatment_repo_url = None
        treatment_repo_commit = None
        if treatment_skill_path is None:
            raise ValueError("treatment_skill_path is required for local evidence metadata")
        evidence_treatment_skill_path = treatment_skill_path

    return EvidenceMetadata(
        evaluator="seasonsolt/agent-lab",
        treatment_repo_url=treatment_repo_url,
        treatment_repo_commit=treatment_repo_commit,
        treatment_skill_path=evidence_treatment_skill_path,
        baseline_skill_path=str(baseline_path),
        task_pack_path=str(task_pack_path),
        reproduction_command=_reproduction_command(args),
    )


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _external_clone_root() -> Path:
    return _project_root() / ".agent-lab" / "external-skills"


def _reproduction_command(args: argparse.Namespace) -> str:
    command = [
        "python3",
        "-m",
        "skill_lab.cli",
        "compare",
        "--baseline",
        args.baseline,
    ]
    if args.treatment_repo:
        command.extend(["--treatment-repo", args.treatment_repo])
        if args.treatment_skill_path:
            command.extend(["--treatment-skill-path", args.treatment_skill_path])
    else:
        command.extend(["--treatment", args.treatment])
    command.extend(
        [
            "--task-pack",
            args.task_pack,
            "--api-url",
            args.api_url,
            "--runs",
            str(args.runs),
        ]
    )
    if args.network:
        command.append("--network")
    if args.timeout_seconds is not None:
        command.extend(["--timeout-seconds", str(args.timeout_seconds)])
    if args.output_dir:
        command.extend(["--output-dir", args.output_dir])
    return shlex.join(command)


def _validate_skill_and_task_pack(skill_path: Path, task_pack_path: Path) -> str | None:
    if not (skill_path / "SKILL.md").exists():
        return f"Missing SKILL.md under {skill_path}"
    if not (task_pack_path / "taskpack.yaml").exists():
        return f"Missing taskpack.yaml under {task_pack_path}"
    return None


def _create_eval_run(args: argparse.Namespace, skill_path: Path, task_pack_path: Path) -> dict:
    timeout_seconds = args.timeout_seconds or 300
    return _request_json(
        _build_url(args.api_url, "/eval-runs"),
        {
            "skill_path": str(skill_path),
            "task_pack_path": str(task_pack_path),
            "network_enabled": args.network,
            "timeout_seconds": args.timeout_seconds,
        },
        timeout=timeout_seconds + 30,
    )


def _run_eval_report(args: argparse.Namespace, skill_path: Path, task_pack_path: Path) -> dict:
    created = _create_eval_run(args, skill_path, task_pack_path)
    return _request_json(_build_url(args.api_url, created["report_url"]))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return run_command(args)
    if args.command == "compare":
        return compare_command(args)
    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
