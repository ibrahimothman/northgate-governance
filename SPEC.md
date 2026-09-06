# MVP Spec v4 — Governed Metadata Catalogue + Conversational Access

**Status:** FROZEN. Changes require a logged decision in `WEEKLOG.md`.
**Budget:** ~51 hours / 4 weeks. 3 hours per session, 5 sessions per week, 17 sessions.
**Ship condition:** public repo + two video cuts + honest evaluation results including failures.
**Rule:** anything not in this document goes in `BACKLOG.md`, not into the build.

**Changes from v3, all pre-decided so they cannot be surrendered under pressure in week 3:**

| Change | Reason |
|---|---|
| `LocalClient` is primary, OpenMetadata is a 90-minute spike for the finding | The mapping mismatch is already the finding. Standing up Docker does not strengthen it and risks a lost week. ADR-005. |
| CLI, not Streamlit | Saves ~3 hrs. A terminal recording is a better demo than a web UI — nothing for the viewer to evaluate but the answer. |
| 12 evaluation questions, not 20 | Saves ~4 hrs. Twelve scored questions with published misses beats twenty unscored. |
| Walking skeleton built in session 2, on fake data | Integration risk moves from hour 30 to hour 6. The demo exists on day two. |
| Consistency check is a script, not an eyeball | Declared quality that does not match computed reality destroys the argument on inspection. |
| One evaluation question must be a governance trap | A question where an ungoverned model would confidently produce a plausible wrong answer. |

---

## The thesis

> EA repositories model applications, capabilities, and technologies — but carry no classification, stewardship, retention, or quality rules.
> Data catalogues model classification, stewardship, and quality — but have no concept of an application portfolio.
> Neither side spans the gap. And even where governed content exists, nobody reads it.

This project governs architecture metadata as a data asset, and puts an agent over it that answers from governed content, cites its source, refuses when the answer isn't there, and routes the refusal to the steward who owns the gap.

The claim runs in both directions, and the README says so explicitly:

**Governed metadata is what makes an enterprise agent trustworthy. An agent is what finally makes governance get read.**

**Two findings underpin this, both from direct inspection — they go in the README:**

- A reference EA model contained 0 properties, 0 constraints, 0 dates on elements, and 1 documentation field. EA describes structure, not who may keep what, at what sensitivity, for how long.
- OpenMetadata has no first-class Application or Capability entity. The catalogue side of the gap is equally real.

---

## The signature behaviour

Everything below exists to make one behaviour possible. If the build is going badly, protect this and cut anything else.

**The agent answers an EA question with the governance caveat attached.**

> *"What's affected if we retire the ServerOS 7 platform?"*
> Four applications, each cited. **Then:** the technology registry declares a 30-day staleness rule; these rows were last verified 34 days ago, so the lifecycle data is outside its own declared quality threshold. Verify before acting.

> *"Which applications support Medication Management?"*
> Three applications, each cited. **Then:** the application registry declares 88% owner completeness against a 95% threshold, and two of the applications returned are among those with no owner recorded.

An EA tool cannot say this — it has no quality metadata. A data catalogue cannot say this — it has no application portfolio. The registry layer is what makes it possible, and it is the entire argument of the project in fifteen seconds.

**Framing ladder — same argument at three altitudes. Use the right rung for the audience:**

| Rung | Line | Used in |
|---|---|---|
| Abstract | Governed metadata is what makes an enterprise agent trustworthy. An agent is what finally makes governance get read. | LinkedIn hooks, README intro |
| Domain | EA holds the portfolio but no quality rules; catalogues hold the quality rules but no portfolio. Neither can tell you your impact analysis is correct *and* built on data that already failed its own freshness rule. | Interviews, README body |
| Concrete | Four applications are affected, and the lifecycle data behind that answer is 34 days old against a declared 30-day rule. | The video |

Healthcare appears at none of these levels. It is set dressing — it makes the hard cases believable and supplies a rich classification story. If someone repeats the thesis back and mentions hospitals, they remembered the demo instead of the point.

---

## The organisation

**Northgate Health Group** — a fictional hospital group formed from the merger of three previously independent hospitals.

Front office consolidated first (one patient portal, one appointment system). Clinical back-office systems still run in parallel per site. Document management is already fully consolidated — the control case showing what "done" looks like.

