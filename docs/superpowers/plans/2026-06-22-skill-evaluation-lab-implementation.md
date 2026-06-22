# Skill Evaluation Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP skill evaluation lab: local `SKILL.md` input, local task packs, CLI + API run orchestration, per-run Docker sandbox execution, Postgres score metadata, and Langfuse trace references.

**Architecture:** Keep the existing FastAPI coding-agent service and add an evaluation layer around it. The evaluation layer registers skill and task-pack identities, creates eval runs, starts a fresh coding-agent container per run, calls that container's `/runs` endpoint, runs task scorers, stores metadata in Postgres, and returns reports. Langfuse remains the process trace source; reports link trace IDs instead of copying trace payloads.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, psycopg, PyYAML, Docker SDK for Python, httpx, pytest, Docker Compose, Postgres, Langfuse/ClickHouse.

---

## Scope Check

This plan implements one cohesive MVP. It does not build a Web UI, public marketplace, Git URL skill ingestion, distributed workers, CI integration, or leaderboard governance.

The current project is not an isolated git repository: `git rev-parse --show-toplevel` returns `/Users/Thin`. Every commit step below includes a guard. Do not commit from `/Users/Thin`; only run commit steps after the project has an isolated git root at `/Users/Thin/Source/git/seasonsolt/agent-lab`.

## File Structure

Create or modify these files:

- Modify `agent/requirements.txt`: add runtime dependencies.
- Modify `agent/Dockerfile`: copy tests into the image for containerized verification.
- Modify `.env.example`: document eval-lab and Docker sandbox settings.
- Modify `docker-compose.yml`: expose Postgres to the coding-agent service, mount Docker socket, mount project root, and mount run workspace.
- Modify `agent/app/config.py`: add eval-lab settings.
- Modify `agent/app/main.py`: initialize eval-lab schema on startup.
- Modify `agent/app/routing.py`: include eval-lab router.
- Create `agent/app/eval_lab/__init__.py`: package marker.
- Create `agent/app/eval_lab/schemas.py`: request, response, manifest, score, and report models.
- Create `agent/app/eval_lab/hashing.py`: deterministic directory hashing.
- Create `agent/app/eval_lab/manifests.py`: load and validate `manifest.yaml` and `taskpack.yaml`.
- Create `agent/app/eval_lab/paths.py`: map host paths to container paths and validate project boundaries.
- Create `agent/app/eval_lab/db.py`: Postgres connection and schema bootstrap.
- Create `agent/app/eval_lab/repository.py`: app-owned metadata persistence.
- Create `agent/app/eval_lab/scorer.py`: run task scorer scripts and normalize score output.
- Create `agent/app/eval_lab/sandbox.py`: create, call, and clean per-run coding-agent containers.
- Create `agent/app/eval_lab/runner.py`: orchestrate eval runs.
- Create `agent/app/eval_lab/report.py`: build human-readable run reports.
- Create `agent/app/eval_lab/routing.py`: `POST /eval-runs`, `GET /eval-runs/{id}`, `GET /eval-runs/{id}/report`.
- Create `skill_lab/__init__.py`: CLI package marker.
- Create `skill_lab/cli.py`: host-side CLI.
- Create `skills/example-coding-skill/SKILL.md`: sample skill.
- Create `skills/example-coding-skill/manifest.yaml`: sample skill manifest.
- Create `task_packs/coding-basic/taskpack.yaml`: sample task pack.
- Create `task_packs/coding-basic/tasks/fix-bug-001/task.yaml`: sample task metadata.
- Create `task_packs/coding-basic/tasks/fix-bug-001/fixture/README.md`: deterministic fixture.
- Create `task_packs/coding-basic/tasks/fix-bug-001/expected/README.md`: expected output.
- Create `task_packs/coding-basic/tasks/fix-bug-001/scorer.py`: sample automatic scorer.
- Create tests under `agent/tests/eval_lab/`.

## Task 1: Runtime Dependencies And Compose Wiring

**Files:**
- Modify: `agent/requirements.txt`
- Modify: `agent/Dockerfile`
- Modify: `.env.example`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Update dependency list**

Modify `agent/requirements.txt` so it contains these lines:

```text
fastapi
uvicorn[standard]
deepagents
langchain
langchain-openai
pydantic
langfuse
pytest
httpx
PyYAML
psycopg[binary]
docker
```

- [ ] **Step 2: Copy tests into the coding-agent image**

Modify `agent/Dockerfile` to copy tests:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Add eval-lab environment defaults**

Append these lines to `.env.example`:

```dotenv

# Skill evaluation lab
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/postgres
EVAL_LAB_HOST_PROJECT_DIR=/Users/Thin/Source/git/seasonsolt/agent-lab
EVAL_LAB_CONTAINER_PROJECT_DIR=/lab
EVAL_LAB_HOST_RUNS_DIR=/tmp/agent-lab-runs
EVAL_LAB_CONTAINER_RUNS_DIR=/runs
EVAL_LAB_SANDBOX_IMAGE=agent-lab-coding-agent
EVAL_LAB_DOCKER_NETWORK=agent-lab_default
EVAL_LAB_NETWORK_ENABLED=false
EVAL_LAB_TASK_TIMEOUT_SECONDS=300
```

- [ ] **Step 4: Wire coding-agent to Postgres, Docker socket, project root, and run dir**

In `docker-compose.yml`, update the `coding-agent` service environment and volumes:

```yaml
  coding-agent:
    build:
      context: ./agent
    restart: unless-stopped
    depends_on:
      - langfuse-web
    environment:
      DEEP_AGENT_HOST: 0.0.0.0
      DEEP_AGENT_PORT: 8000
      DEEP_AGENT_MODEL: ${DEEP_AGENT_MODEL:-openai:gpt-4o-mini}
      OPENAI_API_BASE: ${OPENAI_API_BASE:-}
      OPENAI_BASE_URL: ${OPENAI_BASE_URL:-}
      AGENT_WORKSPACE: /workspace
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      DEEP_AGENT_SYSTEM_PROMPT: "You are a reliable coding assistant. Use tools to inspect files and make minimal, correct edits for the given task."
      LANGFUSE_HOST: ${LANGFUSE_HOST:-http://langfuse-web:3000}
      LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY:-}
      LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY:-}
      LANGFUSE_ENABLED: ${LANGFUSE_ENABLED:-false}
      LANGFUSE_DEBUG: ${LANGFUSE_DEBUG:-false}
      DATABASE_URL: ${DATABASE_URL:-postgresql://postgres:postgres@postgres:5432/postgres}
      EVAL_LAB_HOST_PROJECT_DIR: ${EVAL_LAB_HOST_PROJECT_DIR:-/Users/Thin/Source/git/seasonsolt/agent-lab}
      EVAL_LAB_CONTAINER_PROJECT_DIR: ${EVAL_LAB_CONTAINER_PROJECT_DIR:-/lab}
      EVAL_LAB_HOST_RUNS_DIR: ${EVAL_LAB_HOST_RUNS_DIR:-/tmp/agent-lab-runs}
      EVAL_LAB_CONTAINER_RUNS_DIR: ${EVAL_LAB_CONTAINER_RUNS_DIR:-/runs}
      EVAL_LAB_SANDBOX_IMAGE: ${EVAL_LAB_SANDBOX_IMAGE:-agent-lab-coding-agent}
      EVAL_LAB_DOCKER_NETWORK: ${EVAL_LAB_DOCKER_NETWORK:-agent-lab_default}
      EVAL_LAB_NETWORK_ENABLED: ${EVAL_LAB_NETWORK_ENABLED:-false}
      EVAL_LAB_TASK_TIMEOUT_SECONDS: ${EVAL_LAB_TASK_TIMEOUT_SECONDS:-300}
    volumes:
      - ./agent/workspace:/workspace
      - ${EVAL_LAB_HOST_PROJECT_DIR:-/Users/Thin/Source/git/seasonsolt/agent-lab}:${EVAL_LAB_CONTAINER_PROJECT_DIR:-/lab}:ro
      - ${EVAL_LAB_HOST_RUNS_DIR:-/tmp/agent-lab-runs}:${EVAL_LAB_CONTAINER_RUNS_DIR:-/runs}
      - /var/run/docker.sock:/var/run/docker.sock
    ports:
      - "8000:8000"
```

