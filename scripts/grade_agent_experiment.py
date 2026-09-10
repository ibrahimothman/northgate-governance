from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.eval_grader import grade_q1, grade_q2, grade_q3, grade_q4, load_trace
from src.eval_grader_multi import grade_q5, grade_q6, grade_q7, grade_q8


DEFAULT_CASE_IDS = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"]
GRADERS = {
    "Q1": grade_q1,
    "Q2": grade_q2,
    "Q3": grade_q3,
    "Q4": grade_q4,
    "Q5": grade_q5,
    "Q6": grade_q6,
    "Q7": grade_q7,
    "Q8": grade_q8,
}


def normalize_experiment_id(value: str) -> str:
    safe_value = value.strip().replace(":", "-")
    try:
        datetime.strptime(safe_value, "%H-%M-%S")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "experiment id must be a time in HH:MM:SS or HH-MM-SS format"
        ) from exc
    return safe_value


def latest_experiment_id(date_dir: Path) -> str:
    candidates = []
    if date_dir.exists():
        for path in date_dir.iterdir():
            if not path.is_dir():
                continue
            try:
                candidates.append(normalize_experiment_id(path.name))
            except argparse.ArgumentTypeError:
                continue
    if not candidates:
        raise SystemExit(
            f"No timestamped experiments found in {date_dir}. "
            "Pass --experiment-id explicitly."
        )
    return max(candidates)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def copy_replicate(src: Path, dest: Path, case_ids: list[str]) -> list[Path]:
    if not src.exists():
        raise SystemExit(f"Missing source replicate directory: {src}")

    missing = [
        f"{case_id.lower()}_real_run.json"
        for case_id in case_ids
        if not (src / f"{case_id.lower()}_real_run.json").exists()
    ]
    if missing:
        raise SystemExit(
            f"Incomplete replicate {src}; missing: {', '.join(missing)}"
        )

    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for path in sorted(src.iterdir()):
        if path.suffix not in {".json", ".jsonl"}:
            continue
        target = dest / path.name
        shutil.copy2(path, target)
        copied.append(target)
    if not copied:
        raise SystemExit(f"No log files found in {src}")
    return copied


def grade_replicate(dest: Path, spec_path: Path, case_ids: list[str]) -> dict:
    results = []
    print(f"\n=== {dest.relative_to(ROOT)} ===")
    for case_id in case_ids:
        trace_path = dest / f"{case_id.lower()}_real_run.json"
        grader = GRADERS.get(case_id)
        if grader is None:
            raise SystemExit(f"No grader registered for {case_id}")

        grade = grader(load_trace(trace_path), spec_path)
        grade_path = dest / f"{case_id.lower()}_grade.json"
        write_json(grade_path, grade)

        passed = bool(grade.get("passed"))
        dims = grade.get("dimensions") or {}
        dim_bits = " ".join(
            f"{name[0]}={'P' if score['passed'] else 'F'}"
            for name, score in dims.items()
        )
        severity = grade.get("highest_failure_severity") or "-"
        print(f"  {case_id}: {'PASS' if passed else 'FAIL'}  {dim_bits}  sev={severity}")
        results.append({
            "case_id": case_id,
            "passed": passed,
            "highest_failure_severity": grade.get("highest_failure_severity"),
            "dimensions": {
                name: {"passed": score["passed"]}
                for name, score in dims.items()
            },
            "failed_checks": [
                check["name"]
                for check in grade.get("checks", [])
                if not check.get("passed")
            ],
            "grade_file": grade_path.name,
            "trace_file": trace_path.name,
        })

    passed_count = sum(1 for item in results if item["passed"])
    summary = {
        "replicate_dir": str(dest.relative_to(ROOT)).replace("\\", "/"),
        "cases_passed": passed_count,
        "cases_total": len(results),
        "results": results,
    }
    write_json(dest / "summary.json", summary)
    print(f"  replicate: {passed_count}/{len(results)} passed")
    return summary


def summarize_experiment(experiment_dir: Path, replicate_summaries: list[dict]) -> dict:
    case_ids = []
    for summary in replicate_summaries:
        for item in summary["results"]:
            if item["case_id"] not in case_ids:
                case_ids.append(item["case_id"])

    pass_rate_by_case = {}
    for case_id in case_ids:
        scores = [
            item["passed"]
            for summary in replicate_summaries
            for item in summary["results"]
            if item["case_id"] == case_id
        ]
        pass_rate_by_case[case_id] = f"{sum(scores)}/{len(scores)}"

    payload = {
        "experiment_dir": str(experiment_dir.relative_to(ROOT)).replace("\\", "/"),
        "experiment_id": experiment_dir.name,
        "replicates": len(replicate_summaries),
        "pass_rate_by_case": pass_rate_by_case,
        "pass_rate_by_replicate": {
            str(index + 1): f"{summary['cases_passed']}/{summary['cases_total']}"
            for index, summary in enumerate(replicate_summaries)
        },
        "replicates_detail": replicate_summaries,
    }
    write_json(experiment_dir / "summary.json", payload)

    print("\n=== Experiment summary ===")
    print("By replicate:")
    for key, value in payload["pass_rate_by_replicate"].items():
        print(f"  {key}: {value}")
    print("By case:")
    for case_id, value in pass_rate_by_case.items():
        print(f"  {case_id}: {value}")
    print(f"\nWrote {experiment_dir / 'summary.json'}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Copy logs into eval/experiments/<date>/<time>/<n> and grade Q1-Q8."
        )
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument(
        "--experiment-id",
        type=normalize_experiment_id,
        help=(
            "Experiment time in HH:MM:SS or HH-MM-SS format. "
            "Defaults to the latest experiment for the selected date."
        ),
    )
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--spec", default="eval/spec.yaml")
    parser.add_argument("--log-root", default="logs/experiments")
    parser.add_argument("--eval-root", default="eval/experiments")
    parser.add_argument(
        "--cases",
        default=",".join(DEFAULT_CASE_IDS),
        help="Comma-separated case ids. Default: Q1-Q8.",
    )
    args = parser.parse_args()

    if args.replicates < 1:
        print("--replicates must be at least 1.")
        return 2

    spec_path = ROOT / args.spec
    log_date_dir = ROOT / args.log_root / args.date
    experiment_id = args.experiment_id or latest_experiment_id(log_date_dir)
    log_root = log_date_dir / experiment_id
    eval_root = ROOT / args.eval_root / args.date / experiment_id
    case_ids = [item.strip().upper() for item in args.cases.split(",") if item.strip()]
    if not case_ids:
        print("--cases must contain at least one case id.")
        return 2
    unknown = [case_id for case_id in case_ids if case_id not in GRADERS]
    if unknown:
        print(f"No grader registered for: {', '.join(unknown)}")
        return 2
    replicate_summaries = []

    for replicate in range(1, args.replicates + 1):
        src = log_root / str(replicate)
        dest = eval_root / str(replicate)
        copied = copy_replicate(src, dest, case_ids)
        print(f"Copied {len(copied)} files -> {dest.relative_to(ROOT)}")
        replicate_summaries.append(grade_replicate(dest, spec_path, case_ids))

    summarize_experiment(eval_root, replicate_summaries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
