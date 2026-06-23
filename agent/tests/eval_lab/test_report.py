from __future__ import annotations

import pytest

from app.eval_lab.report import build_report_from_records


def test_build_report_marks_useful_when_scores_are_high():
    report = build_report_from_records(
        eval_run={
            "id": "run-1",
            "status": "passed",
            "skill_id": "skill-1",
            "task_pack_id": "pack-1",
            "langfuse_trace_ids": ["trace-1"],
            "error": None,
        },
        skill={
            "id": "skill-1",
            "name": "Skill",
            "version_hash": "skill-hash",
            "manifest": {"tags": ["coding"]},
        },
        task_pack={
            "id": "pack-1",
            "name": "Pack",
            "domain": "coding",
            "version_hash": "pack-hash",
        },
        scores=[
            {"task_id": "task-1", "score_type": "auto", "score": 90, "max_score": 100, "details": {}},
            {"task_id": "task-1", "score_type": "rubric", "score": 80, "max_score": 100, "details": {}},
        ],
    )

    assert report.final_score == 87
    assert report.auto_score == 90
    assert report.value_score == 80
    assert report.pass_rate == 1
    assert report.verdict == "useful"


def test_build_report_averages_auto_and_value_scores():
    report = build_report_from_records(
        eval_run={
            "id": "run-1",
            "status": "passed",
            "skill_id": "skill-1",
            "task_pack_id": "pack-1",
            "langfuse_trace_ids": [],
            "error": None,
        },
        skill={"id": "skill-1", "name": "Skill", "version_hash": "skill-hash", "manifest": {}},
        task_pack={"id": "pack-1", "name": "Pack", "domain": "coding", "version_hash": "pack-hash"},
        scores=[
            {"task_id": "task-1", "score_type": "auto", "score": 9, "max_score": 10, "details": {}},
            {"task_id": "task-2", "score_type": "auto", "score": 40, "max_score": 50, "details": {}},
            {"task_id": "task-1", "score_type": "rubric", "score": 7, "max_score": 10, "details": {}},
            {"task_id": "task-1", "score_type": "llm_judge", "score": 18, "max_score": 20, "details": {}},
            {"task_id": "task-1", "score_type": "human", "score": 4, "max_score": 5, "details": {}},
        ],
    )

    assert report.auto_score == 85
    assert report.value_score == 80
    assert report.final_score == 83.5
    assert report.pass_rate == 1
    assert report.verdict == "useful"


def test_build_report_weights_value_score_types_evenly():
    report = build_report_from_records(
        eval_run={
            "id": "run-1",
            "status": "passed",
            "skill_id": "skill-1",
            "task_pack_id": "pack-1",
            "langfuse_trace_ids": [],
            "error": None,
        },
        skill={"id": "skill-1", "name": "Skill", "version_hash": "skill-hash", "manifest": {}},
        task_pack={"id": "pack-1", "name": "Pack", "domain": "coding", "version_hash": "pack-hash"},
        scores=[
            {"task_id": "task-1", "score_type": "auto", "score": 80, "max_score": 100, "details": {}},
            {"task_id": "task-1", "score_type": "rubric", "score": 100, "max_score": 100, "details": {}},
            {"task_id": "task-2", "score_type": "rubric", "score": 100, "max_score": 100, "details": {}},
            {"task_id": "task-1", "score_type": "human", "score": 50, "max_score": 100, "details": {}},
        ],
    )

    assert report.value_score == 75
    assert report.final_score == 78.5


def test_build_report_counts_zero_value_score_type():
    report = build_report_from_records(
        eval_run={
            "id": "run-1",
            "status": "passed",
            "skill_id": "skill-1",
            "task_pack_id": "pack-1",
            "langfuse_trace_ids": [],
            "error": None,
        },
        skill={"id": "skill-1", "name": "Skill", "version_hash": "skill-hash", "manifest": {}},
        task_pack={"id": "pack-1", "name": "Pack", "domain": "coding", "version_hash": "pack-hash"},
        scores=[
            {"task_id": "task-1", "score_type": "auto", "score": 100, "max_score": 100, "details": {}},
            {"task_id": "task-1", "score_type": "rubric", "score": 0, "max_score": 100, "details": {}},
            {"task_id": "task-1", "score_type": "human", "score": 100, "max_score": 100, "details": {}},
        ],
    )

    assert report.value_score == 50
    assert report.final_score == 85


