#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml


EXPECTED_COUNTS = {
    "applications": 15,
    "capabilities": 6,
    "technologies": 12,
    "datasets": 8,
    "glossary": 15,
    "registries": 3,
}
RELATIONSHIP_MIN = 35
RELATIONSHIP_MAX = 40

ALLOWED_SITES = {"NGC", "RIV", "STH", "GROUP"}
ALLOWED_RELATIONSHIP_TYPES = {
    "application → capability",
    "application → technology",
    "application → dataset",
}

EXPECTED_EVALUATION_TRAVERSALS = {
    ("application → technology", "postgresql-11"): {
        "helixcare-record-sth",
        "rxbridge-riv",
        "riverlab-imaging-riv",
    },
    ("application → dataset", "inpatient-clinical-record"): {
        "northgate-document-hub",
    },
    ("application → capability", "medication-management"): {
        "medcore-pharmacy-ngc",
        "rxbridge-riv",
        "pharmatrack-sth",
    },
}


class CheckResult:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.passes: list[str] = []

    def check(self, condition: bool, message: str) -> None:
        if condition:
            self.passes.append(message)
        else:
            self.failures.append(message)

    def fail(self, message: str) -> None:
        self.failures.append(message)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: top level must be a mapping")
    return data


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def compare(actual: float, operator: str, threshold: float) -> bool:
    if operator == "greater_than_or_equal":
        return actual >= threshold
    if operator == "less_than_or_equal":
        return actual <= threshold
    if operator == "equal":
        return actual == threshold
    raise ValueError(f"Unsupported operator: {operator}")


