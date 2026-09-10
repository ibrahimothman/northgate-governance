from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from datetime import date, datetime
from typing import Any, Iterator

from src.utils.normalize import normalize_identifier


class CatalogueClient(ABC):
    @abstractmethod
    def get_entity(self, entity_type: str, identifier: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def traverse(
        self,
        from_entity: str,
        relationship_type: str,
        depth: int = 1,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def search_glossary(self, term: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_registry_health(
        self,
        registry: str,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def identify_steward(self, topic: str) -> dict[str, Any]:
        raise NotImplementedError


class LocalClient(CatalogueClient):
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _resolved_entity(
        row: sqlite3.Row,
        *,
        match_type: str,
        normalized_query: str | None = None,
    ) -> dict[str, Any]:
        payload = json.loads(row["payload_json"])
        result = {
            "found": True,
            "status": "ok",
            "entity_type": row["entity_type"],
            **payload,
            "match_type": match_type,
        }
        if normalized_query is not None:
            result["normalized_query"] = normalized_query
        return result

    @staticmethod
    def _ambiguous_entities(
        rows: list[sqlite3.Row],
        *,
        include_entity_type: bool,
        match_type: str,
        normalized_query: str | None = None,
    ) -> dict[str, Any]:
        candidates = []
        for row in rows:
            candidate = {
                "identifier": row["id"],
                "entity_url": row["entity_url"],
            }
            if include_entity_type:
                candidate["entity_type"] = row["entity_type"]
            candidates.append(candidate)

        result = {
            "found": False,
            "status": "ambiguous",
            "match_type": match_type,
            "candidates": candidates,
        }
        if normalized_query is not None:
            result["normalized_query"] = normalized_query
        return result

    def _resolve_entity(
        self,
        identifier: str,
        entity_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Resolve by:
        1) exact entity id
        2) exact entity_url
        3) exact case-insensitive name/business/synonym
        4) normalized name/business/synonym

        Normalized matching is collision-aware and never applies to ids or URLs.
        """
        with self._connect() as conn:
            if entity_type is None:
                direct = conn.execute(
                    """
                    SELECT *
                    FROM entities
                    WHERE id = ?
                       OR entity_url = ?
                    """,
                    (identifier, identifier),
                ).fetchall()
            else:
                direct = conn.execute(
                    """
                    SELECT *
                    FROM entities
                    WHERE entity_type = ?
                      AND (id = ? OR entity_url = ?)
                    """,
                    (entity_type, identifier, identifier),
                ).fetchall()

            if len(direct) == 1:
                return self._resolved_entity(direct[0], match_type="exact")

            if entity_type is None:
                rows = conn.execute(
                    """
                    SELECT DISTINCT e.*
                    FROM entity_names n
                    JOIN entities e ON e.id = n.entity_id
                    WHERE lower(n.name) = lower(?)
                    ORDER BY e.entity_type, e.canonical_name, e.id
                    """,
                    (identifier,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT DISTINCT e.*
                    FROM entity_names n
                    JOIN entities e ON e.id = n.entity_id
                    WHERE e.entity_type = ?
                      AND lower(n.name) = lower(?)
                    ORDER BY e.canonical_name, e.id
                    """,
                    (entity_type, identifier),
                ).fetchall()

            if rows:
                if len(rows) > 1:
                    return self._ambiguous_entities(
                        rows,
                        include_entity_type=entity_type is None,
                        match_type="exact",
                    )
                return self._resolved_entity(rows[0], match_type="exact")

            normalized_query = normalize_identifier(identifier)
            if entity_type is None:
                named_rows = conn.execute(
                    """
                    SELECT e.*, n.name AS lookup_name
                    FROM entity_names n
                    JOIN entities e ON e.id = n.entity_id
                    ORDER BY e.entity_type, e.canonical_name, e.id
                    """
                ).fetchall()
            else:
                named_rows = conn.execute(
                    """
                    SELECT e.*, n.name AS lookup_name
                    FROM entity_names n
                    JOIN entities e ON e.id = n.entity_id
                    WHERE e.entity_type = ?
                    ORDER BY e.canonical_name, e.id
                    """,
                    (entity_type,),
                ).fetchall()

            normalized_matches: dict[str, sqlite3.Row] = {}
            for row in named_rows:
                if normalize_identifier(row["lookup_name"]) == normalized_query:
                    normalized_matches.setdefault(row["id"], row)
            rows = list(normalized_matches.values())

        if not rows:
            return {"found": False, "status": "not_found"}

        if len(rows) > 1:
            return self._ambiguous_entities(
                rows,
                include_entity_type=entity_type is None,
                match_type="normalized",
                normalized_query=normalized_query,
            )

        return self._resolved_entity(
            rows[0],
            match_type="normalized",
            normalized_query=normalized_query,
        )

    def _resolve_entity_any_type(self, identifier: str) -> dict[str, Any]:
        return self._resolve_entity(identifier)

    def get_entity(self, entity_type: str, identifier: str) -> dict[str, Any]:
        return self._resolve_entity(identifier, entity_type)

    def traverse(
        self,
        from_entity: str,
        relationship_type: str,
        depth: int = 1,
    ) -> dict[str, Any]:
        """
        Walk exactly one hop, bidirectionally.

        Contract:
        - depth is capped at 1. Any other value is an invalid argument.
        - relationship_type names the stored edge type, not the walk direction.
        - from_entity may be an id, entity_url, or exact unique name.
        """
        if depth != 1:
            return {
                "found": False,
                "status": "invalid_argument",
                "error": "depth must be exactly 1",
            }

        start = self._resolve_entity_any_type(from_entity)

        if start["status"] == "not_found":
            return {"found": False, "status": "not_found"}

        if start["status"] == "ambiguous":
            return start

        start_id = start["id"]

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    r.id AS relationship_id,
                    r.relationship_type,
                    r.predicate,
                    r.from_entity_id,
                    r.to_entity_id,
                    CASE
                        WHEN r.from_entity_id = ? THEN r.to_entity_id
                        ELSE r.from_entity_id
                    END AS connected_entity_id
                FROM relationships r
                WHERE r.relationship_type = ?
                  AND (r.from_entity_id = ? OR r.to_entity_id = ?)
                ORDER BY r.id
                """,
                (start_id, relationship_type, start_id, start_id),
            ).fetchall()

            results = []
            for rel in rows:
                entity = conn.execute(
                    """
                    SELECT *
                    FROM entities
                    WHERE id = ?
                    """,
                    (rel["connected_entity_id"],),
                ).fetchone()

                payload = json.loads(entity["payload_json"])
                results.append(
                    {
                        "relationship_id": rel["relationship_id"],
                        "relationship_type": rel["relationship_type"],
                        "predicate": rel["predicate"],
                        "direction": (
                            "forward"
                            if rel["from_entity_id"] == start_id
                            else "reverse"
                        ),
                        "entity": {
                            "entity_type": entity["entity_type"],
                            **payload,
                        },
                    }
                )

        return {
            "found": bool(results),
            "status": "ok",
            "from_entity": {
                "entity_type": start["entity_type"],
                "id": start["id"],
                "entity_url": start["entity_url"],
            },
            "relationship_type": relationship_type,
            "depth": 1,
            "results": results,
        }

    def search_glossary(self, term: str) -> dict[str, Any]:
        """
        Search governed glossary content.

        Precedence:
        1. exact glossary term match (case-insensitive)
        2. synonym match only when no exact term exists

        Exact conflicts are all returned; aliases and replacements are
        resolved inline from governed catalogue records.
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM entities
                WHERE entity_type = 'glossary'
                  AND lower(canonical_name) = lower(?)
                ORDER BY id
                """,
                (term,),
            ).fetchall()
            match_type = "exact"

            if not rows:
                rows = conn.execute(
                    """
                    SELECT DISTINCT e.*
                    FROM entity_names n
                    JOIN entities e ON e.id = n.entity_id
                    WHERE e.entity_type = 'glossary'
                      AND n.name_type = 'synonym'
                      AND lower(n.name) = lower(?)
                    ORDER BY e.id
                    """,
                    (term,),
                ).fetchall()
                match_type = "synonym"

            if not rows:
                return {
                    "found": False,
                    "status": "not_found",
                    "query": term,
                    "results": [],
                }

            results = []
            for row in rows:
                payload = json.loads(row["payload_json"])
                item = {"entity_type": "glossary", **payload}

                if payload.get("replaced_by"):
                    replacement = conn.execute(
                        """
                        SELECT *
                        FROM entities
                        WHERE entity_type = 'glossary' AND id = ?
                        """,
                        (payload["replaced_by"],),
                    ).fetchone()
                    if replacement:
                        rp = json.loads(replacement["payload_json"])
                        item["replacement"] = {
                            "identifier": rp["id"],
                            "name": rp["term"],
                            "status": rp["status"],
                            "entity_url": rp["entity_url"],
                        }

                if payload.get("alias_of"):
                    canonical = conn.execute(
                        """
                        SELECT *
                        FROM entities
                        WHERE entity_type = 'glossary' AND id = ?
                        """,
                        (payload["alias_of"],),
                    ).fetchone()
                    if canonical:
                        cp = json.loads(canonical["payload_json"])
                        item["canonical_term"] = {
                            "identifier": cp["id"],
                            "name": cp["term"],
                            "definition": cp["definition"],
                            "status": cp["status"],
                            "entity_url": cp["entity_url"],
                        }

                results.append(item)

        return {
            "found": True,
            "status": "ok",
            "query": term,
            "match_type": match_type,
            "results": results,
        }

    def get_registry_health(
        self,
        registry: str,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        """
        Compute declared registry quality rules against the live catalogue.

        `registry` accepts either:
          - application / capability / technology
          - application_registry / capability_registry / technology_registry
          - exact registry name

        `as_of` is YYYY-MM-DD. If omitted, today's date is used.
        """
        as_of_date = (
            datetime.strptime(as_of, "%Y-%m-%d").date()
            if as_of
            else date.today()
        )

        aliases = {
            "application": "application_registry",
            "applications": "application_registry",
            "capability": "capability_registry",
            "capabilities": "capability_registry",
            "technology": "technology_registry",
            "technologies": "technology_registry",
        }
        lookup = aliases.get(registry.lower(), registry)

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM entities
                WHERE entity_type = 'registry'
                  AND (
                    id = ?
                    OR lower(canonical_name) = lower(?)
                  )
                """,
                (lookup, lookup),
            ).fetchone()

            if row is None:
                return {
                    "found": False,
                    "status": "not_found",
                }

            registry_payload = json.loads(row["payload_json"])
            registry_id = row["id"]
            governed_type = registry_payload["entity_type"]

            rules = conn.execute(
                """
                SELECT *
                FROM registry_rules
                WHERE registry_id = ?
                ORDER BY id
                """,
                (registry_id,),
            ).fetchall()

            results = []

            for rule in rules:
                metric = rule["metric"]
                operator = rule["operator"]
                threshold = rule["threshold"]
                field_name = rule["field_name"]
                relationship_type = rule["relationship_type"]
                config = json.loads(rule["config_json"] or "{}")

                actual = None
                evidence = []

                if metric == "field_completeness":
                    entity_rows = conn.execute(
                        """
                        SELECT id, canonical_name, payload_json
                        FROM entities
                        WHERE entity_type = ?
                        ORDER BY id
                        """,
                        (governed_type,),
                    ).fetchall()

                    populated = 0
                    missing = []
                    for e in entity_rows:
                        payload = json.loads(e["payload_json"])
                        value = payload.get(field_name)
                        if value not in (None, "", []):
                            populated += 1
                        else:
                            missing.append({
                                "identifier": e["id"],
                                "name": e["canonical_name"],
                            })

                    actual = populated / len(entity_rows) if entity_rows else 0.0
                    evidence = missing

                elif metric == "parent_completeness":
                    level = int(config["applicable_level"])
                    entity_rows = conn.execute(
                        """
                        SELECT id, canonical_name, payload_json
                        FROM entities
                        WHERE entity_type = 'capability'
                        ORDER BY id
                        """
                    ).fetchall()

                    applicable = []
                    complete = 0
                    missing = []
                    for e in entity_rows:
                        payload = json.loads(e["payload_json"])
                        if payload.get("level") != level:
                            continue
                        applicable.append(payload)
                        if payload.get("parent_id"):
                            complete += 1
                        else:
                            missing.append({
                                "identifier": e["id"],
                                "name": e["canonical_name"],
                            })

                    actual = complete / len(applicable) if applicable else 0.0
                    evidence = missing

                elif metric == "hierarchy_violations":
                    entity_rows = conn.execute(
                        """
                        SELECT id, canonical_name, payload_json
                        FROM entities
                        WHERE entity_type = 'capability'
                        ORDER BY id
                        """
                    ).fetchall()
                    payloads = {
                        e["id"]: json.loads(e["payload_json"])
                        for e in entity_rows
                    }

                    violations = []
                    for entity_id, payload in payloads.items():
                        level = payload.get("level")
                        parent_id = payload.get("parent_id")

                        if level == 1:
                            if parent_id is not None:
                                violations.append({
                                    "identifier": entity_id,
                                    "reason": "level_1_has_parent",
                                })
                        elif level == 2:
                            parent = payloads.get(parent_id)
                            if parent_id is None:
                                violations.append({
                                    "identifier": entity_id,
                                    "reason": "missing_parent",
                                })
                            elif parent_id == entity_id:
                                violations.append({
                                    "identifier": entity_id,
                                    "reason": "self_parent",
                                })
                            elif parent is None:
                                violations.append({
                                    "identifier": entity_id,
                                    "reason": "parent_not_found",
                                })
                            elif parent.get("level") != 1:
                                violations.append({
                                    "identifier": entity_id,
                                    "reason": "invalid_parent_level",
                                })
                        else:
                            violations.append({
                                "identifier": entity_id,
                                "reason": "unsupported_level",
                            })

                    actual = float(len(violations))
                    evidence = violations

                elif metric == "relationship_coverage":
                    if governed_type == "application":
                        excluded = set(config.get("excluded_application_types", []))
                        entity_rows = conn.execute(
                            """
                            SELECT id, canonical_name, payload_json
                            FROM entities
                            WHERE entity_type = 'application'
                            ORDER BY id
                            """
                        ).fetchall()
                        applicable = []
                        for e in entity_rows:
                            payload = json.loads(e["payload_json"])
                            if payload.get("application_type") not in excluded:
                                applicable.append(e)

                        covered_ids = {
                            r["from_entity_id"]
                            for r in conn.execute(
                                """
                                SELECT from_entity_id
                                FROM relationships
                                WHERE relationship_type = ?
                                """,
                                (relationship_type,),
                            ).fetchall()
                        }

                    elif governed_type == "capability":
                        level = int(config["applicable_level"])
                        entity_rows = conn.execute(
                            """
                            SELECT id, canonical_name, payload_json
                            FROM entities
                            WHERE entity_type = 'capability'
                            ORDER BY id
                            """
                        ).fetchall()
                        applicable = [
                            e for e in entity_rows
                            if json.loads(e["payload_json"]).get("level") == level
                        ]
                        covered_ids = {
                            r["to_entity_id"]
                            for r in conn.execute(
                                """
                                SELECT to_entity_id
                                FROM relationships
                                WHERE relationship_type = ?
                                """,
                                (relationship_type,),
                            ).fetchall()
                        }

                    elif governed_type == "technology":
                        entity_rows = conn.execute(
                            """
                            SELECT id, canonical_name, payload_json
                            FROM entities
                            WHERE entity_type = 'technology'
                            ORDER BY id
                            """
                        ).fetchall()
                        applicable = list(entity_rows)
                        covered_ids = {
                            r["to_entity_id"]
                            for r in conn.execute(
                                """
                                SELECT to_entity_id
                                FROM relationships
                                WHERE relationship_type = ?
                                """,
                                (relationship_type,),
                            ).fetchall()
                        }
                    else:
                        applicable = []
                        covered_ids = set()

                    missing = [
                        {
                            "identifier": e["id"],
                            "name": e["canonical_name"],
                        }
                        for e in applicable
                        if e["id"] not in covered_ids
                    ]
                    covered = len(applicable) - len(missing)
                    actual = covered / len(applicable) if applicable else 0.0
                    evidence = missing

                elif metric == "maximum_age_days":
                    entity_rows = conn.execute(
                        """
                        SELECT id, canonical_name, payload_json
                        FROM entities
                        WHERE entity_type = ?
                        ORDER BY id
                        """,
                        (governed_type,),
                    ).fetchall()

                    ages = []
                    for e in entity_rows:
                        payload = json.loads(e["payload_json"])
                        verified = datetime.strptime(
                            payload[field_name], "%Y-%m-%d"
                        ).date()
                        age = (as_of_date - verified).days
                        ages.append((age, e))

                    actual = float(max(age for age, _ in ages)) if ages else 0.0
                    evidence = [
                        {
                            "identifier": e["id"],
                            "name": e["canonical_name"],
                            "age_days": age,
                        }
                        for age, e in ages
                        if age == actual
                    ]

                else:
                    results.append({
                        "id": rule["id"],
                        "metric": metric,
                        "status": "unsupported_metric",
                    })
                    continue

                if operator == "greater_than_or_equal":
                    passed = actual >= threshold
                elif operator == "less_than_or_equal":
                    passed = actual <= threshold
                elif operator == "equal":
                    passed = actual == threshold
                else:
                    passed = False

                results.append({
                    "id": rule["id"],
                    "metric": metric,
                    "operator": operator,
                    "threshold": threshold,
                    "actual": actual,
                    "passed": passed,
                    "status": "pass" if passed else "fail",
                    "evidence": evidence,
                })

        return {
            "found": True,
            "status": "ok",
            "registry": {
                "id": registry_payload["id"],
                "name": registry_payload["name"],
                "steward": registry_payload["steward"],
                "classification": registry_payload["classification"],
                "source_systems": registry_payload["source_systems"],
                "refresh_cadence": registry_payload["refresh_cadence"],
                "last_refreshed": registry_payload["last_refreshed"],
                "entity_url": registry_payload["entity_url"],
            },
            "as_of": as_of_date.isoformat(),
            "rules": results,
            "overall_status": (
                "pass"
                if all(r.get("passed") for r in results)
                else "fail"
            ),
        }

    def identify_steward(self, topic: str) -> dict[str, Any]:
        """
        Deterministically route a topic to one of Northgate's governed registries.

        This tool does not invent a person. It returns the steward declared on
        the matching registry record.

        Precedence matters: application-oriented phrases win over technology
        words inside the same phrase. For example, "applications past end of
        life" routes to the Application Registry because the governed subject
        is the application portfolio.
        """
        normalized = " ".join(topic.lower().replace("_", " ").replace("-", " ").split())

        application_terms = (
            "application",
            "applications",
            "app ",
            "apps ",
            "system",
            "systems",
            "portfolio",
        )
        capability_terms = (
            "capability",
            "capabilities",
            "business capability",
        )
        technology_terms = (
            "technology",
            "technologies",
            "technical standard",
            "platform",
            "database",
            "operating system",
            "runtime",
            "version",
            "end of life",
            "eol",
            "support lifecycle",
        )

        registry_id = None
        matched_domain = None

        if any(term in normalized for term in application_terms):
            registry_id = "application_registry"
            matched_domain = "application"
        elif any(term in normalized for term in capability_terms):
            registry_id = "capability_registry"
            matched_domain = "capability"
        elif any(term in normalized for term in technology_terms):
            registry_id = "technology_registry"
            matched_domain = "technology"

        if registry_id is None:
            return {
                "found": False,
                "status": "not_found",
                "topic": topic,
                "reason": "No governed registry could be determined from the topic.",
            }

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM entities
                WHERE entity_type = 'registry'
                  AND id = ?
                """,
                (registry_id,),
            ).fetchone()

        if row is None:
            return {
                "found": False,
                "status": "not_found",
                "topic": topic,
                "reason": "Mapped registry is not present in the catalogue.",
            }

        payload = json.loads(row["payload_json"])

        return {
            "found": True,
            "status": "ok",
            "topic": topic,
            "matched_domain": matched_domain,
            "registry": {
                "id": payload["id"],
                "name": payload["name"],
                "steward": payload["steward"],
                "classification": payload["classification"],
                "source_systems": payload["source_systems"],
                "refresh_cadence": payload["refresh_cadence"],
                "entity_url": payload["entity_url"],
            },
        }

