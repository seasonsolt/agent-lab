from pathlib import Path

from app.eval_lab.manifests import load_skill_manifest, load_task_pack_manifest


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
