# Architecture Review Checklists

Use these checklists when reviewing a backend design, system design answer, architecture document, or production migration.

## Workload Checklist

- What are the primary reads and writes?
- What are p50, p95, and p99 latency goals?
- What is the expected data volume now and after one year?
- Which keys, tenants, users, or regions may become hot?
- Which operations must keep working during degraded dependency behavior?
- Which backfills, migrations, or analytical jobs will compete with serving traffic?

## Data Model Checklist

- Which entities need independent updates?
- Which relationships are many-to-one or many-to-many?
- Which invariants must be enforced by storage rather than application convention?
- Which queries require joins, graph traversal, search, or aggregation?
- How will schema changes roll out across old and new application versions?

## Replication And Consistency Checklist

- Which reads can be stale and which must be current?
- Does the user need read-your-writes, monotonic reads, or consistent prefix reads?
- What happens during leader failover?
- How are write conflicts detected and resolved?
- What observability shows replica lag and replication failure?

## Partitioning Checklist

- What partition key distributes load for the hardest write path?
- Which queries cross partitions?
- How are secondary indexes partitioned?
- What is the hot-key mitigation plan?
- How does rebalancing happen without causing an incident?

## Transaction And Correctness Checklist

- Which invariants span multiple rows, documents, services, or partitions?
- Which isolation level is required to protect those invariants?
- Can concurrent requests cause lost update, write skew, or phantom anomalies?
- Are retries idempotent?
- Are uniqueness, balance, inventory, quota, and booking constraints tested under concurrency?

## Distributed Failure Checklist

- Which calls have timeouts, and what happens after timeout?
- Can retries amplify overload?
- What happens when a process pauses after taking a lock or lease?
- Does any correctness decision depend on wall-clock time?
- What is the behavior under network partition, packet delay, duplicate messages, and reordered messages?

## Batch And Stream Checklist

- Can the job or consumer be safely replayed?
- Are outputs idempotent or transactionally committed?
- How are late, duplicate, missing, or out-of-order events handled?
- Where is stream processor state stored and restored?
- How are backfills coordinated with live updates?

## Derived Data Checklist

- What is the source of truth?
- How is derived state updated?
- How is lag measured?
- How is divergence detected?
- How is corrupted derived state rebuilt?
- What user or business action is unsafe while derived state is stale?

## Recommendation Checklist

- State the recommendation in one paragraph.
- List the top three trade-offs.
- Name the most likely failure mode.
- Name the operational signal that would reveal that failure mode.
- Give one test or experiment that can falsify the recommendation.
