#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.catalogue_client import LocalClient


def rule(response: dict[str, Any], rule_id: str) -> dict[str, Any]:
    return next(r for r in response["rules"] if r["id"] == rule_id)


def call_tool(client: LocalClient, tool: str, args: dict[str, Any], context: dict[str, Any]):
    if tool == "get_entity":
        return client.get_entity(**args)
    if tool == "search_glossary":
        return client.search_glossary(**args)
    if tool == "traverse":
        return client.traverse(**args)
    if tool == "get_registry_health":
        return client.get_registry_health(**args)
    if tool == "identify_steward":
        return client.identify_steward(**args)
    if tool == "resolve_ambiguous_candidates":
        ambiguous = context["last_result"]
        if ambiguous.get("status") != "ambiguous":
            return {"found": False, "status": "invalid_precondition", "results": []}
        results = []
        for candidate in ambiguous["candidates"]:
            results.append(
                client.get_entity(
                    args["entity_type"],
                    candidate["identifier"],
                )
            )
        return {"found": True, "status": "ok", "results": results}
    raise ValueError(f"Unknown tool: {tool}")


def names_from_traverse(response):
    return sorted(x["entity"]["name"] for x in response["results"])


def evaluate_case(case, outputs):
    qid = case["id"]
    exp = case["expect"]
    checks = []

    def check(name, condition, actual=None):
        checks.append({"name": name, "passed": bool(condition), "actual": actual})

    if qid == "Q1":
        r = outputs[0]
        check("three definitions", len(r["results"]) == 3, len(r["results"]))
        check("contexts", sorted(x["context"] for x in r["results"]) == sorted(exp["contexts"]))
        check("none canonical", all(x["canonical"] is False for x in r["results"]))

    elif qid == "Q2":
        x = outputs[0]["results"][0]
        check("single term", len(outputs[0]["results"]) == 1)
        check("owner empty", x["owner"] is None, x["owner"])
        check("steward", x["steward"] == exp["steward"], x["steward"])

    elif qid == "Q3":
        x = outputs[0]["results"][0]
        check("deprecated", x["status"] == exp["status"], x["status"])
        check("replacement", x["replacement"]["name"] == exp["replacement"], x["replacement"]["name"])

    elif qid == "Q4":
        x = outputs[0]["results"][0]
        check("alias", x["status"] == exp["status"], x["status"])
        check("canonical", x["canonical_term"]["name"] == exp["canonical_term"], x["canonical_term"]["name"])

    elif qid == "Q5":
        tech, traversal, tech_health, app_health = outputs
        check("technology found", tech["status"] == "ok")
        check("affected applications", names_from_traverse(traversal) == sorted(exp["applications"]), names_from_traverse(traversal))
        freshness = rule(tech_health, "technology-verification-freshness")
        owner = rule(app_health, "application-owner-completeness")
        check("tech registry fail", tech_health["overall_status"] == "fail", tech_health["overall_status"])
        check("freshness 34", freshness["actual"] == exp["technology_freshness_days"], freshness["actual"])
        check("app registry fail", app_health["overall_status"] == "fail", app_health["overall_status"])
        check("owner completeness", abs(owner["actual"] - exp["application_owner_completeness"]) < 1e-9, owner["actual"])

    elif qid == "Q6":
        entity = outputs[0]
        check("retention", entity["retention"] == exp["retention"], entity["retention"])
        check("classification", entity["classification"] == exp["classification"], entity["classification"])
        check("steward", entity["steward"] == exp["steward"], entity["steward"])
        check("no source registry", "source_registry" not in entity, entity.get("source_registry"))

    elif qid == "Q7":
        capability, traversal, app_health = outputs
        apps = sorted(x["entity"]["name"] for x in traversal["results"])
        sites = sorted(x["entity"]["site"] for x in traversal["results"])
        owner = rule(app_health, "application-owner-completeness")
        check("capability found", capability["status"] == "ok")
        check("three apps", apps == sorted(exp["applications"]), apps)
        check("sites", sites == sorted(exp["sites"]), sites)
        check("app registry fail", app_health["overall_status"] == "fail")
        check("owner completeness", abs(owner["actual"] - exp["application_owner_completeness"]) < 1e-9, owner["actual"])

    elif qid == "Q8":
        health = outputs[0]
        owner = rule(health, "application-owner-completeness")
        missing = sorted(e["name"] for e in owner["evidence"])
        check("actual", abs(owner["actual"] - exp["owner_completeness"]) < 1e-9, owner["actual"])
        check("threshold", owner["threshold"] == exp["threshold"], owner["threshold"])
        check("fail", owner["status"] == exp["status"], owner["status"])
        check("missing owners", missing == sorted(exp["missing_owners"]), missing)

    elif qid == "Q9":
        entity, health = outputs
        freshness = rule(health, "technology-verification-freshness")
        check("source", exp["source_system"] in entity["source_systems"], entity["source_systems"])
        check("steward", entity["steward"] == exp["steward"], entity["steward"])
        check("cadence", entity["refresh_cadence"] == exp["refresh_cadence"], entity["refresh_cadence"])
        check("freshness", freshness["actual"] == exp["freshness_days"], freshness["actual"])
        check("threshold", freshness["threshold"] == exp["threshold"], freshness["threshold"])
        check("fail", freshness["status"] == exp["status"], freshness["status"])

    elif qid == "Q10":
        ambiguous, resolved, health = outputs
        check("ambiguous", ambiguous["status"] == "ambiguous", ambiguous["status"])
        check("candidate count", len(ambiguous["candidates"]) == exp["candidate_count"], len(ambiguous["candidates"]))
        apps = sorted(x["name"] for x in resolved["results"])
        check("resolved names", apps == sorted(exp["applications"]), apps)
        owners = {x["name"]: x["owner"] for x in resolved["results"]}
        check("owners", owners == exp["owners"], owners)
        check("app registry fail", health["overall_status"] == exp["application_registry_status"], health["overall_status"])

    elif qid == "Q11":
        entity, steward = outputs
        check("not found", entity["status"] == exp["entity_status"], entity["status"])
        check("technology registry", steward["registry"]["name"] == exp["registry"], steward.get("registry"))
        check("steward", steward["registry"]["steward"] == exp["steward"], steward["registry"]["steward"])

    elif qid == "Q12":
        steward = outputs[0]
        check("application registry", steward["registry"]["name"] == exp["registry"], steward["registry"]["name"])
        check("steward", steward["registry"]["steward"] == exp["steward"], steward["registry"]["steward"])

    return checks


