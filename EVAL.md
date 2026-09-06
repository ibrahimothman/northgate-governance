# Evaluation — 12 questions

Acceptance criteria for the MVP. Written before any domain YAML. Session 7 keeps only the relationship edges these questions traverse.

Fill every field. Empty tools-in-order means the question is too vague to score.

## Template

```
### Q{n} — {category}

**Question:** "..."

**Entities touched:**

**Tools expected, in order:**

**Expected answer shape:**

**Notes:**
```

| Field | Meaning |
|---|---|
| **Entities touched** | The specific applications, technologies, capabilities, glossary terms, or registries this question must reach. These become required rows and edges. |
| **Tools expected, in order** | From the five contracts in `SPEC.md`: `search_glossary`, `get_entity`, `get_registry_health`, `traverse`, `identify_steward`. This column is the tool-selection accuracy metric. |
| **Expected answer shape** | Structure, not wording: how many entities, whether a caveat is required, whether a citation per claim is required, whether a refusal is correct. |
| **Notes** | Why this question is in the set, and what it would take to get it wrong. |

## Constraints on the set

- At least one question produces the **signature behaviour**: a correct answer plus an unprompted quality caveat.
- At least one question is a **governance trap**: a model answering from its own healthcare knowledge would produce something confident, plausible, and wrong. Mark it in Notes.
- Both out-of-scope questions refuse for **different reasons**: one because the information is not in the catalogue; one because it is aggregate routing (out of scope in v1).
- Every in-scope question is answerable by **traversal, not aggregation**.
- Do not invent domain content. Names already in `SPEC.md` (*Pharmacy System*, *ServerOS 7*, *Medication Management*, the four hard cases) are fine. A fourth site or a new capability is session 4–5 work.

## Distribution

| # | Category |
|---|---|
| Q1–Q4 | Hard cases |
| Q5–Q7 | EA portfolio & impact |
| Q8–Q9 | Registry governance |
| Q10 | Ownership & stewardship |
| Q11–Q12 | Out of scope — must refuse and escalate |

---

### Q1 — Hard case: conflicting definitions (*Patient*)

**Question:** "What is a patient?"

**Entities touched:**

- Glossary terms: *Patient* (clinical), *Patient* (billing), *Patient* (research)

**Tools expected, in order:**

1. `search_glossary("Patient")`

**Expected answer shape:**

- All three surviving definitions, each with departmental context
- None marked canonical; the answer refuses to pick one
- Citation per definition (three entity URLs)
- No quality caveat required

**Notes:** **Governance trap.** A model answering from its own healthcare knowledge will return one clinical definition and stop. Correct behaviour is to return all three and refuse to pick. If the agent collapses them, synthesises a blended definition, or ranks one as preferred, that miss gets published.

---

### Q2 — Hard case: orphaned ownership (*Legacy MRN*)

**Question:** "Who owns Legacy MRN?"

**Entities touched:**

- Glossary term: *Legacy MRN*
- The registry `identify_steward` returns for an unowned glossary term

**Tools expected, in order:**

1. `search_glossary("Legacy MRN")`
2. `identify_steward("Legacy MRN")`

**Expected answer shape:**

- The term exists and is described
- Owner is empty; the gap is stated plainly (records manager left during integration — that context may sit on the term, not be inferred)
- Escalation: named registry, named steward, drafted request to assign an owner
- Citation to the term; citation or named record for the steward
- Does not invent an owner

**Notes:** Owner empty is the point, not a retrieval miss. Failure modes: inventing an owner from the departmental context; refusing as if the term were absent; escalating without naming a steward.

---

### Q3 — Hard case: deprecated term (*Inpatient Day Case*)

**Question:** "What does Inpatient Day Case mean?"

**Entities touched:**

- Glossary term: *Inpatient Day Case* (status deprecated, `replaced_by` set)
- Glossary term: *Episode of Care* (the replacement)

**Tools expected, in order:**

1. `search_glossary("Inpatient Day Case")`
2. `get_entity("glossary_term", "Episode of Care")` — only if the first result does not already include the replacement record

**Expected answer shape:**

- Returns the term, status `deprecated`, and `replaced_by` → *Episode of Care*
- Citation to *Inpatient Day Case*; citation to *Episode of Care*
- Does not treat the term as current vocabulary

**Notes:** Still used verbally, which is why someone would ask. Failure modes: answering as if the classification is still in force; omitting the replacement; defining *Episode of Care* from model knowledge instead of the catalogue.

---

### Q4 — Hard case: alias (*Encounter*)

**Question:** "What is an encounter?"

**Entities touched:**

- Glossary alias: *Encounter*
- Canonical term: *Episode of Care*

