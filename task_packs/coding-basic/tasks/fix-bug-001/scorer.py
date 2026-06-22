from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--agent-output", required=True)
    args = parser.parse_args()

    workspace_readme = Path(args.workspace) / "README.md"
    expected_readme = Path(args.expected) / "README.md"
    actual = workspace_readme.read_text(encoding="utf-8") if workspace_readme.exists() else ""
    expected = expected_readme.read_text(encoding="utf-8")
    matched = actual.strip() == expected.strip()
    print(
        json.dumps(
            {
                "score": 100 if matched else 0,
                "max_score": 100,
                "details": {
                    "readme_matched": matched,
                    "expected_phrase_present": "skill evaluation complete" in actual,
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
