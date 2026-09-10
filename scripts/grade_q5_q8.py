from pathlib import Path
import argparse, json, sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.eval_grader import load_trace
from src.eval_grader_multi import grade_q5,grade_q6,grade_q7,grade_q8
G={'Q5':grade_q5,'Q6':grade_q6,'Q7':grade_q7,'Q8':grade_q8}
D={q:f'eval/fixtures/{q.lower()}_representative_run.json' for q in G}
p=argparse.ArgumentParser(); p.add_argument('case_id',choices=G); p.add_argument('--trace'); a=p.parse_args()
r=G[a.case_id](load_trace(ROOT/(a.trace or D[a.case_id])),ROOT/'eval/spec.yaml')
out=ROOT/'eval'/f'{a.case_id.lower()}_grade.json'; out.write_text(json.dumps(r,indent=2,ensure_ascii=False))
print(f"{a.case_id}: {'PASS' if r['passed'] else 'FAIL'}")
for d,s in r['dimensions'].items(): print(f"  {d:10} {'PASS' if s['passed'] else 'FAIL'} ({s['checks_passed']}/{s['checks_total']})")
for c in r['checks']: print(f"  {'PASS' if c['passed'] else 'FAIL'} {c['name']} [{c['dimension']}]")
raise SystemExit(0 if r['passed'] else 1)