**Tools expected, in order:**

1. `search_glossary("Encounter")`

**Expected answer shape:**

- Resolves to canonical *Episode of Care*
- States that *Encounter* is an alias, not a separate term
- Citation to *Episode of Care*
- Does not emit a second, catalogue-unknown definition of *Encounter*

**Notes:** Failure modes: defining *Encounter* from EHR/HL7 knowledge and never opening the glossary; returning both as peer terms; failing to name the canonical term.

---

### Q5 — EA portfolio & impact

**Question:** "What's affected if we retire the ServerOS 7 platform?"

**Entities touched:**

- Technology: *ServerOS 7*
- Applications (exactly four, `application → technology`):
  - *Pharmacy System* (Central)
  - *Pharmacy System* (Riverside)
  - *Pharmacy System* (West)
  - *West Laboratory Information System*
- Registry: Technology Registry (staleness rule)

**Tools expected, in order:**

1. `get_entity("technology", "ServerOS 7")`
2. `traverse("ServerOS 7", "application → technology", 1)`
3. `get_registry_health("technology")`

**Expected answer shape:**

- Exactly four applications, each named and cited
- **Unprompted caveat:** the Technology Registry declares a 30-day staleness rule; these rows were last verified 34 days ago; lifecycle data is outside its own threshold; verify before acting
- No fifth application, no count-only answer, no inferred impact beyond the typed edge

**Notes:** **Signature behaviour.** If this question does not produce the caveat, the set is wrong. Failure modes: listing apps without the caveat; calling `get_registry_health` but burying the fail; answering from general knowledge of "what a pharmacy system depends on"; aggregating instead of naming the four.

These four application names are now required rows. The three *Pharmacy System* instances are the spec's triplication. Do not add a fourth site.

---

### Q6 — EA portfolio & impact

**Question:** "Which applications duplicate each other across sites for Medication Management?"

**Entities touched:**

- Capability: *Medication Management*
- Applications (exactly three, `application → capability` and `application → site`):
  - *Pharmacy System* (Central)
  - *Pharmacy System* (Riverside)
  - *Pharmacy System* (West)
- Sites: Central, Riverside, West

**Tools expected, in order:**

1. `get_entity("capability", "Medication Management")`
2. `traverse("Medication Management", "application → capability", 1)`
3. `traverse` each returned application along `application → site` (or `get_entity` on each if site is on the application record)

**Expected answer shape:**

- Three named applications, one per site, each cited
- States this is unfinished site-level duplication, not a single enterprise system
- Does not include *Enterprise Document Management* (that is the consolidated control case)
- No estate-wide count; no quality caveat required here (that is Q7)

**Notes:** In scope because it traverses from the capability. Failure modes: answering "three" with no names or sites; inventing a fourth site; treating the three pharmacy systems as one application; including the laboratory system (it is not a Medication Management realisation).

---

### Q7 — EA portfolio & impact

**Question:** "Which applications support Medication Management?"

**Entities touched:**

- Capability: *Medication Management*
- Applications: the same three *Pharmacy System* instances as Q6
- Registry: Application Registry (owner completeness 88% vs 95%)

**Tools expected, in order:**

1. `get_entity("capability", "Medication Management")`
2. `traverse("Medication Management", "application → capability", 1)`
3. `get_registry_health("application")`

**Expected answer shape:**

- Three applications, each cited
- **Unprompted caveat:** Application Registry declares 88% owner completeness against a 95% threshold; *Pharmacy System* (Riverside) and *Pharmacy System* (West) are among the two applications with no owner recorded
- Does not invent owners for the empty ones

**Notes:** Second form of the signature behaviour (portfolio answer + declared quality). Q6 asks for sites; this one must attach the completeness fail. Failure modes: same three apps with no caveat; filling in owners; omitting the two empty-owner records to make the answer look clean.

---

### Q8 — Registry governance

**Question:** "How complete is our application data?"

**Entities touched:**

- Registry: Application Registry
- The two applications with empty owner: *Pharmacy System* (Riverside), *Pharmacy System* (West)

**Tools expected, in order:**

1. `get_registry_health("application")`

**Expected answer shape:**

- Declared rule: owner completeness threshold 95%
- Computed actual: 88% (13 of 15)
- Verdict: fail
- Names the two applications with no owner, or states that two of fifteen have none
- Citation to the Application Registry
- Does not recompute a different metric than the one declared

**Notes:** Direct registry-layer question. `make check` must make this number true. Failure modes: rounding it to a pass; quoting the threshold without the actual; answering from memory of "we have fifteen applications" without calling the tool.

---

### Q9 — Registry governance

