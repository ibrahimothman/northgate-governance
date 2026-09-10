from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from openai import OpenAI, OpenAIError

from src.catalogue_client import LocalClient
from src.openai_agent import CitationIntegrityError, OpenAIGovernanceAgent


ROOT = Path(__file__).resolve().parents[1]
CATALOGUE_URI_RE = re.compile(r"\s*\(northgate://[A-Za-z0-9._~:/-]+\)")
BARE_CATALOGUE_URI_RE = re.compile(r"northgate://[A-Za-z0-9._~:/-]+")
CATALOGUE_LINK_RE = re.compile(
    r"\[([^\]]+)\]\(northgate://[A-Za-z0-9._~:/-]+\)"
)


class AskRequest(BaseModel):
    question: str = Field(max_length=2_000)


class ServiceUnavailableError(RuntimeError):
    pass


def _display_name(value: dict[str, Any]) -> str:
    return str(
        value.get("name")
        or value.get("term")
        or value.get("canonical_name")
        or value.get("identifier")
        or value.get("id")
        or "Catalogue record"
    )


def _entity_view(value: dict[str, Any]) -> dict[str, Any] | None:
    entity_id = value.get("id") or value.get("identifier")
    uri = value.get("entity_url")
    entity_type = value.get("entity_type")
    if not entity_id or not uri or not entity_type:
        return None

    omitted = {
        "id",
        "identifier",
        "entity_type",
        "entity_url",
        "name",
        "term",
        "canonical_name",
        "found",
        "status",
        "match_type",
        "normalized_query",
    }
    return {
        "id": str(entity_id),
        "entity_type": str(entity_type),
        "name": _display_name(value),
        "uri": str(uri),
        "attributes": {key: val for key, val in value.items() if key not in omitted},
    }


def _operator_symbol(operator: str | None) -> str | None:
    return {
        "less_than_or_equal": "<=",
        "greater_than_or_equal": ">=",
        "equal": "=",
    }.get(operator or "", operator)


def _caveat_message(metric: str, registry_name: str) -> tuple[str, str]:
    if metric == "maximum_age_days":
        return (
            f"{registry_name} freshness is outside its declared target",
            "Verify the catalogue record before using this answer for a decision.",
        )
    if metric == "field_completeness":
        return (
            f"{registry_name} completeness is below its declared target",
            "Some records may be missing accountable ownership or other required fields.",
        )
    if metric == "relationship_coverage":
        return (
            f"{registry_name} relationship coverage is incomplete",
            "Impact results may omit records without governed relationships.",
        )
    return (
        f"{registry_name} has a failing governance rule",
        "Review the registry quality evidence before relying on this answer.",
    )


def _trace_label(name: str, result: dict[str, Any]) -> str:
    if name == "get_entity":
        entity_type = str(result.get("entity_type", "record")).replace("_", " ")
        return f"Retrieved {entity_type}"
    if name == "search_glossary":
        return "Searched governed glossary"
    if name == "traverse":
        return "Traversed dependencies"
    if name == "get_registry_health":
        registry = result.get("registry") or {}
        return f"Checked {registry.get('name', 'registry health')}"
    if name == "identify_steward":
        return "Identified responsible steward"
    return name.replace("_", " ").title()


def _trace_summary(name: str, result: dict[str, Any]) -> str:
    status = result.get("status")
    if status == "tool_error":
        return str(result.get("error", "Tool execution failed"))
    if status == "not_found":
        return "No governed record found"
    if status == "ambiguous":
        count = len(result.get("candidates") or [])
        return f"{count} possible matches found"
    if name == "get_entity":
        return f"{_display_name(result)} found"
    if name == "search_glossary":
        count = len(result.get("results") or [])
        return f"{count} governed definition{'s' if count != 1 else ''} found"
    if name == "traverse":
        count = len(result.get("results") or [])
        return f"{count} related record{'s' if count != 1 else ''} found"
    if name == "get_registry_health":
        rules = result.get("rules") or []
        failures = sum(rule.get("status") == "fail" for rule in rules)
        return (
            f"{failures} governance rule{'s' if failures != 1 else ''} failed"
            if failures
            else "All governance rules passed"
        )
    if name == "identify_steward":
        registry = result.get("registry") or {}
        return f"Escalation routed to {registry.get('steward', 'the registry steward')}"
    return str(status or "Completed").replace("_", " ").title()


