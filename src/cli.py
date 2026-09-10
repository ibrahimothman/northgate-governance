from __future__ import annotations

import argparse
from dotenv import load_dotenv
import os
from pathlib import Path

from openai import OpenAI

from src.catalogue_client import LocalClient
from src.openai_agent import CitationIntegrityError, OpenAIGovernanceAgent

load_dotenv()


def build_agent() -> OpenAIGovernanceAgent:
    model = os.getenv("OPENAI_MODEL", "gpt-5.6")
    reasoning_effort = os.getenv("OPENAI_REASONING_EFFORT", "medium")

    return OpenAIGovernanceAgent(
        openai_client=OpenAI(),
        catalogue=LocalClient(Path("data/catalogue.db")),
        model=model,
        reasoning_effort=reasoning_effort,
        log_path=Path("logs/trajectories.jsonl"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Northgate governed catalogue agent")
    parser.add_argument(
        "question",
        nargs="*",
        help="Ask one question non-interactively. Omit to enter interactive mode.",
    )
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set.")
        return 2

    agent = build_agent()

    if args.question:
        question = " ".join(args.question)
        try:
            result = agent.ask(question)
        except CitationIntegrityError as exc:
            print(f"Answer blocked by citation-integrity guard: {exc}")
            return 3
        print(result["final_answer"])
        return 0

    print("Northgate governed catalogue agent")
    print("Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            question = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            return 0

        try:
            result = agent.ask(question)
            print(f"\nAgent> {result['final_answer']}\n")
        except CitationIntegrityError as exc:
            print(f"\nAgent> Answer blocked by citation-integrity guard: {exc}\n")
        except Exception as exc:
            print(f"\nAgent error: {type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