- [ ] **Step 5: Run compose config validation**

Run:

```bash
docker compose config >/tmp/agent-lab-compose.yaml
```

Expected: exit code `0`.

- [ ] **Step 6: Rebuild coding-agent image**

Run:

```bash
docker compose build coding-agent
```

Expected: image builds successfully and includes `app` and `tests`.

- [ ] **Step 7: Commit if project git root is isolated**

Run:

```bash
git rev-parse --show-toplevel
```

Expected before committing: `/Users/Thin/Source/git/seasonsolt/agent-lab`.

If the expected root matches, run:

```bash
git add agent/requirements.txt agent/Dockerfile .env.example docker-compose.yml
git commit -m "chore: wire skill evaluation runtime"
```

If the output is `/Users/Thin`, skip this commit step.

## Task 2: Eval-Lab Configuration And Package Skeleton

**Files:**
- Modify: `agent/app/config.py`
- Create: `agent/app/eval_lab/__init__.py`
- Test: `agent/tests/eval_lab/test_paths.py`
- Create: `agent/app/eval_lab/paths.py`

- [ ] **Step 1: Add eval-lab settings**

Append these class attributes to `Settings` in `agent/app/config.py`:

```python
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/postgres")
    eval_lab_host_project_dir = os.getenv("EVAL_LAB_HOST_PROJECT_DIR", "/Users/Thin/Source/git/seasonsolt/agent-lab")
    eval_lab_container_project_dir = os.getenv("EVAL_LAB_CONTAINER_PROJECT_DIR", "/lab")
    eval_lab_host_runs_dir = os.getenv("EVAL_LAB_HOST_RUNS_DIR", "/tmp/agent-lab-runs")
    eval_lab_container_runs_dir = os.getenv("EVAL_LAB_CONTAINER_RUNS_DIR", "/runs")
    eval_lab_sandbox_image = os.getenv("EVAL_LAB_SANDBOX_IMAGE", "agent-lab-coding-agent")
    eval_lab_docker_network = os.getenv("EVAL_LAB_DOCKER_NETWORK", "agent-lab_default")
    eval_lab_network_enabled = os.getenv("EVAL_LAB_NETWORK_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    eval_lab_task_timeout_seconds = int(os.getenv("EVAL_LAB_TASK_TIMEOUT_SECONDS", "300"))
```

- [ ] **Step 2: Create package marker**

Create `agent/app/eval_lab/__init__.py`:

```python
"""Skill evaluation lab package."""
```

- [ ] **Step 3: Write failing path-mapping tests**

Create `agent/tests/eval_lab/test_paths.py`:

```python
from pathlib import Path

import pytest

from app.eval_lab.paths import PathMapping, ensure_child_path


def test_host_to_container_path_maps_project_child():
    mapping = PathMapping(
        host_project_dir=Path("/host/project"),
        container_project_dir=Path("/lab"),
        host_runs_dir=Path("/host/runs"),
        container_runs_dir=Path("/runs"),
    )

    assert mapping.host_to_container_project_path(Path("/host/project/skills/demo")) == Path("/lab/skills/demo")


def test_host_to_container_path_rejects_external_path():
    mapping = PathMapping(
        host_project_dir=Path("/host/project"),
        container_project_dir=Path("/lab"),
        host_runs_dir=Path("/host/runs"),
        container_runs_dir=Path("/runs"),
    )

    with pytest.raises(ValueError, match="outside project root"):
        mapping.host_to_container_project_path(Path("/tmp/skills/demo"))


def test_ensure_child_path_rejects_traversal(tmp_path):
    root = tmp_path / "root"
    root.mkdir()

    with pytest.raises(ValueError, match="outside"):
        ensure_child_path(root, root.parent / "escape")
```

- [ ] **Step 4: Run test to verify it fails**

Run:

```bash
docker compose run --rm coding-agent pytest tests/eval_lab/test_paths.py -q
```

Expected: fails with `ModuleNotFoundError` or missing `app.eval_lab.paths`.

- [ ] **Step 5: Implement path mapping**

Create `agent/app/eval_lab/paths.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def ensure_child_path(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    if resolved_candidate == resolved_root or resolved_root in resolved_candidate.parents:
        return resolved_candidate
    raise ValueError(f"Path '{candidate}' is outside '{root}'")


@dataclass(frozen=True)
class PathMapping:
    host_project_dir: Path
    container_project_dir: Path
    host_runs_dir: Path
    container_runs_dir: Path

    def host_to_container_project_path(self, path: Path) -> Path:
        resolved = ensure_child_path(self.host_project_dir, path)
        relative = resolved.relative_to(self.host_project_dir.resolve())
        return self.container_project_dir / relative

    def host_run_path(self, run_id: str) -> Path:
        return self.host_runs_dir / run_id

    def container_run_path(self, run_id: str) -> Path:
        return self.container_runs_dir / run_id
```

- [ ] **Step 6: Run test to verify it passes**

Run:

```bash
docker compose run --rm coding-agent pytest tests/eval_lab/test_paths.py -q
```

Expected: `3 passed`.

- [ ] **Step 7: Commit if project git root is isolated**

Run:

```bash
git rev-parse --show-toplevel
```

Expected before committing: `/Users/Thin/Source/git/seasonsolt/agent-lab`.

If the expected root matches, run:

```bash
git add agent/app/config.py agent/app/eval_lab/__init__.py agent/app/eval_lab/paths.py agent/tests/eval_lab/test_paths.py
git commit -m "feat: add eval lab path settings"
```

If the output is `/Users/Thin`, skip this commit step.

## Task 3: Manifests And Version Hashing

**Files:**
- Create: `agent/app/eval_lab/schemas.py`
- Create: `agent/app/eval_lab/hashing.py`
- Create: `agent/app/eval_lab/manifests.py`
- Test: `agent/tests/eval_lab/test_manifests.py`

- [ ] **Step 1: Write failing manifest and hashing tests**

Create `agent/tests/eval_lab/test_manifests.py`:

```python
from pathlib import Path

import pytest

from app.eval_lab.hashing import hash_directory
from app.eval_lab.manifests import load_skill_manifest, load_task_pack_manifest


def test_load_skill_manifest_requires_skill_file(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "manifest.yaml").write_text(
        "id: demo\nname: Demo Skill\nentry: SKILL.md\ntags:\n  - coding\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="SKILL.md"):
        load_skill_manifest(skill_dir)


def test_load_skill_manifest_reads_valid_manifest(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
    (skill_dir / "manifest.yaml").write_text(
        "id: demo\nname: Demo Skill\nentry: SKILL.md\ntags:\n  - coding\n",
        encoding="utf-8",
    )

    manifest = load_skill_manifest(skill_dir)

    assert manifest.id == "demo"
    assert manifest.name == "Demo Skill"
    assert manifest.entry == "SKILL.md"
    assert manifest.tags == ["coding"]


def test_load_task_pack_manifest_reads_tasks(tmp_path):
    pack_dir = tmp_path / "pack"
    task_dir = pack_dir / "tasks" / "fix-001"
    task_dir.mkdir(parents=True)
    (task_dir / "fixture").mkdir()
    (task_dir / "expected").mkdir()
    (task_dir / "scorer.py").write_text("print('{}')\n", encoding="utf-8")
    (pack_dir / "taskpack.yaml").write_text(
        "id: coding-basic\n"
        "name: Coding Basic\n"
        "domain: coding\n"
        "tasks:\n"
        "  - id: fix-001\n"
        "    type: coding\n"
        "    prompt: Fix it.\n"
        "    fixture: tasks/fix-001/fixture\n"
        "    expected: tasks/fix-001/expected\n"
        "    scorer: tasks/fix-001/scorer.py\n"
        "    max_score: 100\n",
        encoding="utf-8",
    )

    manifest = load_task_pack_manifest(pack_dir)

    assert manifest.id == "coding-basic"
    assert manifest.tasks[0].id == "fix-001"
    assert manifest.tasks[0].max_score == 100


def test_hash_directory_changes_when_file_changes(tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    file_path = folder / "a.txt"
    file_path.write_text("one", encoding="utf-8")
    first = hash_directory(folder)

    file_path.write_text("two", encoding="utf-8")
    second = hash_directory(folder)

    assert first != second
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
docker compose run --rm coding-agent pytest tests/eval_lab/test_manifests.py -q
```

