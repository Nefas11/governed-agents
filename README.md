# Governed Agents

Deterministic verification and persistent reputation scoring for AI sub-agent work.

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue)
![No Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

## The Problem

Agent orchestration frameworks delegate tasks to sub-agents and accept
self-reported success. A sub-agent can claim "done" when files are missing,
tests fail, or nothing was implemented. The calling agent has no ground truth.

This is not an edge case. It is the default failure mode of every multi-agent
system that trusts self-reports.

**No existing framework solves this.** CrewAI, LangGraph, AutoGen, and
LlamaIndex all lack deterministic post-task verification combined with
persistent agent scoring. See [Framework Comparison](#framework-comparison).

Governed Agents closes this gap.

## How It Works

```
                    ┌──────────────────┐
                    │  Task Contract   │
                    │  (before spawn)  │
                    └────────┬─────────┘
                             │
                    ┌────────v─────────┐
                    │ Agent Execution  │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────v───┐  ┌──────v──────┐  ┌───v────────┐
     │ Self-Report │  │ Verification│  │ (ignored   │
     │ status=X    │  │ Gates       │  │  for score)│
     └─────────────┘  └──────┬──────┘  └────────────┘
                             │
                    ┌────────v─────────┐
                    │ Reputation       │
                    │ Ledger (SQLite)  │
                    └──────────────────┘
```

Three layers:

1. **Task Contract** — Defines objective, acceptance criteria, required files,
   and test commands before the agent starts. The contract becomes the prompt.

2. **Verification Gates** — Four deterministic checks run independently after
   completion. The agent's self-report is not trusted.

3. **Reputation Ledger** — Persistent per-model scoring. Tracks reliability
   over time using exponential moving average.

## Formal Model

### Score Function

The task score `s(t)` is determined by comparing the agent's self-report
against independent verification:

```
s(t) = +1.0   if agent_report = success  ∧  V(task) = True
s(t) = −1.0   if agent_report = success  ∧  V(task) = False   (hallucinated)
s(t) = +0.5   if agent_report = blocked                       (honest blocker)
s(t) =  0.0   if agent_report = failure
```

The critical distinction: hallucinated success (claiming done when verification
fails) receives the harshest penalty. An honest failure report is scored higher
than a fake success.

### Verification Gate Composition

```
V(task) = Gate_Files(task) ∧ Gate_Tests(task) ∧ Gate_Lint(task) ∧ Gate_AST(task)
```

Gates execute sequentially. First failure short-circuits the pipeline and sets
`score_override = −1.0`. No LLM is involved — all gates are deterministic:

| Gate  | Check                                  | Method               |
|-------|----------------------------------------|----------------------|
| Files | Required output files exist (> 0 bytes) | `pathlib.Path.exists` |
| Tests | Test command exits with code 0         | `subprocess.run`     |
| Lint  | Linter passes (graceful skip if absent) | `subprocess.run`     |
| AST   | Python files parse without syntax error | `ast.parse`          |

### Reputation Update (EMA)

Reputation is updated after each task using an exponential moving average:

```
R(t+1) = (1 − α) · R(t) + α · s(t)

where:
  R(t)  ∈ [0, 1]     Reputation score at time t
  α     = 0.3         Learning rate (configurable)
  s(t)  ∈ {−1, 0, 0.5, 1}   Task score
  R(0)  = 0.5         Neutral prior
```

Properties:
- A single hallucination drops reputation significantly
  (R=0.5 → 0.5·0.7 + 0.3·(−1) = 0.05)
- Recovery requires multiple consecutive successes
- The asymmetry is intentional: trust is hard to build, easy to destroy

### Supervision Thresholds

Reputation maps to supervision levels that control agent autonomy:

```
Supervision(R) = autonomous    if R > 0.8
                 standard      if 0.6 < R ≤ 0.8
                 supervised    if 0.4 < R ≤ 0.6
                 strict        if 0.2 < R ≤ 0.4
                 suspended     if R ≤ 0.2
```

## Quick Start

**Install:**

```bash
bash install.sh
# Copies governed_agents/ into ~/.openclaw/workspace/
```

**Define a contract and spawn:**

```python
from governed_agents.orchestrator import GovernedOrchestrator

g = GovernedOrchestrator.for_task(
    objective="Add CSV export endpoint",
    model="openai/gpt-5.2-codex",
    criteria=[
        "export() writes report.csv",
        "pytest tests/test_export.py passes",
    ],
    required_files=["app/export.py", "tests/test_export.py"],
    run_tests="pytest tests/test_export.py -q",
)

# Pass g.instructions() as the task prompt to your sub-agent
```

**Record outcome (verification runs automatically):**

```python
result = g.record_success()
# If agent delivered: score = +1.0, verification_passed = True
# If agent lied:     score = -1.0, gate_failed = "files"

# Honest blocker:
g.record_blocked("Database credentials not configured")
# score = +0.5 (rewarded for honesty)
```

**Query reputation:**

```python
from governed_agents.reputation import get_agent_stats

for agent in get_agent_stats():
    print(f"{agent['agent_id']:30s} "
          f"rep={agent['reputation']:.2f} "
          f"level={agent['supervision']['level']}")
```

## Framework Comparison

| Capability                          | Governed Agents | CrewAI | LangGraph | AutoGen | LlamaIndex |
|-------------------------------------|:---:|:---:|:---:|:---:|:---:|
| Task contract before execution      | ✅ | ❌¹ | ❌ | ❌ | ❌ |
| Deterministic file verification     | ✅ | ❌ | ❌ | ❌ | ❌ |
| Independent test execution          | ✅ | ❌ | ❌ | ⚠️² | ❌ |
| AST syntax validation               | ✅ | ❌ | ❌ | ❌ | ❌ |
| Hallucination penalty (−1.0)        | ✅ | ❌ | ❌ | ❌ | ❌ |
| Persistent reputation ledger        | ✅ | ❌ | ❌ | ❌ | ❌ |
| Supervision level adjustment        | ✅ | ❌ | ❌ | ❌ | ❌ |

¹ CrewAI has `expected_output` but it is a text description, not deterministically evaluated.
² AutoGen supports code execution but has no contract schema, no reputation tracking, and no hallucination penalty.

**The gap:** No existing framework combines deterministic post-task verification
of sub-agent claims with persistent reputation scoring. Governed Agents is
designed to fill exactly this gap.

## Architecture

```
governed_agents/
├── contract.py      Task contract dataclass + JSON schema enforcement
├── orchestrator.py  GovernedOrchestrator: for_task(), record_*(), spawn_task()
├── verifier.py      4-gate verification pipeline
├── reputation.py    SQLite ledger, EMA scoring, supervision levels
├── self_report.py   CLI for sub-agent self-reporting
└── test_verification.py   Unit tests for all gates
```

## Score Matrix

| Outcome                | s(t)     | Meaning                                       |
|------------------------|----------|-----------------------------------------------|
| Verified success       | **+1.0** | All gates pass on first completion             |
| Honest blocker         | **+0.5** | Agent reported it could not proceed            |
| Failed but tried       | **0.0**  | Work ran but did not meet gates                |
| Hallucinated success   | **−1.0** | Agent claimed success, verification failed     |

## Requirements

- Python 3.10+
- No pip dependencies (pure stdlib: `sqlite3`, `ast`, `subprocess`, `pathlib`)
- `git` + `bash` for `install.sh`

## Contributing

Issues and PRs welcome. Run tests before submitting:

```bash
python3 governed_agents/test_verification.py
```

## License

MIT
