from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent_instructions import SYSTEM_INSTRUCTIONS
from src.catalogue_client import LocalClient
from src.openai_agent import CitationIntegrityError, OpenAIGovernanceAgent


DEFAULT_CASE_IDS = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"]


def normalize_experiment_id(value: str) -> str:
    safe_value = value.strip().replace(":", "-")
    try:
        datetime.strptime(safe_value, "%H-%M-%S")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "experiment id must be a time in HH:MM:SS or HH-MM-SS format"
        ) from exc
    return safe_value


def load_cases(spec_path: Path, case_ids: list[str]) -> tuple[list[dict], str | None]:
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    by_id = {case["id"]: case for case in spec["cases"]}
    missing = [case_id for case_id in case_ids if case_id not in by_id]
    if missing:
        raise SystemExit(f"Unknown case ids in spec: {', '.join(missing)}")
    as_of = spec.get("evaluation_context", {}).get("as_of")
    return [by_id[case_id] for case_id in case_ids], as_of


def last_jsonl_record(path: Path) -> dict:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"No records in {path}")
    return json.loads(lines[-1])


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def ask_one(agent: OpenAIGovernanceAgent, question: str) -> dict:
    log_size_before = agent.log_path.stat().st_size if agent.log_path.exists() else 0
    try:
        return agent.ask(question)
    except CitationIntegrityError:
        record = last_jsonl_record(agent.log_path)
        record.setdefault("status", "blocked_invalid_citation")
        return record
    except Exception as exc:
        if agent.log_path.exists() and agent.log_path.stat().st_size > log_size_before:
            record = last_jsonl_record(agent.log_path)
        else:
            record = {
                "question": question,
                "tools_called": [],
                "final_answer": "",
                "status": "error",
            }
        record["status"] = record.get("status") or "error"
        record["error"] = f"{type(exc).__name__}: {exc}"
        if not agent.log_path.exists() or agent.log_path.stat().st_size == log_size_before:
            append_jsonl(agent.log_path, record)
        return record


def run_replicate(
    *,
    replicate: int,
    cases: list[dict],
    log_root: Path,
    date: str,
    experiment_id: str,
    catalogue: Path,
    overwrite: bool,
    benchmark_as_of: str | None,
) -> dict:
    replicate_dir = log_root / date / experiment_id / str(replicate)
    if replicate_dir.exists() and any(replicate_dir.iterdir()):
        if not overwrite:
            raise SystemExit(
                f"{replicate_dir} already contains an experiment. "
                "Use --overwrite or choose another --experiment-id."
            )
        shutil.rmtree(replicate_dir)
    replicate_dir.mkdir(parents=True, exist_ok=True)
    agent_log = replicate_dir / "trajectories.jsonl"
    global_log = ROOT / "logs" / "trajectories.jsonl"

    openai_client = OpenAI()
    if not hasattr(openai_client, "responses"):
        raise SystemExit(
            "The installed OpenAI package does not provide the Responses API. "
            "Run this script with the project virtual environment or upgrade openai."
        )

    agent = OpenAIGovernanceAgent(
        openai_client=openai_client,
        catalogue=LocalClient(catalogue),
        model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
        reasoning_effort=os.getenv("OPENAI_REASONING_EFFORT", "medium"),
        log_path=agent_log,
        instructions=(
            SYSTEM_INSTRUCTIONS
            + (
                "\n\nEVALUATION CONTEXT\n"
                f"This benchmark is frozen as of {benchmark_as_of}. "
                "For every get_registry_health call in this experiment, pass "
                f"`as_of: \"{benchmark_as_of}\"`."
                if benchmark_as_of
                else ""
            )
        ),
    )

    manifest_cases = []
    print(f"\n=== Replicate {replicate} ===")

    for case in cases:
        case_id = case["id"]
        question = case["question"]
        print(f"[{replicate}/{case_id}] {question}")
        record = ask_one(agent, question)
        record["case_id"] = case_id
        record["experiment"] = {
            "date": date,
            "experiment_id": experiment_id,
            "replicate": replicate,
            "case_id": case_id,
            "benchmark_as_of": benchmark_as_of,
        }

        trace_path = replicate_dir / f"{case_id.lower()}_real_run.json"
        write_json(trace_path, record)
        append_jsonl(global_log, record)

        status = record.get("status", "unknown")
        preview = (record.get("final_answer") or "").replace("\n", " ")[:120]
        print(f"  status={status} tools={len(record.get('tools_called') or [])}")
        if preview:
            print(f"  answer: {preview}")

        manifest_cases.append({
            "id": case_id,
            "status": status,
            "file": trace_path.name,
            "error": record.get("error"),
        })

    manifest = {
        "date": date,
        "experiment_id": experiment_id,
        "replicate": replicate,
        "model": agent.model,
        "reasoning_effort": agent.reasoning_effort,
        "benchmark_as_of": benchmark_as_of,
        "cases": manifest_cases,
    }
    write_json(replicate_dir / "manifest.json", manifest)
    return manifest


def main() -> int:
    load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(
        description="Run Q1-Q8 against the live agent three times and log each replicate."
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument(
        "--experiment-id",
        type=normalize_experiment_id,
        help=(
            "Experiment start time in HH:MM:SS or HH-MM-SS format. "
            "Defaults to the current time."
        ),
    )
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--spec", default="eval/spec.yaml")
    parser.add_argument(
        "--cases",
        default=",".join(DEFAULT_CASE_IDS),
        help="Comma-separated case ids. Default: Q1-Q8.",
    )
    parser.add_argument("--catalogue", default="data/catalogue.db")
    parser.add_argument(
        "--log-root",
        default="logs/experiments",
        help="Root directory for per-replicate traces.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing logs for the selected date and replicates.",
    )
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set.")
        return 2

    catalogue = ROOT / args.catalogue
    if not catalogue.exists():
        print(f"Catalogue not found: {catalogue}. Run `make seed` first.")
        return 2

    if args.replicates < 1:
        print("--replicates must be at least 1.")
        return 2

    case_ids = [item.strip().upper() for item in args.cases.split(",") if item.strip()]
    if not case_ids:
        print("--cases must contain at least one case id.")
        return 2
    cases, benchmark_as_of = load_cases(ROOT / args.spec, case_ids)
    log_root = ROOT / args.log_root
    experiment_id = args.experiment_id or datetime.now().strftime("%H-%M-%S")
    experiment_dir = log_root / args.date / experiment_id

    print(
        f"Running {len(cases)} cases x {args.replicates} replicates "
        f"into {experiment_dir}"
    )

    for replicate in range(1, args.replicates + 1):
        run_replicate(
            replicate=replicate,
            cases=cases,
            log_root=log_root,
            date=args.date,
            experiment_id=experiment_id,
            catalogue=catalogue,
            overwrite=args.overwrite,
            benchmark_as_of=benchmark_as_of,
        )

    print(f"\nLogs written to {experiment_dir}/{{1..{args.replicates}}}")
    print(
        f'Next: "{sys.executable}" scripts/grade_agent_experiment.py '
        f"--date {args.date} --experiment-id {experiment_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
