# Northgate Governance Assistant

**A governance-aware AI agent for enterprise architecture knowledge.**

Organizations are increasingly connecting AI agents to enterprise systems so they can retrieve information, perform tasks, and interact with users.

Most of the design attention goes to the workflow:

**systems → tools → agent → user**

But connecting an agent to enterprise data does not automatically make that data trustworthy.

**Is the source fresh? Is it complete? Who owns it? Are definitions consistent? What happens when the catalogue is ambiguous or incomplete?**

At the same time, Data Governance already creates much of this context — ownership, stewardship, glossary definitions, classifications, quality rules, and refresh expectations — but that content is often separate from the moment where a user is making a decision.

**Northgate Governance Assistant explores what happens when those two problems are brought together.**

> **Governance makes agents more trustworthy. Agents make governance easier to consume.**

---

## The idea

This project treats **enterprise architecture metadata as governed data**, rather than only as a static inventory.

The assistant can answer questions about:

- applications
- business capabilities
- technologies
- datasets
- enterprise terminology

But it does more than retrieve facts.

When the evidence supporting an answer comes from a registry that is failing one of its own declared quality rules, the agent surfaces that caveat automatically.

The goal is not to build a general-purpose enterprise chatbot. It is to demonstrate a narrower idea:

> **The answer and the trustworthiness of its evidence should travel together.**

---

## The signature behaviour

Ask:

> **What's affected if we retire PostgreSQL 11?**

The governed catalogue identifies three dependent applications:

- **HelixCare Record**
- **RiverLab Imaging**
- **RxBridge**

A normal architecture assistant could stop there.

Northgate also checks the governance metadata attached to the source registries:

| Registry             | Governed rule            | Actual  | Result   |
| -------------------- | ------------------------ | ------- | -------- |
| Technology Registry  | Data age ≤ 30 days       | 34 days | **FAIL** |
| Application Registry | Owner completeness ≥ 95% | 86.7%   | **FAIL** |

The impact analysis therefore arrives **with the quality caveat attached**.

The agent did not decide that 34 days was too old.

**The registry declared the rule. The agent read it.**

---

## Two layers of governed knowledge

The project models two related layers.

### Entity layer

Individual enterprise concepts:

- applications
- capabilities
- technologies
- datasets
- glossary terms

This layer answers questions such as:

> Which applications support Medication Management?

> How long are inpatient clinical records retained?

> What does Patient mean?

### Registry layer

The inventories themselves are treated as governed assets.

The project contains:

- **Application Registry**
- **Capability Registry**
- **Technology Registry**

Each registry can declare:

- steward
- classification
- source systems
- refresh cadence
- last refresh
- quality rules
- quality thresholds

This allows the assistant to work with both:

```text
enterprise facts
       +
governance context about those facts
```

---

## What governance gives the agent

| Governance property | What it gives the agent                                               |
| ------------------- | --------------------------------------------------------------------- |
| **Identity**        | Stable entities and source URLs to cite                               |
| **Boundaries**      | A way to distinguish catalogue absence from enterprise absence        |
| **Freshness**       | Declared thresholds that determine when an answer needs a caveat      |
| **Accountability**  | Owners and stewards to identify when information is missing           |
| **Disambiguation**  | Governed terminology and candidate records instead of silent guessing |
| **Quality**         | Computed rules that can travel with the answer                        |
| **Classification**  | Context about the sensitivity of governed information                 |

The important distinction is that the agent does not invent these rules.

**Governance metadata becomes runtime context.**

---

## Architecture

```text
┌──────────────────────────┐
│       YAML domain        │
│  governed source of truth│
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│     SQLite catalogue     │
│  runtime representation  │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────────────────────┐
│             Governance tools             │
│                                          │
│  get_entity                              │
│  search_glossary                         │
│  traverse                                │
│  get_registry_health                     │
│  identify_steward                        │
└────────────────────┬─────────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  Tool-calling agent  │
          │  governed contract   │
          └──────────┬───────────┘
                     │
                     ▼
┌──────────────────────────────────────────┐
│ Answer + evidence + caveats + citations │
│              + trace                     │
└──────────────────────────────────────────┘
```