Expected: fails because `schemas.py`, `hashing.py`, and `manifests.py` do not exist.

- [ ] **Step 3: Implement schema models**

Create `agent/app/eval_lab/schemas.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


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
    fixture: str
    expected: str
    scorer: str
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
    max_score: float
    details: dict[str, Any] = Field(default_factory=dict)


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
```

- [ ] **Step 4: Implement deterministic directory hashing**

Create `agent/app/eval_lab/hashing.py`:

```python
from __future__ import annotations

import hashlib
from pathlib import Path


IGNORED_NAMES = {".DS_Store", "__pycache__", ".pytest_cache"}


def hash_directory(path: Path) -> str:
    root = path.resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Directory '{path}' does not exist")

    digest = hashlib.sha256()
    for file_path in sorted(p for p in root.rglob("*") if p.is_file()):
        if any(part in IGNORED_NAMES for part in file_path.relative_to(root).parts):
            continue
        relative = file_path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
```

- [ ] **Step 5: Implement manifest loading and validation**

Create `agent/app/eval_lab/manifests.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .schemas import SkillManifest, TaskPackManifest


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"Manifest '{path}' does not exist")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Manifest '{path}' must contain a YAML mapping")
    return data


def load_skill_manifest(skill_dir: Path) -> SkillManifest:
    manifest = SkillManifest.model_validate(_load_yaml(skill_dir / "manifest.yaml"))
    entry = skill_dir / manifest.entry
    if manifest.entry != "SKILL.md" or not entry.exists() or not entry.is_file():
        raise ValueError(f"Skill directory '{skill_dir}' must contain SKILL.md")
    return manifest


def load_task_pack_manifest(task_pack_dir: Path) -> TaskPackManifest:
    manifest = TaskPackManifest.model_validate(_load_yaml(task_pack_dir / "taskpack.yaml"))
    for task in manifest.tasks:
        for relative in (task.fixture, task.expected, task.scorer):
            target = task_pack_dir / relative
            if not target.exists():
                raise ValueError(f"Task '{task.id}' references missing path '{relative}'")
    return manifest
```

- [ ] **Step 6: Run tests to verify they pass**

Run:

```bash
docker compose run --rm coding-agent pytest tests/eval_lab/test_manifests.py -q
```

Expected: `4 passed`.

- [ ] **Step 7: Commit if project git root is isolated**

Run:

```bash
git rev-parse --show-toplevel
```

Expected before committing: `/Users/Thin/Source/git/seasonsolt/agent-lab`.

If the expected root matches, run:

```bash
git add agent/app/eval_lab/schemas.py agent/app/eval_lab/hashing.py agent/app/eval_lab/manifests.py agent/tests/eval_lab/test_manifests.py
git commit -m "feat: load skill and task pack manifests"
```

If the output is `/Users/Thin`, skip this commit step.

## Task 4: Postgres Schema And Repository

**Files:**
- Create: `agent/app/eval_lab/db.py`
- Create: `agent/app/eval_lab/repository.py`
- Test: `agent/tests/eval_lab/test_repository.py`
- Modify: `agent/app/main.py`

- [ ] **Step 1: Write failing repository integration test**

Create `agent/tests/eval_lab/test_repository.py`:

```python
from app.eval_lab.db import init_schema
from app.eval_lab.repository import EvalRepository


def test_repository_persists_eval_run():
    init_schema()
    repo = EvalRepository()

    skill = repo.upsert_skill(
        skill_id="repo-test-skill",
        name="Repo Test Skill",
        version_hash="hash-skill",
        source_type="local_dir",
        source_path="/lab/skills/repo-test-skill",
        manifest={"id": "repo-test-skill", "name": "Repo Test Skill"},
    )
    task_pack = repo.upsert_task_pack(
        task_pack_id="repo-test-pack",
        name="Repo Test Pack",
        domain="coding",
        version_hash="hash-pack",
        source_path="/lab/task_packs/repo-test-pack",
        manifest={"id": "repo-test-pack", "name": "Repo Test Pack", "domain": "coding"},
    )
    run = repo.create_eval_run(skill["id"], task_pack["id"])
    repo.mark_run_running(run["id"], sandbox_container_id="container-1")
    repo.add_score(run["id"], "task-1", "auto", 70, 100, {"tests_passed": True})
    repo.finish_run(run["id"], "passed", ["trace-1"])

    stored_run = repo.get_eval_run(run["id"])
    scores = repo.list_scores(run["id"])

    assert stored_run["status"] == "passed"
    assert stored_run["langfuse_trace_ids"] == ["trace-1"]
    assert scores[0]["score"] == 70
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
docker compose up -d postgres
docker compose run --rm coding-agent pytest tests/eval_lab/test_repository.py -q
```

Expected: fails because DB modules do not exist.

- [ ] **Step 3: Implement schema bootstrap**

Create `agent/app/eval_lab/db.py`:

```python
from __future__ import annotations

import psycopg

from app.config import Settings


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS eval_skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version_hash TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_path TEXT NOT NULL,
    manifest JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eval_task_packs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    domain TEXT NOT NULL,
    version_hash TEXT NOT NULL,
    source_path TEXT NOT NULL,
    manifest JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eval_runs (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL REFERENCES eval_skills(id),
    task_pack_id TEXT NOT NULL REFERENCES eval_task_packs(id),
    status TEXT NOT NULL,
    sandbox_container_id TEXT,
    langfuse_trace_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eval_scores (
    id TEXT PRIMARY KEY,
    eval_run_id TEXT NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    task_id TEXT NOT NULL,
    score_type TEXT NOT NULL,
    score DOUBLE PRECISION NOT NULL,
    max_score DOUBLE PRECISION NOT NULL,
    details JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def connect():
    return psycopg.connect(Settings.database_url)


def init_schema() -> None:
    with connect() as conn:
        conn.execute(SCHEMA_SQL)
        conn.commit()
```

- [ ] **Step 4: Implement repository**

Create `agent/app/eval_lab/repository.py`:

```python
from __future__ import annotations

import uuid
from typing import Any

from psycopg.rows import dict_row

from .db import connect


class EvalRepository:
    def upsert_skill(
        self,
        skill_id: str,
        name: str,
        version_hash: str,
        source_type: str,
        source_path: str,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        with connect() as conn:
            row = conn.execute(
                """
                INSERT INTO eval_skills (id, name, version_hash, source_type, source_path, manifest)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    version_hash = EXCLUDED.version_hash,
                    source_type = EXCLUDED.source_type,
                    source_path = EXCLUDED.source_path,
                    manifest = EXCLUDED.manifest
                RETURNING *
                """,
                (skill_id, name, version_hash, source_type, source_path, manifest),
                prepare=False,
                row_factory=dict_row,
            ).fetchone()
            conn.commit()
            return dict(row)

    def upsert_task_pack(
        self,
        task_pack_id: str,
        name: str,
        domain: str,
        version_hash: str,
        source_path: str,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        with connect() as conn:
            row = conn.execute(
                """
                INSERT INTO eval_task_packs (id, name, domain, version_hash, source_path, manifest)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    domain = EXCLUDED.domain,
                    version_hash = EXCLUDED.version_hash,
                    source_path = EXCLUDED.source_path,
                    manifest = EXCLUDED.manifest
                RETURNING *
                """,
                (task_pack_id, name, domain, version_hash, source_path, manifest),
                prepare=False,
                row_factory=dict_row,
            ).fetchone()
            conn.commit()
            return dict(row)

    def create_eval_run(self, skill_id: str, task_pack_id: str) -> dict[str, Any]:
        run_id = f"eval-{uuid.uuid4().hex}"
        with connect() as conn:
            row = conn.execute(
                """
                INSERT INTO eval_runs (id, skill_id, task_pack_id, status)
                VALUES (%s, %s, %s, 'queued')
                RETURNING *
                """,
                (run_id, skill_id, task_pack_id),
                row_factory=dict_row,
            ).fetchone()
            conn.commit()
            return dict(row)

    def mark_run_running(self, run_id: str, sandbox_container_id: str) -> None:
        with connect() as conn:
            conn.execute(
                """
                UPDATE eval_runs
                SET status = 'running', sandbox_container_id = %s, started_at = now()
                WHERE id = %s
                """,
                (sandbox_container_id, run_id),
            )
            conn.commit()

    def finish_run(self, run_id: str, status: str, trace_ids: list[str], error: str | None = None) -> None:
        with connect() as conn:
            conn.execute(
                """
                UPDATE eval_runs
                SET status = %s, langfuse_trace_ids = %s, finished_at = now(), error = %s
                WHERE id = %s
                """,
                (status, trace_ids, error, run_id),
            )
            conn.commit()

    def add_score(
        self,
        eval_run_id: str,
        task_id: str,
        score_type: str,
        score: float,
        max_score: float,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        score_id = f"score-{uuid.uuid4().hex}"
        with connect() as conn:
            row = conn.execute(
                """
                INSERT INTO eval_scores (id, eval_run_id, task_id, score_type, score, max_score, details)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (score_id, eval_run_id, task_id, score_type, score, max_score, details),
                row_factory=dict_row,
            ).fetchone()
            conn.commit()
            return dict(row)

    def get_eval_run(self, run_id: str) -> dict[str, Any]:
        with connect() as conn:
            row = conn.execute(
                "SELECT * FROM eval_runs WHERE id = %s",
                (run_id,),
                row_factory=dict_row,
            ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return dict(row)

    def get_skill(self, skill_id: str) -> dict[str, Any]:
        with connect() as conn:
            row = conn.execute("SELECT * FROM eval_skills WHERE id = %s", (skill_id,), row_factory=dict_row).fetchone()
        if row is None:
            raise KeyError(skill_id)
        return dict(row)

    def get_task_pack(self, task_pack_id: str) -> dict[str, Any]:
        with connect() as conn:
            row = conn.execute("SELECT * FROM eval_task_packs WHERE id = %s", (task_pack_id,), row_factory=dict_row).fetchone()
        if row is None:
            raise KeyError(task_pack_id)
        return dict(row)

    def list_scores(self, eval_run_id: str) -> list[dict[str, Any]]:
        with connect() as conn:
            rows = conn.execute(
                "SELECT * FROM eval_scores WHERE eval_run_id = %s ORDER BY created_at ASC",
                (eval_run_id,),
                row_factory=dict_row,
            ).fetchall()
        return [dict(row) for row in rows]
```

- [ ] **Step 5: Initialize schema on API startup**

Modify `agent/app/main.py`:

```python
from __future__ import annotations

from fastapi import FastAPI

from .config import Settings
from .eval_lab.db import init_schema
from .routing import router


app = FastAPI(title="Coding Agent", version="0.1.1")
app.include_router(router)


@app.on_event("startup")
def startup() -> None:
    init_schema()


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "coding-agent",
        "version": "0.1.1",
        "workspace": Settings.workspace,
    }
```

- [ ] **Step 6: Run repository test**

Run:

```bash
docker compose up -d postgres
docker compose run --rm coding-agent pytest tests/eval_lab/test_repository.py -q
```

Expected: `1 passed`.

- [ ] **Step 7: Commit if project git root is isolated**

Run:

```bash
git rev-parse --show-toplevel
```

Expected before committing: `/Users/Thin/Source/git/seasonsolt/agent-lab`.

If the expected root matches, run:

```bash
git add agent/app/eval_lab/db.py agent/app/eval_lab/repository.py agent/app/main.py agent/tests/eval_lab/test_repository.py
git commit -m "feat: persist eval lab metadata"
```

If the output is `/Users/Thin`, skip this commit step.

## Task 5: Scorer Execution And Report Calculation

**Files:**
- Create: `agent/app/eval_lab/scorer.py`
- Create: `agent/app/eval_lab/report.py`
- Test: `agent/tests/eval_lab/test_scorer.py`
- Test: `agent/tests/eval_lab/test_report.py`

- [ ] **Step 1: Write failing scorer tests**

Create `agent/tests/eval_lab/test_scorer.py`:

```python
import json

from app.eval_lab.scorer import run_scorer


def test_run_scorer_reads_json_output(tmp_path):
    scorer = tmp_path / "scorer.py"
    workspace = tmp_path / "workspace"
    expected = tmp_path / "expected"
    output = tmp_path / "agent_output.json"
    workspace.mkdir()
    expected.mkdir()
    output.write_text(json.dumps({"agent_output": "done"}), encoding="utf-8")
    scorer.write_text(
        "import json\n"
        "import sys\n"
        "print(json.dumps({\n"
        "  'score': 90,\n"
        "  'max_score': 100,\n"
        "  'details': {'tests_passed': True}\n"
        "}))\n",
        encoding="utf-8",
    )

    result = run_scorer(scorer, workspace, expected, output, timeout_seconds=10)

    assert result.score == 90
    assert result.max_score == 100
    assert result.details == {"tests_passed": True}
```

- [ ] **Step 2: Write failing report tests**

Create `agent/tests/eval_lab/test_report.py`:

```python
from app.eval_lab.report import build_report_from_records


def test_build_report_marks_useful_when_scores_are_high():
    report = build_report_from_records(
        eval_run={"id": "run-1", "status": "passed", "skill_id": "skill-1", "task_pack_id": "pack-1", "langfuse_trace_ids": ["trace-1"], "error": None},
        skill={"id": "skill-1", "name": "Skill", "version_hash": "skill-hash", "manifest": {"tags": ["coding"]}},
        task_pack={"id": "pack-1", "name": "Pack", "domain": "coding", "version_hash": "pack-hash"},
        scores=[
            {"task_id": "task-1", "score_type": "auto", "score": 90, "max_score": 100, "details": {}},
            {"task_id": "task-1", "score_type": "rubric", "score": 80, "max_score": 100, "details": {}},
        ],
    )

    assert report.final_score == 87
    assert report.verdict == "useful"
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
docker compose run --rm coding-agent pytest tests/eval_lab/test_scorer.py tests/eval_lab/test_report.py -q
```

Expected: fails because scorer and report modules do not exist.

- [ ] **Step 4: Implement scorer execution**

Create `agent/app/eval_lab/scorer.py`:

```python
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ScorerResult(BaseModel):
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    details: dict[str, Any] = Field(default_factory=dict)


def run_scorer(
    scorer_path: Path,
    workspace_path: Path,
    expected_path: Path,
    agent_output_path: Path,
    timeout_seconds: int,
) -> ScorerResult:
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
    if completed.returncode != 0:
        return ScorerResult(
            score=0,
            max_score=100,
            details={
                "scorer_error": completed.stderr.strip(),
                "returncode": completed.returncode,
            },
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return ScorerResult(score=0, max_score=100, details={"scorer_error": str(exc), "stdout": completed.stdout})
    return ScorerResult.model_validate(payload)
```

- [ ] **Step 5: Implement report calculation**

Create `agent/app/eval_lab/report.py`:

```python
from __future__ import annotations

from typing import Any

from .schemas import EvalReport, ScoreRecord


def _normalized_score(scores: list[dict[str, Any]], score_type: str) -> float:
    typed = [score for score in scores if score["score_type"] == score_type]
    if not typed:
        return 0.0
    ratios = [float(score["score"]) / float(score["max_score"]) * 100 for score in typed]
    return round(sum(ratios) / len(ratios), 2)


def _verdict(status: str, auto_score: float, value_score: float) -> str:
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
    auto_score = _normalized_score(scores, "auto")
    rubric_score = _normalized_score(scores, "rubric")
    llm_score = _normalized_score(scores, "llm_judge")
    human_score = _normalized_score(scores, "human")
    value_components = [score for score in (rubric_score, llm_score, human_score) if score > 0]
    value_score = round(sum(value_components) / len(value_components), 2) if value_components else 0.0
    final_score = round(auto_score * 0.7 + value_score * 0.3, 2)
    task_ids = {score["task_id"] for score in scores}
    passed_tasks = {
        score["task_id"]
        for score in scores
        if score["score_type"] == "auto" and float(score["score"]) / float(score["max_score"]) >= 0.6
    }
    pass_rate = round(len(passed_tasks) / len(task_ids), 2) if task_ids else 0.0

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
        scores=[ScoreRecord(task_id=s["task_id"], score_type=s["score_type"], score=s["score"], max_score=s["max_score"], details=s["details"]) for s in scores],
        trace_ids=eval_run.get("langfuse_trace_ids", []),
        verdict=_verdict(eval_run["status"], auto_score, value_score),
        error=eval_run.get("error"),
    )
```

- [ ] **Step 6: Run tests**

Run:

```bash
docker compose run --rm coding-agent pytest tests/eval_lab/test_scorer.py tests/eval_lab/test_report.py -q
```

Expected: `2 passed`.

- [ ] **Step 7: Commit if project git root is isolated**

Run:

```bash
git rev-parse --show-toplevel
```

Expected before committing: `/Users/Thin/Source/git/seasonsolt/agent-lab`.

If the expected root matches, run:

```bash
git add agent/app/eval_lab/scorer.py agent/app/eval_lab/report.py agent/tests/eval_lab/test_scorer.py agent/tests/eval_lab/test_report.py
git commit -m "feat: score and report eval runs"
```

If the output is `/Users/Thin`, skip this commit step.

## Task 6: Per-Run Docker Sandbox

**Files:**
- Create: `agent/app/eval_lab/sandbox.py`
- Test: `agent/tests/eval_lab/test_sandbox.py`

- [ ] **Step 1: Write failing sandbox unit tests**

Create `agent/tests/eval_lab/test_sandbox.py`:

```python
from pathlib import Path

from app.eval_lab.sandbox import SandboxRunResult, build_task_prompt


def test_build_task_prompt_includes_skill_and_task():
    prompt = build_task_prompt(
        skill_container_path=Path("/skills/demo/SKILL.md"),
        task_prompt="Fix the failing test.",
    )

    assert "/skills/demo/SKILL.md" in prompt
    assert "Fix the failing test." in prompt


def test_sandbox_result_defaults_trace_ids():
    result = SandboxRunResult(
        task_id="task-1",
        status="passed",
        agent_output="done",
        changed_files=[],
        trace_ids=[],
    )

    assert result.trace_ids == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
docker compose run --rm coding-agent pytest tests/eval_lab/test_sandbox.py -q
```

Expected: fails because `sandbox.py` does not exist.

- [ ] **Step 3: Implement sandbox module**

Create `agent/app/eval_lab/sandbox.py`:

```python
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import docker
import httpx
from pydantic import BaseModel, Field

from app.config import Settings


class SandboxRunResult(BaseModel):
    task_id: str
    status: str
    agent_output: str
    changed_files: list[str] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)


def build_task_prompt(skill_container_path: Path, task_prompt: str) -> str:
    return (
        f"Use the skill instructions at {skill_container_path.as_posix()}.\n"
        f"Work inside /workspace.\n"
        f"Task: {task_prompt}"
    )


class DockerSandbox:
    def __init__(self) -> None:
        self.client = docker.from_env()

    def start_container(
        self,
        run_id: str,
        task_id: str,
        skill_host_dir: Path,
        fixture_host_dir: Path,
        workspace_host_dir: Path,
        network_enabled: bool,
    ) -> Any:
        container_name = f"agent-lab-{run_id}-{task_id}".replace("_", "-")[:63]
        binds = {
            str(skill_host_dir): {"bind": "/skills/current", "mode": "ro"},
            str(fixture_host_dir): {"bind": "/fixture", "mode": "ro"},
            str(workspace_host_dir): {"bind": "/workspace", "mode": "rw"},
        }
        network_mode = Settings.eval_lab_docker_network if network_enabled else "none"
        return self.client.containers.run(
            Settings.eval_lab_sandbox_image,
            detach=True,
            name=container_name,
            volumes=binds,
            network=network_mode,
            environment={
                "AGENT_WORKSPACE": "/workspace",
                "DEEP_AGENT_MODEL": Settings.model,
                "OPENAI_API_BASE": Settings.openai_api_base or "",
                "OPENAI_BASE_URL": Settings.openai_api_base or "",
                "OPENAI_API_KEY": __import__("os").environ.get("OPENAI_API_KEY", ""),
                "LANGFUSE_HOST": Settings.langfuse_host,
                "LANGFUSE_PUBLIC_KEY": Settings.langfuse_public_key or "",
                "LANGFUSE_SECRET_KEY": Settings.langfuse_secret_key or "",
                "LANGFUSE_ENABLED": "true" if Settings.langfuse_enabled else "false",
                "LANGFUSE_DEBUG": "true" if Settings.langfuse_debug else "false",
            },
        )

    def wait_for_health(self, container_name: str, timeout_seconds: int) -> None:
        deadline = time.time() + timeout_seconds
        url = f"http://{container_name}:8000/health"
        while time.time() < deadline:
            try:
                response = httpx.get(url, timeout=2)
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                time.sleep(1)
        raise TimeoutError(f"Sandbox '{container_name}' did not become healthy")

    def run_task(
        self,
        run_id: str,
        task_id: str,
        task_prompt: str,
        skill_host_dir: Path,
        fixture_host_dir: Path,
        workspace_host_dir: Path,
        network_enabled: bool,
        timeout_seconds: int,
    ) -> SandboxRunResult:
        container = self.start_container(run_id, task_id, skill_host_dir, fixture_host_dir, workspace_host_dir, network_enabled)
        try:
            self.wait_for_health(container.name, timeout_seconds)
            prompt = build_task_prompt(Path("/skills/current/SKILL.md"), task_prompt)
            response = httpx.post(
                f"http://{container.name}:8000/runs",
                json={"task": prompt},
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            changed_files = sorted(
                path.relative_to(workspace_host_dir).as_posix()
                for path in workspace_host_dir.rglob("*")
                if path.is_file()
            )
            return SandboxRunResult(
                task_id=task_id,
                status="passed" if payload.get("success") else "failed",
                agent_output=payload.get("output", ""),
                changed_files=changed_files,
                trace_ids=[],
            )
        except Exception as exc:
            return SandboxRunResult(task_id=task_id, status="error", agent_output=str(exc), changed_files=[], trace_ids=[])
        finally:
            container.remove(force=True)
```

- [ ] **Step 4: Run sandbox unit tests**

Run:

```bash
docker compose run --rm coding-agent pytest tests/eval_lab/test_sandbox.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit if project git root is isolated**

Run:

```bash
git rev-parse --show-toplevel
```

Expected before committing: `/Users/Thin/Source/git/seasonsolt/agent-lab`.

If the expected root matches, run:

```bash
git add agent/app/eval_lab/sandbox.py agent/tests/eval_lab/test_sandbox.py
git commit -m "feat: add docker sandbox runner"
```

If the output is `/Users/Thin`, skip this commit step.

## Task 7: Eval Runner Orchestration

**Files:**
- Create: `agent/app/eval_lab/runner.py`
- Test: `agent/tests/eval_lab/test_runner.py`

- [ ] **Step 1: Write failing runner test using fakes**

Create `agent/tests/eval_lab/test_runner.py`:

```python
from pathlib import Path

from app.eval_lab.runner import EvalRunner
from app.eval_lab.sandbox import SandboxRunResult


