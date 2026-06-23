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


def test_load_skill_manifest_rejects_non_skill_entry(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "README.md").write_text("# Demo\n", encoding="utf-8")
    (skill_dir / "manifest.yaml").write_text(
        "id: demo\nname: Demo Skill\nentry: README.md\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="SKILL.md"):
        load_skill_manifest(skill_dir)


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


def test_load_task_pack_manifest_rejects_traversal_paths(tmp_path):
    pack_dir = tmp_path / "pack"
    pack_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "fixture").mkdir()
    (pack_dir / "expected").mkdir()
    (pack_dir / "scorer.py").write_text("print('{}')\n", encoding="utf-8")
    (pack_dir / "taskpack.yaml").write_text(
        "id: coding-basic\n"
        "name: Coding Basic\n"
        "domain: coding\n"
        "tasks:\n"
        "  - id: fix-001\n"
        "    type: coding\n"
        "    prompt: Fix it.\n"
        "    fixture: ../outside/fixture\n"
        "    expected: expected\n"
        "    scorer: scorer.py\n"
        "    max_score: 100\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="outside task pack"):
        load_task_pack_manifest(pack_dir)


def test_load_task_pack_manifest_rejects_absolute_paths(tmp_path):
    pack_dir = tmp_path / "pack"
    pack_dir.mkdir()
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (pack_dir / "expected").mkdir()
    (pack_dir / "scorer.py").write_text("print('{}')\n", encoding="utf-8")
    (pack_dir / "taskpack.yaml").write_text(
        "id: coding-basic\n"
        "name: Coding Basic\n"
        "domain: coding\n"
        "tasks:\n"
        "  - id: fix-001\n"
        "    type: coding\n"
        "    prompt: Fix it.\n"
        f"    fixture: {fixture}\n"
        "    expected: expected\n"
        "    scorer: scorer.py\n"
        "    max_score: 100\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must be relative"):
        load_task_pack_manifest(pack_dir)


def test_load_task_pack_manifest_rejects_absolute_in_pack_paths(tmp_path):
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
        f"    fixture: {task_dir / 'fixture'}\n"
        "    expected: tasks/fix-001/expected\n"
        "    scorer: tasks/fix-001/scorer.py\n"
        "    max_score: 100\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must be relative"):
        load_task_pack_manifest(pack_dir)


def test_load_task_pack_manifest_rejects_wrong_path_types(tmp_path):
    pack_dir = tmp_path / "pack"
    task_dir = pack_dir / "tasks" / "fix-001"
    task_dir.mkdir(parents=True)
    (task_dir / "fixture").write_text("not a directory", encoding="utf-8")
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

    with pytest.raises(ValueError, match="fixture path must be a directory"):
        load_task_pack_manifest(pack_dir)


def test_load_task_pack_manifest_rejects_expected_file(tmp_path):
    pack_dir = tmp_path / "pack"
    task_dir = pack_dir / "tasks" / "fix-001"
    task_dir.mkdir(parents=True)
    (task_dir / "fixture").mkdir()
    (task_dir / "expected").write_text("not a directory", encoding="utf-8")
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

    with pytest.raises(ValueError, match="expected path must be a directory"):
        load_task_pack_manifest(pack_dir)


def test_load_task_pack_manifest_rejects_scorer_directory(tmp_path):
    pack_dir = tmp_path / "pack"
    task_dir = pack_dir / "tasks" / "fix-001"
    task_dir.mkdir(parents=True)
    (task_dir / "fixture").mkdir()
    (task_dir / "expected").mkdir()
    (task_dir / "scorer.py").mkdir()
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

    with pytest.raises(ValueError, match="scorer path must be a file"):
        load_task_pack_manifest(pack_dir)