Healthcare because: richest classification story (restricted patient data, confidential clinical notes, internal research extracts, public statistics), real multi-decade retention, genuine consent and legal-basis requirements, and stewardship contested between clinical, administrative, and research functions.

---

## Two layers — the distinctive idea

**Entity layer** — individual applications, capabilities, technologies, datasets, and glossary terms as catalogue entities. Answers *"who owns the Pharmacy System?"*

**Registry layer** — the application, capability, and technology *inventories* catalogued as governed datasets in their own right, each with a steward, classification, source systems, refresh cadence, and quality rules. Answers *"where does our application inventory come from, who stewards it, and how complete is it?"*

Almost nobody governs their architecture data. That is why EA repositories rot. The registry layer is this project's original contribution and it directly encodes real portfolio-ownership experience.

**Technologies is the sharpest registry** — its source is genuinely external (endoflife.date), refreshed monthly, with a staleness rule flagging rows unverified for 30+ days. Governance data has a supply chain and decays; demonstrating that is more sophisticated than a static catalogue.

---

## What the MVP must demonstrate

1. **Domain modelling competence** — a coherent metamodel, not a sample database dumped into a catalogue
2. **Governed architecture data** — the registry layer, with declared quality that the actual rows honour
3. **EA portfolio reasoning** — impact, duplication, and capability questions answered from the catalogue
4. **Grounded, cited answers** — every response links to its source entity
5. **Agentic tool use** — the model plans and calls tools; it is not a fixed pipeline
6. **Correct refusal, then escalation** — not in the catalogue means the system says so *and* names the steward who would own it
7. **Honest evaluation** — measured results, including tool-selection accuracy, with failures published

**Not in v1:** lineage, external source ingestion, policy enforcement, gap analysis, aggregate query routing, any write path to the catalogue, access control by classification.

---

## Scope — domain files (`/domain`)

| File | Count | Notes |
|---|---|---|
| `applications.yaml` | 15 | 3 triplicated across sites; 1 already consolidated; **exactly 2 with empty owner** |
| `capabilities.yaml` | 6 | levelled, with parents |
| `technologies.yaml` | 12 | ≥3 past EOL, real dates from endoflife.date, cached |
| `datasets.yaml` | 8 | non-uniform classification, split stewardship |
| `glossary.yaml` | 15 | includes all four hard cases |
| `registries.yaml` | 3 | schema + governance metadata for the three inventories |
| `relationships.yaml` | 35–40 | **Write `EVAL.md` first. Keep only edges the 12 questions traverse.** |

### Relationship priority

These four edge types carry nearly every question in the evaluation set. Build them first and completely:

`application → technology` · `application → capability` · `application → site` · `application → dataset`

Everything else is opportunistic.

### The four hard cases — non-negotiable

| Case | Implementation |
|---|---|
| **Conflicting definitions** | *Patient* — clinical, billing, and research definitions all surviving the merger, each with departmental context. None marked canonical. |
| **Orphaned ownership** | *Legacy MRN* — owner empty; the records manager left during integration. |
| **Deprecated term** | *Inpatient Day Case* — status deprecated, `replaced_by` set. Still used verbally. |
| **Alias** | *Encounter* — resolves to canonical *Episode of Care*. |

### Declared quality must match reality — checked by script

If `registries.yaml` says application owner completeness is 88% against a 95% threshold, then two of the fifteen applications must actually have an empty owner.

`make check` computes every declared metric from the YAML and fails loudly on any mismatch. This runs in session 7 and again before shipping. A registry passing every rule is a fantasy; a visibly failing rule gives the agent something real to report — and the signature behaviour depends on the numbers being true.

---

## The agent

Not a RAG pipeline with routing. A tool-calling loop: the model plans, selects tools, and composes an answer with citations.

### Tool contracts

| Tool | Signature | Returns |
|---|---|---|
| `search_glossary` | `(term: str)` | Matching terms with definitions, status, synonyms, `replaced_by`, departmental context. Exact match first, then semantic. Returns **all** conflicting definitions — never picks one. |
| `get_entity` | `(entity_type: str, identifier: str)` | Full governed record: owner, steward, classification, retention, lifecycle dates, source registry, entity URL for citation. |
| `get_registry_health` | `(registry: str)` | Declared rules and thresholds, computed actual values, pass/fail per rule, last refresh timestamp, staleness verdict. |
| `traverse` | `(from_entity: str, relationship_type: str, depth: int = 1)` | Connected entities along typed edges. Materialises ADR-001 paths. Depth capped at 2. |
| `identify_steward` | `(topic: str)` | Which registry would own this information and its declared steward. **Called on the refusal path.** |