class FakeRepo:
    def __init__(self):
        self.scores = []
        self.finished = None

    def upsert_skill(self, **kwargs):
        return {"id": kwargs["skill_id"], **kwargs}

    def upsert_task_pack(self, **kwargs):
        return {"id": kwargs["task_pack_id"], **kwargs}

    def create_eval_run(self, skill_id, task_pack_id):
        return {"id": "run-1", "skill_id": skill_id, "task_pack_id": task_pack_id, "status": "queued"}

    def mark_run_running(self, run_id, sandbox_container_id):
        self.running = (run_id, sandbox_container_id)

    def add_score(self, eval_run_id, task_id, score_type, score, max_score, details):
        self.scores.append((eval_run_id, task_id, score_type, score, max_score, details))

    def finish_run(self, run_id, status, trace_ids, error=None):
        self.finished = (run_id, status, trace_ids, error)


class FakeSandbox:
    def run_task(self, **kwargs):
        return SandboxRunResult(task_id=kwargs["task_id"], status="passed", agent_output="done", changed_files=["README.md"], trace_ids=["trace-1"])


def test_runner_executes_task_pack(tmp_path):
    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Demo Skill\n", encoding="utf-8")
    (skill_dir / "manifest.yaml").write_text("id: demo\nname: Demo\nentry: SKILL.md\ntags:\n  - coding\n", encoding="utf-8")
    task_dir = tmp_path / "task_packs" / "pack" / "tasks" / "task-1"
    task_dir.mkdir(parents=True)
    (task_dir / "fixture").mkdir()
    (task_dir / "expected").mkdir()
    (task_dir / "scorer.py").write_text(
        "import json\nprint(json.dumps({'score': 100, 'max_score': 100, 'details': {'ok': True}}))\n",
        encoding="utf-8",
    )
    pack_dir = tmp_path / "task_packs" / "pack"
    (pack_dir / "taskpack.yaml").write_text(
        "id: pack\nname: Pack\ndomain: coding\ntasks:\n"
        "  - id: task-1\n    type: coding\n    prompt: Do it.\n"
        "    fixture: tasks/task-1/fixture\n    expected: tasks/task-1/expected\n"
        "    scorer: tasks/task-1/scorer.py\n    max_score: 100\n",
        encoding="utf-8",
    )
    repo = FakeRepo()
    runner = EvalRunner(repo=repo, sandbox=FakeSandbox(), runs_root=tmp_path / "runs")

    run = runner.run(skill_dir=skill_dir, task_pack_dir=pack_dir, network_enabled=False, timeout_seconds=10)

    assert run["id"] == "run-1"
    assert repo.scores[0][3] == 100
    assert repo.finished == ("run-1", "passed", ["trace-1"], None)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
docker compose run --rm coding-agent pytest tests/eval_lab/test_runner.py -q
```

Expected: fails because `runner.py` does not exist.

- [ ] **Step 3: Implement runner**

Create `agent/app/eval_lab/runner.py`:

```python
from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.config import Settings

from .hashing import hash_directory
from .manifests import load_skill_manifest, load_task_pack_manifest
from .repository import EvalRepository
from .sandbox import DockerSandbox
from .scorer import run_scorer


class EvalRunner:
    def __init__(self, repo: EvalRepository | None = None, sandbox: DockerSandbox | None = None, runs_root: Path | None = None) -> None:
        self.repo = repo or EvalRepository()
        self.sandbox = sandbox or DockerSandbox()
        self.runs_root = runs_root or Path(Settings.eval_lab_host_runs_dir)

    def run(self, skill_dir: Path, task_pack_dir: Path, network_enabled: bool, timeout_seconds: int) -> dict:
        skill_manifest = load_skill_manifest(skill_dir)
        task_pack_manifest = load_task_pack_manifest(task_pack_dir)
        skill_hash = hash_directory(skill_dir)
        task_pack_hash = hash_directory(task_pack_dir)
        self.repo.upsert_skill(
            skill_id=skill_manifest.id,
            name=skill_manifest.name,
            version_hash=skill_hash,
            source_type="local_dir",
            source_path=str(skill_dir),
            manifest=skill_manifest.model_dump(),
        )
        self.repo.upsert_task_pack(
            task_pack_id=task_pack_manifest.id,
            name=task_pack_manifest.name,
            domain=task_pack_manifest.domain,
            version_hash=task_pack_hash,
            source_path=str(task_pack_dir),
            manifest=task_pack_manifest.model_dump(),
        )
        run = self.repo.create_eval_run(skill_manifest.id, task_pack_manifest.id)
        trace_ids: list[str] = []
        run_dir = self.runs_root / run["id"]
        run_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.repo.mark_run_running(run["id"], sandbox_container_id=f"{run['id']}-sandbox")
            for task in task_pack_manifest.tasks:
                task_workspace = run_dir / task.id / "workspace"
                if task_workspace.exists():
                    shutil.rmtree(task_workspace)
                shutil.copytree(task_pack_dir / task.fixture, task_workspace)
                task_output = self.sandbox.run_task(
                    run_id=run["id"],
                    task_id=task.id,
                    task_prompt=task.prompt,
                    skill_host_dir=skill_dir,
                    fixture_host_dir=task_pack_dir / task.fixture,
                    workspace_host_dir=task_workspace,
                    network_enabled=network_enabled,
                    timeout_seconds=timeout_seconds,
                )
                trace_ids.extend(task_output.trace_ids)
                output_path = run_dir / task.id / "agent_output.json"
                output_path.write_text(task_output.model_dump_json(), encoding="utf-8")
                score = run_scorer(task_pack_dir / task.scorer, task_workspace, task_pack_dir / task.expected, output_path, timeout_seconds)
                self.repo.add_score(run["id"], task.id, "auto", score.score, score.max_score, score.details)
            self.repo.finish_run(run["id"], "passed", trace_ids)
            return self.repo.get_eval_run(run["id"])
        except Exception as exc:
            self.repo.finish_run(run["id"], "error", trace_ids, error=str(exc))
            return self.repo.get_eval_run(run["id"])
```

- [ ] **Step 4: Run runner test**

Run:

```bash
docker compose run --rm coding-agent pytest tests/eval_lab/test_runner.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit if project git root is isolated**

Run:

```bash
git rev-parse --show-toplevel
```

Expected before committing: `/Users/Thin/Source/git/seasonsolt/agent-lab`.

If the expected root matches, run:

```bash
git add agent/app/eval_lab/runner.py agent/tests/eval_lab/test_runner.py
git commit -m "feat: orchestrate eval runs"
```

If the output is `/Users/Thin`, skip this commit step.

## Task 8: Eval REST API

**Files:**
- Create: `agent/app/eval_lab/routing.py`
- Modify: `agent/app/routing.py`
- Test: `agent/tests/eval_lab/test_eval_api.py`

- [ ] **Step 1: Write failing API tests**

Create `agent/tests/eval_lab/test_eval_api.py`:

```python
from fastapi.testclient import TestClient

from app.eval_lab import routing as eval_routing
from app.main import app


class FakeRunner:
    def run(self, skill_dir, task_pack_dir, network_enabled, timeout_seconds):
        return {"id": "run-1", "status": "passed"}


class FakeRepo:
    def get_eval_run(self, run_id):
        return {"id": run_id, "status": "passed", "skill_id": "skill-1", "task_pack_id": "pack-1", "langfuse_trace_ids": [], "error": None}

    def get_skill(self, skill_id):
        return {"id": skill_id, "name": "Skill", "version_hash": "skill-hash", "manifest": {"tags": []}}

    def get_task_pack(self, task_pack_id):
        return {"id": task_pack_id, "name": "Pack", "domain": "coding", "version_hash": "pack-hash"}

    def list_scores(self, eval_run_id):
        return [{"task_id": "task-1", "score_type": "auto", "score": 100, "max_score": 100, "details": {}}]


def test_create_eval_run(monkeypatch, tmp_path):
    monkeypatch.setattr(eval_routing, "get_runner", lambda: FakeRunner())
    skill = tmp_path / "skill"
    pack = tmp_path / "pack"
    skill.mkdir()
    pack.mkdir()

    with TestClient(app) as client:
        response = client.post("/eval-runs", json={"skill_path": str(skill), "task_pack_path": str(pack)})

    assert response.status_code == 200
    assert response.json()["id"] == "run-1"


def test_get_report(monkeypatch):
    monkeypatch.setattr(eval_routing, "get_repo", lambda: FakeRepo())

    with TestClient(app) as client:
        response = client.get("/eval-runs/run-1/report")

    assert response.status_code == 200
    assert response.json()["final_score"] == 70
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
docker compose run --rm coding-agent pytest tests/eval_lab/test_eval_api.py -q
```