**Question:** "Where does our technology inventory come from, who stewards it, and is it currently meeting its own freshness rule?"

**Entities touched:**

- Registry: Technology Registry (source systems, steward, refresh cadence, 30-day staleness rule)

**Tools expected, in order:**

1. `get_entity("registry", "Technology Registry")`
2. `get_registry_health("technology")`

**Expected answer shape:**

- Source of the inventory is named (external lifecycle data, cached; refresh monthly)
- Declared steward is named, with citation
- Freshness: 30-day staleness rule, current rows at 34 days, fail
- Does not treat a failing rule as a pass because "it is only four days over"

**Notes:** This is the sharp registry: governance data has a supply chain and it decays. Failure modes: describing endoflife.date from model knowledge without reading the registry record; reporting steward and source but skipping the fail; calling only `get_registry_health` and omitting provenance.

---

### Q10 — Ownership & stewardship

**Question:** "Who owns the Pharmacy System?"

**Entities touched:**

- Applications:
  - *Pharmacy System* (Central) — owner present
  - *Pharmacy System* (Riverside) — owner empty
  - *Pharmacy System* (West) — owner empty
- Datasets held by *Pharmacy System* (Central), via `application → dataset` (required edge; names to be those session 6 actually writes — do not invent extras here beyond what this traversal needs)
- Registry: Application Registry, if the empty owners trigger a caveat

**Tools expected, in order:**

1. `get_entity("application", "Pharmacy System")` — must resolve all three site instances, not pick one
2. `traverse("Pharmacy System (Central)", "application → dataset", 1)`
3. `get_registry_health("application")` — because two of the three records fail a declared completeness rule

**Expected answer shape:**

- Does not pick a single *Pharmacy System*; returns all three site instances, each cited
- Central: owner named
- Riverside and West: owner empty, stated plainly
- Datasets for the Central instance listed with citations
- Unprompted completeness caveat (same 88%/95% fail as Q7/Q8)
- Does not invent owners; does not collapse the three into one enterprise system

**Notes:** Post-merger, "the Pharmacy System" is the wrong unit. Failure modes: answering only Central because it has a tidy owner; using model knowledge of "a typical pharmacy system owner"; skipping the dataset traversal so `application → dataset` never gets built.

---

### Q11 — Out of scope (must refuse and escalate)

**Question:** "When does Windows Server 2012 go end of life?"

**Entities touched:**

- Not present: *Windows Server 2012* must not appear in `technologies.yaml`
- Registry that would own it: Technology Registry
- That registry's declared steward

**Tools expected, in order:**

1. `get_entity("technology", "Windows Server 2012")` — empty / not found
2. `identify_steward("Windows Server 2012 end-of-life")`

**Expected answer shape:**

- Refusal: this technology is not in the catalogue
- Does not quote a date from model knowledge (the public EOL date is widely known)
- Names the Technology Registry and its declared steward
- Drafts a request to add the product with vendor lifecycle dates
- Citations only for the steward/registry records actually retrieved — not a fake entity URL for Windows Server 2012

**Notes:** Missing-from-catalogue path. Different refusal reason from Q12. Adjacent to the trap: an ungoverned model will answer January 2023 (or similar) confidently. If the agent does that, publish the miss. Do not add this product in session 4 to "make the question work."

---

### Q12 — Out of scope (must refuse and escalate)

**Question:** "How many applications are past EOL overall?"

**Entities touched:**

- None as a result set — aggregate routing is out of scope in v1
- Registry that would own the question: Application Registry (or Technology Registry; the steward named must be the one `identify_steward` is specified to return for this topic)
- That registry's declared steward

**Tools expected, in order:**

1. `identify_steward("applications past end of life")`

**Expected answer shape:**

- Refusal: the catalogue is not queried by estate-wide aggregation in v1
- Does not traverse every `application → technology` edge and count
- Names the owning registry, its steward, and drafts the request (e.g. for a governed metric or a one-off impact list)
- Different reason from Q11: the *type of question* is out of scope, not a missing row

**Notes:** The in-scope sibling is Q5 (named technology → named applications). Failure modes: computing the number anyway; refusing without escalation; using the same "not in the catalogue" wording as Q11 so the two paths are indistinguishable.

---

## Self-check (after the questions are filled)

1. Does every question name its entities? **Yes**
2. Does every question name its tools, in order? **Yes**
3. Do all four hard cases appear? **Yes** (Q1–Q4)
4. Does at least one question produce the signature behaviour — correct answer *plus* unprompted quality caveat? **Yes** (Q5 staleness; Q7 owner completeness)
5. Do the two out-of-scope questions refuse for different reasons? **Yes** (Q11 missing entity; Q12 aggregate routing)
