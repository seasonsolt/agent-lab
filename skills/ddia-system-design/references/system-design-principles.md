# System Design Principles

These principles are original engineering guidance extracted from DDIA reading notes.

## Start With Workload Shape

- Define load with concrete dimensions: request rate, write rate, read fan-out, data volume, key distribution, peak-to-average ratio, and growth rate.
- Choose representative operations before choosing storage. A system optimized for point lookups can be poor for range scans or aggregations.
- Include operational load: deployments, backfills, failover, rebalancing, compaction, and schema migrations.

## Treat Guarantees As Product Behavior

- Translate consistency terms into user-visible outcomes, such as whether a user sees their own write after refresh.
- Decide which anomalies are acceptable before selecting isolation levels or replication modes.
- Stronger guarantees often move cost into coordination, latency, reduced availability, or operational complexity.

## Model Derived Data Explicitly

- Caches, replicas, indexes, search documents, materialized views, and stream outputs are derived data.
- Every derived data path needs a source of truth, update mechanism, lag signal, and repair procedure.
- If derived state can affect correctness, add reconciliation instead of relying only on happy-path propagation.

## Design For Partial Failure

- In distributed systems, some components can continue while others are slow, paused, partitioned, or unreachable.
- Timeouts detect uncertainty, not truth. Retried operations need idempotency or deduplication.
- Clocks are useful for measurement and ordering hints, but correctness should not depend on perfectly synchronized wall time unless the system proves that bound.

## Make Evolution A First-Class Requirement

- Store and transmit data in formats that allow old and new code to coexist.
- Plan for rolling deploys, replaying old events, reading old records, and adding optional fields.
- Prefer explicit contracts over language-specific serialization formats that couple producers and consumers.

## Prefer Simple Ownership Boundaries

- Put invariants near the data and transaction boundary that protects them.
- Avoid splitting a strongly consistent invariant across services unless the design includes coordination or compensation.
- Keep operational ownership clear: someone must know how to backfill, repair, monitor, and recover each data path.

## Review Storage Choices By Access Pattern

- Relational models fit many-to-one and many-to-many relationships when joins and constraints matter.
- Document models fit locality and whole-document access when independent updates are limited.
- Graph models fit highly connected data with traversal-heavy queries.
- LSM-style storage often favors write throughput and compression at the cost of compaction behavior.
- B-tree-style storage often favors predictable point and range reads with different write and space costs.

## Review Replication Choices By Failure Behavior

- Synchronous replication can reduce data loss but increases write latency and availability risk.
- Asynchronous replication improves availability and latency but introduces lag and stale reads.
- Multi-leader replication can support multi-region writes but requires explicit conflict handling.
- Leaderless quorum systems need careful reasoning about read/write quorums, stale replicas, sloppy quorum behavior, and concurrent writes.

## Review Partitioning Choices By Skew And Query Routing

- Hash partitioning spreads keys but weakens range locality.
- Range partitioning preserves ordering but can create hot partitions.
- Secondary indexes either scatter writes or scatter reads; both costs should be visible.
- Rebalancing should be observable, rate-limited, reversible, and planned around operational risk.

## Review Transactions By Anomaly

- Read committed, snapshot isolation, and serializable isolation prevent different anomaly sets.
- Lost updates, write skew, and phantoms should be tested with concurrent operations, not assumed away.
- Single-object atomicity does not protect multi-object invariants.
- Application-level checks outside the database transaction can be invalidated by concurrent writes.

## Review Streams By Replay And Time

- Event logs are useful when consumers need replay, ordering per partition, and independent consumption.
- Stream processors should define event time, processing time, late data behavior, state storage, and recovery.
- Exactly-once claims usually depend on idempotent sinks, transactions, or deduplication; ask where duplicates are eliminated.
- CDC and event sourcing can keep systems in sync, but they also create schema evolution and backfill obligations.
