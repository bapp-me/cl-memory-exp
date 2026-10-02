"""Generate the completed section-6 report from committed outcomes; no model calls."""
import json
from pathlib import Path
from core import ROOT, save

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def run(name,total):
    folder=ROOT/'runs'/name
    records=read(folder/'summary.json')
    assert len(records)==total and len(list(folder.glob('*/commit.json')))==total,name
    assert (folder/'final-memory.json').exists(),name
    return records
def agg(rows):
    valid=[x for x in rows if x['scorable']]
    return {'executed':len(rows),'valid':len(valid),'correct':sum(x['correct'] is True for x in valid),
            'tokens':sum(x['usage']['totalTokens'] for x in rows),'tool_calls':sum(x['tool_calls'] for x in rows)}
def pair(a,b):
    aa={x['task_id']:x for x in a if x['scorable']};bb={x['task_id']:x for x in b if x['scorable']}
    assert set(aa)==set(bb)
    counts={'both_correct':0,'memory_only_correct':0,'no_memory_only_correct':0,'both_incorrect':0}
    for k,x in aa.items():
        y=bb[k]
        key='both_correct' if x['correct'] and y['correct'] else 'memory_only_correct' if y['correct'] else 'no_memory_only_correct' if x['correct'] else 'both_incorrect'
        counts[key]+=1
    return counts