def _trace_status(result: dict[str, Any]) -> str:
    status = result.get("status", "ok")
    if status in {"ok", "not_found", "ambiguous", "tool_error"}:
        return status
    return "tool_error"


def _result_type(events: list[dict[str, Any]]) -> str:
    results = [event.get("result") or {} for event in events]
    if any(result.get("status") == "not_found" for result in results) and any(
        event.get("name") == "identify_steward" for event in events
    ):
        return "refusal"
    if any(result.get("status") == "ambiguous" for result in results):
        return "ambiguous"
    for event in events:
        result = event.get("result") or {}
        if event.get("name") == "search_glossary" and len(result.get("results") or []) > 1:
            return "glossary_conflict"
    if any(event.get("name") == "traverse" for event in events):
        return "impact"
    if any(
        event.get("name") == "get_entity"
        and (event.get("result") or {}).get("entity_type") == "dataset"
        for event in events
    ):
        return "governed_fact"
    return "answer"


def present_agent_result(record: dict[str, Any], question: str) -> dict[str, Any]:
    """Convert the internal agent trajectory into the stable frontend DTO."""
    events: list[dict[str, Any]] = record.get("tools_called") or []
    entities: dict[str, dict[str, Any]] = {}
    relationships: list[dict[str, str]] = []
    caveats: list[dict[str, Any]] = []
    labels_by_uri: dict[str, str] = {}

    def remember(value: dict[str, Any]) -> None:
        view = _entity_view(value)
        if view:
            existing = entities.get(view["id"])
            if existing:
                view["attributes"] = {
                    **existing["attributes"],
                    **view["attributes"],
                }
                if view["name"] == view["id"] and existing["name"] != existing["id"]:
                    view["name"] = existing["name"]
            entities[view["id"]] = view
            labels_by_uri[view["uri"]] = view["name"]

    for event in events:
        name = event.get("name")
        result = event.get("result") or {}

        if name == "get_entity" and result.get("status") == "ok":
            remember(result)

        if name == "get_entity" and result.get("status") == "ambiguous":
            entity_type = str((event.get("arguments") or {}).get("entity_type", "record"))
            for candidate in result.get("candidates") or []:
                remember(
                    {
                        **candidate,
                        "id": candidate.get("identifier"),
                        "name": candidate.get("name") or candidate.get("identifier"),
                        "entity_type": candidate.get("entity_type") or entity_type,
                    }
                )

        if name == "search_glossary":
            for item in result.get("results") or []:
                remember(item)

        if name == "traverse":
            start = result.get("from_entity") or {}
            start_id = start.get("id")
            remember(
                {
                    **start,
                    "name": (event.get("arguments") or {}).get("from_entity")
                    or start.get("id"),
                }
            )
            for item in result.get("results") or []:
                connected = item.get("entity") or {}
                remember(connected)
                connected_id = connected.get("id")
                if not start_id or not connected_id:
                    continue
                if item.get("direction") == "reverse":
                    from_id, to_id = connected_id, start_id
                else:
                    from_id, to_id = start_id, connected_id
                relationships.append(
                    {
                        "from_id": str(from_id),
                        "to_id": str(to_id),
                        "relationship_type": str(
                            item.get("relationship_type")
                            or result.get("relationship_type")
                            or "related to"
                        ),
                    }
                )

        if name in {"get_registry_health", "identify_steward"}:
            registry = result.get("registry") or {}
            uri = registry.get("entity_url")
            if uri:
                labels_by_uri[str(uri)] = _display_name(registry)
            if name == "identify_steward" and registry:
                remember({"entity_type": "registry", **registry})

        if name == "get_registry_health" and result.get("status") == "ok":
            registry = result.get("registry") or {}
            registry_name = str(registry.get("name", "Registry"))
            for rule in result.get("rules") or []:
                if rule.get("status") != "fail":
                    continue
                metric = str(rule.get("metric", "governance_rule"))
                title, message = _caveat_message(metric, registry_name)
                caveats.append(
                    {
                        "id": str(rule.get("id") or uuid4()),
                        "registry_id": str(registry.get("id", "")),
                        "registry_name": registry_name,
                        "severity": "warning",
                        "title": title,
                        "metric": metric,
                        "actual": rule.get("actual"),
                        "operator": _operator_symbol(rule.get("operator")),
                        "threshold": rule.get("threshold"),
                        "status": "fail",
                        "message": message,
                        "uri": registry.get("entity_url"),
                    }
                )

    citation_data = record.get("citations") or {}
    citation_uris = citation_data.get("cited_urls") or citation_data.get("retrieved_urls") or []
    citations = [
        {
            "entity_id": uri.rstrip("/").rsplit("/", 1)[-1],
            "label": labels_by_uri.get(uri, uri.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()),
            "uri": uri,
        }
        for uri in citation_uris
    ]

    raw_answer = str(record.get("final_answer") or "")
    answer = CATALOGUE_LINK_RE.sub(r"\1", raw_answer)
    answer = CATALOGUE_URI_RE.sub("", answer)
    answer = BARE_CATALOGUE_URI_RE.sub("", answer).strip()
    kind = _result_type(events)

    trace = [
        {
            "sequence": int(event.get("sequence", index)),
            "tool": str(event.get("name", "unknown_tool")),
            "label": _trace_label(str(event.get("name", "")), event.get("result") or {}),
            "arguments": event.get("arguments") or {},
            "status": _trace_status(event.get("result") or {}),
            "summary": _trace_summary(str(event.get("name", "")), event.get("result") or {}),
            "result": event.get("result"),
        }
        for index, event in enumerate(events, start=1)
    ]

    response_ids = record.get("response_ids") or []
    return {
        "request_id": str(response_ids[0] if response_ids else f"req_{uuid4().hex}"),
        "status": "refused" if kind == "refusal" else "completed",
        "question": question,
        "answer": answer,
        "result_type": kind,
        "entities": list(entities.values()),
        "relationships": relationships,
        "caveats": caveats,
        "citations": citations,
        "trace": trace,
        "meta": {
            "model": record.get("model"),
            "tool_call_count": len(events),
            "duration_ms": record.get("duration_ms"),
        },
    }


