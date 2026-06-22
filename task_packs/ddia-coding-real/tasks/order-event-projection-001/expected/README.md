# Expected Behavior

The implementation should handle at-least-once event delivery:

- duplicate event IDs do not change state twice
- stale lower-version events do not overwrite newer state
- invalid transitions are recorded in `dead_letters`
- replaying the same stream produces deterministic final state
