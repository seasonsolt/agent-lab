from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .comparison import summarize_comparison


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
    if args.treatment_repo:
        print("--treatment-repo compare is not implemented yet", file=sys.stderr)
        return 2

    baseline_path = Path(args.baseline).resolve()
    treatment_path = Path(args.treatment).resolve()
    task_pack_path = Path(args.task_pack).resolve()
    for skill_path in (baseline_path, treatment_path):
        validation_error = _validate_skill_and_task_pack(skill_path, task_pack_path)
        if validation_error is not None:
            print(validation_error, file=sys.stderr)
            return 2
    if args.runs < 1:
        print("--runs must be greater than or equal to 1", file=sys.stderr)
        return 2

    try:
        baseline_reports = [
            _run_eval_report(args, baseline_path, task_pack_path)
            for _ in range(args.runs)
        ]
        treatment_reports = [
            _run_eval_report(args, treatment_path, task_pack_path)
            for _ in range(args.runs)
        ]
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"Eval comparison failed: {exc}", file=sys.stderr)
        return 1

    summary = summarize_comparison(
        baseline_skill=baseline_path.name,
        treatment_skill=treatment_path.name,
        task_pack=task_pack_path.name,
        baseline_reports=baseline_reports,
        treatment_reports=treatment_reports,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


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
