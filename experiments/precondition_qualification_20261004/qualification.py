#!/usr/bin/env python3
"""Qualification workflow: scaffold -> validate -> freeze -> opt-in run -> report.
Only the run subcommand with --execute may send model requests. Standard library.
Private labels/reviews are checked locally; model_gate loads only public/history.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys
from model_gate import ARMS, assert_public, load_json, load_jsonl, sha256, write_json
from score_model_gate import evaluate, expected

ROOT = Path(__file__).parent
FILES = ('public_cases.jsonl', 'history.json', 'evaluator_cases.jsonl', 'incidents.json', 'review.json')
VARIANTS = ('recurrence', 'normal', 'legitimate_neighbor', 'scope_change')
CHECKS = ('sources_verified', 'independent_mechanisms', 'pre_action_only',
          'no_secrets', 'no_hidden_answers_in_public', 'no_future_or_target_outcomes',
          'evaluator_positive_and_negative_tests', 'arm_specific_observability_reviewed')
PLACEHOLDER = '<FILL>'


def dump_lines(path, rows):
    path.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')


def initialize(data):
    if data.exists():
        raise ValueError('Data path exists; refusing to overwrite')
    data.mkdir(parents=True)
    public, private, incidents, history = [], [], [], []
    for family_no in (1, 2):
        family = f'f{family_no}'
        incidents.append(dict(family_id=family, origin='real_incident', mechanism=PLACEHOLDER,
                              source_refs=[PLACEHOLDER], original_task=PLACEHOLDER,
                              pre_action_state=PLACEHOLDER, failure_and_feedback=PLACEHOLDER,
                              repair_and_verification=PLACEHOLDER, legitimate_exception=PLACEHOLDER,
                              current_information_sufficiency=PLACEHOLDER,
                              simple_existing_fix=PLACEHOLDER, verifier_evidence=PLACEHOLDER))
        history.append(dict(episode_id=f'h{family_no}', task=PLACEHOLDER,
                            visible_actions=PLACEHOLDER, observed_feedback=PLACEHOLDER,
                            repair_observation=PLACEHOLDER, source_ref=PLACEHOLDER))
        for offset, variant in enumerate(VARIANTS):
            ident = f'q{(family_no-1)*4+offset+1:03d}'
            public.append(dict(case_id=ident, task=PLACEHOLDER, current_state=PLACEHOLDER,
                               proposed_action=PLACEHOLDER))
            private.append(dict(case={'case_id':ident}, family_id=family, variant=variant,
                                expected_by_arm={a:PLACEHOLDER for a in ARMS},
                                decision_basis=PLACEHOLDER, evidence_refs=[PLACEHOLDER]))
    dump_lines(data/'public_cases.jsonl', public)
    dump_lines(data/'evaluator_cases.jsonl', private)
    write_json(data/'history.json', history)
    write_json(data/'incidents.json', incidents)
    write_json(data/'review.json', dict(approved=False, reviewer=PLACEHOLDER,
               reviewed_at=PLACEHOLDER, checks={k:False for k in CHECKS},
               decision_policy=PLACEHOLDER, cost_scope=PLACEHOLDER))
    print(f'Templates only: {data}. Replace <FILL>; no incidents or labels were fabricated.')


def validate(data):
    for name in FILES:
        text = (data/name).read_text(encoding='utf-8-sig')
        if PLACEHOLDER in text:
            raise ValueError(f'Unfilled template: {name}')
    cases = load_jsonl(data/'public_cases.jsonl')
    history = load_json(data/'history.json')
    truth = load_jsonl(data/'evaluator_cases.jsonl')
    incidents = load_json(data/'incidents.json')
    review = load_json(data/'review.json')
    assert_public(cases)
    assert_public(history)
    ids = [c.get('case_id') for c in cases]
    if len(ids) != 8 or len(set(ids)) != 8 or any(not isinstance(i,str) or not re.fullmatch(r'q\d{3}',i) for i in ids):
        raise ValueError('Pilot requires 8 unique opaque case IDs such as q001')
    for case in cases:
        if set(case) != {'case_id','task','current_state','proposed_action'}:
            raise ValueError('Public case fields must be case_id/task/current_state/proposed_action')
        if any(not str(case[k]).strip() for k in ('task','current_state','proposed_action')):
            raise ValueError('Empty public field')
    if not isinstance(history, list) or len(history) < 2:
        raise ValueError('Provide at least two legitimate historical episodes')
    if len(incidents) != 2 or len({r['family_id'] for r in incidents}) != 2:
        raise ValueError('Require two incident families')
    required = ('mechanism','source_refs','original_task','pre_action_state','failure_and_feedback',
                'repair_and_verification','legitimate_exception','current_information_sufficiency',
                'simple_existing_fix','verifier_evidence')
    for row in incidents:
        if row.get('origin') != 'real_incident' or any(not row.get(k) for k in required):
            raise ValueError('Incident evidence incomplete; synthetic examples are not real incidents')
    if incidents[0]['mechanism'].strip() == incidents[1]['mechanism'].strip():
        raise ValueError('Two renamed copies of one mechanism are not two families')
    families = {r['family_id'] for r in incidents}
    if len(truth) != 8 or {r['case']['case_id'] for r in truth} != set(ids):
        raise ValueError('Evaluator/public IDs must agree exactly')
    coverage = Counter()
    for row in truth:
        if row['family_id'] not in families or row['variant'] not in VARIANTS:
            raise ValueError('Unknown family or variant')
        coverage[row['family_id'], row['variant']] += 1
        if not row.get('decision_basis') or not row.get('evidence_refs'):
            raise ValueError('Each truth decision needs an external basis')
        for arm in ARMS:
            expected(row, arm)
        if expected(row,'history') != expected(row,'preflight'):
            raise ValueError('B/C have identical evidence, so their truth must agree')
        if expected(row,'preflight') == 'inspect':
            raise ValueError('Initial binary gate requires sufficient B/C evidence; keep ambiguous cases outside this pilot')
    if any(coverage[f,v] != 1 for f in families for v in VARIANTS):
        raise ValueError('Each family needs exactly four registered variants')
    for family in families:
        if {expected(r,'history') for r in truth if r['family_id']==family} != {'allow','block'}:
            raise ValueError('Each family needs both legitimate and invalid proposed actions')
    if review.get('approved') is not True or any(review.get('checks',{}).get(k) is not True for k in CHECKS):
        raise ValueError('Manual evidence/privacy/verifier review is not approved')
    if any(not review.get(k) for k in ('reviewer','reviewed_at','decision_policy','cost_scope')):
        raise ValueError('Reviewer and preregistered decision/cost policy required')
    return dict(status='STRUCTURE_AND_ATTESTATIONS_PASS_NOT_SEMANTIC_PROOF',
                cases=8, families=sorted(families), planned_calls=48,
                hashes={n:sha256(data/n) for n in FILES})


def prepare(data, run, model, options_file=None):
    qualified = validate(data)
    if model == 'UNSET' or not model.strip():
        raise ValueError('Freeze the real model ID even for the dry run')
    command = [sys.executable,str(ROOT/'model_gate.py'),'--data',str(data),
               '--run-dir',str(run),'--arm','all','--all-cases','--repeats','2',
               '--max-calls','48','--model',model]
    if options_file:
        command += ['--options-file',str(options_file)]
    subprocess.run(command,check=True)
    write_json(run/'qualification.json',qualified)
    write_json(run/'frozen_options.json',load_json(options_file) if options_file else {})
    write_json(run/'payload_review.json',dict(approved=False,reviewer='',reviewed_at='',
               request_hashes={p.name:sha256(p) for p in sorted(run.glob('*.request.json'))}))
    print('Review ALL request payloads, then fill payload_review.json. No model calls made.')


def execute(data, plan, run, acknowledged):
    if not acknowledged:
        raise ValueError('Explicit --execute required; no request was sent')
    qualified = validate(data)
    if qualified != load_json(plan/'qualification.json'):
        raise ValueError('Data, truth or review changed; create a new frozen plan')
    review = load_json(plan/'payload_review.json')
    if review.get('approved') is not True or not review.get('reviewer') or not review.get('reviewed_at'):
        raise ValueError('Actual payload review has not been approved')
    actual = {p.name:sha256(p) for p in sorted(plan.glob('*.request.json'))}
    if actual != review['request_hashes'] or len(actual) != 48:
        raise ValueError('Reviewed payloads changed or incomplete')
    manifest = load_json(plan/'manifest.json')
    command = [sys.executable,str(ROOT/'model_gate.py'),'--data',str(data),
               '--run-dir',str(run),'--arm','all','--all-cases','--repeats','2',
               '--max-calls','48','--model',manifest['model'],'--options-file',str(plan/'frozen_options.json'),
               '--plan',str(plan),'--execute']
    # Copy the frozen private hash record even if a transport failure stops the run.
    result = subprocess.run(command)
    if (run/'manifest.json').exists():
        write_json(run/'qualification.json',qualified)
        write_json(run/'payload_review.json',review)
    if result.returncode:
        raise SystemExit(result.returncode)


def accept(data, run):
    qualified = validate(data)
    if qualified != load_json(run/'qualification.json'):
        raise ValueError('Frozen qualification data changed; do not rescore with edited labels')
    report = evaluate(data, run)
    write_json(run/'score.json',report)
    lines = ['# 资格检查结果（判定层，不是端到端成功）','',
             f"完整有效响应：{report['technical_complete']}；计划 {report['planned']}，收到 {report['received']}，缺失 {report['missing']}。",'',
             '| 组 | 计划 | 有效 | 漏拦 | 误拦 | inspect | 匹配判定 |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for arm in ARMS:
        c = report['by_arm'].get(arm,{})
        lines.append('| '+arm+' | '+' | '.join(str(c.get(k,0)) for k in
                     ('planned','valid_outputs','missed_unsafe','false_blocks','inspect','matched_decision'))+' |')
    lines += ['', 'inspect 即使有合理依据也不表示任务完成。原始证据见请求/响应；按族分项与逐题结果见 score.json。',
              '', '## 人工判定（必须补充证据，脚本不自动给研究 GO）',
              '- 当前组的信息是否充分？对应来源：',
              '- C 组重复错误是否属于适用条件，而非格式/接口/评分问题？',
              '- 是否涉及两个独立机制？重复失败列表只是候选，不是因果证明。',
              '- 决定：停止 / 修数据或接口 / 采用简单方案 / 进入有限端到端验证 / 转成本假设。',
              '- 判定人、证据位置、下一阶段上限：', '',
              '下一阶段不得自动启动。缺失、错误响应和未知费用必须保留。']
    (run/'资格检查结果.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'Report: {run}/资格检查结果.md; no automatic research acceptance.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('init','check','prepare','run','accept'))
    parser.add_argument('--data',type=Path,default=ROOT/'.local/cases')
    parser.add_argument('--run-dir',type=Path)
    parser.add_argument('--plan',type=Path)
    parser.add_argument('--model',default='UNSET')
    parser.add_argument('--options-file',type=Path)
    parser.add_argument('--execute',action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'init': initialize(args.data)
        elif args.command == 'check': print(json.dumps(validate(args.data),ensure_ascii=False,indent=2))
        elif args.command == 'prepare':
            if args.run_dir is None: raise ValueError('--run-dir required')
            prepare(args.data,args.run_dir,args.model,args.options_file)
        elif args.command == 'run':
            if args.plan is None or args.run_dir is None: raise ValueError('--plan and --run-dir required')
            execute(args.data,args.plan,args.run_dir,args.execute)
        else:
            if args.run_dir is None: raise ValueError('--run-dir required')
            accept(args.data,args.run_dir)
    except (ValueError,KeyError,TypeError,OSError,subprocess.CalledProcessError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
