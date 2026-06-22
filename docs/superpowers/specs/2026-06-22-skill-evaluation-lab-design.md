# Skill Evaluation Lab Design

## Goal

Build Agent Lab into a unified skill evaluation lab. The lab should separate skills with real domain value from skills that are only plausible LLM-generated text. It should do this through reproducible tasks, isolated execution, trace evidence, scoring, and reports that explain why a skill is useful, weak, harmful, or inconclusive.

## Confirmed Scope

- Use one unified evaluation framework for coding skills, business-domain skills, and agent-engineering skills.
- Use local skill directories with `SKILL.md` as the MVP skill input format.
- Use mixed task packs: automatic scoring plus rubric, LLM judge, or human review.
- Use CLI + API as the MVP interaction model.
- Use Docker sandbox per run for execution isolation.
- Keep Langfuse as the trace and process-observation layer.
- Do not build a Web UI in the MVP.

## Current Foundation

The project already has:

- A Docker Compose stack.
- A FastAPI coding-agent service.
- Langfuse web and worker services.
- Postgres, ClickHouse, Redis, and MinIO for Langfuse.
- A `/runs` API that can invoke the coding agent.
- Langfuse tracing wired into agent execution.

The MVP should build on this foundation instead of replacing it.

## Architecture

```text
CLI
  -> Eval API
      -> Skill Registry
      -> Task Pack Registry
      -> Run Orchestrator
          -> Docker Sandbox per Run
              -> Coding Agent
              -> Skill + Task Fixture
          -> Langfuse Trace
      -> Score Store
      -> Report API
```

The standard flow is:

1. The CLI receives `--skill` and `--task-pack`.
2. The API computes `skill_hash` and `task_pack_hash`.
3. The API creates an eval run record.
4. The run orchestrator creates a dedicated Docker sandbox for the run.
5. The sandbox mounts the skill and task fixture read-only, and mounts a writable run workspace.
6. A per-run coding-agent container executes each task inside the sandbox.
7. Langfuse records traces, model calls, tool calls, token usage, latency, and errors.
8. Scorers evaluate the run outputs.
9. The API stores scores and exposes a report.

## MVP Components

### CLI

Primary local interface for running evaluations.

Example:

```bash
skill-lab run \
  --skill ./skills/example-coding-skill \
  --task-pack ./task_packs/coding-basic
```

The CLI should:

- Validate local paths.
- Call the Eval API.
- Stream high-level run status.
- Print the final report location and score summary.

### Eval API

FastAPI remains the service boundary.

MVP endpoints:

```text
POST /eval-runs
GET /eval-runs/{id}
GET /eval-runs/{id}/report
```

The existing `/runs` endpoint can remain as a low-level coding-agent API. The evaluation API should orchestrate skill and task-pack execution around it.

### Skill Registry

Tracks evaluated skills and their immutable identity.

MVP input format:

```text
skills/
  example-coding-skill/
    SKILL.md
    manifest.yaml
```

Example manifest:

```yaml
id: example-coding-skill
name: Example Coding Skill
entry: SKILL.md
tags:
  - coding
  - testing
```

`version_hash` must be derived from `SKILL.md` and `manifest.yaml`.

### Task Pack Registry

Tracks reproducible task packs.

Example:

```text
task_packs/
  coding-basic/
    taskpack.yaml
    tasks/
      fix-bug-001/
        task.yaml
        fixture/
        expected/
        scorer.py
```

Example task pack:

```yaml
id: coding-basic
name: Coding Basic
domain: coding
tasks:
  - id: fix-bug-001
    type: coding
    prompt: Fix the failing test.
    fixture: tasks/fix-bug-001/fixture
    expected: tasks/fix-bug-001/expected
    scorer: tasks/fix-bug-001/scorer.py
    max_score: 100
```

`version_hash` must be derived from `taskpack.yaml` and all task files used by the pack.

### Docker Sandbox

Each eval run should execute in a dedicated Docker sandbox.

For the MVP, the sandbox is a fresh coding-agent container created for the run, not a shared long-lived workspace. The orchestrator should start it with the run-specific mounts and environment, call its `/runs` endpoint, then clean it up after scoring.

The sandbox should mount:

- Skill directory as read-only.
- Task fixture as read-only.
- Run workspace as writable.
- Required runtime config as environment variables.