### Answer contract

Every response must satisfy all four:

1. Every factual claim carries a citation to a catalogue entity URL
2. If a returned entity's source registry is failing a declared quality rule, the answer says so unprompted
3. If the catalogue does not contain the answer, the agent says so plainly and does not infer
4. On refusal, `identify_steward` is called and the answer names the owning registry, its steward, and drafts the request

### Trajectory logging

Every run logs: question, tools called in order, arguments, results, final answer, citations. This file is the input to the evaluation and is the difference between "I built an agent" and "I can evaluate an agent."

---

## Technologies

| Layer | Choice |
|---|---|
| **Catalogue access** | **`CatalogueClient` interface. `LocalClient` (SQLite over the YAML) is the primary implementation. See ADR-005.** |
| Catalogue (spike only) | OpenMetadata, Docker Compose — 90 minutes, to verify the mapping mismatch first-hand |
| Source data | YAML in repo |
| Lifecycle data | endoflife.date API, response cached in repo |
| Embeddings / vector store | ChromaDB or FAISS, local |
| Agent | Plain Python tool-calling loop. No agent framework — they hide the decisions you need to defend. |
| LLM | Any API model with tool use. Do not write about model choice in the README. |
| **Interface** | **CLI.** Streamlit is cut. |
| Packaging | `make demo`, `make check` |

### The OpenMetadata spike — 90 minutes, timer set

Compose up; create one glossary term, one Table with a custom property, one Data Product; read all three back. The purpose is **not** to decide whether to build on it. That is already decided. The purpose is to be able to write "I stood it up and checked" rather than "I read the docs" when publishing finding two.

If it fights you past the timer, stop mid-task, write ADR-005 and the finding from what you saw, and move on. There is no failure condition here.

---

## OpenMetadata mapping — documented as a finding

| Concept | Representation | Fit |
|---|---|---|
| Datasets, registries | **Table** | Native |
| Glossary terms | **Glossary + GlossaryTerm** | Native |
| Departments | **Team** | Native |
| Capabilities | **Domain / sub-domain** | Reasonable |
| Applications | **Data Product** | Closest native abstraction — and the mismatch is the finding |
| Technology attributes, EOL dates | **Custom properties** | No native home |

**Do not build custom entity types.** That is a different project and not a four-week one.

---

## Evaluation — 12 questions

Written in session 1, before any YAML. They are the acceptance criteria and they determine which relationship edges get built.

| Category | Count |
|---|---|
| EA portfolio & impact (EOL impact, duplication across sites, capability realisation) | 3 |
| Hard cases | 4 |
| Registry governance (*"how complete is our application data?"*) | 2 |
| Ownership & stewardship | 1 |
| Out of scope (must refuse and escalate) | 2 |

**At least one question must be a governance trap** — one where a model answering from its own healthcare knowledge would produce a confident, plausible, wrong answer. A retention period, or *Patient* answered with one definition instead of three. If the agent fails this, publish it. A documented case of the model overriding governed content is worth more than another pass.

**Boundary reminder:** *"which applications duplicate each other across sites"* is a traversal from the capability — in scope. *"How many applications are past EOL overall"* is aggregate routing — out of scope in v1, and a fine question to refuse.

Each question in `EVAL.md` records: the question, the entities it touches, the tools that should be called and in what order, and the expected answer shape.

### Metrics reported

- Retrieval hit rate
- Answer correctness
- Citation validity
- Refusal accuracy
- **Tool-selection accuracy** — did the agent call the right tools in a sensible order?
- **Caveat rate** — when an answer drew on a registry that was failing a rule, did the answer say so?

**Publish the misses with an explanation of each.**

---

## Outputs

1. **Public GitHub repo**, runnable in one command
2. **README** — the two-sided gap thesis, the two findings, **the "what the agent gets from governance" section**, architecture, design decisions, results including failures, and a DMBOK mapping (Metadata Management, Data Governance, Data Quality, Data Architecture, Reference & Master Data)
3. **5 ADRs**
4. **Two video cuts from one recording session** — footage captured during session 13, from a real evaluation run
5. **Four LinkedIn posts, one per week** — three of them findings and positions, only the last one about the project

