from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import traceback
from pathlib import Path


def _java_files(root: Path) -> list[str]:
    return sorted(str(path) for path in root.rglob("*.java"))


def _expected_java_files(root: Path) -> list[str]:
    return sorted(str(path) for path in root.glob("*.java"))


def _emit(score: int, details: dict[str, object]) -> None:
    print(json.dumps({"score": score, "max_score": 100, "details": details}))


def _prepare_build_dir(workspace: Path) -> tuple[Path, bool]:
    build_dir = workspace / ".agent-lab-java-build"
    try:
        if build_dir.exists():
            shutil.rmtree(build_dir)
        build_dir.mkdir(parents=True)
        return build_dir, False
    except OSError:
        fallback_name = workspace.as_posix().strip("/").replace("/", "_").replace(":", "_")
        build_dir = Path("/tmp") / ".agent-lab-java-build" / fallback_name
        if build_dir.exists():
            shutil.rmtree(build_dir)
        build_dir.mkdir(parents=True)
        return build_dir, True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--agent-output", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace)
    expected = Path(args.expected)

    try:
        build_dir, used_fallback_build_dir = _prepare_build_dir(workspace)

        sources = _java_files(workspace / "src" / "main" / "java") + _expected_java_files(expected)
        if not sources:
            _emit(
                0,
                {
                    "compiled": False,
                    "error": "No Java sources found for scoring",
                    "workspace": str(workspace),
                    "expected": str(expected),
                    "build_dir": str(build_dir),
                    "used_fallback_build_dir": used_fallback_build_dir,
                    "agent_output": args.agent_output,
                },
            )
            return 0

        compile_result = subprocess.run(
            ["javac", "-encoding", "UTF-8", "-d", str(build_dir), *sources],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if compile_result.returncode != 0:
            _emit(
                0,
                {
                    "compiled": False,
                    "compile_returncode": compile_result.returncode,
                    "compile_stdout": compile_result.stdout,
                    "compile_stderr": compile_result.stderr,
                    "build_dir": str(build_dir),
                    "used_fallback_build_dir": used_fallback_build_dir,
                    "agent_output": args.agent_output,
                },
            )
            return 0

        run_result = subprocess.run(
            ["java", "-cp", str(build_dir), "TestRunner"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        passed = run_result.returncode == 0
        _emit(
            100 if passed else 0,
            {
                "compiled": True,
                "tests_passed": passed,
                "test_returncode": run_result.returncode,
                "stdout": run_result.stdout,
                "stderr": run_result.stderr,
                "build_dir": str(build_dir),
                "used_fallback_build_dir": used_fallback_build_dir,
                "agent_output": args.agent_output,
            },
        )
        return 0
    except Exception as exc:
        _emit(
            0,
            {
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "agent_output": args.agent_output,
            },
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
