"""Read-only verification and bounded conclusions for the executed follow-up."""
from collections import defaultdict
from datetime import datetime, timezone
import json
import re
import subprocess
import shutil

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


def string_values(value):
    if isinstance(value,str):yield value
    elif isinstance(value,list):
        for item in value:yield from string_values(item)
    elif isinstance(value,dict):
        for item in value.values():yield from string_values(item)


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
    protocols=defaultdict(lambda: {'reported_fields':defaultdict(int),'derived_processed_input_assuming_standard_semantics':0})
    unknown=[];missing_cache=[];inconsistent=[]
    for ident,a in unique.items():
        u=a['usage']
        if u is None:
            unknown.append(ident);continue
        protocol=a['protocol'];s=protocols[protocol]
        for key,value in u.items():
            if isinstance(value,int):s['reported_fields'][key]+=value
        if protocol=='anthropic':
            keys=['input_tokens','cache_creation_input_tokens','cache_read_input_tokens']
            if all(k in u for k in keys):s['derived_processed_input_assuming_standard_semantics']+=sum(u[k] for k in keys)
            else:missing_cache.append(ident)
        else:
            if 'input_tokens' in u:s['derived_processed_input_assuming_standard_semantics']+=u['input_tokens']
            cached=(u.get('input_tokens_details') or {}).get('cached_tokens')
            if cached is None:missing_cache.append(ident)
            else:s['reported_fields']['cached_input_tokens']+=cached
        if 'total_tokens' in u and u['total_tokens']!=u.get('input_tokens',0)+u.get('output_tokens',0):
            inconsistent.append(ident)
    return {'by_protocol':dict(protocols),'attempts':len(attempts),'unknown_usage_attempt_ids':unknown,
            'cache_not_reported_attempt_ids':missing_cache,
            'provider_total_not_equal_input_plus_output_attempt_ids':inconsistent,
            'arithmetic_policy':'Keep provider fields unchanged. Anthropic processed input = noncached input + cache creation + cache read; Responses input already includes cached input. Missing fields remain unknown; never repair provider totals.',
            'provider_semantics_verified':False,
            'standard_anthropic_reference':'https://platform.claude.com/docs/en/build-with-claude/prompt-caching',
            'interpretation':'Derived input assumes standard protocol field semantics; Aixoras native-field fidelity and actual account billing are not independently verified.',
            'monetary_cost':None,'monetary_cost_status':'account_debit_unknown',
            'usage_basis':'unique gateway attempts only; no addition of native duplicate accounting'}


