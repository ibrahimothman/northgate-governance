# Milestones — 17 sessions

**Cadence:** 3 hours per session, 5 sessions per week, 4 weeks. ~51 hours.

**How to use this file.** Before each session, write the session number and its deliverable in `WEEKLOG.md`. After it, write three lines: hours, shipped, blocked. If the done-test passes early, stop — do not roll forward into the next session. If it fails, write why and carry it into the buffer.

**The one rule that matters:** never miss two sessions in a row. A 45-minute session that keeps the chain alive beats a skipped day.

---

## Week 1 — the argument is real and something runs

| # | Deliverable | Done when |
|---|---|---|
| 1 | Repo + 12 evaluation questions | Each question names the entities it touches, the tools that should fire, and the expected answer shape |
| 2 | Walking skeleton | `python agent.py "what's affected if we retire ServerOS 7"` prints a cited answer with the staleness caveat, off hardcoded dicts |
| 3 | OpenMetadata spike (90-min timer) + ADR-002 + ADR-005 | Decision recorded, finding verified first-hand, post 1 drafted |
| 4 | `technologies.yaml` (12) + `registries.yaml` (3) | Real EOL dates cached from endoflife.date, ≥3 past EOL, staleness rule declared |
| 5 | `applications.yaml` (15) + `capabilities.yaml` (6) | 3 triplicated across sites, 1 consolidated, **exactly 2 with empty owner** |

**End-of-week state:** the signature behaviour runs, faked underneath. It looks finished to anyone watching. The shape is proven and the largest technical risk is retired on day two.

**Post 1 — Thursday.** The empty reference EA model: 0 properties, 0 constraints, 0 dates, 1 documentation field. State the number, say what was checked, draw the conclusion in two lines. No mention of the project.

**Watch for:** skipping session 2 because it feels like throwaway work. It is the integration test for everything downstream. Guard it.

---

## Week 2 — it runs on real data and refuses correctly

| # | Deliverable | Done when |
|---|---|---|
| 6 | `glossary.yaml` (15) + `datasets.yaml` (8) | All four hard cases present and findable |
| 7 | `relationships.yaml` + `make check` | The script computes owner completeness and it equals the declared 88%. Every declared metric matches computed reality. |
| 8 | `CatalogueClient` + `LocalClient` over SQLite | `get_entity` and `get_registry_health` run off real data; the skeleton still passes |
| 9 | `traverse` + `search_glossary`, hybrid retrieval | *Patient* returns all three definitions; the EOL traversal returns exactly the right four applications |
| 10 | Refusal + `identify_steward` + escalation | An out-of-scope question refuses, names the registry and steward, and drafts the request |

**End-of-week state:** every core behaviour works end to end on real data. If the build stopped here, the video could still be recorded and the project shipped.

**Post 2 — mid-week.** OpenMetadata has no first-class Application or Capability entity. Frame it as the second half of a two-sided gap: post 1 showed EA has no governance vocabulary, this one shows catalogues have no portfolio vocabulary. The two posts now form an argument.

**Watch for:** sessions 6 is where the project has historically eaten you. Fifteen glossary terms is not a lore-writing exercise. Timer per file; when it goes, whatever exists is final. Ugly and consistent beats rich and half-finished.

Session 7 is the least glamorous work in the build and the signature behaviour is worthless without it. Write the script. Do not eyeball the numbers.

---

## Week 3 — it is evaluated and written up

| # | Deliverable | Done when |
|---|---|---|
| 11 | Trajectory logging + clean CLI | Every run writes question, tools, arguments, results, answer, citations |
| 12 | **Buffer** | Whatever slipped. If nothing slipped, take the day off. |
| 13 | Run the 12 questions, score them, **record the terminal** | Twelve trajectory files exist and are scored. Footage captured from the real run. |
| 14 | Evaluation write-up including misses | Every miss has an explanation |
| 15 | README + DMBOK mapping + ADRs final | A stranger understands the thesis in two minutes. The "what the agent gets from governance" section is in. |

**End-of-week state:** a complete repo. Clone, `make demo`, read the eval table, see the failures. Everything except the video exists.

**Post 3 — early week.** Refusal and escalation, as a position rather than a finding. A governance agent that refuses is table stakes; a refusal that just stops is a dead end. One screenshot of the real refusal output. This is the most quotable post — spend the effort here.

**Watch for:** using the buffer for a feature. It is for slippage only.

---

## Week 4 — shipped and sent

| # | Deliverable | Done when |
|---|---|---|
| 16 | Two 90-second cuts from session 13's footage | Both exported. Voice recorded separately over the terminal capture, not narrated live. |
| 17 | Ship, post, send | The link is public, post 4 is up, and five or six named people have received it directly |

**End-of-week state:** done. Public repo, two videos, four posts, twelve evaluated questions with published failures.

**Post 4 — end of week.** Evaluation results, **leading with a miss**. "Eleven of twelve, and here is the one it got wrong and why" is more credible than a clean number. Repo linked, EA cut embedded. The only post allowed to be about the project.

**Watch for:** the direct sends. Easy to skip, and the substantive conversation comes from them rather than the feed.

---

## Video structure — for session 16

One recording session, cut twice. Terminal, large font, voice over the top. No face, no slides, no music, no architecture explanation.

Every cut runs three beats: **question → ordinary answer → the caveat that breaks the category.**

**EA cut (90s):** title card, two seconds · ServerOS 7 retirement question, four applications cited · the staleness caveat, and go silent while it prints · duplication across sites, fast · refusal with escalation. End on that frame.

**Governance cut (90s):** *Patient* returning three definitions with none canonical · registry health failing its own 95% threshold · one portfolio question as the crossover · the same refusal close.

Before recording, write down the single sentence a viewer should repeat to a colleague. If a cut does not produce it, the cut is wrong regardless of how well the software ran.

---

## Slippage protocol

If a week ends behind, do not extend it. Take the next cut:

3. 12 questions → 8 (keep all 4 hard cases, 2 EA, 2 out of scope)
4. ADRs 5 → 3
5. Two video cuts → one combined cut
6. Applications and capabilities → registries and glossary only

Cuts 1 (Streamlit) and 2 (20 questions) are already taken.

**Never cut:** the signature behaviour, the four hard cases, citation, refusal with escalation, the registry layer, `make check`, or the published failures.
