# Java Agent Workflow Bench Design

## Goal

Evolve Agent Lab from a skill-only evaluator into a Java agent workflow
benchmark. The benchmark should measure whether tools, skills, RAG, wiki
knowledge, or hybrid expert workflows improve real Java coding outcomes.

The central question changes from:

```text
Does this skill help?
```

to:

```text
Does this knowledge workflow improve a Java coding agent on this engineering
risk domain?
```

## Product Positioning

Agent Lab should be a benchmark harness, not a business knowledge repository.
It should load and compare different knowledge delivery mechanisms:

- no-knowledge baseline
- skill package
- RAG retrieval
- wiki or handbook context
- tool-backed analyzer
- hybrid workflow combining tools and expert lenses

This lets the lab answer stronger questions:

- Is a skill better than no extra knowledge?
- Is RAG more token-efficient than a skill?
- Does a Sonar-style analyzer plus agent triage outperform a static-quality
  skill alone?
- Does a multi-lens architecture workflow outperform a single DDIA-style skill?
- Does a security scanner plus AppSec skill produce safer patches than either
  one alone?

## Java Benchmark Tracks

The Java bench should classify tasks by engineering risk domain, not by the
tool or evaluation method used.

### Static Quality And Maintainability

This track is inspired by Sonar-style quality analysis, but is broader than a
Sonar clone. It evaluates whether a workflow helps the agent produce cleaner,
safer, more maintainable Java code.

Capability areas:

- correctness bugs
- maintainability
- resource management
- concurrency footguns
- Spring misuse
- transaction annotation misuse
- exception and logging quality
- test quality

Primary scoring signals:

- Java compilation
- unit tests
- static rule assertions
- no superficial suppressions
- no behavior regressions

### Architecture And Production Engineering

This track covers data-intensive and production-system correctness. DDIA is the
first strong knowledge source, but it is one lens rather than the whole track.

Capability areas:

- data consistency and DDIA-style correctness
- high concurrency
- high performance
- high availability
- messaging and streaming
- caching
- database transactions
- observability and resilience
- capacity and failure-mode design

Primary scoring signals:

- executable behavior tests
- concurrency simulations
- performance or latency checks where practical
- optional architecture rubric judge
- evidence that the patch respects source-of-truth and failure boundaries

### Security And AppSec

This track should be named Security/AppSec rather than Pentest. Pentest is one
validation method inside the broader security domain.

Capability areas:

- injection
- authentication and authorization
- SSRF, path traversal, and file handling
- deserialization
- secrets and sensitive data exposure
- dependency vulnerabilities
- Spring Security configuration
- controlled pentest scenarios

Primary scoring signals:

- exploit regression tests
- security assertions
- dependency or SAST findings
- no broken legitimate behavior
- optional security rubric judge

Security tasks must run in controlled local fixtures only. The benchmark should
not instruct agents to attack third-party systems or uncontrolled targets.

## Knowledge Delivery Modes

Each evaluation arm should declare how knowledge is delivered to the agent.

```yaml
knowledge_mode:
  type: skill | rag | wiki | tool | hybrid
  source: ./skills/ddia-system-design
  version: 7f1f6c2
```

### Skill

Best for compact expert workflows, checklists, decision procedures, and
specialized reasoning. Risks include prompt bloat and plausible but shallow
advice.

### RAG

Best for larger knowledge bases, policy documents, production handbooks, and
historical incidents. Risks include retrieval noise and attribution ambiguity:
the benchmark must distinguish retrieval quality from knowledge quality.

### Wiki Or Handbook

Best for human-maintained engineering standards and business rules. Risks
include context stuffing if the workflow simply injects large documents.

### Tool

Best for deterministic signals such as static analysis, dependency scanning,
coverage, exploit regression, or performance measurements. Tool outputs are
evidence, not final answers.

### Hybrid

Best for realistic enterprise workflows. A hybrid arm can combine scanners,
retrieval, skills, expert lenses, and a final coding agent. It has the highest
realism and the hardest attribution, so reports must show each node's artifact.

## Evaluation Workflow Model

Agent Lab should introduce an Evaluation Workflow abstraction. A workflow is a
small DAG that controls which steps run, which artifacts they produce, and which
steps can run in parallel.

```text
Java task
  -> workflow DAG
  -> agent action
  -> deterministic scorer
  -> optional judge
  -> evidence report
```

