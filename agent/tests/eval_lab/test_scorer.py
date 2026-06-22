from __future__ import annotations

import json

from app.eval_lab.scorer import run_scorer


def test_run_scorer_reads_json_output(tmp_path):
    scorer = tmp_path / "scorer.py"
    workspace = tmp_path / "workspace"
    expected = tmp_path / "expected"
    output = tmp_path / "agent_output.json"
    workspace.mkdir()
    expected.mkdir()
    output.write_text(json.dumps({"agent_output": "done"}), encoding="utf-8")
    scorer.write_text(
        "import json\n"
        "print(json.dumps({\n"
        "  'score': 90,\n"
        "  'max_score': 100,\n"
        "  'details': {'tests_passed': True}\n"
        "}))\n",
        encoding="utf-8",
    )

    result = run_scorer(scorer, workspace, expected, output, timeout_seconds=10)

    assert result.score == 90
    assert result.max_score == 100
    assert result.details == {"tests_passed": True}


def test_run_scorer_passes_expected_arguments(tmp_path):
    scorer = tmp_path / "scorer.py"
    workspace = tmp_path / "workspace"
    expected = tmp_path / "expected"
    output = tmp_path / "agent_output.json"
    workspace.mkdir()
    expected.mkdir()
    output.write_text("{}", encoding="utf-8")
    scorer.write_text(
        "import argparse\n"
        "import json\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--workspace')\n"
        "parser.add_argument('--expected')\n"
        "parser.add_argument('--agent-output')\n"
        "args = parser.parse_args()\n"
        "print(json.dumps({'score': 100, 'max_score': 100, 'details': vars(args)}))\n",
        encoding="utf-8",
    )

    result = run_scorer(scorer, workspace, expected, output, timeout_seconds=10)

    assert result.details == {
        "workspace": str(workspace),
        "expected": str(expected),
        "agent_output": str(output),
    }


def test_run_scorer_returns_error_for_nonzero_exit(tmp_path):
    scorer = tmp_path / "scorer.py"
    workspace = tmp_path / "workspace"
    expected = tmp_path / "expected"
    output = tmp_path / "agent_output.json"
    workspace.mkdir()
    expected.mkdir()
    output.write_text("{}", encoding="utf-8")
    scorer.write_text(
        "import sys\n"
        "print('bad scorer', file=sys.stderr)\n"
        "raise SystemExit(7)\n",
        encoding="utf-8",
    )

    result = run_scorer(scorer, workspace, expected, output, timeout_seconds=10)

    assert result.score == 0
    assert result.max_score == 100
    assert result.details["returncode"] == 7
    assert "bad scorer" in result.details["scorer_error"]


def test_run_scorer_returns_error_for_invalid_json(tmp_path):
    scorer = tmp_path / "scorer.py"
    workspace = tmp_path / "workspace"
    expected = tmp_path / "expected"
    output = tmp_path / "agent_output.json"
    workspace.mkdir()
    expected.mkdir()
    output.write_text("{}", encoding="utf-8")
    scorer.write_text("print('not json')\n", encoding="utf-8")

    result = run_scorer(scorer, workspace, expected, output, timeout_seconds=10)

    assert result.score == 0
    assert result.max_score == 100
    assert "scorer_error" in result.details
    assert result.details["stdout"] == "not json\n"


def test_run_scorer_returns_error_for_score_above_max(tmp_path):
    scorer = tmp_path / "scorer.py"
    workspace = tmp_path / "workspace"
    expected = tmp_path / "expected"
    output = tmp_path / "agent_output.json"
    workspace.mkdir()
    expected.mkdir()
    output.write_text("{}", encoding="utf-8")
    scorer.write_text(
        "import json\n"
        "print(json.dumps({'score': 150, 'max_score': 100, 'details': {}}))\n",
        encoding="utf-8",
    )

    result = run_scorer(scorer, workspace, expected, output, timeout_seconds=10)

    assert result.score == 0
    assert result.max_score == 100
    assert "max_score" in result.details["scorer_error"]


def test_run_scorer_returns_error_for_timeout(tmp_path):
    scorer = tmp_path / "scorer.py"
    workspace = tmp_path / "workspace"
    expected = tmp_path / "expected"
    output = tmp_path / "agent_output.json"
    workspace.mkdir()
    expected.mkdir()
    output.write_text("{}", encoding="utf-8")
    scorer.write_text("import time\ntime.sleep(5)\n", encoding="utf-8")

    result = run_scorer(scorer, workspace, expected, output, timeout_seconds=1)

    assert result.score == 0
    assert result.max_score == 100
    assert result.details["timeout"] is True
    assert "timed out" in result.details["scorer_error"]
