from pathlib import Path

from app.eval_lab.manifests import load_skill_manifest, load_task_pack_manifest


def test_sample_skill_and_task_pack_are_valid():
    root = Path("/lab")
    skill = load_skill_manifest(root / "skills" / "example-coding-skill")
    task_pack = load_task_pack_manifest(root / "task_packs" / "coding-basic")

    assert skill.id == "example-coding-skill"
    assert task_pack.id == "coding-basic"
    assert task_pack.tasks[0].id == "fix-bug-001"