### README section: what the agent gets from governance

~200 words, non-negotiable. It is the section that makes the project legible to the AI-engineering audience rather than only the governance one.

| Property | Supplied by |
|---|---|
| **Identity** — what to cite | Stable entity identifiers and canonical records |
| **Boundaries** — when to refuse | Declared registry coverage |
| **Freshness** — when to caveat | Declared quality rules and refresh cadence |
| **Accountability** — who to escalate to | Recorded stewardship |
| **Disambiguation** — when not to pick | The glossary |

The line that goes with it: *the agent didn't work the caveat out — the registry declared the rule and the agent read it.*

### Video — three beats per cut

Terminal recording, large font, voice over. No face, no slides, no music. **Never explain the architecture.** Every cut runs: **question → ordinary answer → the caveat that breaks the category.**

| Cut | Contents |
|---|---|
| **EA (90s)** | EOL impact with the staleness caveat · duplication across sites · refusal with escalation |
| **Governance (90s)** | *Patient* returning three definitions · registry health failing its own threshold · one portfolio question as the crossover · refusal with escalation |

Both cuts close on refusal-and-escalation. Go silent for a beat when the caveat prints — that is the product. Real output only; if a miss is instructive, show it.

---

## Architecture decisions to record

- **ADR-001 — Traversal paths, not shortcut edges.** A business object and a business process share no direct edge; the path runs through the application component. Documents must materialise paths, or dependency questions return nothing.
- **ADR-002 — Live reads, not a frozen export.** Retrieval reads from the store at query time. Change a definition, the answer changes. This is what makes it governance rather than a document chatbot. Holds under `LocalClient`.
- **ADR-003 — Read-only boundary.** The system never writes to the catalogue. An AI editing glossary definitions is a different risk conversation.
- **ADR-004 — Entity-level chunking + hybrid retrieval.** *"Who owns X"* is exact-match; semantic search alone handles it badly.
- **ADR-005 — `LocalClient` as primary, OpenMetadata as a documented finding.** A deliberate scope decision taken before the build, not a retreat taken during it. The `CatalogueClient` interface keeps OpenMetadata a two-hour swap if it is ever worth doing.

---

## Repo files, created in session 1

| File | Purpose |
|---|---|
| `SPEC.md` | This document. Frozen. |
| `MOTIVATION.md` | Part One only. Part Two stays local. |
| `MILESTONES.md` | The 17 sessions and their done-tests. |
| `BACKLOG.md` | Every good idea that isn't in the spec. The pressure valve. |
| `WEEKLOG.md` | One entry per session: hours, shipped, blocked. Three lines. |
| `EVAL.md` | The 12 questions. Written session 1 — they are the acceptance criteria. |
| `docs/adr/` | ADR-001 to ADR-005 |

---

## Cut list

Cuts 1 and 2 are already taken. Continue from 3 if you slip.

1. ~~Streamlit UI → CLI~~ **taken**
2. ~~20 questions → 12~~ **taken**
3. 12 questions → 8 (keep all 4 hard cases, 2 EA, 2 out of scope)
4. ADRs 5 → 3
5. Two video cuts → one combined cut
6. Applications and capabilities → registries and glossary only

**Never cut:** the signature behaviour, the four hard cases, citation, refusal with escalation, the registry layer, the consistency check, or the published failures.

---

## Standing rules

1. **New idea → `BACKLOG.md`.** No exceptions, including ideas your mentor suggests mid-build.
2. **No new documents.** After session 1, the next thing you write is code or YAML. Not SPEC v5.
3. **Set an actual timer** on any task involving infrastructure. Noticing the clock is exactly what you cannot do inside a rabbit hole.
4. **Blocked past the timer → stop.** Take the fallback, write one line in the ADR, move on.
5. **Never miss two sessions in a row.** A 45-minute session that keeps the chain alive beats a skipped day.
6. **One named task per session, written in `WEEKLOG.md` before you start.** If you hit the done-test early, stop. Do not roll forward.
7. **Anything that moves the ship date gets escalated before it happens.** The default answer is no.

---

## Constraints

- Nothing traceable to a former employer. Different sector, different systems, different vocabulary.
- Nothing borrowed from licensed reference models. Own names, own descriptions, own structure.
- Version controlled from commit one.
