# Eval

This folder contains the lightweight evaluation harness for the Northgate governance assistant.

It is deliberately small and project-specific. The goal is to verify the most important agent behaviors, not to build a general-purpose eval platform.

---

## What is evaluated

The benchmark currently covers **Q1–Q8**, with three repeated runs per case.

Each case is graded across four dimensions:

### Outcome

Did the agent return the governed facts required by the case?

Examples:

- all three `Patient` definitions are preserved;
- PostgreSQL 11 returns the correct affected applications;
- the declared retention period is returned exactly;
- application owner completeness is reported from the registry rule.

### Trajectory

Did the agent use the right tools and follow the required tool relationships?

Examples:

- `search_glossary` for governed terms;
- `get_entity` for named catalogue entities;
- `traverse` for typed relationships;
- `get_registry_health` when returned entities come from governed registries.

Multi-tool cases use **required calls and meaningful ordering constraints**, not one brittle exact trace.

### Governance

Did the agent respect the governance contract?

Examples:

- preserve conflicting definitions instead of choosing one;
- treat a null owner as an ownership gap;
- identify deprecated terms and aliases correctly;
- surface failing registry-quality rules automatically;
- avoid replacing governed values with outside model knowledge.

### Citations

Did the answer cite retrieved catalogue evidence and avoid invented `northgate://` URLs?

Citation checks focus on **claim support**, not simply citing every entity observed during retrieval.

---

## Folder structure

A typical layout is:

```text
eval/
├── README.md
├── spec.yaml
├── cases.yaml
├── experiments/
│   └── 2026-09-09/
│       ├── 14-00-00/
│       ├── 15-30-05/
│       └── 17-58-58/
└── EXPERIMENT_RESULTS.md

logs/
└── experiments/
    └── ...

scripts/
├── run_agent_eval.py
└── regrade_experiment.py

tests/
└── test_*eval*.py
```

Exact filenames may evolve, but the responsibilities stay the same:

- `spec.yaml` — machine-readable grading contract;
- `cases.yaml` — benchmark questions;
- `experiments/` — grades and summaries for each experiment;
- `logs/experiments/` — stored model trajectories;
- `run_agent_eval.py` — run the live agent benchmark;
- `regrade_experiment.py` — replay stored traces against the current evaluator;
- tests — regression coverage for evaluator behavior.

---

## Evaluation workflow

### 1. Run the benchmark

Each question is executed multiple times because agent behavior is nondeterministic.

```text
Q1–Q8
×
3 replicates
=
24 agent runs
```

Each run stores:

- question;
- model/configuration;
- tool calls in order;
- tool arguments;
- tool results;
- final answer;
- citations.

### 2. Grade each trajectory

Deterministic graders compare the stored trace with `spec.yaml`.

They are used for objective checks such as:

```text
tool selected?
arguments correct?
expected entities returned?
registry rule failed?
required caveat present?
citation URL retrieved?
```

### 3. Inspect failures

A failed run is classified by the layer that actually failed:

```text
routing
retrieval
tool trajectory
governance behavior
answer completeness
citation
evaluator
```

This distinction matters. A wrong final answer and a broken grader are not the same problem.

### 4. Make the smallest targeted change

Examples from this project:

```text
Q6 retrieval failure
→ normalized entity resolution

Q2 routing failure
→ clearer glossary tool description

Evaluator false negative
→ evaluator-only repair
```

### 5. Replay before rerunning when possible

If only evaluator logic changes, existing model traces are replayed instead of calling the model again.

Trace hashes are checked to confirm model outputs remain unchanged.

This allows evaluator changes to be separated from agent changes.

---

## Reproducibility

The benchmark uses:

```text
model: gpt-5.6
reasoning effort: medium
benchmark as-of date: 2026-09-08
```

The frozen date is important because registry freshness metrics change over time.

Interactive demo mode may use the real current date; benchmark runs use the fixed evaluation date so experiments remain comparable.

---

## Current experiment summary

| Experiment | Strict pass | Critical failures |
|---|---:|---:|
| `14-00-00` | 18/24 | 6 |
| `15-30-05` | 21/24 | 1 |
| `17-58-58` | 21/24 | 2 |

See [`EXPERIMENT_RESULTS.md`](./EXPERIMENT_RESULTS.md) for the case-by-case story and interpretation.

---

## Scope

This eval layer is intentionally lightweight.

Included:

- deterministic grading;
- repeated runs;
- trajectory inspection;
- failure classification;
- evaluator regression tests;
- experiment replay;
- simple reliability comparison.

Not currently included:

- large-scale benchmark suites;
- judge-model calibration;
- statistical significance testing;
- automated prompt search;
- production observability platforms;
- general-purpose evaluation frameworks.

Those are useful in larger AI systems, but are outside the scope of this governance MVP.

---

## Why this exists

The eval harness supports the main project thesis:

> Governed metadata should make AI answers more trustworthy, and the agent should make governance easier to consume.

The benchmark provides evidence that the assistant is not only capable of answering successful demo questions, but that its retrieval, governance behavior, and failure modes can also be measured.
