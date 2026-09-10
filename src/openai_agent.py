from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.agent_instructions import SYSTEM_INSTRUCTIONS
from src.catalogue_client import LocalClient
from src.openai_tools import TOOLS


NORTHGATE_URL_RE = re.compile(r"northgate://[A-Za-z0-9._~:/-]+")


class CitationIntegrityError(RuntimeError):
    pass


@dataclass
class ToolEvent:
    sequence: int
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    call_id: str | None = None


class OpenAIGovernanceAgent:
    """
    Plain Responses API tool-calling loop.

    The OpenAI client is injected so the loop can be tested without an API key.
    """

    def __init__(
        self,
        *,
        openai_client: Any,
        catalogue: LocalClient,
        model: str = "gpt-5.6",
        reasoning_effort: str = "medium",
        log_path: str | Path = "logs/trajectories.jsonl",
        max_tool_rounds: int = 12,
        strict_citations: bool = True,
        instructions: str = SYSTEM_INSTRUCTIONS,
    ):
        self.openai = openai_client
        self.catalogue = catalogue
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.log_path = Path(log_path)
        self.max_tool_rounds = max_tool_rounds
        self.strict_citations = strict_citations
        self.instructions = instructions

    def _dispatch(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            if name == "get_entity":
                return self.catalogue.get_entity(**arguments)
            if name == "search_glossary":
                return self.catalogue.search_glossary(**arguments)
            if name == "traverse":
                return self.catalogue.traverse(**arguments)
            if name == "get_registry_health":
                return self.catalogue.get_registry_health(**arguments)
            if name == "identify_steward":
                return self.catalogue.identify_steward(**arguments)
            return {
                "found": False,
                "status": "tool_error",
                "error": f"Unknown tool: {name}",
            }
        except Exception as exc:
            return {
                "found": False,
                "status": "tool_error",
                "error": f"{type(exc).__name__}: {exc}",
            }

    @staticmethod
    def _collect_urls(value: Any) -> set[str]:
        urls: set[str] = set()

        if isinstance(value, dict):
            for key, child in value.items():
                if key == "entity_url" and isinstance(child, str):
                    urls.add(child)
                urls.update(OpenAIGovernanceAgent._collect_urls(child))
        elif isinstance(value, list):
            for child in value:
                urls.update(OpenAIGovernanceAgent._collect_urls(child))

        return urls

    def _validate_citations(
        self,
        answer: str,
        tool_events: list[ToolEvent],
    ) -> dict[str, Any]:
        retrieved_urls: set[str] = set()
        for event in tool_events:
            retrieved_urls.update(self._collect_urls(event.result))

        cited_urls = set(NORTHGATE_URL_RE.findall(answer))
        invalid_urls = sorted(cited_urls - retrieved_urls)

        return {
            "retrieved_urls": sorted(retrieved_urls),
            "cited_urls": sorted(cited_urls),
            "invalid_urls": invalid_urls,
            "passed": not invalid_urls,
        }

    def _request(self, input_items: list[Any]):
        return self.openai.responses.create(
            model=self.model,
            instructions=self.instructions,
            input=input_items,
            tools=TOOLS,
            tool_choice="auto",
            parallel_tool_calls=False,
            reasoning={"effort": self.reasoning_effort},
            text={"verbosity": "low"},
            store=True,
        )

    def ask(self, question: str) -> dict[str, Any]:
        input_items: list[Any] = [
            {
                "role": "user",
                "content": question,
            }
        ]
        events: list[ToolEvent] = []
        response_ids: list[str] = []

        for _round in range(self.max_tool_rounds + 1):
            response = self._request(input_items)
            if getattr(response, "id", None):
                response_ids.append(response.id)

            function_calls = [
                item
                for item in getattr(response, "output", [])
                if getattr(item, "type", None) == "function_call"
            ]

            if not function_calls:
                answer = getattr(response, "output_text", "") or ""
                citation_validation = self._validate_citations(answer, events)

                record = {
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "question": question,
                    "model": self.model,
                    "reasoning_effort": self.reasoning_effort,
                    "response_ids": response_ids,
                    "tools_called": [asdict(event) for event in events],
                    "final_answer": answer,
                    "citations": citation_validation,
                }

                if self.strict_citations and not citation_validation["passed"]:
                    record["status"] = "blocked_invalid_citation"
                    self._append_log(record)
                    raise CitationIntegrityError(
                        "Model produced a Northgate citation that was not returned by a tool: "
                        + ", ".join(citation_validation["invalid_urls"])
                    )

                record["status"] = "completed"
                self._append_log(record)
                return record

            # OpenAI recommends passing response output items back when continuing
            # a reasoning/tool loop. This preserves function-call and reasoning items.
            input_items.extend(response.output)

            for call in function_calls:
                try:
                    arguments = json.loads(call.arguments)
                except json.JSONDecodeError as exc:
                    arguments = {}
                    result = {
                        "found": False,
                        "status": "tool_error",
                        "error": f"Invalid JSON arguments: {exc}",
                    }
                else:
                    result = self._dispatch(call.name, arguments)

                events.append(
                    ToolEvent(
                        sequence=len(events) + 1,
                        name=call.name,
                        arguments=arguments,
                        result=result,
                        call_id=getattr(call, "call_id", None),
                    )
                )

                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(
                            result,
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    }
                )

        record = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "question": question,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "response_ids": response_ids,
            "tools_called": [asdict(event) for event in events],
            "final_answer": "",
            "status": "max_tool_rounds_exceeded",
        }
        self._append_log(record)
        raise RuntimeError(
            f"Agent exceeded {self.max_tool_rounds} tool rounds without a final answer."
        )

    def _append_log(self, record: dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