The sandbox should enforce:

- Per-task timeout.
- Configurable network mode.
- Clean workspace per run.
- Container cleanup after completion.

This is stricter than a shared `/workspace` and is required for trustworthy evaluation.

## Data Model

MVP tables should live in Postgres as app-owned tables. Langfuse trace data remains in ClickHouse and should be linked by trace IDs.

MVP tables:

```text
skills
- id
- name
- version_hash
- source_type
- source_path
- manifest
- created_at

task_packs
- id
- name
- domain
- version_hash
- source_path
- manifest
- created_at

eval_runs
- id
- skill_id
- task_pack_id
- status
- sandbox_container_id
- langfuse_trace_ids
- started_at
- finished_at
- error

scores
- id
- eval_run_id
- task_id
- score_type
- score
- max_score
- details
- created_at
```

Status values:

```text
queued
running
passed
failed
error
```

Score types:

```text
auto
rubric
llm_judge
human
```

## Evaluation Protocol

An eval run contains one or more task runs:

```text
EvalRun
  -> TaskRun
      -> prepare sandbox
      -> inject skill
      -> inject fixture
      -> call coding-agent /runs
      -> collect output
      -> run auto scorer
      -> optional rubric scorer
      -> persist score + trace ids
```

Standard task input:

```json
{
  "skill_path": "/skills/example-coding-skill/SKILL.md",
  "workspace_path": "/workspace",
  "task": "Fix the failing test.",
  "constraints": {
    "network": false,
    "timeout_seconds": 300,
    "max_cost_usd": 1.0
  }
}
```

Standard task output:

```json
{
  "task_id": "fix-bug-001",
  "status": "passed",
  "agent_output": "...",
  "changed_files": ["src/foo.py", "tests/test_foo.py"],
  "trace_id": "langfuse-trace-id",
  "scores": [
    {
      "type": "auto",
      "score": 80,
      "max_score": 100,
      "details": {
        "tests_passed": true,
        "diff_constraints_passed": true
      }
    }
  ]
}
```

## Scoring

The MVP uses mixed scoring:

```text
final_score = auto_score * 0.7 + rubric_score * 0.3
```

The report must always show the components separately. The total score is useful, but the lab's purpose is evidence, not only ranking.

### Automatic Score

Default weight: 70%.

Signals:

- Tests passed.
- Expected output or diff matched.
- File-change constraints passed.
- No timeout.
- No execution error.
- Cost and token budget respected.

### Value Score

Default weight: 30%.

Signals:

- The skill shows behavior beyond generic prompting.
- The result reduces expert review effort.
- The output follows domain-specific judgment.
- The method is reusable across similar tasks.
- The run avoids harmful or misleading actions.

Value scoring may be produced by rubric, LLM judge, or human review.

## Report

The report should answer whether a skill has real value.

Report sections:

```text
Skill Value Report
- Skill identity: name, hash, tags
- Task pack identity: name, hash, domain
- Run summary: pass rate, average score, average cost, average duration
- Auto evidence: tests, diffs, constraints, errors
- Value evidence: rubric comments, judge notes, human review
- Trace evidence: Langfuse trace links
- Verdict: useful / weak / harmful / inconclusive
```

Verdict rules:

- `useful`: high automatic score and credible value evidence.
- `weak`: passes basic tasks but lacks domain-specific value.
- `harmful`: fails constraints, produces misleading output, or creates unsafe changes.
- `inconclusive`: insufficient evidence or unstable results.

## Non-Goals For MVP

- Public marketplace.
- Web UI.
- Git URL skill ingestion.
- Multi-tenant permission model.
- Distributed evaluation workers.
- Full CI integration.
- Long-term leaderboard governance.

## Open Implementation Notes

- The existing Langfuse stack stores trace data in ClickHouse; report generation should reference trace IDs instead of duplicating full traces.
- The current project directory is not an isolated git repository; implementation should avoid relying on repository-level git metadata until that is resolved.
- Secrets must remain environment-driven and must not be committed into source files.

## Acceptance Criteria

- A local `SKILL.md` directory can be evaluated against a local task pack.
- Each run executes in a fresh Docker sandbox.
- The run produces Langfuse traces.
- The run produces automatic score records.
- The API can return run status and a report.
- The CLI can start a run and print the report summary.
- Skill and task pack hashes are recorded in every report.
