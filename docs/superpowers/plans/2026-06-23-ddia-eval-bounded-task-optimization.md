# DDIA Eval Bounded Task Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the DDIA Skill comparison finish cleanly often enough that Agent Lab measures coding quality instead of universal sandbox timeouts.

**Architecture:** Keep the existing Agent Lab CLI, Eval API, Docker sandbox, scorer, and evidence export flow. Tighten the sandbox prompt builder so every coding task has bounded evaluation instructions, then tighten the DDIA order-projection task text and fixture README so the agent has concrete scorer-aligned requirements. Validate first with unit tests, then with one baseline/treatment smoke comparison, then with a repeated comparison whose artifacts can refresh `ddia-skill` evidence.

**Tech Stack:** Python 3.12, FastAPI service code, pytest, Docker Compose, YAML task packs, Agent Lab CLI, Langfuse tracing.

---

## Scope Check

This plan covers one focused optimization: making the existing DDIA coding eval bounded and finishable. It does not change external repo ingestion, Langfuse integration, comparison verdict rules, Docker sandbox isolation, model credentials, or the DDIA scorer.

The plan touches `agent-lab` source and task-pack files. It may refresh static evidence artifacts in `/Users/Thin/Source/git/seasonsolt/ddia-skill` after a meaningful repeated comparison is generated.

## File Structure

Agent Lab repository root: `/Users/Thin/Source/git/seasonsolt/agent-lab`

- Modify `agent/app/eval_lab/sandbox.py`: add bounded evaluation and stop conditions to `build_task_prompt`.
- Modify `agent/tests/eval_lab/test_sandbox.py`: assert the sandbox prompt includes bounded-eval constraints while preserving skill path, workspace, and task text.
- Modify `agent/tests/eval_lab/test_sample_assets.py`: assert the DDIA coding task pack is valid and its prompt carries the scorer-critical order-projection requirements.
- Modify `task_packs/ddia-coding-real/taskpack.yaml`: replace the broad prompt with a concrete bounded DDIA coding prompt.
- Modify `task_packs/ddia-coding-real/tasks/order-event-projection-001/fixture/README.md`: align fixture instructions with the task-pack prompt so agents that inspect files see the same behavioral contract.

DDIA Skill repository root: `/Users/Thin/Source/git/seasonsolt/ddia-skill`

- Optionally refresh `evaluation/agent-lab/latest-comparison.json` from generated Agent Lab output after the repeated comparison is no longer timeout-dominated.
- Optionally refresh `evaluation/agent-lab/latest-comparison.md` from generated Agent Lab output after the repeated comparison is no longer timeout-dominated.

## Task 1: Bound The Sandbox Prompt

**Files:**
- Modify: `agent/tests/eval_lab/test_sandbox.py`
- Modify: `agent/app/eval_lab/sandbox.py`

- [ ] **Step 1: Add the failing prompt constraint test**

Append this test after `test_build_task_prompt_includes_skill_workspace_and_task` in `agent/tests/eval_lab/test_sandbox.py`:

```python
def test_build_task_prompt_includes_bounded_evaluation_constraints():
    prompt = build_task_prompt(
        skill_container_path=Path("/skills/demo/SKILL.md"),
        task_prompt="Fix the failing test.",
    )

    expected_phrases = [
        "This is a bounded evaluation task.",
        "Edit only files needed to satisfy the task.",
        "Do not add dependencies.",
        "Do not spend time on documentation unless the task asks for it.",
        "Prefer a small correct implementation over exploration.",
        "When the implementation is complete, stop and return a concise summary.",
    ]
    for phrase in expected_phrases:
        assert phrase in prompt
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_sandbox.py::test_build_task_prompt_includes_bounded_evaluation_constraints -q
```

Expected: the new test fails because `build_task_prompt` does not yet include bounded evaluation instructions.

- [ ] **Step 3: Implement the bounded prompt**

Replace `build_task_prompt` in `agent/app/eval_lab/sandbox.py` with:

```python
def build_task_prompt(skill_container_path: Path, task_prompt: str) -> str:
    return "\n".join(
        [
            f"Use the skill instructions at {skill_container_path.as_posix()}.",
            "Work inside /workspace.",
            "This is a bounded evaluation task.",
            "Edit only files needed to satisfy the task.",
            "Do not add dependencies.",
            "Do not spend time on documentation unless the task asks for it.",
            "Prefer a small correct implementation over exploration.",
            "When the implementation is complete, stop and return a concise summary.",
            f"Task: {task_prompt}",
        ]
    )
```

