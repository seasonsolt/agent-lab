# Agent Lab DDIA Skill Evidence Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repeatable evidence bridge where Agent Lab evaluates `seasonsolt/ddia-skill` from GitHub and DDIA Skill cites the resulting Agent Lab comparison artifacts.

**Architecture:** Extend the existing host-side `skill-lab compare` command with external treatment repo ingestion and evidence artifact export. Keep evaluation execution inside the current Eval API and Docker sandbox path. Add DDIA Skill documentation and static checks that reference Agent Lab artifacts as external evidence.

**Tech Stack:** Python 3.12, argparse, urllib, subprocess git calls, pathlib, JSON, Markdown, pytest/unittest, Docker Compose, GitHub repos `seasonsolt/agent-lab` and `seasonsolt/ddia-skill`.

---

## Scope Check

This plan covers two repositories but one cohesive feature:

- `agent-lab`: generates external comparison evidence.
- `ddia-skill`: stores and cites the generated external evidence.

The plan does not add CI, UI, model-key management, marketplace ingestion, statistical analysis, or multi-model orchestration.
External repositories are cloned under Agent Lab's project root in a gitignored work directory because the Eval API rejects skill paths outside the configured project root.

## File Structure

Agent Lab repository root:

- Create `skill_lab/repo_ingestion.py`: clone an external Git repository, resolve a skill path safely, record commit SHA, and create a temporary manifest when missing.
- Create `skill_lab/evidence.py`: build evidence metadata, render Markdown, and write `comparison.json` plus `comparison.md`.
- Modify `skill_lab/cli.py`: add `--treatment-repo`, `--treatment-skill-path`, and `--output-dir`; integrate repo ingestion and evidence export into `compare`.
- Modify `.gitignore`: ignore `.agent-lab/`, the local external-repo clone workspace.
- Modify `agent/tests/eval_lab/test_cli.py`: parser tests for local and external treatment forms.
- Create `agent/tests/eval_lab/test_repo_ingestion.py`: unit tests using a local git repo.
- Create `agent/tests/eval_lab/test_evidence.py`: artifact rendering/export tests.
- Modify `README.md`: document external repo compare and evidence export.

DDIA Skill repository root:

- Create `evaluation/agent-lab/README.md`: describe Agent Lab as external evaluator.
- Create `evaluation/agent-lab/latest-comparison.json`: copied from Agent Lab generated artifact.
- Create `evaluation/agent-lab/latest-comparison.md`: copied from Agent Lab generated artifact.
- Create `tests/test_agent_lab_evidence.py`: static artifact and README link checks.
- Modify `README.md`: add External Agent Lab Evaluation section.

## Task 1: Agent Lab CLI Contract Tests

**Repo:** `/Users/Thin/Source/git/seasonsolt/agent-lab`

**Files:**
- Modify: `agent/tests/eval_lab/test_cli.py`
- Modify: `skill_lab/cli.py`

- [ ] **Step 1: Add failing parser tests**

Append these tests to `agent/tests/eval_lab/test_cli.py`:

```python
import pytest


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
```

- [ ] **Step 2: Run parser tests to verify failure**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_cli.py -q
```

Expected: fails because `build_parser()` does not define `--treatment-repo`, `--treatment-skill-path`, or `--output-dir`.

- [ ] **Step 3: Implement the minimal parser contract**

In `skill_lab/cli.py`, replace the current compare parser block:

```python
    compare = subcommands.add_parser("compare")
    compare.add_argument("--baseline", required=True)
    compare.add_argument("--treatment", required=True)
    compare.add_argument("--task-pack", required=True)
    compare.add_argument("--api-url", default="http://localhost:8000")
    compare.add_argument("--runs", type=int, default=3)
    compare.add_argument("--network", action="store_true")
    compare.add_argument("--timeout-seconds", type=int, default=None)
```

with:

```python
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
```

- [ ] **Step 4: Run parser tests to verify pass**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_cli.py -q
```

Expected: all existing CLI tests and the new parser tests pass.

- [ ] **Step 5: Commit parser contract**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
git add skill_lab/cli.py agent/tests/eval_lab/test_cli.py
git commit -m "feat: define external skill compare CLI contract"
```

## Task 2: External Repo Ingestion Helper

**Repo:** `/Users/Thin/Source/git/seasonsolt/agent-lab`

**Files:**
- Create: `skill_lab/repo_ingestion.py`
- Create: `agent/tests/eval_lab/test_repo_ingestion.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing repo-ingestion tests**

