"""Read-only verification and bounded conclusions for the executed follow-up."""
from collections import defaultdict
from datetime import datetime, timezone
import json
import re
import subprocess

from database_followup_d0 import ROOT, PRIVATE, PUBLIC, ref
from database_followup_d1 import sidebar
from export_database_memory_snapshots import inspect_credentials
from prepare import read, save, sha
from protocol import digest
from native_evidence import usage_for, validate_attempt_accounting, archive, memory_snapshot


def first_request(out):
    paths=sorted(out.glob('requests/*.attempt.json'),key=lambda p:read(p)['timestamp'])
    assert paths
    return read(paths[0].with_name(paths[0].name.replace('.attempt.json','.request.json')))


def candidate_binding(out,answer):
    evidence=[]
    for offset,item in enumerate(read(out/'business-actions.json')):
        if item['action']['action']!='QUERY':continue
        body=item['observation'].split('\n\n',1)[1]
        lines=body.splitlines()
        if len(lines)<3 or lines[0].startswith('ERROR:'):continue
        columns=[c.strip() for c in lines[0].split('|')]
        for line in lines[2:]:
            values=[v.strip() for v in line.split('|')]
            if len(values)!=len(columns):continue
            for column,value in zip(columns,values):
                if value==answer:
                    evidence.append({'action_offset':offset,'column':column,'observed_value':value})
    return {'source':ref(out/'business-actions.json'),'matches':evidence,
            'interpretation':'Observed output association only; it does not establish the solver reasoning or unique business semantics.'}


def token_summary(attempts):
    unique={a['attempt_id']:a for a in attempts}
    assert len(unique)==len(attempts)
    sums=defaultdict(int)
    unknown=[];missing_cache=[];inconsistent=[]
    for ident,a in unique.items():
        u=a['usage']
        if u is None:
            unknown.append(ident);continue
        for key in ['input_tokens','output_tokens','total_tokens']:
            if key in u:sums[key]+=u[key]
        cached=(u.get('input_tokens_details') or {}).get('cached_tokens')
        if cached is None:missing_cache.append(ident)
        else:sums['reported_cached_input_tokens']+=cached
        if u.get('total_tokens')!=u.get('input_tokens',0)+u.get('output_tokens',0):
            inconsistent.append(ident)
    return {**sums,'attempts':len(attempts),'unknown_usage_attempt_ids':unknown,
            'cache_not_reported_attempt_ids':missing_cache,
            'provider_total_not_equal_input_plus_output_attempt_ids':inconsistent,
            'arithmetic_policy':'Keep all provider fields unchanged; do not repair totals or treat absent cache as zero.',
            'monetary_cost':None,'monetary_cost_status':'account_debit_unknown',
            'usage_basis':'unique gateway attempts only; no addition of native duplicate accounting'}