def summarize_output(tool, result):
    if tool == "search_glossary":
        return {
            "status": result["status"],
            "match_type": result.get("match_type"),
            "result_ids": [x["id"] for x in result.get("results", [])],
        }
    if tool == "get_entity":
        if result["status"] == "ok":
            return {"status": "ok", "id": result["id"], "name": result.get("name") or result.get("term")}
        return {
            "status": result["status"],
            "candidates": [x["identifier"] for x in result.get("candidates", [])],
        }
    if tool == "traverse":
        return {
            "status": result["status"],
            "results": [x["entity"]["id"] for x in result.get("results", [])],
        }
    if tool == "get_registry_health":
        return {
            "status": result["status"],
            "registry": result.get("registry", {}).get("name"),
            "overall_status": result.get("overall_status"),
            "rules": {
                x["id"]: {"actual": x.get("actual"), "status": x.get("status")}
                for x in result.get("rules", [])
            },
        }
    if tool == "identify_steward":
        return {
            "status": result["status"],
            "registry": result.get("registry", {}).get("name"),
            "steward": result.get("registry", {}).get("steward"),
        }
    if tool == "resolve_ambiguous_candidates":
        return {
            "status": result["status"],
            "results": [x["id"] for x in result.get("results", [])],
        }
    return result


def main():
    config = yaml.safe_load((ROOT / "eval" / "cases.yaml").read_text(encoding="utf-8"))
    client = LocalClient(ROOT / "data" / "catalogue.db")

    run_records = []
    total_checks = 0
    passed_checks = 0
    case_passes = 0

    for case in config["cases"]:
        outputs = []
        calls_log = []
        context = {}

        for call in case["calls"]:
            result = call_tool(client, call["tool"], call["args"], context)
            outputs.append(result)
            calls_log.append({
                "tool": call["tool"],
                "args": call["args"],
                "result": summarize_output(call["tool"], result),
            })
            context["last_result"] = result

        checks = evaluate_case(case, outputs)
        passed = all(c["passed"] for c in checks)
        total_checks += len(checks)
        passed_checks += sum(c["passed"] for c in checks)
        case_passes += int(passed)

        record = {
            "id": case["id"],
            "question": case["question"],
            "passed": passed,
            "calls": calls_log,
            "checks": checks,
        }
        run_records.append(record)

        print(f"{case['id']}: {'PASS' if passed else 'FAIL'} — {case['question']}")
        for check in checks:
            marker = "✓" if check["passed"] else "✗"
            print(f"  {marker} {check['name']}")
        print()

    report = {
        "as_of": config["as_of"],
        "purpose": config["purpose"],
        "cases_passed": case_passes,
        "cases_total": len(config["cases"]),
        "checks_passed": passed_checks,
        "checks_total": total_checks,
        "records": run_records,
    }

    (ROOT / "eval" / "tool_run.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    md = [
        "# Tool-layer evaluation report",
        "",
        f"- As of: `{config['as_of']}`",
        f"- Cases: **{case_passes}/{len(config['cases'])} passed**",
        f"- Assertions: **{passed_checks}/{total_checks} passed**",
        "",
        "> This is a deterministic catalogue/tool acceptance check. It does not measure LLM tool-selection accuracy or answer quality.",
        "",
        "| Case | Result | Tool trace |",
        "|---|---|---|",
    ]
    for r in run_records:
        trace = " → ".join(c["tool"] for c in r["calls"])
        md.append(f"| {r['id']} | {'PASS' if r['passed'] else 'FAIL'} | `{trace}` |")

    (ROOT / "eval" / "TOOL_EVAL_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"SUMMARY: {case_passes}/{len(config['cases'])} cases passed; {passed_checks}/{total_checks} assertions passed")
    return 0 if case_passes == len(config["cases"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
