from __future__ import annotations

import re
from typing import Any

from src.eval_grader import (
    Grade,
    URL_RE,
    _case_spec,
    _citation_grades,
    _required_citation_urls,
    _summary,
)
from src.utils.normalize import normalize_identifier


def _norm(value: Any) -> str:
    return str(value).casefold().replace("_", " ").strip()


def _match(actual: Any, expected: Any, mode: str) -> bool:
    if mode == "case_insensitive_exact":
        return isinstance(actual, str) and isinstance(expected, str) and actual.casefold() == expected.casefold()
    if mode == "normalized_identifier_equivalent":
        return (
            isinstance(actual, str)
            and isinstance(expected, str)
            and normalize_identifier(actual) == normalize_identifier(expected)
        )
    if mode == "registry_alias_equivalent":
        groups = [
            {"application", "applications", "application registry"},
            {"technology", "technologies", "technology registry"},
            {"capability", "capabilities", "capability registry"},
        ]
        a, e = _norm(actual), _norm(expected)
        return any(a in g and e in g for g in groups)
    return actual == expected


def _result(trace, pos):
    if pos is None:
        return {}
    return trace["tools_called"][pos].get("result", {})


def _entity_references(result: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for key in ("id", "name", "canonical_name", "business_name", "entity_url"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            refs.add(value.casefold().strip())
    return refs


def _resolved_entity_id(event: dict[str, Any]) -> str | None:
    result = event.get("result", {})
    if not isinstance(result, dict) or result.get("status") != "ok":
        return None
    if event.get("name") == "get_entity":
        return result.get("id")
    from_entity = result.get("from_entity", {})
    return from_entity.get("id") if isinstance(from_entity, dict) else None


def _required_calls(trace: dict[str, Any], case: dict[str, Any]):
    calls = trace.get("tools_called", [])
    grades, positions = [], {}
    used = set()

    for req in case["trajectory"].get("required_calls", []):
        pos = None
        for i, ev in enumerate(calls):
            if i in used or ev.get("name") != req["tool"]:
                continue
            args, ok = ev.get("arguments", {}), True
            for key, expected in req.get("arguments", {}).items():
                mode = req.get("argument_matching", {}).get(key, "exact")
                actual = args.get(key)
                if mode == "entity_reference_equivalent":
                    source_call_id = req.get("reference_from", {}).get(key)
                    source_result = _result(trace, positions.get(source_call_id))
                    accepted = _entity_references(source_result)
                    if isinstance(expected, str):
                        accepted.add(expected.casefold().strip())
                    if not isinstance(actual, str) or actual.casefold().strip() not in accepted:
                        ok = False
                        break
                elif not _match(actual, expected, mode):
                    ok = False
                    break
            expected_entity_id = req.get("resolved_entity_id")
            if ok and expected_entity_id is not None:
                ok = _resolved_entity_id(ev) == expected_entity_id
            if ok:
                pos = i
                break

        grades.append(Grade(
            name=f"required_call:{req['id']}", dimension="trajectory", passed=pos is not None,
            severity_if_failed="major", expected={"tool": req["tool"], "arguments": req.get("arguments", {})},
            actual=calls[pos].get("arguments") if pos is not None else None,
        ))
        if pos is not None:
            used.add(pos)
            positions[req["id"]] = pos

    for before, after in case["trajectory"].get("ordering_constraints", []):
        passed = before in positions and after in positions and positions[before] < positions[after]
        grades.append(Grade(
            name=f"ordering:{before}_before_{after}", dimension="trajectory", passed=passed,
            severity_if_failed="major", expected=f"{before} before {after}",
            actual={before: positions.get(before), after: positions.get(after)},
        ))

    for tool in case["trajectory"].get("forbidden_tools", []):
        n = sum(1 for ev in calls if ev.get("name") == tool)
        grades.append(Grade(
            name=f"forbidden_tool:{tool}", dimension="trajectory", passed=n == 0,
            severity_if_failed="major", expected=0, actual=n,
        ))

    extra = max(0, len(calls) - len(case["trajectory"].get("required_calls", [])))
    allowed = case["trajectory"].get("allowed_extra_calls", 0)
    grades.append(Grade(
        name="extra_tool_calls", dimension="trajectory", passed=extra <= allowed,
        severity_if_failed="minor", expected=allowed, actual=extra,
    ))
    return grades, positions


def _rule(health, rule_id):
    return next((r for r in health.get("rules", []) if r.get("id") == rule_id), None)


def _urls(trace, ids):
    mapping = {}
    def walk(v):
        if isinstance(v, dict):
            key = v.get("id") or v.get("identifier")
            if key and v.get("entity_url"):
                mapping[key] = v["entity_url"]
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    for ev in trace.get("tools_called", []):
        walk(ev.get("result", {}))
    return {mapping[i] for i in ids if i in mapping}


def grade_q5(trace, spec_path):
    case = _case_spec(spec_path, "Q5")
    grades, p = _required_calls(trace, case)
    tech = _result(trace, p.get("fetch_technology"))
    walk = _result(trace, p.get("impact_walk"))
    th = _result(trace, p.get("technology_health"))
    ah = _result(trace, p.get("application_health"))
    ids = {x.get("entity", {}).get("id") for x in walk.get("results", [])}
    expected_ids = {"helixcare-record-sth", "riverlab-imaging-riv", "rxbridge-riv"}
    grades += [
        Grade("technology_retrieved", "outcome", tech.get("id") == "postgresql-11", "major", "postgresql-11", tech.get("id")),
        Grade("exact_impact_set", "outcome", ids == expected_ids, "critical", sorted(expected_ids), sorted(x for x in ids if x)),
    ]
    tr, ar = _rule(th, "technology-verification-freshness"), _rule(ah, "application-owner-completeness")
    grades += [
        Grade("technology_freshness_rule", "governance", bool(tr) and tr.get("actual") == 34.0 and tr.get("threshold") == 30.0 and tr.get("status") == "fail", "major" if tr is None else "critical", {"actual":34.0,"threshold":30.0,"status":"fail"}, tr),
        Grade("application_owner_rule", "governance", bool(ar) and abs(ar.get("actual",0)-(13/15))<1e-9 and ar.get("threshold") == 0.95 and ar.get("status") == "fail", "major" if ar is None else "critical", {"actual":13/15,"threshold":0.95,"status":"fail"}, ar),
    ]
    ans = trace.get("final_answer", "").casefold()
    freshness_comparison = (
        "34" in ans and "30" in ans
        and any(x in ans for x in ["technology", "verification", "freshness"])
        and any(x in ans for x in ["limit", "maximum", "threshold", "against", "versus", "above", "exceed", "fail", "stale"])
    )
    owner_comparison = (
        ("86.7" in ans or "13 of 15" in ans or "13/15" in ans)
        and "95" in ans and "owner" in ans
        and any(x in ans for x in ["below", "against", "versus", "threshold", "fail", "less than"])
    )
    grades += [
        Grade("all_affected_applications_named", "outcome", all(x in ans for x in ["helixcare record","riverlab imaging","rxbridge"]), "major"),
        Grade("freshness_caveat_stated", "governance", freshness_comparison, "major"),
        Grade("owner_completeness_caveat_stated", "governance", owner_comparison, "major"),
    ]
    grades += _citation_grades(trace, _urls(trace, case["citations"]["required_entity_ids"]))
    return _summary(grades, "Q5", trace.get("question"), "Typed impact plus mandatory technology/application registry caveats.")


def grade_q6(trace, spec_path):
    case = _case_spec(spec_path, "Q6")
    grades, p = _required_calls(trace, case)
    ds = _result(trace, p.get("fetch_dataset"))
    grades += [
        Grade("dataset_retention", "outcome", ds.get("retention") == "30 years from date of last attendance", "critical", "30 years from date of last attendance", ds.get("retention")),
        Grade("dataset_classification", "outcome", ds.get("classification") == "RESTRICTED", "major", "RESTRICTED", ds.get("classification")),
        Grade("dataset_steward", "outcome", ds.get("steward") == "Health Information Management", "major", "Health Information Management", ds.get("steward")),
    ]
    ans = trace.get("final_answer", "").casefold()
    nums = [int(x) for x in re.findall(r"\b(\d{1,3})\s+years?\b", ans)]
    exact_retention = re.search(
        r"\b30 years from (?:the )?date of last attendance\b",
        ans,
    ) is not None
    grades += [
        Grade("exact_retention_stated", "governance", exact_retention, "critical"),
        Grade("no_alternative_retention_period", "governance", not any(x != 30 for x in nums), "critical", "only 30-year retention", nums),
        Grade("no_dataset_registry_claim", "governance", "dataset registry" not in ans and "data set registry" not in ans, "critical"),
    ]
    grades += _citation_grades(trace, _urls(trace, case["citations"]["required_entity_ids"]))
    return _summary(grades, "Q6", trace.get("question"), "Governance trap: preserve exact catalogue retention and avoid invented registry behavior.")


def grade_q7(trace, spec_path):
    case = _case_spec(spec_path, "Q7")
    grades, p = _required_calls(trace, case)
    cap = _result(trace, p.get("fetch_capability"))
    walk = _result(trace, p.get("capability_walk"))
    capability_health = _result(trace, p.get("capability_health"))
    health = _result(trace, p.get("application_health"))
    rows = [x.get("entity",{}) for x in walk.get("results",[])]
    ids = {x.get("id") for x in rows}
    sites = {x.get("site") for x in rows}
    expected = {"medcore-pharmacy-ngc","rxbridge-riv","pharmatrack-sth"}
    grades += [
        Grade("capability_retrieved","outcome",cap.get("id")=="medication-management","major"),
        Grade("capability_registry_checked","governance", capability_health.get("registry",{}).get("id")=="capability_registry", "major", "capability_registry", capability_health.get("registry",{}).get("id")),
        Grade("exact_duplication_set","outcome",ids==expected,"critical",sorted(expected),sorted(x for x in ids if x)),
        Grade("all_three_sites","outcome",sites=={"NGC","RIV","STH"},"major",["NGC","RIV","STH"],sorted(x for x in sites if x)),
    ]
    ar = _rule(health,"application-owner-completeness")
    grades.append(Grade("application_owner_rule","governance",bool(ar) and abs(ar.get("actual",0)-(13/15))<1e-9 and ar.get("threshold")==0.95 and ar.get("status")=="fail","critical"))
    raw_answer = trace.get("final_answer","")
    ans = raw_answer.casefold()
    prose = URL_RE.sub("", raw_answer).casefold()
    grades += [
        Grade("all_applications_named","outcome",all(x in prose for x in ["medcore pharmacy","rxbridge","pharmatrack"]),"major"),
        Grade("all_sites_named","outcome",all(x in prose for x in ["ngc","riv","sth"]),"major"),
        Grade("owner_completeness_caveat_stated","governance",("86.7" in ans or "13 of 15" in ans or "13/15" in ans) and "95" in ans and "owner" in ans and any(x in ans for x in ["fail","below","against","versus","threshold"]),"major"),
    ]
    grades += _citation_grades(trace, _required_citation_urls(trace, case))
    return _summary(grades,"Q7",trace.get("question"),"Site duplication plus mandatory capability/application registry health propagation.")


def grade_q8(trace, spec_path):
    case=_case_spec(spec_path,"Q8")
    grades,p=_required_calls(trace,case)
    health=_result(trace,p.get("application_health")); ar=_rule(health,"application-owner-completeness")
    evidence={x.get("identifier") for x in (ar or {}).get("evidence",[])}
    grades += [
        Grade("declared_metric_used","governance",bool(ar) and ar.get("metric")=="field_completeness","critical"),
        Grade("owner_completeness_actual","outcome",bool(ar) and abs(ar.get("actual",0)-(13/15))<1e-9,"critical",13/15,ar.get("actual") if ar else None),
        Grade("owner_completeness_threshold","outcome",bool(ar) and ar.get("threshold")==0.95,"major",0.95,ar.get("threshold") if ar else None),
        Grade("rule_fails","governance",bool(ar) and ar.get("status")=="fail","critical","fail",ar.get("status") if ar else None),
        Grade("missing_owner_evidence","outcome",evidence=={"rxbridge-riv","pharmatrack-sth"},"major",["pharmatrack-sth","rxbridge-riv"],sorted(x for x in evidence if x)),
    ]
    ans=trace.get("final_answer","").casefold()
    grades += [
        Grade("metric_stated_in_answer","outcome",("86.7" in ans or "13 of 15" in ans) and "95" in ans and "fail" in ans,"major"),
        Grade("missing_apps_named","outcome","rxbridge" in ans and "pharmatrack" in ans,"major"),
    ]
    grades += _citation_grades(trace,_urls(trace,case["citations"]["required_entity_ids"]))
    return _summary(grades,"Q8",trace.get("question"),"Direct grading of the declared application owner-completeness rule.")
