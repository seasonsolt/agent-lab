from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

sys.path.append("/lab")

from skill_lab.repo_ingestion import clone_external_skill_repo


def ensure_git_for_tests() -> None:
    if shutil.which("git"):
        return
    shim_dir = Path(tempfile.mkdtemp(prefix="agent-lab-git-"))
    shim = shim_dir / "git"
    shim.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            from __future__ import annotations

            import hashlib
            import shutil
            import sys
            from pathlib import Path


            def strip_config(args: list[str]) -> list[str]:
                cleaned = []
                index = 0
                while index < len(args):
                    if args[index] == "-c":
                        index += 2
                        continue
                    cleaned.append(args[index])
                    index += 1
                return cleaned


            def commit_for(repo: Path) -> str:
                digest = hashlib.sha1()
                for path in sorted(repo.rglob("*")):
                    if ".git" in path.parts or not path.is_file():
                        continue
                    digest.update(path.relative_to(repo).as_posix().encode())
                    digest.update(path.read_bytes())
                return digest.hexdigest()


            def main() -> int:
                args = strip_config(sys.argv[1:])
                command = args[0]
                cwd = Path.cwd()
                if command == "init":
                    (cwd / ".git").mkdir()
                    return 0
                if command == "add":
                    return 0
                if command == "commit":
                    (cwd / ".git" / "HEAD_COMMIT").write_text(commit_for(cwd), encoding="utf-8")
                    return 0
                if command == "clone":
                    source = Path(args[-2])
                    destination = Path(args[-1])
                    shutil.copytree(source, destination)
                    return 0
                if command == "rev-parse" and args[1] == "HEAD":
                    print((cwd / ".git" / "HEAD_COMMIT").read_text(encoding="utf-8").strip())
                    return 0
                print(f"unsupported git command: {' '.join(args)}", file=sys.stderr)
                return 1


            if __name__ == "__main__":
                raise SystemExit(main())
            """
        ),
        encoding="utf-8",
    )
    shim.chmod(0o755)
    os.environ["PATH"] = f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"


ensure_git_for_tests()


def init_skill_repo(repo_dir: Path, include_manifest: bool = True) -> None:
    skill_dir = repo_dir / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Demo Skill\n", encoding="utf-8")
    if include_manifest:
        (skill_dir / "manifest.yaml").write_text(
            "id: demo-skill\nname: Demo Skill\nentry: SKILL.md\ntags:\n  - demo\n",
            encoding="utf-8",
        )
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True, text=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=agent-lab@example.test",
            "-c",
            "user.name=Agent Lab",
            "commit",
            "-m",
            "init skill",
        ],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )


def test_clone_external_skill_repo_resolves_skill_and_commit(tmp_path):
    repo_dir = tmp_path / "source"
    clone_root = tmp_path / "agent-lab-clones"
    repo_dir.mkdir()
    init_skill_repo(repo_dir)

    with clone_external_skill_repo(str(repo_dir), "skills/demo-skill", clone_root=clone_root) as external:
        assert external.repo_url == str(repo_dir)
        assert external.skill_path == "skills/demo-skill"
        assert external.skill_dir.name == "demo-skill"
        assert clone_root.resolve() in external.clone_dir.resolve().parents
        assert (external.skill_dir / "SKILL.md").exists()
        assert (external.skill_dir / "manifest.yaml").exists()
        assert len(external.commit) == 40


def test_clone_external_skill_repo_creates_temporary_manifest_when_missing(tmp_path):
    repo_dir = tmp_path / "source"
    clone_root = tmp_path / "agent-lab-clones"
    repo_dir.mkdir()
    init_skill_repo(repo_dir, include_manifest=False)

    with clone_external_skill_repo(str(repo_dir), "skills/demo-skill", clone_root=clone_root) as external:
        manifest = (external.skill_dir / "manifest.yaml").read_text(encoding="utf-8")

    assert "id: demo-skill" in manifest
    assert "name: demo-skill" in manifest
    assert "entry: SKILL.md" in manifest


def test_clone_external_skill_repo_rejects_path_outside_clone(tmp_path):
    repo_dir = tmp_path / "source"
    clone_root = tmp_path / "agent-lab-clones"
    repo_dir.mkdir()
    init_skill_repo(repo_dir)

    with pytest.raises(ValueError, match="outside cloned repository"):
        with clone_external_skill_repo(str(repo_dir), "../escape", clone_root=clone_root):
            pass