The agent is implemented as a **plain Python tool-calling loop** rather than a general-purpose agent framework, keeping tool selection, arguments, results, and failure modes explicit.

---

## Domain

**Northgate Health Group** is a fictional healthcare group formed from the merger of three previously independent hospitals.

Healthcare is used as the setting because it creates realistic governance tensions around terminology, classification, retention, ownership, and stewardship.

The project itself is about **governance-aware agents**, not healthcare.

| Entity              | Count |
| ------------------- | ----- |
| Applications        | 15    |
| Capabilities        | 6     |
| Technologies        | 12    |
| Datasets            | 8     |
| Glossary terms      | 15    |
| Registries          | 3     |
| Typed relationships | 39    |

The YAML files are the source of truth. SQLite is the runtime catalogue used by the agent.

---

## Agent tools

### `get_entity`

Retrieves a governed entity by type and identifier.

Entity resolution follows:

```text
exact match
    ↓
conservative normalized match
    ↓
ambiguous if multiple candidates remain
```

Normalization supports:

- case differences
- repeated whitespace
- hyphen variation
- common final-token plural variation

The tool never silently chooses between multiple valid matches.

---

### `search_glossary`

Retrieves governed terminology and preserves:

- conflicting definitions
- departmental context
- aliases
- deprecated terms
- replacement terms
- ownership and stewardship gaps

---

### `traverse`

Performs typed, bidirectional, one-hop relationship traversal.

For example:

> PostgreSQL 11 → which applications depend on it?

---

### `get_registry_health`

Computes the registry's declared quality rules from the actual catalogue data.

It returns:

- metric
- threshold
- actual value
- pass/fail
- refresh context

This is what enables automatic quality caveats.

---

### `identify_steward`

Used when the catalogue cannot establish an answer.

Instead of filling the gap with plausible model knowledge, the assistant identifies who owns the governance gap.

---

## Answer contract

Every response follows four core rules:

1. **Ground factual claims in retrieved catalogue evidence.**
2. **Surface failing registry-quality rules automatically.**
3. **Do not infer enterprise facts that are absent from the catalogue.**
4. **When refusing because information is missing, identify the relevant steward or registry.**

One distinction is particularly important:

```text
not found in the catalogue
            ≠
does not exist in the enterprise
```

A `not_found` result means only that the governed catalogue cannot establish the answer.

---

## Governance cases

The domain deliberately includes situations that an AI assistant should **not smooth over**.

### Conflicting definitions

**Patient** has three surviving definitions:

- Clinical
- Revenue Cycle
- Research

None is declared enterprise-wide canonical.

The assistant returns the conflict rather than choosing one.

### Ownership gap

**Legacy MRN** has no assigned owner.

The assistant preserves the gap and identifies the steward instead of inventing an owner.

### Deprecated terminology

**Inpatient Day Case** is deprecated and replaced by **Day Procedure**.

The lifecycle context survives into the answer.

### Alias resolution

**Encounter** resolves to the canonical **Episode of Care** term.

### Governed retention

For inpatient clinical records, the assistant returns the governed retention value from the catalogue rather than replacing it with outside model knowledge.

---

## Evaluation

The project includes a lightweight, repeatable agent-evaluation harness.

The current benchmark runs:

```text
8 governance scenarios
×
3 repeated runs
=
24 agent executions per experiment
```

Each run records:

- question
- model configuration
- tools called and their order
- arguments
- tool results
- final answer
- citations

Each case is graded across four dimensions:

| Dimension      | Question                                                           |
| -------------- | ------------------------------------------------------------------ |
| **Outcome**    | Did the answer contain the required governed facts?                |
| **Trajectory** | Did the agent use the appropriate tools and relationships?         |
| **Governance** | Did it preserve ambiguity, refusal boundaries and quality caveats? |
| **Citations**  | Were claims supported by retrieved catalogue evidence?             |

