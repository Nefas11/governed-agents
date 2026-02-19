# Governed Agents — Verifiable outcomes for sub-agent work

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue)
![No pip dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)
![Tests](https://img.shields.io/badge/tests-9%2F9%20pass-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)

A Python package that checks whether a sub-agent actually delivered what it claimed, using independent verification after completion.

## The Problem
Current agent runtimes accept self-reported success. A sub-agent can say "done" even if no files were created, tests fail, or output is invalid. This failure mode is subtle because the calling agent has no ground truth and no enforced contract. Until now there was no standard way to score or reject hallucinated success deterministically. Governed Agents closes that gap with post-run verification that does not trust the agent.

## How It Works
```
Contract → Agent Execution → Verification Gates → Reputation Ledger
                ↓                    ↓
          Self-report           Score + Status
          (ignored)             (ground truth)
```
Three layers: (1) **Task Contracts** define concrete deliverables and checks before work starts. (2) **Verification Gates** run deterministic checks after completion (files, AST, tests, lint). (3) **Reputation Ledger** records outcomes and adjusts trust based on verified results, not claims.

## Score Matrix
| Outcome | Score | Meaning |
|---|---:|---|
| Perfect success (first try) | +1.0 | All gates pass on first completion |
| Success after retries | +0.7 | Deliverables verified after allowed retries |
| Honest blocker report | +0.5 | Agent reports a blocker and it is confirmed |
| Failed but tried | 0.0 | Work ran but did not meet gates |
| Hallucinated success | -1.0 | Agent claimed success but gates failed |

A -1.0 score is reserved for hallucinated success because it breaks trust: the agent asserted completion when objective evidence says otherwise.

## Quick Start
1) **Install**
```bash
bash install.sh
# Copies governed_agents/ into ~/.openclaw/workspace/governed_agents
```
2) **Contract + Spawn**
```python
from governed_agents.orchestrator import GovernedOrchestrator

g = GovernedOrchestrator.for_task(
    objective="Add CSV export",
    model="openai/gpt-5.2-codex",
    criteria=[
        "export() writes report.csv",
        "pytest tests/test_export.py passes",
    ],
    required_files=["app/export.py", "tests/test_export.py"],
    run_tests="pytest tests/test_export.py -q",
)
# Pass g.instructions() as the task to your sub-agent (e.g. sessions_spawn)
```
3) **Record + Verify**
```python
# After sub-agent completes:
result = g.record_success()
# Verifier runs independently — hallucinated success → score -1.0
print(result.passed, result.gate_failed)
```

## Verification Gates
| Gate | What it checks | Example |
|---|---|---|
| Files | Required files exist and are non-empty | `app/export.py` exists |
| AST | All .py files parse without SyntaxError | no broken imports or syntax |
| Tests | Defined test command succeeds | `pytest tests/test_export.py -q` |
| Lint | Optional lint command passes | `ruff check app/` |

## Reputation System
```python
from governed_agents.reputation import get_agent_stats

for agent in get_agent_stats():
    print(agent["agent_id"], agent["reputation"], agent["supervision"]["level"])
```

## Architecture
- `contract.py` — TaskContract dataclass + acceptance criteria
- `orchestrator.py` — GovernedOrchestrator: for_task(), record_success/blocked/failure()
- `verifier.py` — 4-gate pipeline: Files → Tests → Lint → AST
- `reputation.py` — SQLite ledger, per-model scoring, supervision levels
- `self_report.py` — CLI for sub-agents to self-report status

## Why This Matters
Accountability is the missing primitive in agent systems: without it, progress reports are indistinguishable from actual results. When agents can claim success without evidence, downstream decisions become unreliable and expensive to correct. Governed Agents makes verification the default, so orchestration relies on facts (files, tests, parseability), not promises.

## Requirements

- Python 3.10+
- No pip dependencies (pure stdlib: `sqlite3`, `subprocess`, `ast`, `glob`, `shlex`)
- `bash` for install.sh

## Contributing

Issues and PRs welcome. Run `python3 governed_agents/tests/test_verification.py` before submitting.

## License

MIT