- [ ] **Step 4: Run the sandbox tests**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_sandbox.py -q
```

Expected: all sandbox tests pass.

- [ ] **Step 5: Commit the sandbox prompt change**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
git add agent/app/eval_lab/sandbox.py agent/tests/eval_lab/test_sandbox.py
git commit -m "fix: bound eval sandbox task prompt"
```

## Task 2: Tighten The DDIA Task Contract

**Files:**
- Modify: `agent/tests/eval_lab/test_sample_assets.py`
- Modify: `task_packs/ddia-coding-real/taskpack.yaml`
- Modify: `task_packs/ddia-coding-real/tasks/order-event-projection-001/fixture/README.md`

- [ ] **Step 1: Add the failing DDIA task-pack test**

Append this test to `agent/tests/eval_lab/test_sample_assets.py`:

```python
def test_ddia_coding_task_pack_is_valid_and_bounded():
    root = Path("/lab")
    task_pack = load_task_pack_manifest(root / "task_packs" / "ddia-coding-real")

    assert task_pack.id == "ddia-coding-real"
    assert task_pack.tasks[0].id == "order-event-projection-001"

    prompt = task_pack.tasks[0].prompt
    expected_phrases = [
        "OrderProjector.apply(event)",
        "order_projection.py",
        "at-least-once order event stream",
        "ignore duplicate deliveries",
        "Ignore stale lower-version events.",
        'terminal status "cancelled"',
        "dead_letters",
        "must not create a durable order",
        "Do not add dependencies",
    ]
    for phrase in expected_phrases:
        assert phrase in prompt
```

- [ ] **Step 2: Run the focused asset test and confirm it fails**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_sample_assets.py::test_ddia_coding_task_pack_is_valid_and_bounded -q
```

Expected: the new test fails because the current DDIA prompt is still broad and does not include the scorer-critical contract.

- [ ] **Step 3: Replace the DDIA task-pack prompt**

Replace `task_packs/ddia-coding-real/taskpack.yaml` with:

```yaml
id: ddia-coding-real
name: DDIA Coding Real Scenario
domain: backend-data-systems
tasks:
  - id: order-event-projection-001
    type: coding
    prompt: >-
      Implement OrderProjector.apply(event) in order_projection.py for an
      at-least-once order event stream. Maintain a deterministic per-order read
      model with status, amount, version, and enough event-id evidence to
      ignore duplicate deliveries. Ignore stale lower-version events. Valid
      status flow: order_created creates status "created"; payment_authorized
      moves created orders to "paid"; order_shipped moves paid orders to
      "shipped"; order_cancelled moves created or paid orders to terminal
      status "cancelled". Preserve terminal cancellation when later events
      arrive, but record invalid higher-version transitions in dead_letters and
      keep version evidence up to date. Payment events that arrive before
      order_created must not create a durable order; record them as dead
      letters. Do not add dependencies or edit documentation.
    fixture: tasks/order-event-projection-001/fixture
    expected: tasks/order-event-projection-001/expected
    scorer: tasks/order-event-projection-001/scorer.py
    max_score: 100
```

- [ ] **Step 4: Align the fixture README**

Replace `task_packs/ddia-coding-real/tasks/order-event-projection-001/fixture/README.md` with:

```markdown
# Order Projection Fixture

Implement `OrderProjector.apply(event)` in `order_projection.py`.

The stream is at-least-once and can deliver duplicate or out-of-order events. A correct projection should be deterministic after replay and should not let stale derived data overwrite newer facts.

Required behavior:

- Maintain a per-order read model with `status`, `amount`, and `version`.
- Track event ids so duplicate deliveries do not change replay results.
- Ignore stale lower-version events.
- Treat cancellation as terminal while keeping version evidence for later invalid higher-version events.
- Record invalid transitions in `dead_letters`.
- Do not create a durable order from a payment event that arrives before `order_created`.

Do not add dependencies or edit documentation.
```

- [ ] **Step 5: Run the asset tests**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_sample_assets.py -q
```

Expected: the sample asset tests pass, including the DDIA task-pack validation test.

