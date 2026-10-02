"""Generate transparent per-group tables and downstream comparisons from raw scores."""
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from analyze import analyze
from make_tasks import CATALOG
from plan_jobs import GROUPS, aid, wid

ROOT = Path(__file__).resolve().parent


def table(headers, rows):
    return '\n'.join(['|' + '|'.join(headers) + '|', '|' + '|'.join('---' for _ in headers) + '|'] + ['|' + '|'.join(str(v) for v in row) + '|' for row in rows]) + '\n'


def main():
    result = analyze()
    byid = {r['run_id']: r for r in result['rows']}
    out = ['# 逐组结果与完整成本表', '', '由 `report_tables.py` 从原始 summary、工具轨迹和 grader v2 生成。所有失败保留；带错误或质量不相当的配对不得解释为效率提升。费用为相同峰时单价的可比较估算，实际峰谷区间另报；没有用不同指标拼成总分。', '']
    main_rows = []
    for group, title, *_ in CATALOG:
        values = []
        q = []
        for stage in 'bc':
            n = byid.get(f'main-pi-{group[:2]}-{stage}-none')
            m = byid.get(f'main-pi-{group[:2]}-{stage}-file')
            if n and m:
                values += [n['task_tools'], m['task_tools'], m['task_tools'] - n['task_tools']]
                q += [n['quality']['success'], m['quality']['success']]
            else:
                values += ['pending'] * 3
        main_rows.append([group + ' ' + title, *values, f'{sum(q)}/{len(q)}'])
    out += ['## 主比较：普通真实 writer + file，固定 DeepSeek/pi', '', table(['组', 'b none', 'b memory', 'Δb', 'c none', 'c memory', 'Δc', '正确数'], main_rows)]
    aggregate = []
    for condition in ('file', 'guided', 'caution', 'search'):
        for stage in 'bc':
            pairs = [r['stages'][stage][condition] for r in result['comparisons'] if stage in r['stages'] and condition in r['stages'][stage]]
            good = [p for p in pairs if p['quality_comparable']]
            if good:
                aggregate.append([condition, stage, f'{len(good)}/{len(pairs)}', *[round(mean(p[k] for p in good), 3) for k in ('delta_task_tools', 'delta_all_tools', 'delta_task_errors', 'delta_memory_errors', 'delta_input_tokens', 'delta_output_tokens', 'delta_seconds')]])
    out += ['## 各基线：每组配对差值的平均，分别计量', '', table(['条件', '任务', '质量可比/全部', '任务工具 Δ', '全部工具 Δ', '任务错误 Δ', '记忆工具错误 Δ', '输入 token Δ', '输出 token Δ', '秒 Δ'], aggregate), '输入 token 包括缓存命中；全部工具包含读写记忆。读取机会、输入内容长度和工具表随 memory 协议改变，是协议成本的一部分。网络/缓存与启动时间使延迟噪声明显。']
    writer_costs, economics = [], []
    for g in GROUPS:
        source, normal, guided = (byid.get(x) for x in (aid(g), wid(g), wid(g, True)))
        if not all((source, normal, guided)):
            continue
        writer_costs.append([g, source['memory_writes'], normal['usage']['all_input_tokens'], normal['usage']['output_tokens'], guided['usage']['all_input_tokens'], guided['usage']['output_tokens'], normal['memory_writes'], guided['memory_writes']])
        ns = [byid.get(f'main-pi-{g[:2]}-{s}-none') for s in 'bc']
        ms = [byid.get(f'main-pi-{g[:2]}-{s}-file') for s in 'bc']
        if all(ns + ms):
            price = lambda r: r['usd_estimate_range'][1]
            ncost, mcost = sum(map(price, ns)), sum(map(price, ms))
            economics.append({'group': g, 'none_b_c_usd_peak': ncost, 'memory_b_c_usd_peak': mcost,
                'writer_plus_memory_b_c_usd_peak': price(normal) + mcost,
                'full_a_writer_b_c_usd_peak': price(source) + price(normal) + mcost,
                'incremental_writer_plus_consumers_delta_usd_peak': price(normal) + mcost - ncost,
                'quality_comparable': all(x['quality']['success'] for x in ns + ms)})
    out += ['', '## 写入触发与 writer 成本', '', table(['组', '自然 a 成功写入调用', '普通 writer 输入', '普通 writer 输出', 'guided 输入', 'guided 输出', '普通写入调用', 'guided 写入调用'], writer_costs), '两种 writer 输入均来自同一 a 消息轨迹和同一自然 a 后存储；writer 本身看不到未来任务或评分。自然未写入的组也保留。写入调用数可大于 1；不同 id 或重试/删除不能算多次独立记忆样本。']
    out += ['', '## 两个后续任务能否摊销写入', '', table(['组', 'none b+c USD峰', 'memory b+c USD峰', 'writer+memory b+c', '完整 a+writer+b+c', '含 writer 增量差'], [[r['group'], *[f'{r[k]:.6f}' for k in ('none_b_c_usd_peak', 'memory_b_c_usd_peak', 'writer_plus_memory_b_c_usd_peak', 'full_a_writer_b_c_usd_peak', 'incremental_writer_plus_consumers_delta_usd_peak')]] for r in economics]), '增量差保守地不计共同源 a；完整一列又把全部 a 计入，作为从头构建开销上界。没有与无记忆 a 做增量配对，不能把完整 a 全当作纯写入成本。两个固定后续任务不代表长期工作量分布。']
    repeats = []
    for g in ('02_coverage', '04_pagination', '06_build', '08_csv'):
        for stage in 'bc':
            for condition in ('file', 'guided', 'caution'):
                pairs = []
                for prefix in ('main', 'repeat2', 'repeat3'):
                    n, m = (byid.get(f'{prefix}-pi-{g[:2]}-{stage}-{c}') for c in ('none', condition))
                    if n and m:
                        pairs.append((n, m))
                if len(pairs) > 1:
                    vals = [m['task_tools'] - n['task_tools'] for n, m in pairs]
                    repeats.append({'group': g, 'stage': stage, 'condition': condition, 'deltas': vals, 'mean': mean(vals),
                                    'qualities': [[n['quality']['success'], m['quality']['success']] for n, m in pairs],
                                    'memory_c_writes': [m['memory_writes'] for n, m in pairs]})
    out += ['', '## 固定同一 M_a 的 consumer 重复', '', table(['组', '任务', '条件', '逐次任务 Δ', '均值', '范围', '每次两端正确'], [[r['group'], r['stage'], r['condition'], str(r['deltas']), round(r['mean'], 3), f'{min(r["deltas"])}..{max(r["deltas"])}', all(all(q) for q in r['qualities'])] for r in repeats]), '每行最多 3 对，显示全部样本与范围，不作显著性检验，不据此声称稳定发生率。其他组没有被筛掉：全部 10 组在主比较中。重复组为正迁移线索 02、冗余动作 06、恢复 08、主动更新 04。']
    fixes = []
    for g in GROUPS:
        original = byid.get(f'fix-pi-{g[:2]}-d-frozen')
        updated = byid.get(f'fix-pi-{g[:2]}-d-natural')
        retain = byid.get(f'fix-pi-{g[:2]}-b-natural')
        c = byid.get(f'main-pi-{g[:2]}-c-file')
        if original and updated and retain:
            fixes.append({'group': g, 'memory_changed_in_c': c['memory_changed'], 'd_frozen': original['task_tools'], 'd_updated': updated['task_tools'],
                          'd_delta': updated['task_tools'] - original['task_tools'], 'd_errors_frozen': original['tool_errors'], 'd_errors_updated': updated['tool_errors'],
                          'b_retention_tools': retain['task_tools'], 'all_success': all(r['quality']['success'] for r in (original, updated, retain))})
    out += ['', '## 独立 d 与 b 保留检查：pi 自然 c 后存储', '', table(['组', 'c 是否改存储', 'd 冻结 Ma', 'd 使用 Mc', 'Δ', 'd 错误 Ma/Mc', 'b 保留调用', '三题全正确'], [[r['group'], r['memory_changed_in_c'], r['d_frozen'], r['d_updated'], r['d_delta'], f'{r["d_errors_frozen"]}/{r["d_errors_updated"]}', r['b_retention_tools'], r['all_success']] for r in fixes]), '未改存储组的 M_a 与 M_c 语义相同；这些 d 成本差是 consumer 波动，不是修复收益。d 是新数据/新状态，未携带 c 对话；b 从另一份 Mc 副本重跑，避免 d 写入污染。']
    repair_rows = []
    for r in result['rows']:
        if r.get('repair_from'):
            repair_rows.append([r['run_id'], r['memory_writes'], r['memory_changed'], r['usage'].get('all_input_tokens', 0), r['usage'].get('output_tokens', 0), r['memory_tool_errors'], r['seconds']])
    out += ['', '## 显式修复自身的开销（不混进 consumer）', '', table(['运行', '成功写入', '存储变化', '输入 token', '输出 token', '记忆工具错误', '秒'], repair_rows), '从对应真实 c 轨迹追加修复机会；source c 的成本是既有开销，不重复计入此行。语义修复质量由 scope_review.json 人工审阅，不能用存储变化自动判定。']
    repair_repeats = []
    for g in ('04_pagination', '08_csv'):
        for condition in ('frozen', 'natural', 'explicit'):
            selected = [byid.get(f'{prefix}-pi-{g[:2]}-d-{condition}') for prefix in ('fix', 'fix2', 'fix3')]
            if all(selected):
                repair_repeats.append([g, condition, str([s['task_tools'] for s in selected]), str([s['task_tool_errors'] for s in selected]), all(s['quality']['success'] for s in selected)])
    out += ['', '## d 固定存储重复（3 次，各版本独立）', '', table(['组', '记忆来源', '逐次任务调用', '逐次任务错误', '全正确'], repair_repeats)]
    cross = []
    for g in ('03_join', '04_pagination', '08_csv'):
        for stage in 'bc':
            n = byid.get(f'cross-hermes-{g[:2]}-{stage}-none')
            if not n:
                continue
            for condition in ('file', 'search'):
                m = byid.get(f'cross-hermes-{g[:2]}-{stage}-{condition}')
                if m:
                    cross.append({'group': g, 'stage': stage, 'condition': condition, 'none': n['task_tools'], 'memory': m['task_tools'], 'delta': m['task_tools'] - n['task_tools'], 'reads': m['memory_reads'], 'writes': m['memory_writes'], 'both_success': n['quality']['success'] and m['quality']['success']})
    out += ['', '## Hermes：同一 M_a、同一适配器、相同 system 与工具能力', '', table(['组', '任务', '条件', 'none', 'memory', 'Δ', '记忆读', '记忆写', '均正确'], [[r[k] for k in ('group', 'stage', 'condition', 'none', 'memory', 'delta', 'reads', 'writes', 'both_success')] for r in cross]), '这是 3 个代表性组，未跑完整 Agent × memory × 全部任务笛卡尔积。SDK 序列化、工具结果呈现、框架循环与随机性仍可能影响结果，不作框架排名。']
    glm = []
    for g in ('02_coverage', '08_csv'):
        for stage in 'bc':
            n = byid.get(f'glm-pi-{g[:2]}-{stage}-none')
            for condition in ('file', 'guided'):
                m = byid.get(f'glm-pi-{g[:2]}-{stage}-{condition}')
                if n and m:
                    comparable = n['quality']['success'] and m['quality']['success'] and not n['error'] and not m['error']
                    glm.append([g, stage, condition, n['task_tools'], m['task_tools'], m['task_tools'] - n['task_tools'] if comparable else '不可比', comparable, m['memory_writes']])
    out += ['', '## 第二模型 GLM：Anthropic 兼容入口补充记录', '', table(['组', '任务', '条件', 'none', 'memory', 'Δ', '质量可比', '记忆写'], glm), '这不是 GLM 独立 writer 的发生率。output_config.effort 映射未由官方资料确认；该组不与原生参数组混用。失败与网络异常保留，不能把更快答错当收益。']
    native_rows = []
    for g, stage in [('02_coverage', 'b'), ('02_coverage', 'c'), ('08_csv', 'c')]:
        n = byid.get(f'glmnative2-pi-{g[:2]}-{stage}-none')
        for condition in ('file', 'guided'):
            m = byid.get(f'glmnative2-pi-{g[:2]}-{stage}-{condition}')
            if n and m:
                comparable = n['quality']['success'] and m['quality']['success'] and not n['error'] and not m['error']
                native_rows.append([g, stage, condition, n['task_tools'], m['task_tools'], m['task_tools'] - n['task_tools'] if comparable else '不可比', comparable])
    out += ['', '## GLM 原生参数核验：reasoning_effort=high', '', table(['组', '任务', '条件', 'none', 'memory', 'Δ', '质量可比'], native_rows), '同组固定官方 /paas/v4/chat/completions、thinking enabled、clear_thinking false、reasoning_effort high、32768 输出上限。保持 pi 核心与同一 M_a。改接口与保留推理会同时改变序列化/上下文通路，不能把两种 GLM 接口之间的差异单独归因于 effort。首次 developer role 配置失败另列保留。']
    raw_rows = []
    for r in result['rows']:
        raw_rows.append([r['run_id'], r['quality']['success'], r['task_tools'], sum(r['tools'].values()), r['tool_errors'], r['repeated_task_calls'], r['usage'].get('all_input_tokens', 0), r['usage'].get('output_tokens', 0), r['seconds'], r['memory_writes'], bool(r['error'])])
    raw = '# 全部运行，包含校准、writer、修复与失败\n\n' + table(['run_id', '质量/落盘成功', '任务调用', '全部调用', '工具错误', '相同参数重复调用', '输入 token', '输出 token', '秒', '记忆写', '运行错误'], raw_rows)
    (ROOT / 'results/逐运行表.md').write_text(raw, encoding='utf-8')
    out += ['', '全部逐运行指标见 [逐运行表](results/逐运行表.md)，按工具类型的明细、所有对照与模型调用见 [scoreboard.json](results/scoreboard.json)。相同参数重复调用包括必要的 GET 保存验证，不能直接称为无效动作。writer/repair 行的 success 只表示非空记忆落盘，不表示语义正确。', '']
    (ROOT / '逐组结果.md').write_text('\n'.join(out), encoding='utf-8')
    (ROOT / 'results/extended-metrics.json').write_text(json.dumps({'economics': economics, 'consumer_repeats': repeats, 'fixes': fixes, 'cross_agent': cross}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Generated per-group tables and all-run ledger.')


if __name__ == '__main__':
    main()