Create `agent/tests/eval_lab/test_repo_ingestion.py`:

```python
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.append("/lab")

from skill_lab.repo_ingestion import clone_external_skill_repo


def init_skill_repo(repo_dir: Path, include_manifest: bool = True) -> None:
    skill_dir = repo_dir / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Demo Skill\n", encoding="utf-8")
    if include_manifest:
        (skill_dir / "manifest.yaml").write_text(
            "id: demo-skill\nname: Demo Skill\nentry: SKILL.md\ntags:\n  - demo\n",
            encoding="utf-8",
        )
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True, text=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=agent-lab@example.test",
            "-c",
            "user.name=Agent Lab",
            "commit",
            "-m",
            "init skill",
        ],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )


def test_clone_external_skill_repo_resolves_skill_and_commit(tmp_path):
    repo_dir = tmp_path / "source"
    clone_root = tmp_path / "agent-lab-clones"
    repo_dir.mkdir()
    init_skill_repo(repo_dir)

    with clone_external_skill_repo(str(repo_dir), "skills/demo-skill", clone_root=clone_root) as external:
        assert external.repo_url == str(repo_dir)
        assert external.skill_path == "skills/demo-skill"
        assert external.skill_dir.name == "demo-skill"
        assert clone_root.resolve() in external.clone_dir.resolve().parents
        assert (external.skill_dir / "SKILL.md").exists()
        assert (external.skill_dir / "manifest.yaml").exists()
        assert len(external.commit) == 40


def test_clone_external_skill_repo_creates_temporary_manifest_when_missing(tmp_path):
    repo_dir = tmp_path / "source"
    clone_root = tmp_path / "agent-lab-clones"
    repo_dir.mkdir()
    init_skill_repo(repo_dir, include_manifest=False)

    with clone_external_skill_repo(str(repo_dir), "skills/demo-skill", clone_root=clone_root) as external:
        manifest = (external.skill_dir / "manifest.yaml").read_text(encoding="utf-8")

    assert "id: demo-skill" in manifest
    assert "name: demo-skill" in manifest
    assert "entry: SKILL.md" in manifest


def test_clone_external_skill_repo_rejects_path_outside_clone(tmp_path):
    repo_dir = tmp_path / "source"
    clone_root = tmp_path / "agent-lab-clones"
    repo_dir.mkdir()
    init_skill_repo(repo_dir)

    with pytest.raises(ValueError, match="outside cloned repository"):
        with clone_external_skill_repo(str(repo_dir), "../escape", clone_root=clone_root):
            pass
```

- [ ] **Step 2: Run repo-ingestion tests to verify failure**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_repo_ingestion.py -q
```

Expected: fails with `ModuleNotFoundError: No module named 'skill_lab.repo_ingestion'`.

- [ ] **Step 3: Implement repo ingestion**

Add this entry to `.gitignore` if it is not already present:

```gitignore
.agent-lab/
```

Create `skill_lab/repo_ingestion.py`:

```python
from __future__ import annotations

import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Iterator


@dataclass(frozen=True)
class ExternalSkillRepo:
    repo_url: str
    skill_path: str
    clone_dir: Path
    skill_dir: Path
    commit: str


