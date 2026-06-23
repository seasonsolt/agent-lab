# DDIA Idempotent Consumer

Fix `OrderEventConsumer.apply(OrderEvent)` for at-least-once event delivery.

Requirements:

- Ignore duplicate `eventId` values.
- Ignore stale lower-version events.
- Do not create an order from payment before creation.
- Preserve terminal cancellation without later invalid events changing status, amount, or version.
- Keep the implementation in memory.
