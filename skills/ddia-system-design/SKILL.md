---
name: ddia-system-design
description: Apply Designing Data-Intensive Applications inspired architecture reasoning for backend engineering and system design. Use when reviewing or designing data-intensive systems, database choices, storage/indexing, replication, partitioning, transactions, isolation levels, distributed faults, consistency, consensus, batch processing, stream processing, derived data, correctness, reliability, scalability, maintainability, or operational trade-offs.
---

# DDIA System Design

Use this skill to turn a backend architecture question into explicit workload assumptions, data model choices, consistency requirements, failure modes, and verification steps.

## Core Workflow

1. Frame the system goal in terms of data, users, writes, reads, latency, durability, and operational ownership.
2. Name the workload before choosing tools: request rate, data size, hot keys, fan-out, read/write ratio, freshness needs, and recovery objectives.
3. Separate facts from choices: required correctness guarantees, acceptable staleness, acceptable data loss, and business-visible failure behavior.
4. Analyze the design through four lenses: reliability, scalability, maintainability, and evolvability.
5. Surface trade-offs explicitly. Do not recommend a database, queue, cache, or consensus mechanism without explaining the cost.
6. Convert abstract guarantees into tests, observability signals, and runbook checks.

## Load References Selectively

- Read `references/topic-map.md` when mapping a user problem to relevant DDIA themes.
- Read `references/system-design-principles.md` when making or reviewing architecture decisions.
- Read `references/architecture-review-checklists.md` when the user asks for a review, critique, design doc, or failure-mode analysis.

## Response Shape

Prefer this structure unless the user asks for a different format:

1. Assumptions and workload shape
2. Recommendation
3. Key trade-offs
4. Failure modes
5. Consistency and correctness implications
6. Operational checks
7. Tests or experiments to validate the design

## Guardrails

- Ask for missing workload and correctness requirements before making a strong recommendation.
- Avoid one-size-fits-all answers such as always using Kafka, microservices, NoSQL, or strong consistency.
- Treat caches, indexes, replicas, materialized views, and streams as derived data that can become stale or incorrect.
- Discuss human operations: deployment, recovery, backfills, schema evolution, monitoring, and incident response.
- Keep direct book quotations out of responses unless the user explicitly asks for a short cited quote.
