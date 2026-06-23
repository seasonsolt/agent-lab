import json
import shutil
import subprocess
import sys
from pathlib import Path

from app.eval_lab.manifests import load_skill_manifest, load_task_pack_manifest
from app.eval_lab.workflows import load_workflow_manifest


def test_sample_skill_and_task_pack_are_valid():
    root = Path("/lab")
    skill = load_skill_manifest(root / "skills" / "example-coding-skill")
    task_pack = load_task_pack_manifest(root / "task_packs" / "coding-basic")

    assert skill.id == "example-coding-skill"
    assert task_pack.id == "coding-basic"
    assert task_pack.tasks[0].id == "fix-bug-001"


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


def test_java_skills_bench_task_pack_is_valid():
    root = Path("/lab")
    task_pack = load_task_pack_manifest(root / "task_packs" / "java-skills-bench")

    assert task_pack.id == "java-skills-bench"
    assert [task.track for task in task_pack.tasks] == [
        "static-quality",
        "architecture",
        "security-appsec",
    ]
    assert [task.capability for task in task_pack.tasks] == [
        "resource-management",
        "messaging-streaming",
        "injection",
    ]
    assert all(task.workflow for task in task_pack.tasks)


def test_java_skills_bench_referenced_workflows_are_valid():
    root = Path("/lab")
    pack_dir = root / "task_packs" / "java-skills-bench"
    task_pack = load_task_pack_manifest(pack_dir)

    workflows = [load_workflow_manifest(pack_dir / task.workflow) for task in task_pack.tasks]

    assert [workflow.id for workflow in workflows] == [
        "static-quality",
        "architecture-review",
        "security-appsec",
    ]
    assert all(workflow.nodes for workflow in workflows)


def test_java_scorer_scores_flawed_sql_fixture_zero():
    root = Path("/lab")
    pack_dir = root / "task_packs" / "java-skills-bench"

    payload = _run_java_scorer(
        workspace=pack_dir / "tasks" / "security-appsec" / "sql-injection" / "fixture",
        expected=pack_dir / "tasks" / "security-appsec" / "sql-injection" / "expected",
    )

    assert payload["score"] == 0
    assert payload["max_score"] == 100
    assert payload["details"]["compiled"] is True
    assert payload["details"]["tests_passed"] is False


def test_java_scorer_scores_architecture_passing_solution(tmp_path):
    root = Path("/lab")
    pack_dir = root / "task_packs" / "java-skills-bench"
    fixture = pack_dir / "tasks" / "architecture" / "ddia-idempotent-consumer" / "fixture"
    workspace = tmp_path / "architecture-solution"
    shutil.copytree(fixture, workspace)
    (
        workspace
        / "src"
        / "main"
        / "java"
        / "com"
        / "agentlab"
        / "architecture"
        / "OrderEventConsumer.java"
    ).write_text(
        """package com.agentlab.architecture;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

public class OrderEventConsumer {
    private final Map<String, OrderView> orders = new HashMap<>();
    private final Set<String> seenEventIds = new HashSet<>();

    public void apply(OrderEvent event) {
        if (!seenEventIds.add(event.eventId())) {
            return;
        }
        OrderView current = orders.get(event.orderId());
        if (current != null && event.version() < current.version()) {
            return;
        }
        if ("order_created".equals(event.type())) {
            orders.put(event.orderId(), new OrderView("created", event.amount(), event.version()));
        } else if ("payment_authorized".equals(event.type())) {
            if (current != null && !"cancelled".equals(current.status())) {
                orders.put(event.orderId(), new OrderView("paid", current.amount(), event.version()));
            }
        } else if ("order_cancelled".equals(event.type())) {
            if (current != null) {
                orders.put(event.orderId(), new OrderView("cancelled", current.amount(), event.version()));
            }
        }
    }

    public Map<String, OrderView> orders() {
        return orders;
    }
}
""",
        encoding="utf-8",
    )

    payload = _run_java_scorer(
        workspace=workspace,
        expected=pack_dir / "tasks" / "architecture" / "ddia-idempotent-consumer" / "expected",
    )

    assert payload["score"] == 100
    assert payload["details"]["compiled"] is True
    assert payload["details"]["tests_passed"] is True


def _run_java_scorer(workspace: Path, expected: Path) -> dict:
    root = Path("/lab")
    scorer = root / "task_packs" / "java-skills-bench" / "scorers" / "java_assertions.py"
    result = subprocess.run(
        [
            sys.executable,
            str(scorer),
            "--workspace",
            str(workspace),
            "--expected",
            str(expected),
            "--agent-output",
            "/tmp/nonexistent-agent-output.json",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)
