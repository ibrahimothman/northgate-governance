from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.eval_grader import load_trace, grade_q2, grade_q3, grade_q4


GRADERS = {
    "Q2": grade_q2,
    "Q3": grade_q3,
    "Q4": grade_q4,
}

DEFAULT_TRACES = {
    "Q2": "eval/fixtures/q2_representative_run.json",
    "Q3": "eval/fixtures/q3_representative_run.json",
    "Q4": "eval/fixtures/q4_representative_run.json",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade Q2-Q4 deterministic agent trajectories.")
    parser.add_argument("case_id", choices=["Q2", "Q3", "Q4"])
    parser.add_argument("--trace", default=None)
    parser.add_argument("--spec", default="eval/spec.yaml")
    args = parser.parse_args()

    trace_path = ROOT / (args.trace or DEFAULT_TRACES[args.case_id])
    result = GRADERS[args.case_id](load_trace(trace_path), ROOT / args.spec)

    out = ROOT / "eval" / f"{args.case_id.lower()}_grade.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{args.case_id}: {'PASS' if result['passed'] else 'FAIL'}")
    for dim, score in result["dimensions"].items():
        print(f"  {dim:10} {'PASS' if score['passed'] else 'FAIL'} ({score['checks_passed']}/{score['checks_total']})")
    print()
    for check in result["checks"]:
        print(f"  {'PASS' if check['passed'] else 'FAIL'} {check['name']} [{check['dimension']}]")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