Expected: fails because eval routing does not exist or is not included.

- [ ] **Step 3: Implement eval routing**

Create `agent/app/eval_lab/routing.py`:

```python
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import Settings

from .report import build_report_from_records
from .repository import EvalRepository
from .runner import EvalRunner
from .schemas import EvalRunCreateRequest, EvalRunCreateResponse, EvalRunRecord, EvalReport


router = APIRouter(prefix="/eval-runs", tags=["eval-runs"])


def get_repo() -> EvalRepository:
    return EvalRepository()


def get_runner() -> EvalRunner:
    return EvalRunner()


@router.post("", response_model=EvalRunCreateResponse)
def create_eval_run(payload: EvalRunCreateRequest) -> EvalRunCreateResponse:
    try:
        run = get_runner().run(
            skill_dir=Path(payload.skill_path),
            task_pack_dir=Path(payload.task_pack_path),
            network_enabled=Settings.eval_lab_network_enabled if payload.network_enabled is None else payload.network_enabled,
            timeout_seconds=Settings.eval_lab_task_timeout_seconds if payload.timeout_seconds is None else payload.timeout_seconds,
        )
        return EvalRunCreateResponse(id=run["id"], status=run["status"], report_url=f"/eval-runs/{run['id']}/report")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{run_id}", response_model=EvalRunRecord)
def get_eval_run(run_id: str) -> EvalRunRecord:
    try:
        return EvalRunRecord.model_validate(get_repo().get_eval_run(run_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Eval run '{run_id}' not found") from exc


@router.get("/{run_id}/report", response_model=EvalReport)
def get_eval_report(run_id: str) -> EvalReport:
    repo = get_repo()
    try:
        run = repo.get_eval_run(run_id)
        skill = repo.get_skill(run["skill_id"])
        task_pack = repo.get_task_pack(run["task_pack_id"])
        scores = repo.list_scores(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Eval resource not found: {exc}") from exc
    return build_report_from_records(run, skill, task_pack, scores)
```

- [ ] **Step 4: Include eval router**

Modify `agent/app/routing.py`:

```python
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import orchestrator
from .eval_lab.routing import router as eval_router


router = APIRouter()
router.include_router(eval_router)


class RunRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4000)


class RunResponse(BaseModel):
    success: bool
    output: str
    raw: Dict[str, Any]


@router.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@router.post("/runs", response_model=RunResponse)
def run_agent(payload: RunRequest) -> RunResponse:
    try:
        from .orchestrator import _build_langfuse_callbacks

        result = orchestrator.get_agent().invoke(
            {"messages": [{"role": "user", "content": payload.task}]},
            config={"callbacks": _build_langfuse_callbacks()},
        )
        return RunResponse(success=True, output=orchestrator.extract_response(result), raw={"result": result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
```

- [ ] **Step 5: Run API tests**

Run:

```bash
docker compose run --rm coding-agent pytest tests/eval_lab/test_eval_api.py -q
```

Expected: `2 passed`.

- [ ] **Step 6: Commit if project git root is isolated**

Run:

```bash
git rev-parse --show-toplevel
```

Expected before committing: `/Users/Thin/Source/git/seasonsolt/agent-lab`.

If the expected root matches, run:

```bash
git add agent/app/eval_lab/routing.py agent/app/routing.py agent/tests/eval_lab/test_eval_api.py
git commit -m "feat: expose eval run API"
```

If the output is `/Users/Thin`, skip this commit step.

## Task 9: Host CLI

**Files:**
- Create: `skill_lab/__init__.py`
- Create: `skill_lab/cli.py`
- Test: `agent/tests/eval_lab/test_cli.py`

- [ ] **Step 1: Write failing CLI argument test**

Create `agent/tests/eval_lab/test_cli.py`:

```python
from skill_lab.cli import build_parser


def test_cli_parser_accepts_run_command():
    parser = build_parser()
    args = parser.parse_args(["run", "--skill", "./skills/demo", "--task-pack", "./task_packs/basic", "--api-url", "http://localhost:8000"])

    assert args.command == "run"
    assert args.skill == "./skills/demo"
    assert args.task_pack == "./task_packs/basic"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
docker compose run --rm coding-agent pytest tests/eval_lab/test_cli.py -q
```

Expected: fails because `skill_lab.cli` does not exist.

- [ ] **Step 3: Create CLI package marker**

Create `skill_lab/__init__.py`:

```python
"""Host-side CLI for Agent Lab skill evaluation."""
```

- [ ] **Step 4: Implement CLI**

Create `skill_lab/cli.py`:

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skill-lab")
    subcommands = parser.add_subparsers(dest="command", required=True)
    run = subcommands.add_parser("run")
    run.add_argument("--skill", required=True)
    run.add_argument("--task-pack", required=True)
    run.add_argument("--api-url", default="http://localhost:8000")
    run.add_argument("--network", action="store_true")
    run.add_argument("--timeout-seconds", type=int, default=None)
    return parser


