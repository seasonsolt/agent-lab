from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import traceback
from pathlib import Path


def load_projector(workspace: Path):
    module_path = workspace / "order_projection.py"
    spec = importlib.util.spec_from_file_location("order_projection_eval", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load order_projection.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.OrderProjector


def run_checks(projector_class) -> dict[str, bool]:
    stream = [
        {"event_id": "e1", "order_id": "o1", "version": 1, "type": "order_created", "amount": 42},
        {"event_id": "e2", "order_id": "o1", "version": 2, "type": "payment_authorized"},
        {"event_id": "e2", "order_id": "o1", "version": 2, "type": "payment_authorized"},
        {"event_id": "e4", "order_id": "o1", "version": 4, "type": "order_cancelled"},
        {"event_id": "e3", "order_id": "o1", "version": 3, "type": "order_shipped"},
        {"event_id": "e5", "order_id": "o1", "version": 5, "type": "order_shipped"},
        {"event_id": "e6", "order_id": "o2", "version": 2, "type": "payment_authorized"},
        {"event_id": "e7", "order_id": "o2", "version": 1, "type": "order_created", "amount": 13},
    ]

    projector = projector_class()
    for event in stream:
        try:
            projector.apply(event)
        except Exception:
            pass

    replay = projector_class()
    for event in stream + stream:
        try:
            replay.apply(event)
        except Exception:
            pass

    order = projector.orders.get("o1", {})
    replay_order = replay.orders.get("o1", {})
    dead_letters = getattr(projector, "dead_letters", [])

    return {
        "tracks_final_version": order.get("version") == 5,
        "keeps_terminal_state": order.get("status") == "cancelled",
        "preserves_amount": order.get("amount") == 42,
        "records_invalid_transitions": len(dead_letters) >= 2,
        "deduplicates_event_ids": replay_order == order,
        "does_not_create_from_late_payment": "o2" not in projector.orders or projector.orders["o2"].get("version") == 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--agent-output", required=True)
    args = parser.parse_args()

    try:
        projector_class = load_projector(Path(args.workspace))
        checks = run_checks(projector_class)
        passed = sum(1 for value in checks.values() if value)
        score = round(passed / len(checks) * 100, 2)
        payload = {"score": score, "max_score": 100, "details": checks}
    except Exception as exc:
        payload = {
            "score": 0,
            "max_score": 100,
            "details": {"error": str(exc), "traceback": traceback.format_exc()},
        }

    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
