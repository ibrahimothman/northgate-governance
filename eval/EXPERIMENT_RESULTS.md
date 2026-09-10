# Experiment Results

This document summarizes the agent-evaluation experiments for the Northgate governance assistant.

The goal of the eval work is intentionally lightweight: test whether the agent behaves reliably on a small set of governance scenarios, use failures to improve the product, and keep a reproducible record of what changed.

---

## Benchmark

The benchmark contains **8 governance scenarios**, each executed **3 times** per experiment.

| Case | What it tests |
|---|---|
| Q1 | Conflicting glossary definitions |
| Q2 | Ownership gap and glossary routing |
| Q3 | Deprecated terminology |
| Q4 | Alias resolution |
| Q5 | Technology impact with automatic governance caveats |
| Q6 | Governed retention and entity resolution |
| Q7 | Cross-site application duplication with data-quality caveat |
| Q8 | Registry data-quality reporting |

Each run is evaluated across four dimensions:

- **Outcome** — was the governed answer correct?
- **Trajectory** — were the appropriate tools used?
- **Governance** — were ambiguity, quality failures, and knowledge boundaries respected?
- **Citations** — were claims grounded in retrieved catalogue records?

The benchmark uses a frozen evaluation date of **2026-09-08** so time-dependent freshness rules remain reproducible.

---

## Experiment history

All stored traces were replayed against the **current evaluator and specification**. The model was not rerun during replay, and trace hashes remained unchanged.

| Experiment | Strict pass | Critical failures |
|---|---:|---:|
| `14-00-00` | 18/24 | 6 |
| `15-30-05` | 21/24 | 1 |
| `17-58-58` | 21/24 | 2 |

### Pass rate by case

| Case | `14-00-00` | `15-30-05` | `17-58-58` |
|---|---:|---:|---:|
| Q1 | 3/3 | 3/3 | 3/3 |
| Q2 | 0/3 | 2/3 | 1/3 |
| Q3 | 3/3 | 3/3 | 3/3 |
| Q4 | 3/3 | 3/3 | 3/3 |
| Q5 | 3/3 | 2/3 | 3/3 |
| Q6 | 0/3 | 3/3 | 3/3 |
| Q7 | 3/3 | 3/3 | 3/3 |
| Q8 | 3/3 | 2/3 | 2/3 |

---

## What the experiments revealed

### 1. Q6 exposed a retrieval problem

The original agent correctly identified the question as a dataset lookup, but exact matching failed on:

```text
"inpatient clinical records"
```

versus the governed entity:

```text
"Inpatient Clinical Record"
```

The fix was a conservative entity resolver:

```text
exact lookup
    ↓
normalized lexical lookup
    ↓
ambiguous if multiple matches
```

Normalization handles case, whitespace, hyphen variation, and common final-token plural variation. IDs and entity URLs remain exact-only.

Result:

```text
Q6: 0/3 → 3/3 → 3/3
```

This removed a systematic critical retrieval failure without introducing fuzzy or semantic matching.

---

### 2. Q2 exposed a routing problem

`Legacy MRN` is a glossary term with:

- no assigned owner;
- steward: Health Information Management.

The baseline agent consistently misclassified it as another entity type.

Tool descriptions were updated so glossary search explicitly covers ownership, stewardship, canonical status, aliases, and lifecycle of governed business terms.

Result:

```text
Q2: 0/3 → 2/3 → 1/3
```

Routing improved, but remains nondeterministic. This is kept as a known limitation rather than tuning the benchmark until it passes.

---

### 3. Evaluators also needed testing

Several early failures were caused by the evaluator rather than the agent.

Examples included:

- Markdown formatting causing `"owner is **unassigned**"` to fail a literal check;
- treating entity IDs and display names as different references;
- requiring one exact multi-tool order when multiple valid orders existed;
- penalizing a required Capability Registry health check as an extra tool call;
- treating citation completeness as “cite every retrieved entity” rather than “cite the evidence needed for the claim.”

Evaluator changes were regression-tested, then all stored traces were replayed without rerunning the model.

This reinforced an important lesson:

> Evals are software too. A failing grader can make an agent look better or worse than it really is.

---

## Interpretation

The experiments improved the **severity and nature of failures** more than the headline pass rate alone suggests.

The most meaningful change was the removal of the systematic Q6 retrieval failure. The later experiments also showed stronger tool routing and governance behavior overall, while remaining failures were increasingly concentrated in nondeterministic routing and answer completeness rather than incorrect governed facts.

The eval harness is therefore used as a practical product-development loop:

```text
run
  ↓
inspect failure
  ↓
identify the failing layer
  ↓
make the smallest targeted change
  ↓
rerun or replay
  ↓
compare
```

---

## Current known limitations

- **Q2 glossary routing remains nondeterministic.**
- Some answer-completeness behaviors can vary between runs even when retrieval and governance behavior are correct.
- The eval suite is intentionally small and project-specific; it is not intended to be a general-purpose agent evaluation framework.
- Deterministic graders handle objective checks. More subtle semantic issues would require a model-based judge or human review, which is intentionally out of scope for this MVP.

---

## Why this matters to the project

The purpose of the assistant is not only to answer questions from governed enterprise metadata.

It should also:

1. use governed sources rather than unsupported model knowledge;
2. preserve ambiguity and ownership gaps;
3. surface source-quality problems automatically;
4. provide traceable citations;
5. behave consistently enough that failures can be measured and improved.

The eval work exists to verify those behaviors rather than relying on a few successful demo prompts.