- [ ] **Step 6: Commit the DDIA task contract change**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
git add agent/tests/eval_lab/test_sample_assets.py task_packs/ddia-coding-real/taskpack.yaml task_packs/ddia-coding-real/tasks/order-event-projection-001/fixture/README.md
git commit -m "fix: bound DDIA coding task contract"
```

## Task 3: Run Local Regression Verification

**Files:**
- No source changes expected.

- [ ] **Step 1: Validate Docker Compose configuration**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
docker compose config >/tmp/agent-lab-compose-config.yaml
```

Expected: command exits `0` and writes `/tmp/agent-lab-compose-config.yaml`.

- [ ] **Step 2: Run focused eval-lab tests**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_sandbox.py tests/eval_lab/test_sample_assets.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run the full Agent Lab test suite**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
docker compose run --build --rm coding-agent pytest -q
```

Expected: the full test suite passes. The previous baseline was `72 passed, 3 warnings`; the new expected count is higher because two tests are added.

## Task 4: Run Live DDIA Smoke And Repeated Comparisons

**Files:**
- Generated outside repo: `/tmp/agent-lab-ddia-smoke/comparison.json`
- Generated outside repo: `/tmp/agent-lab-ddia-smoke/comparison.md`
- Generated outside repo: `/tmp/agent-lab-ddia-evidence/comparison.json`
- Generated outside repo: `/tmp/agent-lab-ddia-evidence/comparison.md`

- [ ] **Step 1: Start the Agent Lab service stack**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
docker compose up -d --build coding-agent
curl -fsS http://localhost:8000/health
```

Expected: `curl` prints a healthy response. Do not write API keys or model credentials into source files; use the existing runtime environment.

- [ ] **Step 2: Run one baseline/treatment smoke comparison**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
rm -rf /tmp/agent-lab-ddia-smoke
python3 -m skill_lab.cli compare \
  --baseline ./skills/example-coding-skill \
  --treatment-repo https://github.com/seasonsolt/ddia-skill \
  --treatment-skill-path skills/ddia-system-design \
  --task-pack ./task_packs/ddia-coding-real \
  --api-url http://localhost:8000 \
  --runs 1 \
  --network \
  --timeout-seconds 300 \
  --output-dir /tmp/agent-lab-ddia-smoke
```

Expected: command exits `0`, and both `/tmp/agent-lab-ddia-smoke/comparison.json` and `/tmp/agent-lab-ddia-smoke/comparison.md` exist.

- [ ] **Step 3: Inspect smoke timeout rates**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("/tmp/agent-lab-ddia-smoke/comparison.json").read_text(encoding="utf-8"))
print(json.dumps({
    "baseline_timeout_rate": payload["baseline"]["timeout_rate"],
    "treatment_timeout_rate": payload["treatment"]["timeout_rate"],
    "baseline_run_ids": payload["baseline"]["run_ids"],
    "treatment_run_ids": payload["treatment"]["run_ids"],
    "verdict": payload["verdict"],
}, indent=2, sort_keys=True))

assert payload["baseline"]["timeout_rate"] < 1.0
assert payload["treatment"]["timeout_rate"] < 1.0
PY
```

Expected: timeout rates are below `1.0` for both arms. If either arm is still `1.0`, stop execution and debug the live run before creating new DDIA evidence.

- [ ] **Step 4: Verify report trace IDs for smoke runs**

Run:

```bash
python3 - <<'PY'
import json
import urllib.request
from pathlib import Path

payload = json.loads(Path("/tmp/agent-lab-ddia-smoke/comparison.json").read_text(encoding="utf-8"))
run_ids = payload["baseline"]["run_ids"] + payload["treatment"]["run_ids"]
reports = []
for run_id in run_ids:
    with urllib.request.urlopen(f"http://localhost:8000/eval-runs/{run_id}/report", timeout=30) as response:
        report = json.loads(response.read().decode("utf-8"))
    reports.append({"run_id": run_id, "trace_ids": report["trace_ids"]})

print(json.dumps(reports, indent=2, sort_keys=True))
assert any(report["trace_ids"] for report in reports)
PY
```

Expected: at least one smoke report contains Langfuse trace IDs. If all trace ID lists are empty, do not call Langfuse validation complete; inspect service logs and Langfuse configuration in a separate debugging pass.

- [ ] **Step 5: Run the repeated comparison**

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

Expected: command exits `0`, writes `comparison.json` and `comparison.md`, and the result is not dominated by 100% timeout on both arms.