The MVP should implement a small internal DAG runner rather than adopting a
large external workflow system. The runner only needs:

- node dependency control through `needs`
- ready-node parallel execution
- per-node timeout
- per-node artifact output
- simple failure policy
- workflow-level and group-level parallelism limits

### Node Contract

Example node:

```yaml
nodes:
  - id: run_sonar
    type: tool
    command: ./gradlew sonar
    needs: []
    timeout_seconds: 120
    max_parallelism_key: static_scan
    on_failure: continue_with_artifact
```

Required fields:

- `id`: stable node identifier within the workflow
- `type`: node executor type
- `needs`: upstream node IDs that must finish before this node starts
- `timeout_seconds`: node timeout
- `on_failure`: failure policy

Optional fields:

- `command`: shell command for tool nodes
- `knowledge_sources`: skills, RAG indexes, wiki paths, or tool outputs
- `max_parallelism_key`: shared concurrency bucket
- `inputs`: named upstream artifacts to read
- `outputs`: declared artifact names

### Node Types

Initial node types:

- `tool`: run scanner, build, tests, or helper command
- `expert_lens`: run an analysis prompt using a skill, wiki, or RAG context
- `aggregate`: merge upstream findings into a compact artifact
- `coding_agent`: ask the coding agent to modify the workspace
- `scorer`: run deterministic task scoring
- `judge`: run optional rubric-based judging

### Parallelism Rules

- Nodes with no unmet `needs` are ready.
- Ready nodes can run concurrently.
- `max_parallelism_key` limits concurrency for expensive node classes, such as
  LLM expert lenses or static scanners.
- A workflow-level limit prevents too many Docker or LLM jobs from running at
  once.
- Downstream nodes can read only declared upstream artifacts.

### Failure Policies

Supported MVP policies:

- `fail_workflow`: stop the workflow and mark the run as error.
- `continue_with_artifact`: preserve the error artifact and let downstream
  nodes decide how to handle degraded evidence.
- `skip_dependents`: mark dependent nodes skipped and continue independent
  branches.

## Track Workflows

### Static Quality Workflow

```text
checkout code
  -> run Sonar/Semgrep/Checkstyle/Error Prone/SpotBugs
  -> normalize findings
  -> agent receives code + findings + optional knowledge context
  -> agent fixes issues
  -> run compile/tests/static checks again
  -> score fixed true positives, false-positive handling, and regressions
```

Scanner nodes can run in parallel. The agent should not be rewarded for hiding
findings through broad suppressions, disabling rules, or deleting tests.

### Architecture Workflow

```text
checkout code + scenario
  -> run expert lenses in parallel
       DDIA lens
       high-concurrency lens
       performance lens
       high-availability lens
       observability lens
  -> aggregate findings
  -> agent decides minimal patch or design change
  -> run behavior/concurrency/performance tests
  -> optional architecture judge scores reasoning quality
```

DDIA should be modeled as one expert lens. Future lenses can include JVM
performance, Spring production patterns, Kafka/RocketMQ reliability, Redis/cache
correctness, SRE/high availability, and database transaction design.

### Security/AppSec Workflow

```text
checkout vulnerable app
  -> run SAST/dependency/security scanner
  -> run controlled exploit setup where appropriate
  -> triage vulnerability evidence
  -> agent patches code/config
  -> rerun exploit regression + tests
  -> score fixed vulnerabilities and preserved behavior
```

Security workflows should evaluate repair quality, not open-ended offensive
capability. Exploit fixtures must be local, bounded, and reproducible.

## Task Pack Metadata

Java tasks should extend the current task-pack style with track and workflow
metadata.

```yaml
id: java-skills-bench
name: Java Skills Bench
domain: java
tasks:
  - id: stream-consumer-idempotency
    type: coding
    track: architecture
    capability: messaging-streaming
    knowledge_sources:
      - DDIA
      - Kafka consumer reliability
      - idempotent consumer pattern
    workflow: workflows/architecture-review.yaml
    prompt: Implement idempotent replay-safe consumer behavior.
    fixture: tasks/stream-consumer-idempotency/fixture
    expected: tasks/stream-consumer-idempotency/expected
    scorer: tasks/stream-consumer-idempotency/scorer.py
    max_score: 100
```

The first benchmark pack should include two executable cases per track:

```text
java-skills-bench
├── static-quality
│   ├── null-resource-exception
│   └── spring-transaction-misuse
├── architecture
│   ├── ddia-idempotent-consumer
│   └── high-concurrency-booking
└── security-appsec
    ├── sql-injection
    └── broken-access-control
```

This gives the taxonomy a working skeleton without creating a large shallow
case library.

## Scoring And Comparison

The existing baseline/treatment comparison should remain, but treatment should
be generalized from "skill path" to "workflow arm".

Comparison examples:

```text
baseline: no extra knowledge
treatment A: DDIA skill
treatment B: DDIA RAG
treatment C: DDIA + high-concurrency + HA expert lenses
treatment D: Sonar scanner + static-quality skill
```

Reports should include:

- task pack ID and version hash
- workflow ID and version hash
- knowledge mode and source hashes
- per-node status, duration, and artifact references
- Langfuse trace IDs for LLM-backed nodes
- deterministic score
- optional judge score
- total token cost and latency where available
- verdict scoped to the benchmark slice

Verdicts should keep the current semantics:

- `useful`
- `weak`
- `harmful`
- `inconclusive`

The verdict is benchmark evidence, not an absolute statement about a skill,
wiki, RAG index, or tool.

## MVP Scope

The first implementation should build the workflow foundation and one Java
benchmark pack skeleton.

Included:

- Workflow manifest schema.
- Internal DAG runner with `needs`, ready-node parallelism, timeouts, artifacts,
  and failure policies.
- Workflow arm abstraction for CLI/API comparison.
- Java task metadata fields: `track`, `capability`, and `workflow`.
- Six small executable Java benchmark cases, two per track.
- Static-quality workflow with scanner adapter nodes backed by simple local
  commands first.
- Architecture workflow with parallel expert-lens nodes.
- Security workflow with local exploit-regression tests only.
- Evidence report extensions for workflow nodes and artifacts.

Deferred:

- Full SonarQube server integration.
- Large RAG infrastructure.
- External workflow engines such as Temporal, Prefect, or Dagster.
- Public leaderboard.
- Multi-tenant security hardening.
- Open-ended penetration testing.

## Data Model Impact

The existing `eval_runs`, `eval_scores`, skills, and task packs can remain. The
workflow design adds workflow-specific records or JSON fields:

```text
eval_workflows
- id
- name
- version_hash
- source_path
- manifest
- created_at

eval_workflow_nodes
- id
- eval_run_id
- node_id
- node_type
- status
- started_at
- finished_at
- duration_ms
- artifact_paths
- langfuse_trace_ids
- error
```

For the MVP, node records can be persisted as JSON details on the run report if
separate tables would slow implementation. The public report shape should still
match the model above so the storage layer can be normalized later.

## Error Handling

Workflow execution should fail predictably:

- Invalid DAGs fail before any node runs.
- Cycles fail validation.
- Missing upstream artifacts fail the consuming node.
- Node timeout follows that node's `on_failure` policy.
- A failed scanner with `continue_with_artifact` should preserve stderr/stdout
  for the agent or report.
- A failed scorer should mark the task score as zero and include scorer details.
- A failed optional judge should not erase deterministic scorer results.

## Testing Strategy

Unit tests:

- workflow manifest validation
- DAG cycle detection
- ready-node scheduling
- parallelism-key enforcement
- failure policy behavior
- artifact dependency validation
- report serialization

Integration tests:

- static-quality workflow with fake scanner nodes
- architecture workflow with fake parallel expert lenses
- security workflow with local exploit-regression fixture
- baseline versus workflow-arm comparison
- Langfuse trace propagation for LLM-backed nodes

Live validation:

- Run a one-case Java workflow comparison through Docker Compose.
- Confirm compile/tests/scorer execute inside the sandbox.
- Confirm LLM-backed nodes emit Langfuse trace IDs.
- Confirm reports include per-node artifacts and a scoped verdict.

## Design Principles

- Benchmark engineering outcomes, not prompt aesthetics.
- Keep deterministic scoring as the primary signal.
- Use rubric judges only for qualities that executable tests cannot capture.
- Treat tools as evidence producers, not final authorities.
- Treat skills, RAG, and wiki content as interchangeable knowledge sources.
- Preserve artifacts so verdicts are inspectable.
- Keep security tasks local, bounded, and reproducible.
- Start with a small high-quality case set before expanding breadth.