def test_load_task_pack_manifest_accepts_java_workflow_metadata(tmp_path):
    pack_dir = tmp_path / "pack"
    task_dir = pack_dir / "tasks" / "case-1"
    workflow_dir = pack_dir / "workflows"
    task_dir.mkdir(parents=True)
    workflow_dir.mkdir()
    (task_dir / "fixture").mkdir()
    (task_dir / "expected").mkdir()
    (task_dir / "scorer.py").write_text("print('{}')\n", encoding="utf-8")
    (workflow_dir / "static-quality.yaml").write_text(
        "id: static-quality\n"
        "name: Static Quality\n"
        "nodes:\n"
        "  - id: scan\n"
        "    type: tool\n"
        "    needs: []\n"
        "    timeout_seconds: 5\n"
        "    on_failure: fail_workflow\n"
        "    command: python -c \"print('scan')\"\n",
        encoding="utf-8",
    )
    (pack_dir / "taskpack.yaml").write_text(
        "id: java-skills-bench\n"
        "name: Java Skills Bench\n"
        "domain: java\n"
        "tasks:\n"
        "  - id: null-resource-exception\n"
        "    type: coding\n"
        "    track: static-quality\n"
        "    capability: resource-management\n"
        "    workflow: workflows/static-quality.yaml\n"
        "    knowledge_sources:\n"
        "      - Sonar-style static quality\n"
        "    prompt: Fix resource handling.\n"
        "    fixture: tasks/case-1/fixture\n"
        "    expected: tasks/case-1/expected\n"
        "    scorer: tasks/case-1/scorer.py\n"
        "    max_score: 100\n",
        encoding="utf-8",
    )

    manifest = load_task_pack_manifest(pack_dir)

    task = manifest.tasks[0]
    assert task.track == "static-quality"
    assert task.capability == "resource-management"
    assert task.workflow == "workflows/static-quality.yaml"
    assert task.knowledge_sources == ["Sonar-style static quality"]


def test_load_task_pack_manifest_rejects_workflow_path_escape(tmp_path):
    pack_dir = tmp_path / "pack"
    outside = tmp_path / "outside"
    task_dir = pack_dir / "tasks" / "case-1"
    outside.mkdir()
    task_dir.mkdir(parents=True)
    (task_dir / "fixture").mkdir()
    (task_dir / "expected").mkdir()
    (task_dir / "scorer.py").write_text("print('{}')\n", encoding="utf-8")
    (outside / "workflow.yaml").write_text("id: outside\nname: Outside\nnodes: []\n", encoding="utf-8")
    (pack_dir / "taskpack.yaml").write_text(
        "id: java-skills-bench\n"
        "name: Java Skills Bench\n"
        "domain: java\n"
        "tasks:\n"
        "  - id: case-1\n"
        "    type: coding\n"
        "    workflow: ../outside/workflow.yaml\n"
        "    prompt: Fix it.\n"
        "    fixture: tasks/case-1/fixture\n"
        "    expected: tasks/case-1/expected\n"
        "    scorer: tasks/case-1/scorer.py\n"
        "    max_score: 100\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="workflow path is outside task pack"):
        load_task_pack_manifest(pack_dir)


def test_hash_directory_changes_when_file_changes(tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    file_path = folder / "a.txt"
    file_path.write_text("one", encoding="utf-8")
    first = hash_directory(folder)

    file_path.write_text("two", encoding="utf-8")
    second = hash_directory(folder)

    assert first != second


def test_hash_directory_ignores_cache_files(tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "a.txt").write_text("one", encoding="utf-8")
    first = hash_directory(folder)

    (folder / ".DS_Store").write_text("ignored", encoding="utf-8")
    (folder / "__pycache__").mkdir()
    (folder / "__pycache__" / "a.pyc").write_text("ignored", encoding="utf-8")
    (folder / ".pytest_cache").mkdir()
    (folder / ".pytest_cache" / "README.md").write_text("ignored", encoding="utf-8")

    assert hash_directory(folder) == first


def test_hash_directory_requires_existing_directory(tmp_path):
    with pytest.raises(ValueError, match="existing directory"):
        hash_directory(tmp_path / "missing")
