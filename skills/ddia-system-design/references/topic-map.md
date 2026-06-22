# DDIA Topic Map For Backend Architecture

Use this map to connect a user's architecture problem to the right review lens.

## Reliability, Scalability, Maintainability

- Use for: system health, load growth, operational maturity, change safety, and complexity control.
- Ask: what can fail, how will the system keep serving users, and how will operators understand it?
- Watch for: unclear load metrics, unbounded queues, hidden coupling, manual recovery, and designs that cannot evolve.

## Data Models And Query Languages

- Use for: relational versus document modeling, graph-shaped relationships, query flexibility, and schema ownership.
- Ask: which access patterns are primary, which relationships change, and which invariants the model must protect.
- Watch for: embedding data that needs independent updates, joins pushed into application code, and models chosen for convenience rather than query shape.

## Storage And Retrieval

- Use for: indexing, write amplification, read latency, analytics layout, and OLTP versus OLAP boundaries.
- Ask: whether the workload is point lookup, range scan, full-text search, aggregation, or analytical scan.
- Watch for: indexes that slow writes, compaction costs, cache dependence, and mixing transactional and analytical workloads without isolation.

## Encoding And Evolution

- Use for: schema evolution, API compatibility, event formats, and rolling deployments.
- Ask: whether old and new producers and consumers can coexist during deployment.
- Watch for: language-specific encodings, ambiguous JSON contracts, and changes that break stored records or asynchronous messages.

## Replication

- Use for: read scaling, high availability, failover, multi-region writes, and replica lag.
- Ask: which reads need fresh data and what users observe during failover or network delay.
- Watch for: stale reads, non-monotonic reads, conflict resolution gaps, split ownership, and assuming asynchronous replicas are current.

## Partitioning

- Use for: large data sets, high throughput, hot keys, secondary indexes, and rebalancing.
- Ask: what key distributes load, what queries cross partitions, and how rebalancing affects availability.
- Watch for: skew, celebrity keys, global secondary index cost, manual routing, and operationally risky repartitioning.

## Transactions And Isolation

- Use for: invariants, concurrent updates, financial correctness, inventory, booking, and workflow state.
- Ask: which anomalies are unacceptable and whether single-object guarantees are enough.
- Watch for: lost updates, write skew, phantoms, read-modify-write races, and assuming "transaction" means serializable behavior.

## Distributed Faults

- Use for: timeouts, retries, clocks, process pauses, network partitions, and partial failure.
- Ask: what the system knows, what it only suspects, and how it behaves when messages are delayed.
- Watch for: unsafe timeout assumptions, wall-clock ordering, retry storms, and failure detectors treated as truth.

## Consistency And Consensus

- Use for: leader election, locks, uniqueness, ordering, coordination, linearizability, and linearizable operations.
- Ask: which operations require a single up-to-date view and what availability cost is acceptable.
- Watch for: global locks, unsafe leases, split-brain risk, two-phase commit blocking, and hidden consensus requirements.

## Batch Processing

- Use for: backfills, analytics, reconciliation, offline joins, and large-scale derived views.
- Ask: whether the job can be rerun, how intermediate state is stored, and how outputs replace old results.
- Watch for: non-idempotent outputs, expensive shuffles, unclear data snapshots, and unrecoverable partial writes.

## Stream Processing

- Use for: event-driven systems, CDC, real-time materialized views, alerting, and near-real-time joins.
- Ask: event time versus processing time, ordering guarantees, replay strategy, and exactly-once expectations.
- Watch for: duplicate events, poison messages, late data, partition ordering assumptions, and state restoration gaps.

## Derived Data And Correctness

- Use for: caches, search indexes, materialized views, denormalized tables, and data integration.
- Ask: source of truth, derivation path, repair mechanism, and verification strategy.
- Watch for: silent divergence, missing reconciliation, privacy leakage, and derived state treated as authoritative.
