from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import yaml


URL_RE = re.compile(r"northgate://[A-Za-z0-9._~:/-]+")


@dataclass
class Grade:
    name: str
    dimension: str
    passed: bool
    severity_if_failed: str
    expected: Any = None
    actual: Any = None
    explanation: str = ""


def load_trace(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _q1_spec(spec_path: str | Path) -> dict[str, Any]:
    spec = yaml.safe_load(Path(spec_path).read_text(encoding="utf-8"))
    return next(case for case in spec["cases"] if case["id"] == "Q1")


def _all_returned_entities(trace: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Collect governed entities observed in tool results, deduplicated by entity id.

    Deduplication is important for eval semantics: if an agent redundantly makes
    the same lookup twice, that is a trajectory-efficiency defect, not evidence
    that the catalogue contains duplicate domain entities.
    """
    by_id: dict[str, dict[str, Any]] = {}

    for event in trace.get("tools_called", []):
        result = event.get("result", {})
        candidates = []

        if isinstance(result, dict) and isinstance(result.get("results"), list):
            candidates.extend(result["results"])
        elif isinstance(result, dict) and "id" in result:
            candidates.append(result)

        for item in candidates:
            if isinstance(item, dict) and item.get("id"):
                by_id[item["id"]] = item

    return list(by_id.values())


def grade_q1(trace: dict[str, Any], spec_path: str | Path) -> dict[str, Any]:
    case = _q1_spec(spec_path)
    grades: list[Grade] = []

    # 1) TRAJECTORY
    calls = trace.get("tools_called", [])
    expected_call = case["trajectory"]["expected_calls"][0]

    grades.append(Grade(
        name="expected_tool",
        dimension="trajectory",
        passed=len(calls) >= 1 and calls[0].get("name") == expected_call["tool"],
        severity_if_failed="major",
        expected=expected_call["tool"],
        actual=calls[0].get("name") if calls else None,
        explanation="Q1 should begin with search_glossary."
    ))

    actual_term = calls[0].get("arguments", {}).get("term") if calls else None
    expected_term = expected_call["arguments"]["term"]
    term_ok = isinstance(actual_term, str) and actual_term.casefold() == expected_term.casefold()

    grades.append(Grade(
        name="tool_arguments",
        dimension="trajectory",
        passed=term_ok,
        severity_if_failed="major",
        expected={"term": expected_term, "matching": "case_insensitive_exact"},
        actual={"term": actual_term},
        explanation="Capitalization is ignored because the catalogue tool contract is case-insensitive exact."
    ))

    allowed_extra = case["trajectory"]["allowed_extra_calls"]
    extra_calls = max(0, len(calls) - len(case["trajectory"]["expected_calls"]))

    grades.append(Grade(
        name="extra_tool_calls",
        dimension="trajectory",
        passed=extra_calls <= allowed_extra,
        severity_if_failed="minor",
        expected=allowed_extra,
        actual=extra_calls,
        explanation="Redundant calls are an efficiency defect, not an outcome failure."
    ))

    # 2) OUTCOME / GOVERNED EVIDENCE
    returned = _all_returned_entities(trace)
    returned_ids = {x.get("id") for x in returned}
    required_ids = set(case["outcome"]["required_entities"])

    grades.append(Grade(
        name="required_entities_retrieved",
        dimension="outcome",
        passed=required_ids <= returned_ids,
        severity_if_failed="major",
        expected=sorted(required_ids),
        actual=sorted(x for x in returned_ids if x),
    ))

    patient_rows = [x for x in returned if x.get("id") in required_ids]
    expected_count = case["outcome"]["required_facts"]["patient_definition_count"]

    grades.append(Grade(
        name="definition_count",
        dimension="outcome",
        passed=len(patient_rows) == expected_count,
        severity_if_failed="major",
        expected=expected_count,
        actual=len(patient_rows),
    ))

    expected_contexts = set(case["outcome"]["required_facts"]["contexts"])
    actual_contexts = {x.get("context") for x in patient_rows}

    grades.append(Grade(
        name="contexts",
        dimension="outcome",
        passed=actual_contexts == expected_contexts,
        severity_if_failed="major",
        expected=sorted(expected_contexts),
        actual=sorted(x for x in actual_contexts if x),
    ))

    canonical_flags = [x.get("canonical") for x in patient_rows]
    grades.append(Grade(
        name="catalogue_conflict_state",
        dimension="governance",
        passed=bool(patient_rows) and all(flag is False for flag in canonical_flags),
        severity_if_failed="critical",
        expected="all three canonical=false",
        actual=canonical_flags,
        explanation="The governed records themselves must preserve the unresolved conflict."
    ))

    # 3) FINAL ANSWER — only deterministic checks for now
    answer = trace.get("final_answer", "")
    answer_lower = answer.casefold()

    no_canonical_phrase = (
        any(phrase in answer_lower for phrase in [
            "no enterprise-wide canonical definition",
            "no canonical definition",
            "none is canonical",
            "none are canonical",
        ])
        or bool(re.search(r"\bnone\b.{0,80}\bcanonical\b", answer_lower, re.DOTALL))
    )

    grades.append(Grade(
        name="conflict_stated_in_answer",
        dimension="governance",
        passed=no_canonical_phrase,
        severity_if_failed="critical",
        expected="explicit statement that no canonical Patient definition exists",
        actual=answer[:220],
        explanation=(
            "This deterministic check catches omission of the central governance invariant. "
            "Subtle synthesis/preference behavior will be judged semantically later."
        ),
    ))

    context_mentions = {
        context: context.casefold() in answer_lower for context in expected_contexts
    }
    grades.append(Grade(
        name="all_contexts_present_in_answer",
        dimension="outcome",
        passed=all(context_mentions.values()),
        severity_if_failed="major",
        expected={x: True for x in sorted(expected_contexts)},
        actual=context_mentions,
    ))

    # 4) CITATIONS
    entity_url_by_id = {
        x["id"]: x["entity_url"]
        for x in patient_rows
        if x.get("id") and x.get("entity_url")
    }
    required_urls = {
        entity_url_by_id[entity_id]
        for entity_id in case["citations"]["required_entity_ids"]
        if entity_id in entity_url_by_id
    }
    cited_urls = set(URL_RE.findall(answer))
    retrieved_urls = set(trace.get("citations", {}).get("retrieved_urls", []))
    invalid_urls = cited_urls - retrieved_urls

    grades.append(Grade(
        name="citation_integrity",
        dimension="citations",
        passed=not invalid_urls,
        severity_if_failed="critical",
        expected="all cited northgate:// URLs were retrieved",
        actual=sorted(invalid_urls),
    ))

    grades.append(Grade(
        name="citation_completeness",
        dimension="citations",
        passed=required_urls <= cited_urls,
        severity_if_failed="minor",
        expected=sorted(required_urls),
        actual=sorted(cited_urls),
        explanation="Each governed Patient definition must be cited."
    ))

    # Summary
    failures = [g for g in grades if not g.passed]
    rank = {"minor": 1, "major": 2, "critical": 3}
    highest = None
    if failures:
        highest = max(
            (g.severity_if_failed for g in failures),
            key=lambda s: rank[s]
        )

    dimensions = {}
    for dimension in ["outcome", "trajectory", "governance", "citations"]:
        subset = [g for g in grades if g.dimension == dimension]
        dimensions[dimension] = {
            "passed": all(g.passed for g in subset),
            "checks_passed": sum(1 for g in subset if g.passed),
            "checks_total": len(subset),
        }

    return {
        "case_id": "Q1",
        "question": trace.get("question"),
        "passed": not failures,
        "highest_failure_severity": highest,
        "dimensions": dimensions,
        "checks": [asdict(g) for g in grades],
        "note": (
            "Deterministic grader only. Semantic behaviors such as subtle definition synthesis, "
            "implicit preference, or external-knowledge leakage are intentionally deferred to an LLM judge."
        ),
    }


def _case_spec(spec_path: str | Path, case_id: str) -> dict[str, Any]:
    spec = yaml.safe_load(Path(spec_path).read_text(encoding="utf-8"))
    return next(case for case in spec["cases"] if case["id"] == case_id)


def _summary(grades: list[Grade], case_id: str, question: str, note: str) -> dict[str, Any]:
    failures = [g for g in grades if not g.passed]
    rank = {"minor": 1, "major": 2, "critical": 3}
    highest = None
    if failures:
        highest = max((g.severity_if_failed for g in failures), key=lambda s: rank[s])

    dimensions = {}
    for dimension in ["outcome", "trajectory", "governance", "citations"]:
        subset = [g for g in grades if g.dimension == dimension]
        dimensions[dimension] = {
            "passed": all(g.passed for g in subset),
            "checks_passed": sum(1 for g in subset if g.passed),
            "checks_total": len(subset),
        }

    return {
        "case_id": case_id,
        "question": question,
        "passed": not failures,
        "highest_failure_severity": highest,
        "dimensions": dimensions,
        "checks": [asdict(g) for g in grades],
        "note": note,
    }


def _basic_single_call_trajectory_grades(
    trace: dict[str, Any],
    case: dict[str, Any],
) -> list[Grade]:
    calls = trace.get("tools_called", [])
    expected = case["trajectory"]["expected_calls"][0]
    grades = []

    grades.append(Grade(
        name="expected_tool",
        dimension="trajectory",
        passed=len(calls) >= 1 and calls[0].get("name") == expected["tool"],
        severity_if_failed="major",
        expected=expected["tool"],
        actual=calls[0].get("name") if calls else None,
    ))

    actual_term = calls[0].get("arguments", {}).get("term") if calls else None
    expected_term = expected["arguments"]["term"]
    grades.append(Grade(
        name="tool_arguments",
        dimension="trajectory",
        passed=isinstance(actual_term, str) and actual_term.casefold() == expected_term.casefold(),
        severity_if_failed="major",
        expected={"term": expected_term, "matching": "case_insensitive_exact"},
        actual={"term": actual_term},
    ))

    allowed_extra = case["trajectory"]["allowed_extra_calls"]
    extra = max(0, len(calls) - len(case["trajectory"]["expected_calls"]))
    grades.append(Grade(
        name="extra_tool_calls",
        dimension="trajectory",
        passed=extra <= allowed_extra,
        severity_if_failed="minor",
        expected=allowed_extra,
        actual=extra,
    ))
    return grades


def _citation_grades(
    trace: dict[str, Any],
    required_urls: set[str],
) -> list[Grade]:
    answer = trace.get("final_answer", "")
    cited_urls = set(URL_RE.findall(answer))
    retrieved_urls = set(trace.get("citations", {}).get("retrieved_urls", []))
    invalid_urls = cited_urls - retrieved_urls

    return [
        Grade(
            name="citation_integrity",
            dimension="citations",
            passed=not invalid_urls,
            severity_if_failed="critical",
            expected="all cited northgate:// URLs were retrieved",
            actual=sorted(invalid_urls),
        ),
        Grade(
            name="citation_completeness",
            dimension="citations",
            passed=required_urls <= cited_urls,
            severity_if_failed="minor",
            expected=sorted(required_urls),
            actual=sorted(cited_urls),
        ),
    ]


def _required_citation_urls(
    trace: dict[str, Any],
    case: dict[str, Any],
) -> set[str]:
    entity_urls: dict[str, str] = {}

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            entity_id = value.get("id") or value.get("identifier")
            entity_url = value.get("entity_url")
            if isinstance(entity_id, str) and isinstance(entity_url, str):
                entity_urls[entity_id] = entity_url
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    for event in trace.get("tools_called", []):
        collect(event.get("result", {}))

    return {
        entity_urls[entity_id]
        for entity_id in case["citations"].get("required_entity_ids", [])
        if entity_id in entity_urls
    }


def grade_q2(trace: dict[str, Any], spec_path: str | Path) -> dict[str, Any]:
    case = _case_spec(spec_path, "Q2")
    grades = _basic_single_call_trajectory_grades(trace, case)

    returned = _all_returned_entities(trace)
    row = next((x for x in returned if x.get("id") == "legacy-mrn"), None)

    grades.append(Grade(
        name="legacy_mrn_retrieved",
        dimension="outcome",
        passed=row is not None,
        severity_if_failed="major",
        expected="legacy-mrn",
        actual=row.get("id") if row else None,
    ))

    grades.append(Grade(
        name="owner_is_null",
        dimension="governance",
        passed=row is not None and row.get("owner") is None,
        severity_if_failed="critical",
        expected=None,
        actual=row.get("owner") if row else None,
        explanation="A null owner is the governed ownership gap."
    ))

    grades.append(Grade(
        name="steward_matches",
        dimension="outcome",
        passed=row is not None and row.get("steward") == "Health Information Management",
        severity_if_failed="major",
        expected="Health Information Management",
        actual=row.get("steward") if row else None,
    ))

    answer = trace.get("final_answer", "").casefold()
    # Markdown emphasis is presentation, not meaning. Remove common inline
    # delimiters before checking whether the ownership gap was stated.
    ownership_answer = re.sub(r"[*_~`]+", "", answer)
    gap_stated = any(
        phrase in ownership_answer for phrase in [
            "owner is currently unassigned",
            "owner is unassigned",
            "no assigned owner",
            "owner is not assigned",
            "ownership has not been assigned",
        ]
    )
    grades.append(Grade(
        name="ownership_gap_stated",
        dimension="governance",
        passed=gap_stated,
        severity_if_failed="major",
        expected="explicitly state that the owner is unassigned",
        actual=trace.get("final_answer", "")[:220],
    ))

    steward_mentioned = "health information management" in answer
    grades.append(Grade(
        name="steward_mentioned",
        dimension="outcome",
        passed=steward_mentioned,
        severity_if_failed="major",
        expected="Health Information Management",
        actual=trace.get("final_answer", "")[:220],
    ))

    required_urls = {"northgate://glossary/legacy-mrn"} if row else set()
    grades.extend(_citation_grades(trace, required_urls))

    return _summary(
        grades, "Q2", trace.get("question"),
        "Deterministic grader for ownership-gap handling. Semantic owner inference is judged later."
    )


def grade_q3(trace: dict[str, Any], spec_path: str | Path) -> dict[str, Any]:
    case = _case_spec(spec_path, "Q3")
    grades = _basic_single_call_trajectory_grades(trace, case)

    returned = _all_returned_entities(trace)
    row = next((x for x in returned if x.get("id") == "inpatient-day-case"), None)

    grades.append(Grade(
        name="deprecated_term_retrieved",
        dimension="outcome",
        passed=row is not None,
        severity_if_failed="major",
        expected="inpatient-day-case",
        actual=row.get("id") if row else None,
    ))

    grades.append(Grade(
        name="deprecated_status",
        dimension="governance",
        passed=row is not None and row.get("status") == "deprecated",
        severity_if_failed="critical",
        expected="deprecated",
        actual=row.get("status") if row else None,
    ))

    replacement = row.get("replacement") if row else None
    grades.append(Grade(
        name="correct_replacement",
        dimension="governance",
        passed=(
            isinstance(replacement, dict)
            and replacement.get("identifier") == "day-procedure"
            and replacement.get("name") == "Day Procedure"
            and replacement.get("status") == "active"
        ),
        severity_if_failed="critical",
        expected={"identifier": "day-procedure", "name": "Day Procedure", "status": "active"},
        actual=replacement,
    ))

    answer = trace.get("final_answer", "").casefold()
    grades.append(Grade(
        name="deprecation_stated",
        dimension="governance",
        passed="deprecated" in answer,
        severity_if_failed="critical",
        expected="answer explicitly states deprecated",
        actual=trace.get("final_answer", "")[:220],
    ))
    grades.append(Grade(
        name="replacement_stated",
        dimension="outcome",
        passed="day procedure" in answer,
        severity_if_failed="major",
        expected="Day Procedure",
        actual=trace.get("final_answer", "")[:220],
    ))

    required_urls = _required_citation_urls(trace, case)
    grades.extend(_citation_grades(trace, required_urls))

    return _summary(
        grades, "Q3", trace.get("question"),
        "Deterministic grader for deprecation and replacement handling."
    )


def grade_q4(trace: dict[str, Any], spec_path: str | Path) -> dict[str, Any]:
    case = _case_spec(spec_path, "Q4")
    grades = _basic_single_call_trajectory_grades(trace, case)

    returned = _all_returned_entities(trace)
    row = next((x for x in returned if x.get("id") == "encounter"), None)

    grades.append(Grade(
        name="alias_term_retrieved",
        dimension="outcome",
        passed=row is not None,
        severity_if_failed="major",
        expected="encounter",
        actual=row.get("id") if row else None,
    ))

    grades.append(Grade(
        name="alias_status",
        dimension="governance",
        passed=row is not None and row.get("status") == "alias",
        severity_if_failed="critical",
        expected="alias",
        actual=row.get("status") if row else None,
    ))

    canonical = row.get("canonical_term") if row else None
    grades.append(Grade(
        name="correct_canonical_target",
        dimension="governance",
        passed=(
            isinstance(canonical, dict)
            and canonical.get("identifier") == "episode-of-care"
            and canonical.get("name") == "Episode of Care"
            and canonical.get("status") == "active"
        ),
        severity_if_failed="critical",
        expected={"identifier": "episode-of-care", "name": "Episode of Care", "status": "active"},
        actual=canonical,
    ))

    answer = trace.get("final_answer", "").casefold()
    grades.append(Grade(
        name="alias_stated",
        dimension="governance",
        passed="alias" in answer,
        severity_if_failed="critical",
        expected="answer explicitly states Encounter is an alias",
        actual=trace.get("final_answer", "")[:220],
    ))
    grades.append(Grade(
        name="canonical_term_stated",
        dimension="outcome",
        passed="episode of care" in answer,
        severity_if_failed="major",
        expected="Episode of Care",
        actual=trace.get("final_answer", "")[:220],
    ))

    required_urls = {"northgate://glossary/episode-of-care"}
    grades.extend(_citation_grades(trace, required_urls))

    return _summary(
        grades, "Q4", trace.get("question"),
        "Deterministic grader for alias-to-canonical resolution."
    )