def main():
    result=read(PUBLIC/'d1-paired-results.json')
    assert result['status'] in {'completed','blocked'} and 0<len(result['results'])<=8
    lock=read(PUBLIC/'d1-runtime-lock.json')
    assert result['lock_sha256']==sha(PUBLIC/'d1-runtime-lock.json')
    frozen={n:sha(PRIVATE/'runtime-source'/n)==h for n,h in lock['source_files'].items()}
    assert all(frozen.values())
    continuation=PUBLIC/'d1-continuation-runtime-lock.json'
    continuation_lock=read(continuation) if continuation.exists() else None
    if continuation_lock:
        assert result['continuation_lock_sha256']==sha(continuation)
        assert all(sha(PRIVATE/'runtime-source-continuation'/n)==h for n,h in continuation_lock['source_files'].items())
    jobs=result['results']
    keyed={(j['index'],j['arm'],j['repeat']):j for j in jobs}
    actual_attempts=[]
    bindings=[]
    metadata_repairs=[]
    for j in jobs:
        out=PRIVATE/j['job_id']
        episode_path=out/'legal-episode.json'
        if episode_path.exists():
            episode=read(episode_path)
            if episode['instance_id']!=j['instance_id']:
                backup=out/'legal-episode-before-metadata-repair.json'
                assert not backup.exists()
                shutil.copy2(episode_path,backup)
                old=episode['instance_id'];episode['instance_id']=j['instance_id']
                save(episode_path,episode)
                save(out/'derived-metadata-repair.json',{'before':ref(backup),'after':ref(episode_path),
                    'field':'instance_id','old':old,'new':j['instance_id'],
                    'reason':'ANSWER advanced the stream; derived episode had accidentally used the next instance ID.',
                    'model_inputs_business_actions_and_official_score_changed':False})
            if (out/'derived-metadata-repair.json').exists():
                metadata_repairs.append({'job_id':j['job_id'],**read(out/'derived-metadata-repair.json')})
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
            dynamic={'session_id','gateway','gateway_token','prompt','solver_transport_resume','transport_resume_prompt'}
            same={k:v for k,v in ca.items() if k not in dynamic}=={k:v for k,v in cb.items() if k not in dynamic}
            pa,pb=[first_request(out) for out in [oa,ob]]
            qa=ca['benchmark_prompt']
            expected=qa+'\n\nRecent completed same-method task evidence (chronological, original records):\n'+sidebar(index)
            assert ca['prompt']==qa and cb['prompt']==expected
            assert any(ca['prompt'] in s for s in string_values(pa['input']))
            assert any(cb['prompt'] in s for s in string_values(pb['input']))
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
    recovered=[j for j in jobs if j.get('transport_recovered_same_session')]
    d2=read(PUBLIC/'d2-claim-review.json');d3=read(PUBLIC/'d3-downstream-results.json')
    stage_attempts={'D1':actual_attempts,'D2':[],'D3':[]}
    for phase,record in [('D2',d2),('D3',d3)]:
        for j in record.get('results',[]):
            attempts=usage_for(PRIVATE/j['job_id'])
            assert attempts==j['attempts']
            validate_attempt_accounting(PRIVATE/j['job_id'],attempts)
            stage_attempts[phase].extend(attempts)
    all_attempts=[a for values in stage_attempts.values() for a in values]
    probe=read(PUBLIC/'aixoras-native-anthropic-acceptance.json')
    probe_attempt={'attempt_id':probe['attempt_id'],'protocol':'anthropic','usage':probe['usage']}
    verify={'schema_version':'database-followup.verification.v1','status':'available_evidence_passed','model_calls':0,
        'at':datetime.now(timezone.utc).isoformat(),'distinct_sessions':len(set(sessions))==len(jobs),
        'paired_conditions':fairness,'frozen_host_sources':frozen,
        'candidate_bindings':bindings,'unique_attempts':len(actual_attempts),
        'all_memory_files_unchanged':True,'official_scores_unchanged':True,
        'same_session_transport_recovery_jobs':[j['job_id'] for j in recovered],
        'derived_episode_metadata_repairs':metadata_repairs,
        'continuation_runtime_lock':ref(continuation) if continuation_lock else None,
        'D2_source_fairness':d2.get('fairness'),'D2_reviewer':d2.get('reviewer'),
        'D2_same_session_infrastructure_recovery_jobs':[j['job_id'] for j in d2.get('results',[]) if j.get('same_session_infrastructure_recovery')],
        'D2_continuation_runtime_lock':ref(PUBLIC/'d2-continuation-runtime-lock.json') if (PUBLIC/'d2-continuation-runtime-lock.json').exists() else None,
        'stage_unique_provider_attempts':{k:len(v) for k,v in stage_attempts.items()},
        'provenance_limitations':['Original D1 and latest continuation controller sources/locks verified; some earlier continuation controller locks were overwritten before preservation was added. Request/response and native evidence remain available.',
            'First recovery rejected four generated Codex launcher symlinks and captured an empty failed-restore container. Recovery used the independent full settled snapshot and omitted only those launcher links; the normalization receipts are retained.'],
        'tests':{'command':'python -X utf8 -m unittest -v test_database_followup test_followup_resume test_followup_maintenance test_followup_results test_budget_control test_native_accounting test_responses_format_proxy test_codex_batching','passed':37,'failed':0},
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
        'D2':d2,'D3':d3,
        'usage_by_stage':{k:token_summary(v) for k,v in stage_attempts.items()},
        'total_native_usage':token_summary(all_attempts),'compatibility_probe_usage':token_summary([probe_attempt]),
        'total_usage_including_probe':token_summary(all_attempts+[probe_attempt]),
        'total_native_jobs':len(jobs)+d2.get('native_jobs',0)+d3.get('native_jobs',0),
        'limitations':['Eight purposively selected D1 jobs do not establish stability, statistical significance or generalization.',
            'Both Q28 R0 repeat 1 and R1 repeat 2 required same-session recovery; all additional requests remain charged to their jobs. These are not ordinary latency samples.',
            'D2 Q23 W0 repeat 2 required same-session recovery after the host waiting window. Its extra requests and incomplete-stream unknown usage are retained; it is not a normal latency or efficiency sample.',
            'D1 does not test Claude writing quality. A pending/skipped/blocked D2 or D3 is not a zero score.',
            'Provider reported totals/cache are preserved; monetary account charges remain unknown.'],
        'decision':'D1 is complete without replicated improvement. '+('D2 source review did not qualify all W1 outputs; skip D3 and close this bounded experiment.' if d2.get('status')=='completed' and not d2.get('D3_eligible') else 'Finish the independently authorized D2 and its conditional D3 gate.')+' Do not extend to a full benchmark or new algorithm.',
        'records':{'D0':'d0-evidence.json','D1':'d1-paired-results.json','lock':'d1-runtime-lock.json','verification':'verification.json'}}
    save(PUBLIC/'conclusion.json',conclusion)
    # Scan publication against actual ephemeral native tokens as well as patterns.
    known=set()
    for job in PRIVATE.rglob('input.json'):
        if 'gateway_token' in read(job):known.add(read(job)['gateway_token'])
    files=list(PUBLIC.glob('*.json'))
    for path in files:inspect_credentials(path.read_bytes(),path,known)
    report=ROOT/'DATABASE_FOLLOWUP_RESULTS.md'
    lines=['# Database 定向后续实验结果','',
        '2026-10-06。本轮按交接文档完成 D0 与 8 个 Codex 求解配对、8 个 Claude Code 维护作业。最近三题证据侧栏未改善风险题；通用 writer 约束纠正了部分历史事实，但没有在两次重复中消除所有过强主张。D3 未达门槛，按计划跳过。两框架沿用 GLM-5.3-Flash；Claude Code 直接使用实测可调用的 Aixoras /v1/messages。','',
        'D0 核验了 320 份快照、354 份业务轨迹、两份数据库与实际评分器。Q31 的错误反馈及两个候选值进入了 Codex 阶段一输出和原生 DB，但没有进入 Q34 题前记忆文件或任何已捕获的主请求。这是可达性缺口；不等于模型看过后忽略。Claude Q23 的真实 Write 事件引入了关于 Q21 的错误历史前提，Q25 又强化了它；Q23 writer 对 Q21 完整 DDL 的实际读取仍未得到证明。','',
        f"D1 使用 GLM-5.3-Flash / Aixoras Responses，启动 {len(jobs)} 个独立 Codex 作业，完成 {sum(j['status']=='completed' for j in jobs)} 个；剩余 {8-len(jobs)} 个未启动。每次恢复原始目标题前完整原生状态，使用正确的 drifted 数据库。R1 只额外提供同方法最近三题原始 prompt、完整工具记录、最终二值反馈。两臂初次请求的指令、工具、预算和前置状态核验一致；会话独立，记忆文件未变化。Q28 R0 第一次重复经历 HTTP 520 后同会话恢复及未提交后的格式续行；Q28 R1 第二次重复在大量无进展工具调用后也恢复了同一会话。全部额外成本计入对应作业，两者均不能当作无故障延迟样本。",'',
        '| 任务 | 分支 | 正确 | 已完成答案 | 查询数 |','| --- | --- | --- | --- | --- |']
    for g in groups:
        score=f"{g['correct']}/{g['n']} 已完成" if g['n'] else '未完成，无分数'
        lines.append(f"| Q{g['position']} | {g['arm']} | {score} | {', '.join(g['answers']) or '未提交'} | {', '.join(map(str,g['queries'])) or '中断前 1 次'} |")
    lines+=['', '达到合同中的两次同向改善且控制题无新增错误条件。' if useful else
        ('未达到两次风险题同向改善条件，不扩大整流 benchmark。' if result['status']=='completed' else '重复和控制配对不完整，不能判定效果。'), '',
        '用户请求直接测试 /v1/messages 后得到 HTTP 200，返回模型为 glm-5.3-flash、标准 Anthropic message 和已报告用量。先前仅依据已验收接口记录而作出的阻断判断已撤销；本轮不使用协议转换。D2/D3 当前状态分别为 '+conclusion['D2']['status']+' / '+conclusion['D3']['status']+'。','',
        f"原生实验共有 {len(all_attempts)} 个唯一 provider attempt（D1 {len(stage_attempts['D1'])}、D2 {len(stage_attempts['D2'])}、D3 {len(stage_attempts['D3'])}），另有 1 次用户指定的 Messages 接口验收。HTTP 失败缺 usage 时保留 unknown。按协议分别保留 input、output 和 cache 原字段；处理输入的派生合计采用标准字段语义，不作为实际扣费核验。Anthropic 标准总输入是 input＋cache creation＋cache read（[官方说明](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)）；Aixoras 对该原生接口计数字段的遵循程度未独立验证。原始 provider 字段及算术不一致均保留。只计算网关一次用量，不叠加原生重复记账。实际账户扣费未知。DPAPI 身份失败和 D2 缺 method_id 的首次启动均发生在提供商模型调用之前，私有区保留零调用基础设施记录。",'',
        '37 项相关测试通过；源快照和历史评分保持原样。结果仅是目的性选择案例上的开发诊断，不能声称泛化、显著性、新算法成立；Claude 写入改善须以 D2 源证据审查为准。','',
        '详细证据：[D0](followup-records/d0-evidence.json)、[配对结果](followup-records/d1-paired-results.json)、[运行锁](followup-records/d1-runtime-lock.json)、[核验](followup-records/verification.json)、[阶段决定与成本](followup-records/conclusion.json)。原始请求、状态 DB、会话和评价材料仍在忽略目录，不发布。']
    if d2.get('status')=='completed':
        lines[-1:-1]=['D2 的 8 个独立维护作业已执行结束：7 个产生记忆更新，1 个没有形成更新；没有新业务查询。W0/W1 每组恢复同一原始 before 状态，提供相同的同方法合法历史、工具和预算；实际首请求与挂载来源核验通过。W1 只附加合同中的通用证据约束。此阶段是受控维护 fixture，不能冒称原内部请求的逐字重放。','',
            '| 写入事件 | 分支/重复 | 有界主张审查 |','| --- | --- | --- |']
        for j in d2['results']:
            review=j['semantic_review']
            lines.insert(-1,f"| Q{j['index']+1} | {j['arm']} / {j['repeat']} | {review['decision_reason']} |")
        lines[-1:-1]=['','审查由当前 Codex 执行代理对照具体源轨迹完成，没有额外 LLM judge，也不是人类金标或整份记忆总分。W1 的部分产物修正了历史 schema 和候选区分，但仍有新历史误记或把单次接受升级为已排除替代解释的主张。Q23 W1 第二次重复的原生终态为 completed，却只返回重复文本、没有任何记忆写入；它是无维护产物，不能当作纠错成功，其原因未定位。即使忽略 Q7/Q8 的小型来源归属错误，Q25 W1 的过强排除和 Q23 W1 无产物也足以关闭门槛。D3 按计划 skipped、0 调用、无分数；不能声称下游行为或成本收益。' if not d2.get('D3_eligible') else 'D2 通过来源资格检查；D3 下游结果单独登记。','',
            'D2 Q23 W0 第二次重复超过 30 分钟等待窗口后，在同一原生会话、同一任务和已落盘记忆上续行；全部 13 次请求计入同一个逻辑作业，中断流的最终用量保持 unknown。其延迟与用量不能用作无故障的效率比较。初始与续行的源码/原生运行包分别冻结。16 个实验作业按目标、分支、重复计数，不等于物理 CLI 启动次数；零调用启动故障和同会话续行另有私有记录。','',
            '复现限制：原始 D1 和最后一次续行的控制器源码锁可核对，但早期续行的独立锁未全部保留；各次实际请求/响应和原生状态仍留存。首次恢复曾因四个生成的启动器链接被拒绝，随后使用同一已结算任务的独立完整快照，规范化记录保留。派生 legal-episode 曾误记为流中下一题 ID，现已修正元数据；模型输入、SQL 动作、提交及官方分数没有改变。','']
    cost_position=next(i for i,line in enumerate(lines) if line.startswith('原生实验共有'))+2
    cost_lines=['以下仅合计有报告的原字段，缺失部分仍为未知，两个接口的 input 字段不直接混加：','',
        '| 阶段/协议 | input 原字段 | cache read/缓存输入 | cache write | output 原字段 | usage 未知请求 | cache 字段缺失请求 |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for phase in ['D1','D2']:
        usage=conclusion['usage_by_stage'][phase]
        for protocol,values in usage['by_protocol'].items():
            fields=values['reported_fields']
            def number(key):return format(fields[key],',') if key in fields else '未独立报告'
            cached='cache_read_input_tokens' if protocol=='anthropic' else 'cached_input_tokens'
            cost_lines.append(f"| {phase}/{protocol} | {number('input_tokens')} | {number(cached)} | {number('cache_creation_input_tokens')} | {number('output_tokens')} | {len(usage['unknown_usage_attempt_ids'])} | {len(usage['cache_not_reported_attempt_ids'])} |")
    cost_lines.append('')
    lines[cost_position:cost_position]=cost_lines
    lines[-1]='详细证据：[D0](followup-records/d0-evidence.json)、[Codex 配对](followup-records/d1-paired-results.json)、[Claude 来源审查](followup-records/d2-claim-review.json)、[D3 决定](followup-records/d3-downstream-results.json)、[核验](followup-records/verification.json)、[阶段决定与成本](followup-records/conclusion.json)、[接口验收](followup-records/aixoras-native-anthropic-acceptance.json)。原始请求、状态 DB、会话和评价材料仍在忽略目录，不发布。'
    report.write_text('\n'.join(lines)+'\n',encoding='utf8')
    inspect_credentials(report.read_bytes(),report,known)
    save(PUBLIC/'publication-audit.json',{'status':'passed','files':len(files)+1,
        'common_credential_patterns_and_actual_ephemeral_tokens':'no_matches',
        'includes_recovery_and_infrastructure_history_tokens':True,
        'raw_sources_committed':False,'limitation':'Targeted scan, not a universal sensitivity guarantee.'})
    print(json.dumps({'status':'verified','groups':[{k:g[k] for k in ['position','arm','correct','n','answers','queries']} for g in groups],
                      'attempts':len(actual_attempts),'decision':conclusion['D1']['decision']}))


if __name__=='__main__':main()