def test_build_report_pass_rate_ignores_value_only_tasks():
    report = build_report_from_records(
        eval_run={
            "id": "run-1",
            "status": "passed",
            "skill_id": "skill-1",
            "task_pack_id": "pack-1",
            "langfuse_trace_ids": [],
            "error": None,
        },
        skill={"id": "skill-1", "name": "Skill", "version_hash": "skill-hash", "manifest": {}},
        task_pack={"id": "pack-1", "name": "Pack", "domain": "coding", "version_hash": "pack-hash"},
        scores=[
            {"task_id": "task-1", "score_type": "auto", "score": 80, "max_score": 100, "details": {}},
            {"task_id": "task-2", "score_type": "rubric", "score": 0, "max_score": 100, "details": {}},
        ],
    )

    assert report.pass_rate == 1


def test_build_report_rejects_invalid_score_bounds():
    with pytest.raises(ValueError, match="max_score"):
        build_report_from_records(
            eval_run={
                "id": "run-1",
                "status": "passed",
                "skill_id": "skill-1",
                "task_pack_id": "pack-1",
                "langfuse_trace_ids": [],
                "error": None,
            },
            skill={"id": "skill-1", "name": "Skill", "version_hash": "skill-hash", "manifest": {}},
            task_pack={"id": "pack-1", "name": "Pack", "domain": "coding", "version_hash": "pack-hash"},
            scores=[
                {"task_id": "task-1", "score_type": "auto", "score": 1, "max_score": 0, "details": {}},
            ],
        )


def test_build_report_marks_error_with_no_scores_harmful():
    report = build_report_from_records(
        eval_run={
            "id": "run-1",
            "status": "error",
            "skill_id": "skill-1",
            "task_pack_id": "pack-1",
            "langfuse_trace_ids": ["trace-1"],
            "error": "sandbox failed",
        },
        skill={"id": "skill-1", "name": "Skill", "version_hash": "skill-hash", "manifest": {}},
        task_pack={"id": "pack-1", "name": "Pack", "domain": "coding", "version_hash": "pack-hash"},
        scores=[],
    )

    assert report.final_score == 0
    assert report.auto_score == 0
    assert report.value_score == 0
    assert report.pass_rate == 0
    assert report.verdict == "harmful"
    assert report.error == "sandbox failed"


def test_build_report_includes_workflow_nodes_from_score_details():
    report = build_report_from_records(
        eval_run={
            "id": "run-1",
            "status": "passed",
            "skill_id": "skill-1",
            "task_pack_id": "pack-1",
            "langfuse_trace_ids": ["trace-1"],
            "error": None,
        },
        skill={"id": "skill-1", "name": "Skill", "version_hash": "skill-hash", "manifest": {}},
        task_pack={"id": "pack-1", "name": "Pack", "domain": "java", "version_hash": "pack-hash"},
        scores=[
            {
                "task_id": "task-1",
                "score_type": "auto",
                "score": 100,
                "max_score": 100,
                "details": {
                    "workflow_nodes": [
                        {
                            "node_id": "scan",
                            "node_type": "tool",
                            "status": "passed",
                            "duration_ms": 12,
                            "artifact_paths": [".agent-lab/artifacts/scan.txt"],
                            "trace_ids": [],
                            "error": None,
                        }
                    ]
                },
            }
        ],
    )

    assert len(report.workflow_nodes) == 1
    assert report.workflow_nodes[0].node_id == "scan"
    assert report.workflow_nodes[0].artifact_paths == [".agent-lab/artifacts/scan.txt"]