### Experiment summary

| Experiment        | Strict passes | Critical failures |
| ----------------- | ------------- | ----------------- |
| Baseline          | **18 / 24**   | **6**             |
| Later experiment  | **21 / 24**   | **1**             |
| Latest experiment | **21 / 24**   | **2**             |

The aggregate score is only part of the story.

One useful failure involved the natural-language phrase:

> **inpatient clinical records**

The original exact-match resolver failed systematically:

**0 / 3**

After adding conservative normalized entity resolution:

**3 / 3 → 3 / 3**

Other behavior remains nondeterministic, particularly some glossary routing and answer/citation completeness.

Those misses are intentionally kept visible.

The objective of the eval layer is not to claim production-grade reliability. It is to make failures **observable, classifiable and actionable**.

See `[eval/README.md](./eval/README.md)` and `[eval/EXPERIMENT_RESULTS.md](./eval/EXPERIMENT_RESULTS.md)` for the detailed benchmark.

---

## Evaluation loop

```text
Run benchmark
      ↓
Identify the failing layer
      ↓
Make the smallest targeted change
      ↓
Replay stored traces when possible
      ↓
Rerun only when agent behaviour changed
```

This helped distinguish between:

- routing failures
- retrieval failures
- governance-behaviour failures
- answer-completeness failures
- citation failures
- evaluator failures

**Evals are software too.**

---

## Key design decisions

### YAML is the source of truth

The governed domain stays transparent, inspectable and version controlled.

### SQLite is the runtime catalogue

The agent queries a deterministic local representation rather than interpreting YAML directly during each interaction.

### Declared quality must match reality

Quality rules are computed from the catalogue itself.

If a registry declares 95% owner completeness while only 13 of 15 applications have owners, the rule fails.

### No silent ambiguity

Multiple matching entities return an ambiguous result.

The agent cannot silently choose the most convenient one.

### Deterministic resolution before semantic retrieval

The MVP uses conservative lexical normalization rather than fuzzy semantic retrieval for entity resolution.

Predictability and inspectability are more important here than matching everything.

### Tool trajectories are logged

Observable agent actions are recorded for evaluation and replay.

The trace contains tool activity — **not hidden chain-of-thought**.

---

## DAMA-DMBOK concepts demonstrated

| Area                        | Demonstrated through                                                 |
| --------------------------- | -------------------------------------------------------------------- |
| **Data Governance**         | ownership, stewardship, decision rights, escalation                  |
| **Metadata Management**     | entities, registries, glossary, source metadata                      |
| **Data Quality**            | rules, thresholds, completeness and freshness                        |
| **Data Architecture**       | applications, capabilities, technologies, datasets and relationships |
| **Reference & Master Data** | governed terminology, aliases, deprecated and canonical concepts     |

The goal is not to implement the full DAMA framework. These concepts are applied where they directly support the agent-governance interaction.

---

## Technology

- Python
- OpenAI API
- SQLite
- YAML
- deterministic evaluation harness
- pytest regression tests

The core agent deliberately avoids a general-purpose agent framework.

---

runs consistency and governance-domain validation checks.

For benchmark execution and replay instructions, see:

`[eval/README.md](./eval/README.md)`

---

## Why this project exists

The project is trying to demonstrate two ideas at the same time.

### For AI systems

Connecting an agent to enterprise sources is not enough.

**Metadata, quality, ownership, freshness and ambiguity affect whether an answer should be trusted.**

### For Data Governance

Governance becomes more useful when its content appears **inside the workflow where a question is being answered or a decision is being made**.

That leads back to the central thesis:

> **Governance makes agents more trustworthy.
> Agents make governance easier to consume.**

---

## Disclaimer

Northgate Health Group and all domain records in this repository are fictional and were created solely for demonstration and learning purposes.

**No real patient or organizational data is used.**
