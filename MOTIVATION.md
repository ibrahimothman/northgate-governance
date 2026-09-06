# Motivation — why this project exists

## The problem I kept running into

I owned an enterprise architecture repository covering 120+ applications. I reconciled its data quarterly against source systems and pushed completeness from roughly 60% to over 80%. Separately, I served as a departmental data steward, coordinating classification, catalogue, and glossary work.

Doing both jobs at once makes something obvious that is invisible from either side alone: **the architecture repository was the least governed data asset in the department.**

It had no owner in the data governance sense. No declared quality rules. No classification. No refresh cadence anyone had written down. It described the organisation's entire application estate, and it was managed the way you manage a spreadsheet.

That is not a local failure. It is structural, and it has two halves.

## The two-sided gap

**EA repositories model applications, capabilities, and technologies — but carry no classification, stewardship, retention, or quality rules.** They describe structure. They do not describe who may keep what, at what sensitivity, for how long.

**Data catalogues model classification, stewardship, and quality — but have no concept of an application portfolio.** They govern datasets. They have no native way to say "this is an application, it realises this capability, it runs on this technology, which is past end of life."

Neither side spans the gap. Both sides think the other one handles it.

### Two findings from direct inspection

Both go in the README, because the argument only carries weight if it is checked rather than asserted.

1. **A reference EA model contained 0 properties, 0 constraints, 0 dates on elements, and 1 documentation field.** The modelling standard itself has almost no vocabulary for governance attributes. This is not a tooling shortfall; it is a scope decision baked into the discipline.

2. **OpenMetadata has no first-class Application or Capability entity.** Applications have to be mapped onto Data Products, capabilities onto Domains, and technology lifecycle attributes onto custom properties. The catalogue side of the gap is equally real, and mapping around it is itself a finding worth documenting.

## Why EA repositories rot

Because nobody governs the architecture data as data.

An application inventory has a source. It has a refresh cadence. It has completeness that can be measured. It decays if nobody refreshes it, and — critically — **it decays silently**, because there is no declared quality rule for it to visibly fail against.

This is why the registry layer is the original contribution here. Cataloguing the *inventories* as governed datasets in their own right, each with a steward, classification, source systems, refresh cadence, and quality rules, is the move almost nobody makes. It turns "our EA repository is out of date" from a vague complaint into a measured, reportable fact.

The technology registry is the sharpest version of this, because its source is genuinely external and genuinely decays. Governance data has a supply chain. Demonstrating that is more sophisticated than a static catalogue.

---

## The claim runs both ways

The argument above is one-directional: governed content exists, nobody reads it, an agent makes it readable. That is true, and it is half the case. The other half is the one that matters more commercially, and it points in the opposite direction.

**Governed metadata is what makes an enterprise agent trustworthy. An agent is what finally makes governance get read.**

Each side supplies what the other lacks. The agent is useless without the substrate; the substrate is unread without the agent. That mutual dependence is why this is one project rather than two portfolio pieces stapled together.

### Direction one — what the agent gets from governance

Every property people want from an enterprise agent is a governance artefact wearing an engineering name. The hard part of enterprise agents is not the model. It is that most organisations have no governed substrate to ground one in.

**Citation requires entity identity.** Every claim links to a catalogue entity URL. That is only possible because each entity has a stable identifier and a canonical record. Without a catalogue you are citing a chunk of a document, which is provenance theatre — the reader cannot tell whether that chunk is authoritative, superseded, or a draft someone pasted into a wiki in 2019.

**Refusal requires a declared boundary.** An agent can only say "that is not in scope" if something defines the scope. The registries do that: three inventories, each with stated coverage. Absent that, the model cannot distinguish "the catalogue does not hold this" from "I retrieved badly," so it fills the gap from its own knowledge of healthcare. That is the failure mode governance cares about most.

**Escalation requires stewardship.** `identify_steward` is not clever engineering. It works because someone recorded a steward against each registry. The agent converts a dead-end query into a governance action purely by reading a field that already existed.

**The caveat requires quality rules.** The signature behaviour is entirely borrowed. The 30-day staleness rule and the 34-day-old rows are data quality artefacts. The agent adds nothing except noticing, and saying so unprompted. The model did not work that out — the registry declared the rule and the agent read it.

**Disambiguation requires a glossary.** *Patient* has three surviving definitions. A model asked about patients will confidently answer using one of them, silently. Only the glossary lets it return all three and refuse to pick. In a merged organisation, that refusal is the correct answer, and no amount of model capability produces it.

Identity, boundaries, freshness, accountability, disambiguation. An agent cannot generate any of them for itself.

### Direction two — what governance gets from the agent