- [ ] **Step 6: Inspect the repeated comparison summary**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("/tmp/agent-lab-ddia-evidence/comparison.json").read_text(encoding="utf-8"))
summary = {
    "baseline": payload["baseline"],
    "treatment": payload["treatment"],
    "score_lift": payload["score_lift"],
    "pass_rate_delta": payload["pass_rate_delta"],
    "verdict": payload["verdict"],
}
print(json.dumps(summary, indent=2, sort_keys=True))

assert payload["baseline"]["timeout_rate"] < 1.0 or payload["treatment"]["timeout_rate"] < 1.0
assert payload["verdict"] in {"useful", "weak", "harmful", "inconclusive"}
PY
```

Expected: the comparison produces a legitimate verdict. The verdict does not need to be positive; it only needs to be based on at least some completed benchmark behavior.

## Task 5: Refresh DDIA Skill Evidence After Meaningful Comparison

**Files:**
- Modify: `/Users/Thin/Source/git/seasonsolt/ddia-skill/evaluation/agent-lab/latest-comparison.json`
- Modify: `/Users/Thin/Source/git/seasonsolt/ddia-skill/evaluation/agent-lab/latest-comparison.md`

- [ ] **Step 1: Copy the generated evidence into DDIA Skill**

Run only after Task 4 shows the repeated comparison is not 100% timeout on both arms:

```bash
cd /Users/Thin/Source/git/seasonsolt/ddia-skill
cp /tmp/agent-lab-ddia-evidence/comparison.json evaluation/agent-lab/latest-comparison.json
cp /tmp/agent-lab-ddia-evidence/comparison.md evaluation/agent-lab/latest-comparison.md
```

Expected: both DDIA Skill evidence files are updated with the latest Agent Lab output.

- [ ] **Step 2: Run DDIA Skill evidence tests**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/ddia-skill
python3 -m unittest tests/test_agent_lab_evidence.py -v
```

Expected: all Agent Lab evidence tests pass.

- [ ] **Step 3: Run DDIA Skill quality checks**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/ddia-skill
scripts/check_ddia_skill_quality.py --repo .
scripts/check_ddia_benchmark.py --repo .
```

Expected: both checks pass. If the local Python environment lacks optional dependencies required by the full DDIA test suite, reuse the existing `/tmp/ddia-skill-venv` validation path from the previous run instead of adding dependencies to the repository.

- [ ] **Step 4: Commit refreshed DDIA evidence**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/ddia-skill
git add evaluation/agent-lab/latest-comparison.json evaluation/agent-lab/latest-comparison.md
git commit -m "docs: refresh Agent Lab DDIA evidence"
```

Expected: a DDIA Skill commit records the refreshed external evidence. Do not push unless the user explicitly asks.

## Task 6: Final Agent Lab Verification And Status Report

**Files:**
- No source changes expected.

- [ ] **Step 1: Confirm Agent Lab git status**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/agent-lab
git status --short --branch
git log --oneline -5
```

Expected: Agent Lab is on the working branch with only intentional commits and no unrelated unstaged source changes.

- [ ] **Step 2: Confirm DDIA Skill git status if evidence was refreshed**

Run:

```bash
cd /Users/Thin/Source/git/seasonsolt/ddia-skill
git status --short --branch
git log --oneline -5
```

Expected: DDIA Skill has the refreshed evidence commit if Task 5 ran.

- [ ] **Step 3: Report the validation outcome**

Include these facts in the final report:

```text
Agent Lab tests:
- docker compose config
- docker compose run --build --rm coding-agent pytest -q

Live DDIA comparison:
- smoke comparison output directory
- repeated comparison output directory
- baseline timeout rate
- treatment timeout rate
- score lift
- pass-rate delta
- verdict
- run IDs
- trace ID check result

DDIA Skill evidence:
- whether latest-comparison.json and latest-comparison.md were refreshed
- DDIA Skill validation commands and results
```

## Plan Self-Review

- Spec coverage: sandbox prompt constraints are covered by Task 1; DDIA task prompt clarity is covered by Task 2; timeout visibility and live smoke/repeated validation are covered by Task 4; optional DDIA evidence refresh is covered by Task 5.
- Placeholder scan: no step uses open-ended implementation language without exact files, code, commands, and expected outcomes.
- Type consistency: `build_task_prompt(skill_container_path: Path, task_prompt: str) -> str` keeps its current signature, and task-pack tests continue to use `load_task_pack_manifest`.
- Scope control: the plan does not change verdict semantics, the scorer, Docker isolation, Langfuse wiring, or credential management.
