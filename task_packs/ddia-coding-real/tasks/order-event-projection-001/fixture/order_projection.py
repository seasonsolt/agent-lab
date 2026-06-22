from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OrderProjector:
    orders: dict[str, dict[str, Any]] = field(default_factory=dict)
    dead_letters: list[dict[str, Any]] = field(default_factory=list)

    def apply(self, event: dict[str, Any]) -> None:
        order_id = event["order_id"]
        event_type = event["type"]
        amount = event.get("amount")

        if event_type == "order_created":
            self.orders[order_id] = {"status": "created", "amount": amount}
        elif event_type == "payment_authorized":
            self.orders[order_id]["status"] = "paid"
        elif event_type == "order_shipped":
            self.orders[order_id]["status"] = "shipped"
        elif event_type == "order_cancelled":
            self.orders[order_id]["status"] = "cancelled"
