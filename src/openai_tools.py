from __future__ import annotations

TOOLS = [
    {
        "type": "function",
        "name": "get_entity",
        "description": (
            "Fetch one governed catalogue entity by exact identifier, entity URL, canonical name, "
            "business name, or stored synonym. Use this for applications, capabilities, technologies, "
            "datasets, glossary records, and registries. Use this first for facts about a named asset, "
            "including its retention, classification, steward, ownership, lifecycle, or holdings. "
            "Names tolerate capitalization, whitespace, hyphenation, and conservative plural variation. "
            "If the identifier is ambiguous, the result contains candidates and you must fetch each "
            "candidate by identifier before answering."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": [
                        "application",
                        "capability",
                        "technology",
                        "dataset",
                        "glossary",
                        "registry",
                    ],
                },
                "identifier": {
                    "type": "string",
                    "description": (
                        "Catalogue id, entity URL, governed name, business name, or synonym. "
                        "Names may use conservative lexical variants."
                    ),
                },
            },
            "required": ["entity_type", "identifier"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "search_glossary",
        "description": (
            "Use this tool for governed business-term questions, including a term's definition, owner, "
            "steward, canonical status, aliases, governance metadata, or lifecycle. Do not use it for "
            "retention, classification, or holdings of a named dataset, application, technology, or "
            "capability; use get_entity for those asset questions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "term": {
                    "type": "string",
                    "description": "Glossary term or stored synonym to look up.",
                },
            },
            "required": ["term"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "traverse",
        "description": (
            "Traverse one typed catalogue relationship hop in either direction. Use for named impact, "
            "duplication, capability realisation, technology dependencies, or dataset holdings. "
            "This tool is not for estate-wide aggregation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "from_entity": {
                    "type": "string",
                    "description": "Exact unique entity id, entity URL, or governed name.",
                },
                "relationship_type": {
                    "type": "string",
                    "enum": [
                        "application → capability",
                        "application → technology",
                        "application → dataset",
                    ],
                },
                "depth": {
                    "type": "integer",
                    "enum": [1],
                    "description": "Traversal depth. Version 1 supports exactly one hop.",
                },
            },
            "required": ["from_entity", "relationship_type", "depth"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_registry_health",
        "description": (
            "Compute the governed registry's declared quality rules against the current catalogue. "
            "Use this whenever a retrieved entity has a source_registry, and for direct questions "
            "about completeness, freshness, quality, or registry health."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "registry": {
                    "type": "string",
                    "description": (
                        "Registry domain, registry id, or registry name; for example application, "
                        "technology, application_registry, or Technology Registry."
                    ),
                },
                "as_of": {
                    "type": ["string", "null"],
                    "description": (
                        "Optional YYYY-MM-DD evaluation date. Pass null for the runtime current date."
                    ),
                },
            },
            "required": ["registry", "as_of"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "identify_steward",
        "description": (
            "Map an unresolved or out-of-scope topic to the governed registry that owns the gap and "
            "return its declared steward. Use after a catalogue not-found result when escalation is "
            "needed, and for aggregate questions that version 1 cannot answer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The unresolved topic or out-of-scope question subject.",
                },
            },
            "required": ["topic"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]