def main():
    names=['no_memory','episodic_retrieval']
    full={m:run(f'full-codeeval-glm-{m}',96) for m in names}
    baby={m:run(f'noncode-babyai-glm-{m}',8) for m in names}
    probes=run('readonly12-codeeval-glm-episodic_retrieval',12)
    targets={m:[x for x in a if x['task_id'].startswith('new:')] for m,a in full.items()}
    ids={x['task_id'] for x in probes}
    selected={m:[x for x in full[m] if x['task_id'] in ids] for m in names}
    source_by_id={x['task_id'].split(':',1)[1]:x for x in full['episodic_retrieval'] if x['task_id'].startswith('raw:')}
    injection_checks=[]
    for target in targets['episodic_retrieval']:
        source=source_by_id[target['task_id'].split(':',1)[1]]
        injected=read(ROOT/'runs/full-codeeval-glm-episodic_retrieval'/f"{target['index']:03d}"/'injected.json')
        injection_checks.append({'task_id':target['task_id'],'target_scorable':target['scorable'],'source_correct':source['correct'],
                                 'paired_source_injected':any(e['sequence']==source['index'] for e in injected),'target_correct':target['correct']})
    report={'scope':'User-revised section 6: R=1, complete first passes, 12 memory-only frozen probes, complete selected BabyAI family',
            'full':{m:agg(full[m]) for m in names},'targets':{m:agg(targets[m]) for m in names},
            'target_pairs':pair(targets[names[0]],targets[names[1]]),
            'paired_source_injection_checks':injection_checks,
            'babyai':{m:agg(baby[m]) for m in names},
            'readonly':agg(probes),'same_probe_first_pass':{m:agg(selected[m]) for m in names},
            'confirmation_executions':220,'section6_executions':444,
            'section6_accounting':'192 pilot + 32 new diagnostic branches + 192 full first-pass + 16 BabyAI + 12 readonly = 444; 16 normal diagnostic branches reused, not additional calls. Calibration/canaries excluded.'}
    save(ROOT/'records/section6-final.json',report)
    lines=['# 第 6 节完成报告（按用户修订范围）','',
           '本报告基于已提交轨迹。主模型 GLM 5.3 Flash；校准使用 DeepSeek V4.1 Flash 和 GLM。每个条件仅 1 次独立运行。用户将原生完整第二遍改为记忆组 12 个有效复杂目标的只读抽测，不执行无记忆第二遍。因此这里的完成是用户修订范围完成，不是原生完整两遍协议完成。','',
           '## 执行范围','',report['section6_accounting'],'',
           '6.1–6.4：两基准接入、隐藏信息边界、评分资产、隔离和恢复检查已完成。6.5：三方法各执行代码 24 题和数据库 40 问。6.6：两基准各 8 个可审计干预目标。6.7–6.8：保留 AgentCL 开发、CL-Bench 其他预留环境验证的默认分工，R=1 无法验证重复稳定性。6.9：完整代码第一遍、记忆抽测和 BabyAI 8 任务完整预选家族检查。6.10：访问数据已登记为开发用途，不恢复为未见验证。','',
           '## 完整代码第一遍','',
           '| 组别 | 全流正确/有效 | 复杂目标正确/有效 | 全流 tokens | 复杂目标 tokens | 复杂目标工具调用 |',
           '|---|---:|---:|---:|---:|---:|']
    for m in names:
        a=report['full'][m];b=report['targets'][m]
        lines.append(f"| {m} | {a['correct']}/{a['valid']} | {b['correct']}/{b['valid']} | {a['tokens']:,} | {b['tokens']:,} | {b['tool_calls']} |")
    c=report['target_pairs']
    lines+=['',f"有效目标逐题配对：两组都对 {c['both_correct']}；仅记忆对 {c['memory_only_correct']}；仅无记忆对 {c['no_memory_only_correct']}；两组都错 {c['both_incorrect']}。",'',
            '全部 96 题保留执行；raw 269、new 217、new 355 按用户决定排除评分。目标指标只含 46 个有效复杂任务，全流分母 93。token 和调用成本包含实际执行的问题题，不隐去其成本。跨任务效率应同时看正确性、工具调用和记忆输入开销；只报告 token 比例不能替代质量约束。','',
            f"对应源任务经验实际进入上下文的目标数：{sum(x['paired_source_injected'] for x in injection_checks)}/48；有效目标中 {sum(x['paired_source_injected'] for x in injection_checks if x['target_scorable'])}/46。此为完整 episode 的注入覆盖，不代表源解答正确、模型实际使用或因果贡献。",'',
            '## 冻结记忆抽测','',
            '| 同一 12 目标 | 正确/有效 | tokens | 工具调用 |','|---|---:|---:|---:|']
    for label,a in [(m+' 第一遍',report['same_probe_first_pass'][m]) for m in names]+[('episodic_retrieval 只读抽测',report['readonly'])]:
        lines.append(f"| {label} | {a['correct']}/{a['valid']} | {a['tokens']:,} | {a['tool_calls']} |")
    lines+=['','抽测读取完整第一遍结束的冻结历史；每题独立新会话、新工具目录，均不回写记忆。选题按原位置等距，不按第一遍结果挑选。记忆可能含当前题自己的第一次解答，因此这是已见经验的可利用性检查，不是未见迁移、长期保持或完整原生第二遍指标。','',
            '## 非代码检查','', '| 组别 | 成功/任务 | tokens | 工具调用 |','|---|---:|---:|---:|']
    for m,a in report['babyai'].items():lines.append(f"| {m} | {a['correct']}/{a['valid']} | {a['tokens']:,} | {a['tool_calls']} |")
    lines+=['','这里只覆盖预登记的 BabyAI goto_door_to_open_door_loc 完整 8 任务家族，不代表整个非代码领域。','',
            '## 成本与当前观察','']
    costs=read(ROOT/'records/run-index.json')
    section_entries=[x for x in costs['entries'] if x['run'].startswith(('pilot-','diagnostic-','full-','noncode-','readonly12-'))]
    assert len(section_entries)==444
    total_tokens=sum(x['usage']['totalTokens'] for x in section_entries)
    usd=sum(x['usd_estimate_min'] for x in section_entries)
    nm=report['targets']['no_memory'];mem=report['targets']['episodic_retrieval']
    lines += [f"第 6 节共 {total_tokens:,} tokens，按已登记官方单价估算 ${usd:.4f}；全部校准/canary/第 6 节及连接探针合计约 ${costs['usd_estimate_min']:.4f}–${costs['usd_estimate_max']:.4f}。这是 usage 单价估计，不是账单；无 usage 的失败请求成本未知。",'',
              f"完整复杂目标阶段，记忆组 token 为无记忆组的 {mem['tokens']/nm['tokens']:.2f} 倍，工具调用从 {nm['tool_calls']} 到 {mem['tool_calls']}；正确题数从 {nm['correct']} 到 {mem['correct']}。本次观察支持正确性与输入成本之间的权衡，不能笼统称为全面效率提升。",'',
              '对应源经验几乎均能检索进入上下文，但仍有目标失败；因此后续不能仅凭这些失败断言检索缺失是主瓶颈。需要结合源经验质量、任务适配和执行/评分契约继续诊断；当前关联不是因果证明。','',
            '## 解释边界与下一阶段','',
            '- 代码 pilot 三方法有效复杂目标均 5/11；数据库 pilot 无记忆 20/40、受限 ICL 30/40、检索记忆 23/40，对应 SQL 查询 448、174、232。不同基准的原始分数不直接比较。',
            '- 代码 8 个干预目标的三分支正确性均未改变；数据库干预方向混合。没有建立单一记忆瓶颈的因果结论。',
            '- 隐藏测试、参考解、数据库标准答案未作为 agent 记忆输入；数据库原生反馈被改为不返回标准答案，属于已披露适配。',
            '- 每题新建 Node/Pi Agent 会话。只有显式经验跨题保存，在线记忆流逐题提交；无记忆流没有历史。',
            '- 无记忆流前 33 题串行、后续 8 槽并发；记忆流串行；抽测 12 槽并发。延迟受并发阶段及整机负载影响，不据此给方法速度排名。',
            '- 所有统计为一次运行的描述结果，不作显著性、稳定性或 GG/未见泛化声明。手工分析工时未独立计时，不编造人工负担数值。',
            '- 第 7 节及复杂方法开发未自动启动。是否继续需基于实际配对效率和失败机制讨论，不能把默认基准分工解释为记忆机制已验证。','',
            '机器可读结果：records/section6-final.json；累计 usage 与价格估计：records/run-index.json；状态审计：records/state-audit.json；诊断审计：records/diagnostic-audit.json；原始归档及 SHA：records/raw-archive.json。']
    (ROOT/'第6节完成报告.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
