# Order Projection Fixture

Implement `OrderProjector.apply(event)` in `order_projection.py`.

The stream is at-least-once and can deliver duplicate or out-of-order events. A correct projection should be deterministic after replay and should not let stale derived data overwrite newer facts.