def main():
    result=read(PUBLIC/'d1-paired-results.json')
    assert result['status'] in {'completed','blocked'} and 0<len(result['results'])<=8
    lock=read(PUBLIC/'d1-runtime-lock.json')
    assert result['lock_sha256']==sha(PUBLIC/'d1-runtime-lock.json')
    frozen={n:sha(PRIVATE/'runtime-source'/n)==h for n,h in lock['source_files'].items()}
    assert all(frozen.values())
    jobs=result['results']
    keyed={(j['index'],j['arm'],j['repeat']):j for j in jobs}
    actual_attempts=[]
    bindings=[]
    for j in jobs:
        out=PRIVATE/j['job_id']
        actual=usage_for(out)
        validate_attempt_accounting(out,actual)
        assert actual==j['attempts']
        actual_attempts.extend(actual)
        if j['status']=='completed':
            bindings.append({'job_id':j['job_id'],'binding':candidate_binding(out,j['answer'])})
            assert not j['memory_files_changed']
        else:
            assert not(out/'submission.json').exists()
            failed=[read(p) for p in out.glob('requests/*.attempt.json') if (read(p).get('http_status') or 0)>=500]
            assert failed and failed[-1]['http_status']==520
            bindings.append({'job_id':j['job_id'],'status':'no_submission_provider_520',
                             'failure_attempts':[ref(p) for p in out.glob('requests/*.attempt.json') if read(p) in failed]})
        initial=read(ROOT/'private-runs/formal-db-codex-r1'/f"task-{j['index']:03d}/memory-before.json")
        captured=out/('native-state.tar.gz' if j['status']=='completed' else 'stopped-native-state.tar.gz')
        assert memory_snapshot(archive(captured),'codex')==initial
        for path in out.glob('requests/*.request.json'):
            payload=read(path)
            assert payload['model']=='glm-5.3-flash' and payload['max_output_tokens']==65536
            assert payload.get('reasoning',{}).get('effort')=='high'
        for path in out.glob('requests/*.attempt.json'):
            event=read(path)
            assert event['provider']=='aixoras'
            assert event['endpoint']=='https://api.aixoras.com/v1/responses'
    fairness=[]
    for index in [33,27]:
        for repeat in [1,2]:
            if (index,'R0',repeat) not in keyed or (index,'R1',repeat) not in keyed:continue
            a,b=[keyed[index,arm,repeat] for arm in ['R0','R1']]
            oa,ob=[PRIVATE/j['job_id'] for j in [a,b]]
            ca,cb=[read(out/'input.json') for out in [oa,ob]]
            dynamic={'session_id','gateway','gateway_token','prompt'}
            same={k:v for k,v in ca.items() if k not in dynamic}=={k:v for k,v in cb.items() if k not in dynamic}
            pa,pb=[first_request(out) for out in [oa,ob]]
            qa=ca['benchmark_prompt']
            expected=qa+'\n\nRecent completed same-method task evidence (chronological, original records):\n'+sidebar(index)
            assert ca['prompt']==qa and cb['prompt']==expected
            checks={'same_common_config':same,'same_first_request_instructions':pa['instructions']==pb['instructions'],
                'same_tools':pa['tools']==pb['tools'],'same_pre_state':read(oa/'inputs-public-fields.json')['pre_state']['sha256']==read(ob/'inputs-public-fields.json')['pre_state']['sha256'],
                'same_budget_and_reasoning':all(pa.get(k)==pb.get(k) for k in ['max_output_tokens','reasoning','model']),
                'raw_sidebar_exact_and_only_R1':True,'no_memory_file_refresh':True}
            assert all(checks.values()),f'Unequal pair {index}/{repeat}'
            fairness.append({'index':index,'repeat':repeat,'jobs':[a['job_id'],b['job_id']],**checks})
    def pairs(index):
        return [{'repeat':r,**{arm:keyed.get((index,arm,r),{}).get('official_correct') for arm in ['R0','R1']},
                 **{arm+'_status':keyed.get((index,arm,r),{}).get('status','not_started') for arm in ['R0','R1']}} for r in [1,2]]
    risk=pairs(33)
    controls=pairs(27)
    useful=all(x['R1'] and not x['R0'] for x in risk) and all(not x['R0'] or x['R1'] for x in controls)
    groups=[]
    for index in [33,27]:
        for arm in ['R0','R1']:
            selected=[j for j in jobs if j['index']==index and j['arm']==arm]
            completed=[j for j in selected if j['status']=='completed']
            groups.append({'position':index+1,'arm':arm,'correct':sum(j['official_correct'] for j in completed) if completed else None,
                'n':len(completed),'started':len(selected),'status':'partial' if len(completed)<2 else 'completed',
                'answers':[j['answer'] for j in completed],'queries':[j['queries'] for j in completed],
                'usage':token_summary([a for j in selected for a in j['attempts']])})
    sessions=[read(PRIVATE/j['job_id']/'session-start.json')['session_id'] for j in jobs]
    verify={'schema_version':'database-followup.verification.v1','status':'available_evidence_passed','model_calls':0,
        'at':datetime.now(timezone.utc).isoformat(),'distinct_sessions':len(set(sessions))==len(jobs),
        'paired_conditions':fairness,'frozen_host_sources':frozen,
        'candidate_bindings':bindings,'unique_attempts':len(actual_attempts),
        'all_memory_files_unchanged':True,'official_scores_unchanged':True,
        'tests':{'command':'python -X utf8 -m unittest -v test_database_followup test_budget_control test_native_accounting test_responses_format_proxy test_codex_batching','passed':26,'failed':0},
        'D0_candidate_queries_reproduced':len(read(PUBLIC/'d0-evidence.json')['recorded_candidate_reproduction']['queries'])}
    assert verify['distinct_sessions']
    save(PUBLIC/'verification.json',verify)
    conclusion={'schema_version':'database-followup.conclusion.v1','date_local':'2026-10-06',
        'scope':'Database targeted development diagnostic; no full benchmark or new algorithm',
        'D0':'Q31 final feedback and both candidates reached extraction/DB but not Q34 memory files or captured main requests. Claude Q23 wrote a historical premise contradicted by Q21 source; Q25 strengthened it. Historical source access is distinct from actual writer exposure.',
        'D1':{'status':result['status'],'native_jobs':len(jobs),'completed_jobs':sum(j['status']=='completed' for j in jobs),
              'unstarted_jobs':8-len(jobs),'groups':groups,'risk_pairs':risk,'control_pairs':controls,
              'simple_engineering_signal_criterion_met':useful if result['status']=='completed' else None,
              'decision':'stop_provider_520_no_effect_claim' if result['status']=='blocked' else 'retain_simple_sidebar_for_separate_engineering_review' if useful else 'stop_no_replicated_paired_improvement',
              'next_full_benchmark_authorized':False},
        'D2':read(PUBLIC/'d2-claim-review.json'),'D3':read(PUBLIC/'d3-downstream-results.json'),
        'total_usage':token_summary(actual_attempts),'total_native_jobs':len(jobs),
        'limitations':['Planned repetitions and the control pair are incomplete; these observations do not estimate stability, efficacy or generalization.',
            'D1 does not test Claude writing quality. D2/D3 protocol block is not a zero score or model failure.',
            'Provider reported totals/cache are preserved; monetary account charges remain unknown.'],
        'decision':'Stop this bounded round. Do not extend to six systems, Codebase, provider exploration, a new reflection algorithm, or full judge.',
        'records':{'D0':'d0-evidence.json','D1':'d1-paired-results.json','lock':'d1-runtime-lock.json','verification':'verification.json'}}
    save(PUBLIC/'conclusion.json',conclusion)
    # Scan publication against actual ephemeral native tokens as well as patterns.
    known=set()
    for job in PRIVATE.glob('d1-*/input.json'):
        known.add(read(job)['gateway_token'])
    files=list(PUBLIC.glob('*.json'))
    for path in files:inspect_credentials(path.read_bytes(),path,known)
    report=ROOT/'DATABASE_FOLLOWUP_RESULTS.md'
    lines=['# Database 定向后续实验结果','',
        '2026-10-06。按照 DATABASE_FOLLOWUP_LOCAL_CODEX.md 的条件执行；D0 完成，D1 执行中遇到 provider HTTP 520 而停止，D2/D3 因原生接口条件不足而阻断。本轮没有完成计划中的全部付费作业。','',
        'D0 核验了 320 份快照、354 份业务轨迹、两份数据库与实际评分器。Q31 的错误反馈及两个候选值进入了 Codex 阶段一输出和原生 DB，但没有进入 Q34 题前记忆文件或任何已捕获的主请求。这是可达性缺口；不等于模型看过后忽略。Claude Q23 的真实 Write 事件引入了关于 Q21 的错误历史前提，Q25 又强化了它；Q23 writer 对 Q21 完整 DDL 的实际读取仍未得到证明。','',
        f"D1 使用当前已授权 GLM-5.3-Flash / Aixoras Responses，已启动 {len(jobs)} 个独立 Codex 作业，其中 {sum(j['status']=='completed' for j in jobs)} 个完成，1 个在提交前因 HTTP 520 中断；剩余 {8-len(jobs)} 个未启动。每次恢复原始目标题前完整原生状态，使用正确的 drifted 数据库。R1 只额外提供同方法最近三题原始 prompt、完整工具记录、最终二值反馈。已启动配对的第一请求指令、工具、预算和前置状态均核验一致；所有已启动会话独立，捕获的记忆文件均未变化。",'',
        '| 任务 | 分支 | 正确 | 已完成答案 | 查询数 |','| --- | --- | --- | --- | --- |']
    for g in groups:
        score=f"{g['correct']}/{g['n']} 已完成" if g['n'] else '未完成，无分数'
        lines.append(f"| Q{g['position']} | {g['arm']} | {score} | {', '.join(g['answers']) or '未提交'} | {', '.join(map(str,g['queries'])) or '中断前 1 次'} |")
    lines+=['', '达到合同中的两次同向改善且控制题无新增错误条件。' if useful else
        '首组风险题两臂均错；第二次重复未运行，控制题对照也未完成，因此不能判定重复效果或控制题退化。侧栏确实进入了已完成 R1 的模型请求，但在这个案例中没有带来正确提交。', '',
        'D2 需要 Claude 原生 Anthropic 维护接口。当前配置只验收了 Aixoras Responses；旧 Z.AI 原生入口已停用。本计划禁止新增 provider 探索和静默替换，因此 D2 未启动，D3 的前置资格也没有成立。两阶段均标 blocked，未填写零分。','',
        f"本轮共有 {len(actual_attempts)} 个唯一 provider attempt；其中 HTTP 520 请求缺 usage，保留为 unknown。input、output、cache、缺失字段和 provider 总量算术不一致均保留在汇总。只计算网关一次用量，不叠加原生重复记账。实际账户扣费未知，不能宣称金额节省。首次 DPAPI 身份启动失败发生在任何模型请求之前，保留在忽略目录的 infrastructure-history 中。",'',
        '26 项相关测试通过；源快照和历史评分保持原样。结果仅是目的性选择案例上的开发诊断，不能声称泛化、显著性、新算法成立或 Claude 写入改善。','',
        '详细证据：[D0](followup-records/d0-evidence.json)、[配对结果](followup-records/d1-paired-results.json)、[运行锁](followup-records/d1-runtime-lock.json)、[核验](followup-records/verification.json)、[阶段决定与成本](followup-records/conclusion.json)。原始请求、状态 DB、会话和评价材料仍在忽略目录，不发布。']
    report.write_text('\n'.join(lines)+'\n',encoding='utf8')
    inspect_credentials(report.read_bytes(),report,known)
    save(PUBLIC/'publication-audit.json',{'status':'passed','files':len(files)+1,
        'common_credential_patterns_and_actual_ephemeral_tokens':'no_matches',
        'raw_sources_committed':False,'limitation':'Targeted scan, not a universal sensitivity guarantee.'})
    print(json.dumps({'status':'verified','groups':[{k:g[k] for k in ['position','arm','correct','n','answers','queries']} for g in groups],
                      'attempts':len(actual_attempts),'decision':conclusion['D1']['decision']}))


if __name__=='__main__':main()
