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


def test_write_comparison_artifacts_formats_missing_treatment_repo_metadata(tmp_path):
    metadata = EvidenceMetadata(
        evaluator="seasonsolt/agent-lab",
        treatment_repo_url=None,
        treatment_repo_commit=None,
        treatment_skill_path="./skills/ddia-system-design",
        baseline_skill_path="./skills/example-coding-skill",
        task_pack_path="./task_packs/ddia-coding-real",
        reproduction_command="python3 -m skill_lab.cli compare --treatment ./skills/ddia-system-design",
    )

    _, markdown_path = write_comparison_artifacts(sample_summary(), metadata, tmp_path)

    markdown = markdown_path.read_text(encoding="utf-8")

    assert "not applicable" in markdown
    assert "`None`" not in markdown
    assert "./skills/ddia-system-design" in markdown
