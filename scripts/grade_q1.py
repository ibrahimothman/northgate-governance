from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.eval_grader import grade_q1, load_trace


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade a Q1 agent trajectory.")
    parser.add_argument("--trace", default="eval/fixtures/q1_real_run.json")
    parser.add_argument("--spec", default="eval/spec.yaml")
    parser.add_argument("--output", default="eval/q1_grade.json")
    args = parser.parse_args()

    result = grade_q1(load_trace(ROOT / args.trace), ROOT / args.spec)
    out = ROOT / args.output
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Q1: {'PASS' if result['passed'] else 'FAIL'}")
    for dim, score in result["dimensions"].items():
        print(f"  {dim:10} {'PASS' if score['passed'] else 'FAIL'} ({score['checks_passed']}/{score['checks_total']})")
    print()
    for check in result["checks"]:
        print(f"  {'PASS' if check['passed'] else 'FAIL'} {check['name']} [{check['dimension']}]")
    print(f"\nDetailed grade: {out}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