def index_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Northgate governed domain YAML.")
    parser.add_argument(
        "--domain",
        default="domain",
        help="Path to domain directory (default: domain)",
    )
    parser.add_argument(
        "--as-of",
        default=None,
        help="Evaluation date YYYY-MM-DD. Defaults to today.",
    )
    args = parser.parse_args()

    domain = Path(args.domain)
    as_of = parse_iso_date(args.as_of) if args.as_of else date.today()
    result = CheckResult()

    required_files = {
        "applications": "applications.yaml",
        "capabilities": "capabilities.yaml",
        "technologies": "technologies.yaml",
        "datasets": "datasets.yaml",
        "glossary": "glossary.yaml",
        "registries": "registries.yaml",
        "relationships": "relationships.yaml",
    }

    for key, filename in required_files.items():
        result.check((domain / filename).exists(), f"{filename} exists")

    if result.failures:
        print_results(result)
        return 1

    docs = {key: load_yaml(domain / filename) for key, filename in required_files.items()}

    apps = docs["applications"]["applications"]
    caps = docs["capabilities"]["capabilities"]
    techs = docs["technologies"]["technologies"]
    data = docs["datasets"]["datasets"]
    terms = docs["glossary"]["glossary"]
    regs = docs["registries"]["registries"]
    rels = docs["relationships"]["relationships"]

    groups = {
        "applications": apps,
        "capabilities": caps,
        "technologies": techs,
        "datasets": data,
        "glossary": terms,
        "registries": regs,
    }

    # ------------------------------------------------------------------
    # 1. Counts
    # ------------------------------------------------------------------
    for group, expected in EXPECTED_COUNTS.items():
        actual = len(groups[group])
        result.check(
            actual == expected,
            f"{group} count = {actual} (expected {expected})",
        )

    result.check(
        RELATIONSHIP_MIN <= len(rels) <= RELATIONSHIP_MAX,
        f"relationships count = {len(rels)} (expected {RELATIONSHIP_MIN}–{RELATIONSHIP_MAX})",
    )

    # ------------------------------------------------------------------
    # 2. Entity identity / citation integrity
    # ------------------------------------------------------------------
    all_entities = [row for rows in groups.values() for row in rows]
    ids = [row.get("id") for row in all_entities]
    urls = [row.get("entity_url") for row in all_entities]

    result.check(None not in ids, "every entity has an id")
    result.check(None not in urls, "every entity has an entity_url")
    result.check(len(ids) == len(set(ids)), "entity ids are globally unique")
    result.check(len(urls) == len(set(urls)), "entity URLs are globally unique")

    entity_ids = set(ids)

    # ------------------------------------------------------------------
    # 3. Relationship integrity
    # ------------------------------------------------------------------
    rel_ids = [r.get("id") for r in rels]
    result.check(None not in rel_ids, "every relationship has an id")
    result.check(len(rel_ids) == len(set(rel_ids)), "relationship ids are unique")

    duplicate_edge_keys = [
        (
            r.get("from_entity"),
            r.get("to_entity"),
            r.get("relationship_type"),
            r.get("predicate"),
        )
        for r in rels
    ]
    result.check(
        len(duplicate_edge_keys) == len(set(duplicate_edge_keys)),
        "no duplicate identical relationship edges",
    )

    for r in rels:
        result.check(
            r.get("from_entity") in entity_ids,
            f"{r['id']}: from_entity resolves",
        )
        result.check(
            r.get("to_entity") in entity_ids,
            f"{r['id']}: to_entity resolves",
        )
        result.check(
            r.get("relationship_type") in ALLOWED_RELATIONSHIP_TYPES,
            f"{r['id']}: relationship_type is allowed",
        )

    # ------------------------------------------------------------------
    # 4. Application registry invariants
    # ------------------------------------------------------------------
    app_by_id = index_by_id(apps)
    ownerless = [a for a in apps if not a.get("owner")]
    owner_completeness = (len(apps) - len(ownerless)) / len(apps)

    result.check(
        {a["id"] for a in ownerless} == {"rxbridge-riv", "pharmatrack-sth"},
        "exactly RxBridge and PharmaTrack have empty owners",
    )
    result.check(
        abs(owner_completeness - (13 / 15)) < 1e-9,
        f"application owner completeness = {owner_completeness:.4f} (86.7%)",
    )
    result.check(
        all(a.get("site") in ALLOWED_SITES for a in apps),
        "all application sites are from NGC/RIV/STH/GROUP",
    )
    result.check(
        sum(a.get("business_name") == "Pharmacy System" for a in apps) == 3,
        'exactly three applications have business_name "Pharmacy System"',
    )

    # Every non-integration application has capability coverage.
    cap_sources = {
        r["from_entity"]
        for r in rels
        if r["relationship_type"] == "application → capability"
    }
    expected_business_apps = {
        a["id"] for a in apps if a.get("application_type") != "integration"
    }
    result.check(
        expected_business_apps <= cap_sources,
        "every non-integration application realises at least one capability",
    )

    # ------------------------------------------------------------------
    # 5. Capability hierarchy + coverage
    # ------------------------------------------------------------------
    cap_by_id = index_by_id(caps)
    roots = [c for c in caps if c.get("level") == 1]
    result.check(len(roots) == 1, "exactly one Level 1 capability exists")

    hierarchy_violations = 0
    for c in caps:
        if c.get("level") == 1:
            if c.get("parent_id") is not None:
                hierarchy_violations += 1
        elif c.get("level") == 2:
            parent_id = c.get("parent_id")
            parent = cap_by_id.get(parent_id)
            if parent is None or parent.get("level") != 1 or parent_id == c["id"]:
                hierarchy_violations += 1
        else:
            hierarchy_violations += 1

    result.check(
        hierarchy_violations == 0,
        "capability hierarchy has zero violations",
    )

    l2_ids = {c["id"] for c in caps if c.get("level") == 2}
    realised_cap_ids = {
        r["to_entity"]
        for r in rels
        if r["relationship_type"] == "application → capability"
    }
    result.check(
        l2_ids <= realised_cap_ids,
        "every Level 2 capability is realised by at least one application",
    )

    # ------------------------------------------------------------------
    # 6. Technology lifecycle + linkage + freshness
    # ------------------------------------------------------------------
    tech_by_id = index_by_id(techs)
    linked_tech_ids = {
        r["to_entity"]
        for r in rels
        if r["relationship_type"] == "application → technology"
    }
    result.check(
        set(tech_by_id) == linked_tech_ids,
        "every technology is linked to at least one application",
    )

    eol_techs = [t for t in techs if t.get("lifecycle_status") == "end_of_life"]
    result.check(
        len(eol_techs) >= 3,
        f"{len(eol_techs)} technologies are end_of_life (minimum 3)",
    )
    result.check(
        all(t.get("lifecycle_status") for t in techs),
        "technology lifecycle_status completeness = 100%",
    )

    ages = []
    for t in techs:
        verified = parse_iso_date(t["last_verified"])
        ages.append((as_of - verified).days)
    max_age = max(ages)
    result.check(
        max_age > 30,
        f"technology freshness intentionally fails: maximum age {max_age} days > 30",
    )

    # Windows Server 2012 must remain absent for Q11.
    names = {t["name"] for t in techs}
    result.check(
        "Windows Server 2012" not in names,
        "Windows Server 2012 is absent for the Q11 not-found path",
    )

    # ------------------------------------------------------------------
    # 7. Dataset invariants
    # ------------------------------------------------------------------
    dataset_by_id = index_by_id(data)
    class_counts = Counter(d["classification"] for d in data)
    result.check(
        class_counts == Counter(
            {
                "RESTRICTED": 4,
                "CONFIDENTIAL": 2,
                "INTERNAL": 1,
                "PUBLIC": 1,
            }
        ),
        "dataset classification distribution is 4/2/1/1",
    )
    result.check(
        all(d.get("steward") for d in data),
        "every dataset has a steward",
    )

    inpatient = dataset_by_id["inpatient-clinical-record"]
    result.check(
        inpatient.get("classification") == "RESTRICTED",
        "Inpatient Clinical Record classification = RESTRICTED",
    )
    result.check(
        inpatient.get("retention") == "30 years from date of last attendance",
        "Inpatient Clinical Record retention matches Q6 exactly",
    )

    # ------------------------------------------------------------------
    # 8. Glossary hard cases
    # ------------------------------------------------------------------
    term_by_id = index_by_id(terms)
    patients = [t for t in terms if t.get("term") == "Patient"]
    result.check(
        len(patients) == 3,
        'exactly three glossary records have term "Patient"',
    )
    result.check(
        all(t.get("canonical") is False for t in patients),
        "no Patient definition is canonical",
    )

    legacy = term_by_id["legacy-mrn"]
    result.check(
        legacy.get("owner") is None and bool(legacy.get("steward")),
        "Legacy MRN has empty owner but populated steward",
    )

    day_case = term_by_id["inpatient-day-case"]
    result.check(
        day_case.get("status") == "deprecated"
        and day_case.get("replaced_by") == "day-procedure",
        "Inpatient Day Case is deprecated and replaced by Day Procedure",
    )

    encounter = term_by_id["encounter"]
    result.check(
        encounter.get("status") == "alias"
        and encounter.get("alias_of") == "episode-of-care",
        "Encounter is an alias of Episode of Care",
    )

    # ------------------------------------------------------------------
    # 9. Evaluation-critical traversals
    # ------------------------------------------------------------------
    for (rel_type, target_id), expected_sources in EXPECTED_EVALUATION_TRAVERSALS.items():
        actual_sources = {
            r["from_entity"]
            for r in rels
            if r["relationship_type"] == rel_type and r["to_entity"] == target_id
        }
        result.check(
            actual_sources == expected_sources,
            f"evaluation traversal {target_id} returns exactly {sorted(expected_sources)}",
        )

    # ------------------------------------------------------------------
    # 10. Declared registry quality rules vs actual domain state
    # ------------------------------------------------------------------
    reg_by_id = index_by_id(regs)

    app_owner_rule = next(
        r for r in reg_by_id["application_registry"]["quality_rules"]
        if r["id"] == "application-owner-completeness"
    )
    result.check(
        not compare(owner_completeness, app_owner_rule["operator"], app_owner_rule["threshold"]),
        "Application Registry owner-completeness rule evaluates to FAIL",
    )

    tech_fresh_rule = next(
        r for r in reg_by_id["technology_registry"]["quality_rules"]
        if r["id"] == "technology-verification-freshness"
    )
    result.check(
        not compare(max_age, tech_fresh_rule["operator"], tech_fresh_rule["threshold"]),
        "Technology Registry freshness rule evaluates to FAIL",
    )

    print_results(result)
    return 1 if result.failures else 0


def print_results(result: CheckResult) -> None:
    for message in result.passes:
        print(f"PASS  {message}")
    for message in result.failures:
        print(f"FAIL  {message}")

    print()
    print(f"{len(result.passes)} passed; {len(result.failures)} failed")


if __name__ == "__main__":
    sys.exit(main())
