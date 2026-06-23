from __future__ import annotations

from pathlib import Path

import pytest

from app.eval_lab.workflows import load_workflow_manifest


def test_load_workflow_manifest_reads_valid_dag(tmp_path):
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(
        "id: java-static-quality\n"
        "name: Java Static Quality\n"
        "max_parallel_nodes: 2\n"
        "nodes:\n"
        "  - id: scan\n"
        "    type: tool\n"
        "    command: python -c \"print('scan')\"\n"
        "    needs: []\n"
        "    timeout_seconds: 5\n"
        "    on_failure: continue_with_artifact\n"
        "    outputs:\n"
        "      - scan.json\n"
        "  - id: agent_fix\n"
        "    type: coding_agent\n"
        "    needs: [scan]\n"
        "    timeout_seconds: 30\n"
        "    on_failure: fail_workflow\n",
        encoding="utf-8",
    )

    manifest = load_workflow_manifest(workflow_path)

    assert manifest.id == "java-static-quality"
    assert manifest.max_parallel_nodes == 2
    assert [node.id for node in manifest.nodes] == ["scan", "agent_fix"]
    assert manifest.nodes[0].outputs == ["scan.json"]


def test_load_workflow_manifest_rejects_duplicate_node_ids(tmp_path):
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(
        "id: duplicate\n"
        "name: Duplicate\n"
        "nodes:\n"
        "  - id: scan\n"
        "    type: tool\n"
        "    command: python -c \"print('a')\"\n"
        "    needs: []\n"
        "    timeout_seconds: 5\n"
        "    on_failure: fail_workflow\n"
        "  - id: scan\n"
        "    type: tool\n"
        "    command: python -c \"print('b')\"\n"
        "    needs: []\n"
        "    timeout_seconds: 5\n"
        "    on_failure: fail_workflow\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate workflow node id"):
        load_workflow_manifest(workflow_path)


def test_load_workflow_manifest_rejects_missing_dependency(tmp_path):
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(
        "id: missing-dependency\n"
        "name: Missing Dependency\n"
        "nodes:\n"
        "  - id: agent_fix\n"
        "    type: coding_agent\n"
        "    needs: [scan]\n"
        "    timeout_seconds: 30\n"
        "    on_failure: fail_workflow\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown dependency"):
        load_workflow_manifest(workflow_path)


def test_load_workflow_manifest_rejects_cycles(tmp_path):
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(
        "id: cycle\n"
        "name: Cycle\n"
        "nodes:\n"
        "  - id: a\n"
        "    type: aggregate\n"
        "    needs: [b]\n"
        "    timeout_seconds: 5\n"
        "    on_failure: fail_workflow\n"
        "  - id: b\n"
        "    type: aggregate\n"
        "    needs: [a]\n"
        "    timeout_seconds: 5\n"
        "    on_failure: fail_workflow\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="cycle"):
        load_workflow_manifest(workflow_path)
