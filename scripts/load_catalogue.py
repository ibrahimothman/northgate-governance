#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

import yaml

ENTITY_FILES = {
    "application": ("applications.yaml", "applications"),
    "capability": ("capabilities.yaml", "capabilities"),
    "technology": ("technologies.yaml", "technologies"),
    "dataset": ("datasets.yaml", "datasets"),
    "glossary": ("glossary.yaml", "glossary"),
    "registry": ("registries.yaml", "registries"),
}


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level YAML must be a mapping")
    return data


def canonical_name(entity_type: str, row: dict[str, Any]) -> str:
    return row["term"] if entity_type == "glossary" else row["name"]


def insert_entity(conn: sqlite3.Connection, entity_type: str, row: dict[str, Any]) -> None:
    name = canonical_name(entity_type, row)
    business_name = row.get("business_name")
    source_registry_id = row.get("source_registry")

    conn.execute(
        """
        INSERT INTO entities (
            id, entity_type, canonical_name, business_name,
            source_registry_id, entity_url, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["id"], entity_type, name, business_name,
            source_registry_id, row["entity_url"],
            json.dumps(row, ensure_ascii=False, sort_keys=True),
        ),
    )

    names = [(name, "canonical")]
    if business_name and business_name != name:
        names.append((business_name, "business"))
    for synonym in row.get("synonyms", []) or []:
        if synonym and synonym != name:
            names.append((synonym, "synonym"))

    seen = set()
    for value, name_type in names:
        key = (value, name_type)
        if key in seen:
            continue
        seen.add(key)
        conn.execute(
            "INSERT INTO entity_names (entity_id, name, name_type) VALUES (?, ?, ?)",
            (row["id"], value, name_type),
        )


def insert_relationships(conn: sqlite3.Connection, domain: Path) -> int:
    rows = load_yaml(domain / "relationships.yaml")["relationships"]
    for row in rows:
        conn.execute(
            """
            INSERT INTO relationships (
                id, from_entity_id, to_entity_id, relationship_type, predicate
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                row["id"], row["from_entity"], row["to_entity"],
                row["relationship_type"], row["predicate"],
            ),
        )
    return len(rows)


def insert_registry_rules(conn: sqlite3.Connection, registry_rows: list[dict[str, Any]]) -> int:
    count = 0
    structural_keys = {
        "id", "metric", "field", "relationship_type", "operator", "threshold"
    }
    for registry in registry_rows:
        for rule in registry.get("quality_rules", []):
            config = {
                k: v for k, v in rule.items()
                if k not in structural_keys and k != "description"
            }
            conn.execute(
                """
                INSERT INTO registry_rules (
                    id, registry_id, metric, field_name, relationship_type,
                    operator, threshold, config_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule["id"], registry["id"], rule["metric"],
                    rule.get("field"), rule.get("relationship_type"),
                    rule["operator"], float(rule["threshold"]),
                    json.dumps(config, ensure_ascii=False, sort_keys=True),
                ),
            )
            count += 1
    return count


def build_catalogue(domain: Path, schema_path: Path, output: Path) -> None:
    if output.exists():
        output.unlink()
    output.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(output)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(schema_path.read_text(encoding="utf-8"))

        entity_count = 0
        registry_rows = []

        for entity_type, (filename, root_key) in ENTITY_FILES.items():
            rows = load_yaml(domain / filename)[root_key]
            for row in rows:
                insert_entity(conn, entity_type, row)
                entity_count += 1
            if entity_type == "registry":
                registry_rows = rows

        relationship_count = insert_relationships(conn, domain)
        rule_count = insert_registry_rules(conn, registry_rows)
        conn.commit()

        print(f"Catalogue rebuilt: {output}")
        print(f"  entities:       {entity_count}")
        print(f"  relationships:  {relationship_count}")
        print(f"  registry rules: {rule_count}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild Northgate SQLite catalogue from YAML.")
    parser.add_argument("--domain", default="domain")
    parser.add_argument("--schema", default="catalogue/schema.sql")
    parser.add_argument("--output", default="data/catalogue.db")
    args = parser.parse_args()
    build_catalogue(Path(args.domain), Path(args.schema), Path(args.output))


if __name__ == "__main__":
    main()
