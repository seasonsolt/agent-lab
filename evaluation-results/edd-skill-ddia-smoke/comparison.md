# Agent Lab Skill Comparison Evidence

- Generated at: `2026-06-26T07:55:11.340812+00:00`
- Evaluator: `seasonsolt/agent-lab`
- Treatment repo: `https://github.com/seasonsolt/edd-skill`
- Treatment commit: `fef3623d5a7d28732f4a007d9fbc4ebd1cdbb39f`
- Treatment skill path: `.agents/skills/eval-driven-ai-tdd`
- Baseline skill path: `/Users/Thin/Source/git/seasonsolt/agent-lab/skills/example-coding-skill`
- Task pack path: `/Users/Thin/Source/git/seasonsolt/agent-lab/task_packs/ddia-coding-real`
- Verdict: `inconclusive`

## Summary

| Metric | Baseline | Treatment | Delta |
| --- | ---: | ---: | ---: |
| Mean auto score | 100.0 | 100.0 | 0.0 |
| Mean final score | 70.0 | 70.0 | 0.0 |
| Mean pass rate | 1.0 | 1.0 | 0.0 |
| Error rate | 1.0 | 0.0 |  |
| Timeout rate | 1.0 | 0.0 |  |

## Run IDs

- Baseline: `eval-fdbc09b5060449be917f2b5b09240947`
- Treatment: `eval-97e053930d704bc98eb6edeac34ec0d2`

## Reproduction

```bash
python3 -m skill_lab.cli compare --baseline ./skills/example-coding-skill --treatment-repo https://github.com/seasonsolt/edd-skill --treatment-skill-path .agents/skills/eval-driven-ai-tdd --task-pack ./task_packs/ddia-coding-real --api-url http://localhost:8000 --runs 1 --network --timeout-seconds 300 --output-dir ./evaluation-results/edd-skill-ddia-smoke
```

## Limitations

This is repeated Agent Lab comparison evidence, not statistical proof. Model output variance, model/provider configuration, task-pack coverage, and sandbox timeouts can affect the result.