@contextmanager
def clone_external_skill_repo(
    repo_url: str,
    skill_path: str,
    clone_root: Path,
) -> Iterator[ExternalSkillRepo]:
    clone_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="repo-", dir=clone_root) as tmp:
        clone_dir = Path(tmp) / "repo"
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(clone_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
        commit = _git_commit(clone_dir)
        skill_dir = _resolve_child_path(clone_dir, skill_path)
        if not (skill_dir / "SKILL.md").is_file():
            raise ValueError(f"External skill path '{skill_path}' does not contain SKILL.md")
        _ensure_manifest(skill_dir)
        yield ExternalSkillRepo(
            repo_url=repo_url,
            skill_path=skill_path,
            clone_dir=clone_dir,
            skill_dir=skill_dir,
            commit=commit,
        )


def _git_commit(repo_dir: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _resolve_child_path(root: Path, relative_path: str) -> Path:
    if Path(relative_path).is_absolute():
        raise ValueError("External skill path must be relative")
    resolved_root = root.resolve()
    candidate = (root / relative_path).resolve()
    if candidate == resolved_root or resolved_root in candidate.parents:
        return candidate
    raise ValueError(f"External skill path '{relative_path}' is outside cloned repository")


def _ensure_manifest(skill_dir: Path) -> None:
    manifest_path = skill_dir / "manifest.yaml"
    if manifest_path.exists():
        return
    skill_id = skill_dir.name
    manifest_path.write_text(
        f"id: {skill_id}\nname: {skill_id}\nentry: SKILL.md\ntags:\n  - external\n",
        encoding="utf-8",
    )
```

- [ ] **Step 4: Run repo-ingestion tests to verify pass**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_repo_ingestion.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit repo ingestion**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
git add .gitignore skill_lab/repo_ingestion.py agent/tests/eval_lab/test_repo_ingestion.py
git commit -m "feat: clone external skill repositories"
```

## Task 3: Evidence Artifact Export

**Repo:** `/Users/Thin/Source/git/seasonsolt/agent-lab`

**Files:**
- Create: `skill_lab/evidence.py`
- Create: `agent/tests/eval_lab/test_evidence.py`

- [ ] **Step 1: Write failing evidence export tests**

Create `agent/tests/eval_lab/test_evidence.py`:

```python
from __future__ import annotations

import json
import sys

sys.path.append("/lab")

from skill_lab.evidence import EvidenceMetadata, write_comparison_artifacts


def sample_summary() -> dict:
    return {
        "baseline_skill": "example-coding-skill",
        "treatment_skill": "ddia-system-design",
        "task_pack": "ddia-coding-real",
        "run_count": {"baseline": 2, "treatment": 2},
        "baseline": {
            "run_ids": ["run-b1", "run-b2"],
            "mean_auto_score": 33.33,
            "mean_final_score": 23.33,
            "mean_pass_rate": 0.0,
            "status_counts": {"failed": 2},
            "error_rate": 0.5,
            "timeout_rate": 0.5,
        },
        "treatment": {
            "run_ids": ["run-t1", "run-t2"],
            "mean_auto_score": 66.67,
            "mean_final_score": 46.67,
            "mean_pass_rate": 1.0,
            "status_counts": {"failed": 1, "passed": 1},
            "error_rate": 0.0,
            "timeout_rate": 0.0,
        },
        "score_lift": {"auto_score": 33.34, "final_score": 23.34},
        "pass_rate_delta": 1.0,
        "verdict": "useful",
    }


def test_write_comparison_artifacts_writes_json_and_markdown(tmp_path):
    metadata = EvidenceMetadata(
        evaluator="seasonsolt/agent-lab",
        treatment_repo_url="https://github.com/seasonsolt/ddia-skill",
        treatment_repo_commit="0123456789abcdef0123456789abcdef01234567",
        treatment_skill_path="skills/ddia-system-design",
        baseline_skill_path="./skills/example-coding-skill",
        task_pack_path="./task_packs/ddia-coding-real",
        reproduction_command="python3 -m skill_lab.cli compare --baseline ./skills/example-coding-skill",
    )

    json_path, markdown_path = write_comparison_artifacts(sample_summary(), metadata, tmp_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert payload["evidence"]["treatment_repo_url"] == "https://github.com/seasonsolt/ddia-skill"
    assert payload["evidence"]["treatment_repo_commit"] == "0123456789abcdef0123456789abcdef01234567"
    assert payload["verdict"] == "useful"
    assert "Agent Lab Skill Comparison Evidence" in markdown
    assert "https://github.com/seasonsolt/ddia-skill" in markdown
    assert "0123456789abcdef0123456789abcdef01234567" in markdown
    assert "run-b1" in markdown
    assert "run-t2" in markdown
    assert "python3 -m skill_lab.cli compare" in markdown
    assert "not statistical proof" in markdown
```

- [ ] **Step 2: Run evidence tests to verify failure**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_evidence.py -q
```

Expected: fails with `ModuleNotFoundError: No module named 'skill_lab.evidence'`.

- [ ] **Step 3: Implement evidence artifact export**

Create `skill_lab/evidence.py`:

```python
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
```

- [ ] **Step 4: Run evidence tests to verify pass**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_evidence.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit evidence export**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
git add skill_lab/evidence.py agent/tests/eval_lab/test_evidence.py
git commit -m "feat: export comparison evidence artifacts"
```

## Task 4: CLI Integration For External Treatment Repo And Output Directory

**Repo:** `/Users/Thin/Source/git/seasonsolt/agent-lab`

**Files:**
- Modify: `skill_lab/cli.py`
- Modify: `agent/tests/eval_lab/test_cli.py`

- [ ] **Step 1: Add CLI command behavior tests**

Append these tests to `agent/tests/eval_lab/test_cli.py`:

```python
from argparse import Namespace
from skill_lab.cli import compare_command


def test_compare_command_requires_treatment_skill_path_for_external_repo(monkeypatch, tmp_path, capsys):
    baseline = tmp_path / "baseline"
    task_pack = tmp_path / "pack"
    baseline.mkdir()
    task_pack.mkdir()
    (baseline / "SKILL.md").write_text("# Baseline\n", encoding="utf-8")
    (task_pack / "taskpack.yaml").write_text("id: pack\nname: Pack\ndomain: coding\ntasks: []\n", encoding="utf-8")
    args = Namespace(
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

    exit_code = compare_command(args)

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--treatment-skill-path is required" in captured.err


def test_compare_command_exports_artifacts_for_external_repo(monkeypatch, tmp_path):
    baseline = tmp_path / "baseline"
    task_pack = tmp_path / "pack"
    external_skill = tmp_path / "external" / "skills" / "ddia-system-design"
    output_dir = tmp_path / "out"
    baseline.mkdir()
    task_pack.mkdir()
    external_skill.mkdir(parents=True)
    (baseline / "SKILL.md").write_text("# Baseline\n", encoding="utf-8")
    (task_pack / "taskpack.yaml").write_text("id: pack\nname: Pack\ndomain: coding\ntasks: []\n", encoding="utf-8")
    (external_skill / "SKILL.md").write_text("# DDIA\n", encoding="utf-8")
    (external_skill / "manifest.yaml").write_text("id: ddia\nname: DDIA\nentry: SKILL.md\n", encoding="utf-8")

    class FakeExternal:
        repo_url = "https://github.com/seasonsolt/ddia-skill"
        skill_path = "skills/ddia-system-design"
        skill_dir = external_skill
        commit = "0123456789abcdef0123456789abcdef01234567"

    class FakeContext:
        def __enter__(self):
            return FakeExternal()

        def __exit__(self, exc_type, exc, tb):
            return False

    reports = [
        {
            "eval_run_id": "baseline-run",
            "status": "failed",
            "auto_score": 30,
            "final_score": 21,
            "pass_rate": 0,
            "scores": [{"details": {"sandbox_status": "failed"}}],
        },
        {
            "eval_run_id": "treatment-run",
            "status": "passed",
            "auto_score": 80,
            "final_score": 56,
            "pass_rate": 1,
            "scores": [{"details": {"sandbox_status": "passed"}}],
        },
    ]

    monkeypatch.setattr("skill_lab.cli.clone_external_skill_repo", lambda repo_url, skill_path, clone_root: FakeContext())
    monkeypatch.setattr("skill_lab.cli._run_eval_report", lambda args, skill_path, task_pack_path: reports.pop(0))

    args = Namespace(
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

    exit_code = compare_command(args)

    assert exit_code == 0
    assert (output_dir / "comparison.json").exists()
    assert (output_dir / "comparison.md").exists()
```

- [ ] **Step 2: Run CLI tests to verify failure**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_cli.py -q
```

Expected: fails because `compare_command` does not support external repo validation, artifact export, or the new imports.

- [ ] **Step 3: Implement CLI integration**

Modify `skill_lab/cli.py`:

```python
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .comparison import summarize_comparison
from .evidence import EvidenceMetadata, write_comparison_artifacts
from .repo_ingestion import clone_external_skill_repo


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
    if args.treatment_repo and not args.treatment_skill_path:
        print("--treatment-skill-path is required when --treatment-repo is used", file=sys.stderr)
        return 2

    try:
        if args.treatment_repo:
            with clone_external_skill_repo(
                args.treatment_repo,
                args.treatment_skill_path,
                clone_root=_external_clone_root(),
            ) as external:
                return _compare_with_treatment_path(args, baseline_path, external.skill_dir, task_pack_path, external)
        treatment_path = Path(args.treatment).resolve()
        validation_error = _validate_skill_and_task_pack(treatment_path, task_pack_path)
        if validation_error is not None:
            print(validation_error, file=sys.stderr)
            return 2
        return _compare_with_treatment_path(args, baseline_path, treatment_path, task_pack_path, None)
    except (HTTPError, URLError, TimeoutError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"Eval comparison failed: {exc}", file=sys.stderr)
        return 1


def _compare_with_treatment_path(
    args: argparse.Namespace,
    baseline_path: Path,
    treatment_path: Path,
    task_pack_path: Path,
    external,
) -> int:
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
    if args.output_dir:
        metadata = _build_evidence_metadata(args, baseline_path, task_pack_path, external)
        write_comparison_artifacts(summary, metadata, Path(args.output_dir))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _build_evidence_metadata(
    args: argparse.Namespace,
    baseline_path: Path,
    task_pack_path: Path,
    external,
) -> EvidenceMetadata:
    return EvidenceMetadata(
        evaluator="seasonsolt/agent-lab",
        treatment_repo_url=None if external is None else external.repo_url,
        treatment_repo_commit=None if external is None else external.commit,
        treatment_skill_path=None if external is None else external.skill_path,
        baseline_skill_path=str(baseline_path),
        task_pack_path=str(task_pack_path),
        reproduction_command=_reproduction_command(args),
    )


def _external_clone_root() -> Path:
    return _project_root() / ".agent-lab" / "external-skills"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _reproduction_command(args: argparse.Namespace) -> str:
    parts = [
        "python3",
        "-m",
        "skill_lab.cli",
        "compare",
        "--baseline",
        args.baseline,
    ]
    if args.treatment_repo:
        parts.extend(["--treatment-repo", args.treatment_repo, "--treatment-skill-path", args.treatment_skill_path])
    else:
        parts.extend(["--treatment", args.treatment])
    parts.extend(["--task-pack", args.task_pack, "--api-url", args.api_url, "--runs", str(args.runs)])
    if args.network:
        parts.append("--network")
    if args.timeout_seconds is not None:
        parts.extend(["--timeout-seconds", str(args.timeout_seconds)])
    if args.output_dir:
        parts.extend(["--output-dir", args.output_dir])
    return " ".join(parts)


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
```

- [ ] **Step 4: Run CLI tests to verify pass**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_cli.py tests/eval_lab/test_repo_ingestion.py tests/eval_lab/test_evidence.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit CLI integration**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
git add skill_lab/cli.py agent/tests/eval_lab/test_cli.py
git commit -m "feat: compare external treatment skills"
```

## Task 5: Agent Lab Documentation And Full Verification

**Repo:** `/Users/Thin/Source/git/seasonsolt/agent-lab`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document external repo comparison**

Append this example under the existing Skill Evaluation Lab compare example in `README.md`:

````markdown

Compare a skill directly from a GitHub repository and export evidence artifacts:

When `--treatment-repo` is used, Agent Lab clones the repository under the
local `.agent-lab/external-skills/` workspace. That directory is ignored by git
and keeps the cloned skill inside the Eval API project-root boundary.

```bash
python3 -m skill_lab.cli compare \
  --baseline ./skills/example-coding-skill \
  --treatment-repo https://github.com/seasonsolt/ddia-skill \
  --treatment-skill-path skills/ddia-system-design \
  --task-pack ./task_packs/ddia-coding-real \
  --api-url http://localhost:8000 \
  --runs 3 \
  --network \
  --timeout-seconds 300 \
  --output-dir ./evaluation-results/ddia-skill
```

The output directory contains:

- `comparison.json`: machine-readable comparison evidence.
- `comparison.md`: human-readable evidence suitable for linking from the evaluated skill repository.
````

- [ ] **Step 2: Run full test suite**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
docker compose run --build --rm coding-agent pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Commit documentation**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
git add README.md
git commit -m "docs: explain external skill evidence export"
```

## Task 6: Generate Agent Lab Evidence For DDIA Skill

**Repo:** `/Users/Thin/Source/git/seasonsolt/agent-lab`

**Files:**
- Generated outside repo first: `/tmp/agent-lab-ddia-evidence/comparison.json`
- Generated outside repo first: `/tmp/agent-lab-ddia-evidence/comparison.md`

- [ ] **Step 1: Ensure Agent Lab stack is running**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
mkdir -p /tmp/agent-lab-runs
docker compose up -d --build
curl -sS http://localhost:8000/health
```

Expected health response:

```json
{"status":"ok"}
```

- [ ] **Step 2: Generate DDIA Skill comparison evidence**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
rm -rf /tmp/agent-lab-ddia-evidence
python3 -m skill_lab.cli compare \
  --baseline ./skills/example-coding-skill \
  --treatment-repo https://github.com/seasonsolt/ddia-skill \
  --treatment-skill-path skills/ddia-system-design \
  --task-pack ./task_packs/ddia-coding-real \
  --api-url http://localhost:8000 \
  --runs 3 \
  --network \
  --timeout-seconds 300 \
  --output-dir /tmp/agent-lab-ddia-evidence
```

Expected:

- Command exits `0`.
- `/tmp/agent-lab-ddia-evidence/comparison.json` exists.
- `/tmp/agent-lab-ddia-evidence/comparison.md` exists.

If the command fails because the model provider or sandbox runtime is unavailable, stop and report the blocker. Do not fabricate evidence files.

- [ ] **Step 3: Inspect generated evidence**

Run:

```bash
python3 -m json.tool /tmp/agent-lab-ddia-evidence/comparison.json >/tmp/agent-lab-ddia-evidence/pretty.json
sed -n '1,220p' /tmp/agent-lab-ddia-evidence/comparison.md
```

Expected:

- JSON contains `evidence.treatment_repo_url`.
- JSON contains `evidence.treatment_repo_commit`.
- Markdown contains `Agent Lab Skill Comparison Evidence`.
- Markdown contains `not statistical proof`.

## Task 7: DDIA Skill Evidence Documentation And Static Checks

**Repo:** `/Users/Thin/Source/git/seasonsolt/ddia-skill`

**Files:**
- Create: `evaluation/agent-lab/README.md`
- Create: `evaluation/agent-lab/latest-comparison.json`
- Create: `evaluation/agent-lab/latest-comparison.md`
- Create: `tests/test_agent_lab_evidence.py`
- Modify: `README.md`

- [ ] **Step 1: Clone or update DDIA Skill repo**

Run:

```bash
mkdir -p /Users/Thin/Source/git/seasonsolt
if [ ! -d /Users/Thin/Source/git/seasonsolt/ddia-skill/.git ]; then
  git clone https://github.com/seasonsolt/ddia-skill /Users/Thin/Source/git/seasonsolt/ddia-skill
fi
cd /Users/Thin/Source/git/seasonsolt/ddia-skill
git pull --ff-only
```

Expected: repo exists and is up to date.

- [ ] **Step 2: Add Agent Lab evidence README**

Create `evaluation/agent-lab/README.md`:

```markdown
# Agent Lab Evaluation Evidence

This directory records external evaluation evidence generated by
`seasonsolt/agent-lab`.

Agent Lab runs repeated baseline/treatment comparisons in isolated coding-agent
sandboxes. For this repository, the treatment skill is
`skills/ddia-system-design` and the baseline is a neutral coding skill from
Agent Lab.

The files in this directory are generated outside this repository and then
committed here as evidence:

- `latest-comparison.json`: machine-readable Agent Lab comparison output.
- `latest-comparison.md`: human-readable summary of the same comparison.

This evidence is not statistical proof. Model output variance, provider
configuration, sandbox timeouts, and task-pack coverage can affect the result.
Repeated runs are expected before making strong claims about the skill.
```

- [ ] **Step 3: Copy generated Agent Lab artifacts**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/ddia-skill
mkdir -p evaluation/agent-lab
cp /tmp/agent-lab-ddia-evidence/comparison.json evaluation/agent-lab/latest-comparison.json
cp /tmp/agent-lab-ddia-evidence/comparison.md evaluation/agent-lab/latest-comparison.md
```

Expected: both files exist under `evaluation/agent-lab/`.

- [ ] **Step 4: Add DDIA Skill static evidence tests**

Create `tests/test_agent_lab_evidence.py`:

```python
from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AgentLabEvidenceTests(unittest.TestCase):
    def test_agent_lab_evidence_files_exist(self) -> None:
        self.assertTrue((ROOT / "evaluation/agent-lab/README.md").is_file())
        self.assertTrue((ROOT / "evaluation/agent-lab/latest-comparison.json").is_file())
        self.assertTrue((ROOT / "evaluation/agent-lab/latest-comparison.md").is_file())

    def test_latest_comparison_json_has_required_fields(self) -> None:
        payload = json.loads((ROOT / "evaluation/agent-lab/latest-comparison.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["evidence"]["evaluator"], "seasonsolt/agent-lab")
        self.assertEqual(payload["evidence"]["treatment_repo_url"], "https://github.com/seasonsolt/ddia-skill")
        self.assertRegex(payload["evidence"]["treatment_repo_commit"], r"^[0-9a-f]{40}$")
        self.assertEqual(payload["evidence"]["treatment_skill_path"], "skills/ddia-system-design")
        self.assertIn(payload["verdict"], {"useful", "weak", "harmful", "inconclusive"})
        self.assertIn("baseline", payload)
        self.assertIn("treatment", payload)
        self.assertIn("score_lift", payload)

    def test_latest_markdown_and_root_readme_link_evidence(self) -> None:
        evidence_markdown = (ROOT / "evaluation/agent-lab/latest-comparison.md").read_text(encoding="utf-8")
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Agent Lab Skill Comparison Evidence", evidence_markdown)
        self.assertIn("not statistical proof", evidence_markdown)
        self.assertIn("evaluation/agent-lab/latest-comparison.md", root_readme)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 5: Update DDIA Skill README**

Add this section to `README.md` after the Pilot A/B Result section:

```markdown
## External Agent Lab Evaluation

This skill is also evaluated by
[`seasonsolt/agent-lab`](https://github.com/seasonsolt/agent-lab), an external
skill evaluation harness that runs repeated baseline/treatment comparisons in
isolated coding-agent sandboxes.

Latest result: see
[`evaluation/agent-lab/latest-comparison.md`](evaluation/agent-lab/latest-comparison.md).
```

- [ ] **Step 6: Run DDIA Skill tests**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/ddia-skill
python3 -m unittest tests/test_agent_lab_evidence.py -v
python3 -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit DDIA Skill evidence docs**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/ddia-skill
git add README.md evaluation/agent-lab tests/test_agent_lab_evidence.py
git commit -m "docs: cite external Agent Lab evaluation"
```

## Task 8: Final Verification And Publication Readiness

**Repos:**
- `/Users/Thin/Source/git/seasonsolt/agent-lab`
- `/Users/Thin/Source/git/seasonsolt/ddia-skill`

- [ ] **Step 1: Run Agent Lab full verification**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
docker compose config >/tmp/agent-lab-compose.yaml
docker compose run --build --rm coding-agent pytest -q
```

Expected: compose config succeeds and all tests pass.

- [ ] **Step 2: Confirm git status in both repos**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
git status --short
cd /Users/Thin/Source/git/seasonsolt/ddia-skill
git status --short
```

Expected: both commands show no uncommitted changes.

- [ ] **Step 3: Report branches and wait for explicit publish approval**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
git branch --show-current
git log --oneline -5
cd /Users/Thin/Source/git/seasonsolt/ddia-skill
git branch --show-current
git log --oneline -5
```

Expected: both repositories show the branch and latest commits that are ready to publish. Stop here and ask the user whether to push both repositories.

## Self-Review Checklist

- Spec coverage: external GitHub repo ingestion is covered by Tasks 1, 2, and 4.
- Spec coverage: JSON and Markdown artifact export is covered by Task 3.
- Spec coverage: repo URL, commit SHA, reproduction command, run IDs, score lift, pass-rate delta, timeout/error rate, and verdict are included by Tasks 3 and 4.
- Spec coverage: DDIA Skill evidence docs and README link are covered by Task 7.
- Scope control: no UI, CI, leaderboard, marketplace, multi-model, or statistical claims are included.
- Operational fit: external repo clones stay under `.agent-lab/external-skills/`, which keeps generated skill paths inside the Eval API project-root boundary while leaving clone artifacts out of git.
- Git safety: final push is not automatic; Task 8 stops after verification and branch reporting until the user explicitly approves publication.
- Type consistency: `ExternalSkillRepo`, `EvidenceMetadata`, `clone_external_skill_repo`, and `write_comparison_artifacts` are introduced before use in later tasks.
