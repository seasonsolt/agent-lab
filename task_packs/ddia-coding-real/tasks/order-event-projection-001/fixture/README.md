# Order Projection Fixture

Implement `OrderProjector.apply(event)` in `order_projection.py`.

The stream is at-least-once and can deliver duplicate or out-of-order events. A correct projection should be deterministic after replay and should not let stale derived data overwrite newer facts.

Required behavior:

- Maintain a per-order read model with `status`, `amount`, and `version`.
- Track event ids so duplicate deliveries do not change replay results.
- Ignore stale lower-version events.
- Treat cancellation as terminal while keeping version evidence for later invalid higher-version events.
- Record invalid transitions in `dead_letters`.
- Do not create a durable order from a payment event that arrives before `order_created`.

Do not add dependencies or edit documentation.