def post_json(url: str, payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(url: str) -> dict:
    with urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def run_command(args: argparse.Namespace) -> int:
    skill_path = Path(args.skill).resolve()
    task_pack_path = Path(args.task_pack).resolve()
    if not (skill_path / "SKILL.md").exists():
        print(f"Missing SKILL.md under {skill_path}", file=sys.stderr)
        return 2
    if not (task_pack_path / "taskpack.yaml").exists():
        print(f"Missing taskpack.yaml under {task_pack_path}", file=sys.stderr)
        return 2
    try:
        created = post_json(
            f"{args.api_url.rstrip('/')}/eval-runs",
            {
                "skill_path": str(skill_path),
                "task_pack_path": str(task_pack_path),
                "network_enabled": args.network,
                "timeout_seconds": args.timeout_seconds,
            },
        )
        report = get_json(f"{args.api_url.rstrip()}{created['report_url']}")
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"Eval request failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return run_command(args)
    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run CLI tests**

Run:

```bash
docker compose run --rm coding-agent pytest tests/eval_lab/test_cli.py -q
```

Expected: `1 passed`.

- [ ] **Step 6: Commit if project git root is isolated**

Run:

```bash
git rev-parse --show-toplevel
```

Expected before committing: `/Users/Thin/Source/git/seasonsolt/agent-lab`.

If the expected root matches, run:

```bash
git add skill_lab/__init__.py skill_lab/cli.py agent/tests/eval_lab/test_cli.py
git commit -m "feat: add skill lab CLI"
```

If the output is `/Users/Thin`, skip this commit step.

## Task 10: Sample Skill And Task Pack

**Files:**
- Create: `skills/example-coding-skill/SKILL.md`
- Create: `skills/example-coding-skill/manifest.yaml`
- Create: `task_packs/coding-basic/taskpack.yaml`
- Create: `task_packs/coding-basic/tasks/fix-bug-001/task.yaml`
- Create: `task_packs/coding-basic/tasks/fix-bug-001/fixture/README.md`
- Create: `task_packs/coding-basic/tasks/fix-bug-001/expected/README.md`
- Create: `task_packs/coding-basic/tasks/fix-bug-001/scorer.py`
- Test: `agent/tests/eval_lab/test_sample_assets.py`

- [ ] **Step 1: Create sample skill**

Create `skills/example-coding-skill/SKILL.md`:

```markdown
---
name: example-coding-skill
description: Minimal coding skill used by Agent Lab smoke tests.
---

# Example Coding Skill

When asked to edit a workspace, inspect files first, make the smallest correct change, and verify the result when a verification command is available.
```

Create `skills/example-coding-skill/manifest.yaml`:

```yaml
id: example-coding-skill
name: Example Coding Skill
entry: SKILL.md
tags:
  - coding
  - smoke-test
```

- [ ] **Step 2: Create sample task pack**

Create `task_packs/coding-basic/taskpack.yaml`:

```yaml
id: coding-basic
name: Coding Basic
domain: coding
tasks:
  - id: fix-bug-001
    type: coding
    prompt: Read README.md and update it so it contains the exact phrase "skill evaluation complete".
    fixture: tasks/fix-bug-001/fixture
    expected: tasks/fix-bug-001/expected
    scorer: tasks/fix-bug-001/scorer.py
    max_score: 100
```

Create `task_packs/coding-basic/tasks/fix-bug-001/task.yaml`:

```yaml
id: fix-bug-001
type: coding
prompt: Read README.md and update it so it contains the exact phrase "skill evaluation complete".
max_score: 100
```

Create `task_packs/coding-basic/tasks/fix-bug-001/fixture/README.md`:

```markdown
# Fixture

This file needs one deterministic edit.
```

Create `task_packs/coding-basic/tasks/fix-bug-001/expected/README.md`:

```markdown
# Fixture

This file needs one deterministic edit.

skill evaluation complete
```

- [ ] **Step 3: Create sample scorer**

Create `task_packs/coding-basic/tasks/fix-bug-001/scorer.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--agent-output", required=True)
    args = parser.parse_args()
    workspace_readme = Path(args.workspace) / "README.md"
    expected_readme = Path(args.expected) / "README.md"
    actual = workspace_readme.read_text(encoding="utf-8") if workspace_readme.exists() else ""
    expected = expected_readme.read_text(encoding="utf-8")
    matched = actual.strip() == expected.strip()
    print(
        json.dumps(
            {
                "score": 100 if matched else 0,
                "max_score": 100,
                "details": {
                    "readme_matched": matched,
                    "expected_phrase_present": "skill evaluation complete" in actual,
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Write sample asset validation test**

Create `agent/tests/eval_lab/test_sample_assets.py`:

```python
from pathlib import Path

from app.eval_lab.manifests import load_skill_manifest, load_task_pack_manifest


def test_sample_skill_and_task_pack_are_valid():
    root = Path("/lab")
    skill = load_skill_manifest(root / "skills" / "example-coding-skill")
    task_pack = load_task_pack_manifest(root / "task_packs" / "coding-basic")

    assert skill.id == "example-coding-skill"
    assert task_pack.id == "coding-basic"
    assert task_pack.tasks[0].id == "fix-bug-001"
```

- [ ] **Step 5: Run sample validation test**

Run:

```bash
docker compose run --rm coding-agent pytest tests/eval_lab/test_sample_assets.py -q
```

Expected: `1 passed`.

- [ ] **Step 6: Commit if project git root is isolated**

Run:

```bash
git rev-parse --show-toplevel
```

Expected before committing: `/Users/Thin/Source/git/seasonsolt/agent-lab`.

If the expected root matches, run:

```bash
git add skills task_packs agent/tests/eval_lab/test_sample_assets.py
git commit -m "test: add sample skill evaluation pack"
```

If the output is `/Users/Thin`, skip this commit step.

## Task 11: End-To-End Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Start the stack with sandbox settings**

Run:

```bash
mkdir -p /tmp/agent-lab-runs
docker compose up -d --build
```

Expected: `coding-agent`, `postgres`, `langfuse-web`, `langfuse-worker`, `clickhouse`, `redis`, and `minio` are running.

- [ ] **Step 2: Verify health**

Run:

```bash
curl -sS http://localhost:8000/health
```

Expected:

```json
{"status":"ok"}
```

- [ ] **Step 3: Run all unit tests**

Run:

```bash
docker compose run --rm coding-agent pytest tests -q
```

Expected: all tests pass.

- [ ] **Step 4: Run a sample evaluation via API**

Run:

```bash
curl -sS -X POST http://localhost:8000/eval-runs \
  -H "Content-Type: application/json" \
  -d '{
    "skill_path": "/Users/Thin/Source/git/seasonsolt/agent-lab/skills/example-coding-skill",
    "task_pack_path": "/Users/Thin/Source/git/seasonsolt/agent-lab/task_packs/coding-basic",
    "network_enabled": true,
    "timeout_seconds": 300
  }'
```

Expected: JSON contains `id`, `status`, and `report_url`.

- [ ] **Step 5: Fetch the generated report**

Run:

```bash
RUN_ID="$(curl -sS -X POST http://localhost:8000/eval-runs \
  -H "Content-Type: application/json" \
  -d '{
    "skill_path": "/Users/Thin/Source/git/seasonsolt/agent-lab/skills/example-coding-skill",
    "task_pack_path": "/Users/Thin/Source/git/seasonsolt/agent-lab/task_packs/coding-basic",
    "network_enabled": true,
    "timeout_seconds": 300
  }' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
curl -sS "http://localhost:8000/eval-runs/${RUN_ID}/report"
```

Expected: report contains `skill`, `task_pack`, `final_score`, `auto_score`, `value_score`, `trace_ids`, and `verdict`.

- [ ] **Step 6: Run a sample evaluation via CLI**

Run:

```bash
python3 -m skill_lab.cli run \
  --skill ./skills/example-coding-skill \
  --task-pack ./task_packs/coding-basic \
  --api-url http://localhost:8000 \
  --network
```

Expected: pretty-printed JSON report.

- [ ] **Step 7: Verify app-owned Postgres records**

Run:

```bash
docker compose exec -T postgres psql -U postgres -d postgres -c "
SELECT count(*) AS eval_runs FROM eval_runs;
SELECT count(*) AS eval_scores FROM eval_scores;
"
```

Expected: both counts are greater than `0`.

- [ ] **Step 8: Verify Langfuse traces still land in ClickHouse**

Run:

```bash
docker compose exec -T clickhouse clickhouse-client -q "SELECT count() FROM default.traces; SELECT count() FROM default.observations;"
```

Expected: both counts are greater than `0`.

- [ ] **Step 9: Document usage**

Append this section to `README.md`:

````markdown

## Skill Evaluation Lab

Run a sample skill evaluation:

```bash
mkdir -p /tmp/agent-lab-runs
docker compose up -d --build
python3 -m skill_lab.cli run \
  --skill ./skills/example-coding-skill \
  --task-pack ./task_packs/coding-basic \
  --api-url http://localhost:8000 \
  --network
```

Eval API:

- `POST /eval-runs`
- `GET /eval-runs/{id}`
- `GET /eval-runs/{id}/report`

The evaluation runner stores app metadata in Postgres tables prefixed with `eval_`. Langfuse trace data remains in ClickHouse and is referenced by trace ID in reports.
````

- [ ] **Step 10: Commit if project git root is isolated**

Run:

```bash
git rev-parse --show-toplevel
```

Expected before committing: `/Users/Thin/Source/git/seasonsolt/agent-lab`.

If the expected root matches, run:

```bash
git add README.md
git commit -m "docs: explain skill evaluation lab usage"
```

If the output is `/Users/Thin`, skip this commit step.

## Self-Review Checklist

- Spec coverage: local `SKILL.md`, task packs, CLI + API, Docker sandbox per run, Postgres metadata, scoring, reports, and Langfuse trace references are all covered by tasks.
- No Web UI, marketplace, Git URL ingestion, distributed workers, or leaderboard work is included.
- Data names are consistent: `eval_skills`, `eval_task_packs`, `eval_runs`, `eval_scores`.
- API endpoints are consistent: `POST /eval-runs`, `GET /eval-runs/{id}`, `GET /eval-runs/{id}/report`.
- Docker sandbox is explicit: fresh coding-agent container per run, with read-only skill and fixture mounts and writable workspace.
- Commit steps are guarded because the current git root is `/Users/Thin`.