Governance work is done and then not consumed. A glossary gets written, classifications get assigned, an application inventory gets reconciled — and nobody opens any of it.

The reasons are all about the interface, not the content:

**The cost of asking exceeds the cost of guessing.** If checking what "encounter" means takes eight minutes — find the tool, log in, navigate, search, interpret — and guessing takes zero, people guess. Every time.

**You have to know the vocabulary to find the vocabulary.** A glossary is searchable by term. The person who needs it does not know the term; that is why they need it. They know "the thing the billing team calls a visit."

**You have to know which tool holds which half.** Ownership sits in the EA repository, classification in the catalogue, retention in a policy document. A question crossing those boundaries has no home, so it gets asked in Slack and answered from memory.

An agent removes the requirement to know where to look and what it is called. That alone is most of the barrier. But three things follow that dashboards cannot do:

**It answers the question nobody anticipated.** A dashboard has fixed axes, built around the questions that seemed important. A traversal question — *what breaks if we retire this, and which sites does that hit* — either was designed in or is unanswerable. The agent composes the path at query time from typed edges.

**It crosses the boundary the tools do not.** *Which applications hold restricted data and have no owner?* Portfolio in one system, classification in the other, completeness in neither. No dashboard owns that question because no team owns both halves.

**It makes gaps visible instead of silent.** Today, when governed content does not cover something, nothing happens — the person shrugs, asks a colleague, and the gap is never recorded. Refusal plus escalation turns that into a named registry, a named steward, and a drafted request. Every failed query becomes a governance backlog item rather than evaporating.

Governance has never failed on content quality. It fails at the point of consumption. The agent moves governed content to where the question actually gets asked.

The profession's usual answer to this has been to change behaviour — training, comms, "please check the glossary first." That never works, because it asks people to absorb a cost for a benefit that lands elsewhere. The agent does not change behaviour. It meets the behaviour that already exists: people ask questions in natural language, of whoever is nearest, in the middle of doing something else.

---

## Why an agent, and not a chatbot

Retrieval with citations is no longer a demonstration of anything. It is assumed.

What is not assumed, and what governance specifically demands, is **an AI layer that knows the boundaries of what it knows.** Three behaviours follow, and they are the reason this is an agent with tools rather than a fixed pipeline:

**It refuses.** If the answer is not in the governed content, it says so. It does not infer, smooth over, or reach into the model's own knowledge of healthcare. In a governance context, a confident wrong answer about retention or classification is worse than no answer.

**It escalates.** Refusal that just stops is a dead end. The agent identifies which registry would own the missing information, names its declared steward, and drafts the request. That converts a failed query into a governance action — which is what a steward would actually do.

**It reports quality unprompted.** When an answer draws on a registry that is currently failing one of its own declared rules, the answer says so. Four applications are affected by this end-of-life technology — *and* the lifecycle data is 34 days old against a 30-day staleness rule.

That last behaviour is the whole thesis compressed into one response. An EA tool cannot produce it, because it has no quality metadata. A data catalogue cannot produce it, because it has no application portfolio. Only something that governs architecture data as a data asset can.

## Why the failures get published

An evaluation with no misses means the questions were too easy or the results were curated. Publishing the misses, with an explanation of each, is a governance argument as much as an engineering one: declared quality that reality does not honour is the exact failure mode this project is about. The same standard applies to the project itself.

The same logic explains why the registries are designed to fail. Application owner completeness sits at 88% against a 95% threshold because two of the fifteen applications genuinely have no owner. A registry that passes every rule is a fantasy, and gives the agent nothing real to report.

One of the twelve evaluation questions is a deliberate trap — a question where a model answering from its own knowledge would produce something confident, plausible, and wrong. If the agent fails it, that failure gets published too. A documented case of a model overriding governed content is worth more than another pass.

## Why a fictional healthcare group

Two reasons, one practical and one about content.

Practically: nothing in this project can be traceable to a former employer. Different sector, different systems, different vocabulary, own names, own structure, nothing borrowed from licensed reference models.

On content: healthcare gives the richest governance story available. Restricted patient data, confidential clinical notes, internal research extracts, and public statistics in one estate. Genuine multi-decade retention. Real consent and legal-basis requirements. And stewardship that is *contested* — clinical, administrative, and research functions all with a legitimate claim on the same terms.

The merger scenario then produces the hard cases without inventing them. Three hospitals merging is why *Patient* has three surviving definitions with none marked canonical. It is why *Legacy MRN* has no owner: the records manager left during integration. These are not puzzles constructed for a demo; they are what mergers actually leave behind.

Healthcare is set dressing, deliberately. It is not part of the argument. The thesis holds in a bank, a telco, or a logistics company, and it should be stated in a form that travels.
