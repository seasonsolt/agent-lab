# DDIA Eval Bounded Task Optimization Design

## Goal

Make the DDIA Skill comparison produce useful evidence instead of timeout-heavy
inconclusive results. The optimization should keep Agent Lab's external skill
comparison flow intact, but make the DDIA coding task bounded enough that the
coding agent can finish and the scorer can compare baseline and treatment runs.

## Root Cause

The latest Agent Lab comparison against `seasonsolt/ddia-skill` produced
`inconclusive` evidence because every baseline and treatment run timed out.
The runs were not empty: the agent edited files and the scorer awarded partial
credit. The failure mode was that the sandbox task did not finish cleanly before
the per-task timeout.

The current sandbox prompt is too open-ended for a benchmark. It tells the
agent where the skill and workspace are, then appends a broad task prompt. It
does not state that this is a bounded evaluation, does not discourage editing
documentation or creating extra tests, and does not tell the agent to stop as
soon as the implementation is complete.

The DDIA task prompt also leaves several scorer-critical details implicit:
duplicate event handling, stale versions, terminal states, invalid transition
dead letters, and late payment events. That ambiguity makes the task less like
a focused coding benchmark and more like an exploratory design exercise.

## Confirmed Approach

Use a bounded-task optimization instead of raising timeouts as the primary fix.

The implementation should:

- Add completion-oriented instructions to the sandbox task prompt.
- Make the DDIA coding task wording concrete enough to match the scorer.
- Preserve timeout rate as a reported quality signal.
- Verify with a small baseline/treatment smoke comparison before rerunning a
  full repeated comparison.

## Out Of Scope

- Changing the external skill repository ingestion contract.
- Changing Langfuse tracing.
- Building a UI.
- Adding a statistical significance system.
- Treating timeout work as successful work.
- Hardcoding model credentials or API keys.
- Making the DDIA Skill look better by relaxing scorer expectations.

## Sandbox Prompt Design

`build_task_prompt` should keep the existing three facts:

- where the skill instructions are mounted
- that the agent should work inside `/workspace`
- the task prompt from the task pack

It should also add benchmark-specific constraints:

- This is a bounded evaluation task.
- Edit only files needed to satisfy the task.
- Do not add dependencies.
- Do not spend time on documentation unless the task asks for it.
- Prefer a small correct implementation over exploration.
- Stop and return a concise summary once the implementation is complete.

The goal is not to constrain the model's coding strategy. The goal is to avoid
non-scorable work that consumes the entire timeout window.

## DDIA Task Prompt Design

The `order-event-projection-001` prompt should describe the exact behavior that
the scorer expects:

- maintain a per-order read model
- preserve amount and current status
- track event ids to ignore duplicates
- ignore stale lower-version events
- preserve terminal cancellation state
- record invalid transitions in `dead_letters`
- avoid creating a durable order from a late payment event
- keep enough version evidence for replay and operations

The prompt should still be a realistic coding task, not a direct list of scorer
assertions. It should ask the agent to implement the projector in the existing
fixture, without adding dependencies or unrelated files.

## Data Flow

```text
skill-lab compare
  -> Eval API
  -> sandbox prompt builder adds bounded-eval instructions
  -> sandbox coding agent edits fixture
  -> scorer evaluates the resulting workspace
  -> comparison report keeps score, timeout rate, and verdict
```

## Error Handling

Timeouts should remain visible. If a run times out, Agent Lab should continue to
report the sandbox error and score whatever output is available, as it does
today. The optimization is successful only if the scenario becomes finishable
under normal comparison settings.

Invalid task pack or skill paths should continue to fail before starting the
comparison. This design does not change path validation or Docker behavior.

## Testing Strategy

Add focused unit coverage before implementation:

- The sandbox prompt includes bounded-evaluation and stop conditions.
- The sandbox prompt still includes the skill path, workspace path, and task
  text.
- The DDIA task pack still loads as a valid task pack.

Then run existing evaluation tests to check no broader regression:

- `docker compose config`
- `docker compose run --build --rm coding-agent pytest -q`

After code tests pass, run live validation:

- One baseline run and one DDIA treatment run against the DDIA task pack.
- If both finish without sandbox timeout, run the repeated comparison.
- Export updated comparison artifacts only after the repeated comparison is
  meaningful.

## Success Criteria

The optimization is successful when:

- the DDIA comparison no longer has a 100% timeout rate under the normal
  per-task timeout
- at least one baseline and one treatment smoke run finish cleanly
- the repeated comparison report can distinguish coding quality from timeout
  behavior
- Langfuse still receives traces for the coding-agent calls
- all local tests pass

The expected result is not guaranteed to be positive for DDIA Skill. A valid
result may be `useful`, `weak`, `harmful`, or `inconclusive`. The important
improvement is that the verdict is based on completed benchmark behavior rather
than universal timeout.