def build_agent() -> OpenAIGovernanceAgent:
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise ServiceUnavailableError("OPENAI_API_KEY is not configured.")
    return OpenAIGovernanceAgent(
        openai_client=OpenAI(),
        catalogue=LocalClient(ROOT / "data" / "catalogue.db"),
        model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
        reasoning_effort=os.getenv("OPENAI_REASONING_EFFORT", "medium"),
        log_path=ROOT / "logs" / "trajectories.jsonl",
    )


def create_app(agent: OpenAIGovernanceAgent | None = None) -> FastAPI:
    app = FastAPI(title="Northgate Governance Assistant API", version="1.0.0")
    app.state.agent = agent
    allowed_origins = [
        origin.strip()
        for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        _request: Request,
        _exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Provide a question of no more than 2,000 characters.",
                },
            },
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/ask")
    async def ask(payload: AskRequest) -> Any:
        question = payload.question.strip()
        if not question:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "error": {
                        "code": "INVALID_REQUEST",
                        "message": "Question must not be empty.",
                    },
                },
            )

        try:
            if app.state.agent is None:
                app.state.agent = build_agent()
            active_agent = app.state.agent
            # The local SQLite catalogue is intentionally executed on the server
            # thread. Python 3.14 on Windows can terminate the process when its
            # sqlite3 extension is entered through AnyIO's worker-thread bridge.
            started_at = perf_counter()
            record = active_agent.ask(question)
            record["duration_ms"] = round((perf_counter() - started_at) * 1000)
            return present_agent_result(record, question)
        except CitationIntegrityError:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "error": {
                        "code": "CITATION_INTEGRITY_FAILED",
                        "message": (
                            "The answer could not be verified against its governed sources."
                        ),
                    },
                },
            )
        except ServiceUnavailableError:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "error": {
                        "code": "MODEL_PROVIDER_UNAVAILABLE",
                        "message": (
                            "The backend is running, but OPENAI_API_KEY is not configured."
                        ),
                    },
                },
            )
        except (OpenAIError, sqlite3.Error):
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "error": {
                        "code": "AGENT_EXECUTION_FAILED",
                        "message": "The assistant could not complete the request.",
                    },
                },
            )
        except Exception:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "error": {
                        "code": "AGENT_EXECUTION_FAILED",
                        "message": "The assistant could not complete the request.",
                    },
                },
            )

    return app


app = create_app()
