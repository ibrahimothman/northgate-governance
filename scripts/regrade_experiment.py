from __future__ import annotations
import argparse, json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.eval_grader import load_trace, grade_q1, grade_q2, grade_q3, grade_q4
from src.eval_grader_multi import grade_q5, grade_q6, grade_q7, grade_q8

GRADERS = {"Q1":grade_q1,"Q2":grade_q2,"Q3":grade_q3,"Q4":grade_q4,
           "Q5":grade_q5,"Q6":grade_q6,"Q7":grade_q7,"Q8":grade_q8}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input', required=True, help='Experiment directory containing replicate folders 1/2/3')
    ap.add_argument('--output', default='eval/regraded/2026-09-09/14-00-00')
    ap.add_argument('--spec', default='eval/spec.yaml')
    args=ap.parse_args()
    inp=Path(args.input)
    out=ROOT/args.output
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    spec=ROOT/args.spec

    summary={
      'source_experiment': str(inp),
      'evaluator_spec_version': None,
      'agent_changed': False,
      'replicates': 0,
      'pass_rate_by_case': {},
      'pass_rate_by_replicate': {},
      'replicates_detail': [],
    }
    import yaml
    summary['evaluator_spec_version']=yaml.safe_load(spec.read_text())['version']
    per_case={f'Q{i}':0 for i in range(1,9)}
    reps=sorted([p for p in inp.iterdir() if p.is_dir() and p.name.isdigit()], key=lambda p:int(p.name))
    summary['replicates']=len(reps)
    total_pass=0; total_runs=0
    severity_counts={'critical':0,'major':0,'minor':0}
    dimension_passes={d:0 for d in ['outcome','trajectory','governance','citations']}
    outcome_success=0

    for rep in reps:
        rep_out=out/rep.name; rep_out.mkdir()
        detail={'replicate':int(rep.name),'cases_passed':0,'cases_total':8,'results':[]}
        for i in range(1,9):
            qid=f'Q{i}'
            trace_path=rep/f'q{i}_real_run.json'
            trace=load_trace(trace_path)
            grade=GRADERS[qid](trace,spec)
            (rep_out/f'q{i}_grade.json').write_text(json.dumps(grade,indent=2,ensure_ascii=False),encoding='utf-8')
            shutil.copy2(trace_path,rep_out/f'q{i}_real_run.json')
            failed=[c['name'] for c in grade['checks'] if not c['passed']]
            if grade['passed']:
                detail['cases_passed']+=1; per_case[qid]+=1; total_pass+=1
            total_runs+=1
            if grade['dimensions']['outcome']['passed']:
                outcome_success+=1
            for d,s in grade['dimensions'].items():
                if s['passed']: dimension_passes[d]+=1
            sev=grade.get('highest_failure_severity')
            if sev: severity_counts[sev]+=1
            detail['results'].append({
                'case_id':qid,'passed':grade['passed'],'highest_failure_severity':sev,
                'dimensions':{d:{'passed':v['passed']} for d,v in grade['dimensions'].items()},
                'failed_checks':failed,
            })
        summary['pass_rate_by_replicate'][rep.name]=f"{detail['cases_passed']}/8"
        summary['replicates_detail'].append(detail)
    for qid,n in per_case.items(): summary['pass_rate_by_case'][qid]=f'{n}/{len(reps)}'
    summary['strict_runs_passed']=total_pass
    summary['strict_runs_total']=total_runs
    summary['strict_pass_rate']=round(total_pass/total_runs,4)
    summary['outcome_runs_passed']=outcome_success
    summary['outcome_pass_rate']=round(outcome_success/total_runs,4)
    summary['failure_severity_by_run']=severity_counts
    summary['dimension_pass_rate']={d:round(n/total_runs,4) for d,n in dimension_passes.items()}
    summary['pass_at_3_cases']=sum(1 for n in per_case.values() if n>=1)
    summary['pass_at_3_rate']=round(summary['pass_at_3_cases']/8,4)
    summary['pass_power_3_cases']=sum(1 for n in per_case.values() if n==len(reps))
    summary['pass_power_3_rate']=round(summary['pass_power_3_cases']/8,4)
    (out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(summary,indent=2,ensure_ascii=False))

if __name__=='__main__': main()
