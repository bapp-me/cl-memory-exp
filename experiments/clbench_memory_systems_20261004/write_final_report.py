"""Generate the final descriptive report from audited local records, offline."""
from datetime import datetime, timedelta, timezone
from prepare import ROOT, read

METHODS = ['pi_none', 'pi_notepad', 'pi_jaccard', 'claude_memory_ready', 'codex_memory_ready', 'hermes_memory_ready']
NAMES = dict(zip(METHODS, ['Pi No Memory', 'Pi Notepad', 'Pi Jaccard', 'Claude Code', 'Codex', 'Hermes']))
ENVS = {'database_exploration': 'Database', 'codebase_adaptation': 'Codebase'}


def main():
    analysis = read(ROOT/'records/corrected-efficiency-analysis.json')
    closure = read(ROOT/'records/final-closure-audit.json')
    assert closure['status'] == 'passed_with_disclosed_historical_deviations'
    streams = {(s['environment'], s['method']): s for s in analysis['streams']}
    at = datetime.fromisoformat(closure['as_of']).astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M HKT')
    lines = [
        '# CL-Bench 跨会话记忆实验：本轮最终结果', '',
        '后续获批的全量观测分析与 LLM judge 见[独立分析报告](FULL_ANALYSIS.md)。本文保留原执行结果与成本口径；新增分析不改业务成绩。', '',
        f'数据核验时间：{at}。本轮 R=1 已结束，353 道任务已完成评分和规定的记忆屏障，另有 1 道按用户要求中止、未评分。12 条流均已结束，当前共享请求门 active=0。没有待执行任务。', '',
        '**完成进度与正确数是两件事。** 例如 Codex Database 已完成 40 道，其中 20 道正确、20 道错误；“20/40”表示正确数，不表示只跑了 20 道。Hermes Codebase 完成评分 18 道，第 16 题中止；第 17–19 题均已执行完。', '',
        '在本次观察中，Database 的最高正确数是 Claude Code 的 32 道；Codebase 的最高正确数是 Codex 的 19 道。两者是不同 agent 完整系统的单次结果，不能据此认定其 memory 机制具有稳定或因果优势。Pi 三组底座更接近：Notepad 的 Codebase 已知用量最低，Jaccard 在 Pi 三组中业务动作最少。', '',
        '## 已完成范围与评分', '',
        '| 环境 | 方法 | 已评分 / 计划 | 正确数 | 错误数 | 中止未评分 | 正确率（已评分题） |',
        '|---|---|---:|---:|---:|---:|---:|',
    ]
    for env in ENVS:
        for method in METHODS:
            s = streams[env, method]; v = s['stats']
            lines.append(f"| {ENVS[env]} | {NAMES[method]} | {v['tasks']}/{s['target']} | {v['correct']} | {v['tasks']-v['correct']} | {s['user_skipped_unscored']} | {v['correct']/v['tasks']:.1%} |")
    lines += ['', 'Hermes Codebase 的 16/18 只描述已评分子集，不把中止题填零，也不与其他方法完整的 19 题直接排名。全部结果采用官方 grader。Database 的数值容差允许近似正确；Codebase 由独立评分器重新应用官方测试，模型自行报告的本地测试通过不替代评分。', '',
        '## 业务动作、原生 reward 与模型用量', '',
        '| 环境 | 方法 | 官方动作 | 平均原生 reward | HTTP 请求 | 已知 tokens | 缺 usage 请求 |',
        '|---|---|---:|---:|---:|---:|---:|']
    for env in ENVS:
        for method in METHODS:
            v = streams[env, method]['stats']
            lines.append(f"| {ENVS[env]} | {NAMES[method]} | {v['actions']:,} | {v['reward_mean']:.4f} | {v['attempts']:,} | {v['total_tokens_known']:,} | {v['total_tokens_unknown_attempts']} |")
    lines += ['', '此表只计最终选用的已评分任务，包含这些任务内部发生的失败与恢复调用；验收、被替代旧结果及中止题另外计入全批次成本。Database 动作为 QUERY 数，Codebase 为官方步骤；reward 同时受官方质量/动作规则影响，不能和正确率互换。未知 usage 不填零，因此有缺失时 tokens 是已知部分。', '',
        '![六组完整系统比较](figures/systems-comparison-corrected.png)', '',
        '## 环境分段', '',
        '| 方法 | Database 迁移前正确 / 20 | Database 迁移后正确 / 20 | tablib 正确 / 已评分 | tenacity 正确 / 已评分 |',
        '|---|---:|---:|---:|---:|']
    for method in METHODS:
        db, code = streams['database_exploration', method]['phases'], streams['codebase_adaptation', method]['phases']
        a, b = code['jazzband/tablib'], code['jd/tenacity']
        lines.append(f"| {NAMES[method]} | {db['before_migration']['correct']}/20 | {db['after_migration']['correct']}/20 | {a['correct']}/{a['tasks']} | {b['correct']}/{b['tasks']} |")
    lines += ['', '迁移前后是不同题目和环境条件，不能把分差直接解释为学习或遗忘。Codex 在代码任务全部通过、数据库任务只通过一半，说明本轮没有一种配置在两个环境都取得最高正确数；原因不能仅凭汇总表确定。', '',
        '## 同题配对效率', '',
        '下表均以 Pi No Memory 为基线，仅选择双方都被官方判对的同题。动作差和 token 差为“该方法 − 基线”；这是按观察结果筛出的子集，不是因果效率估计。Hermes Codebase 因缺一题不做完整流配对。', '',
        '| 环境 / 方法 | 双方正确题数 | 动作差 | 已知 token 差 | usage 完整配对题数 | 完整配对 token 差 |',
        '|---|---:|---:|---:|---:|---:|']
    for env in ENVS:
        for method in METHODS[1:]:
            p = next((p for p in analysis['paired'] if p['environment'] == env and p['method'] == method), None)
            if not p: continue
            g = p['groups']['both_correct']; d = g['delta_target_minus_baseline']; complete = g['complete_usage_pairs']
            lines.append(f"| {ENVS[env]} / {NAMES[method]} | {g['tasks']} | {d['actions']:+,} | {d['total_tokens_known']:+,} | {complete['tasks']} | {complete['token_delta']:+,} |")
    lines += ['', '完整配对列只在同题双方全部调用都有 usage 时计算。包含未知用量的“已知 token 差”不是精确节省量。所有正确性互换、配对子集及来源见 [修正分析](records/corrected-efficiency-analysis.json) 和 [逐题索引](records/corrected-task-index.json)。', '',
        '## 全批次成本：没有遗漏中止题或旧尝试', '',
        '| 互不重叠的成本范围 | 请求数 | 已知 tokens | usage 未知请求 | 记录价目等价值（USD） |',
        '|---|---:|---:|---:|---:|']
    labels = {'selected_scored_tasks': '最终选用的 353 道已评分任务（含三次重跑）',
              'superseded_original_tasks': '被三次重跑替代的原始尝试',
              'user_interrupted_unscored_task': 'Hermes Codebase 第 16 题，中止未评分',
              'acceptance_or_debug': '验收、能力探针与适配调试'}
    for key, label in labels.items():
        v = closure['cost_partition'][key]
        lines.append(f"| {label} | {v['attempts']:,} | {v['total_tokens_known']:,} | {v['unknown_usage_attempts']} | {v['published_price_equivalent_known_usd']:.6f} |")
    v = closure['all_campaign_attempts']
    lines.append(f"| **全批次** | **{v['attempts']:,}** | **{v['total_tokens_known']:,}** | **{v['unknown_usage_attempts']}** | **{v['published_price_equivalent_known_usd']:.6f}** |")
    lines += ['',
        f"已知输入 {v['input_tokens_known']:,} tokens，其中缓存输入 {v['cached_input_tokens_known']:,}；已知输出 {v['output_tokens_known']:,}。缓存是输入的子集，reasoning 是输出的子集，不重复相加。",
        '', '金额使用 [2026-10-04 保存的 Z.AI 公开价格快照](records/provider-pricing.json) 计算，只是已知 token 的价目等价值，不是账户真实扣款，也不能代替资源包、订阅或账单核对。整个批次的 API 用量不包含桌面上本聊天的用量。按唯一实际 attempt 去重，四类恰好覆盖全部请求，见 [最终收尾审计](records/final-closure-audit.json)。', '',
        '早期两个 v1 canary 因错误启用 60 秒业务截止而被中断，原日志只有 started、没有终态；保留其未知 usage 与原日志，不伪造结算。它们不进入正式评分。所有当前正式调用已结束，共享门无占用、全部已有 lease 已释放；“历史日志不完整”与“现在仍在请求”分开记录。', '',
        '## 实际配置、适配与可比性', '',
        '| 项目 | 本轮实际设置与限制 |',
        '|---|---|',
        '| 模型与费用 | 原 Z.AI GLM-5.3-Flash；主求解 high；原生辅助角色保留其 effort；本轮 R=1 不额外设请求或金额上限 |',
        '| 环境隔离 | 每个方法×环境独立 home、会话与长期记忆；Codebase 从空记忆开始，不读 Database 记忆 |',
        '| 反馈与测试 | Database 隐藏正确答案，保留对错、提交、查询数及超时；Codebase test_patch 可见，参考修复隐藏 |',
        '| 输出与窗口 | 总窗口 262,144；后续统一输出上限 65,536、压缩触发 196,608；Codex 通过 config.toml 对齐压缩，无需改压缩源码 |',
        '| 保留历史预算 | 旧题未发现输出截断失败，按用户要求保留；实际预算逐题登记，不称全程统一 64k |',
        '| Codex 调度 | Database 前 8 道完整结果、Codebase 前 7 道完整结果保留逐题整合；续跑每题提取，分别每 10/5 题整合；Codebase 第 19 题最终整合 |',
        '| 等待与恢复 | 新/恢复 Codex 批次整合 1,800 秒，其他维护 600 秒；原已运行控制器保持实际冻结值；原生剩余重试次数保留，不重做冻结业务 |',
        '| 已知接口适配 | 官方动作解析；完整 JSON fence 的确定性解包；维护生命周期/存储提交/请求结算屏障；不替换 writer 提示或官方 grader |',
        '| 准入记录 | Pi 与 Claude Database 的旧版本验收有效并保留成绩；compatibility.json 的新 64k 配置未放行项不代表旧题没跑完 |',
        '| 并发 | 最多 12 条独立流、全角色共享请求上限 50；实际观察峰值 8，最终 active=0 |',
        '',
        'Codex 按批次执行后，Database 的 10/20/30/40 与 Codebase 的 10/15/19 均有真实整合证据；Codebase 第 5 题属于旧逐题整合前缀。所有新规则下的非整合点都未启动阶段二。最终两次整合分别覆盖 40 与 19 份提取源，见 [在线批次审计](records/codex-batch-online-audit.json)。这验证调度执行，不证明记忆在答案中被语义使用。', '',
        '先前观察到 Codex 成本主要来自强制频繁整合时重复发送输入，不是每次都生成 65,536 tokens。原生空闲与整合冷却机制被实验调度加速，因此本轮用量不代表日常默认 Codex。变更前后题目、轨迹与阶段不同，不能直接把成本差归因为批处理。证据见 [调度成本审计](records/codex-memory-scheduling-cost-audit.json)。', '',
        '## 异常、恢复与审计范围', '',
        '原始机械审计仍如实报出三处旧 Codebase 切仓提示偏差；最终视图全部采用授权重跑的结果（No Memory 第 14 题通过、第 17 题失败，Jaccard 第 19 题通过），包括变差结果。原评分、原请求与重跑前报告保留。收尾审计确认没有新增机械错误，并核对重跑题前记忆、官方评分和屏障。', '',
        'Hermes Codebase 第 16 题仅中止、不评分；保留原生会话、业务动作和未执行脚本，但原临时业务容器被旧清理路径删除，不能声称保有完整原文件系统。后续第 17–19 题沿用已验证一致的记忆、新会话完成，没有注入环境提醒。中止题 14 个业务步骤和全部请求成本单列。见 [中止与续跑记录](records/hermes-code-user-skip.json)。', '',
        'Hermes Database 工具参数错误经用户授权在同题同会话恢复；Codex 非法维护 JSON、传输失败与超时恢复按各自授权执行。全部恢复保留原请求和实际成本，不把故障抹掉。353 道题通过业务/记忆机械检查，176 道原生任务另逐一重读快照，验证原生完成证据、持久化记忆及完整请求目录。审计没有调用模型。', '',
        '原生存储总量、所有角色的统一细分、压缩事件和恢复题原始端到端时间仍有观测缺口；不得填零或宣称严格跨框架可比。每题已知时间、未知标记、恢复时间在逐题索引中。并行观测耗时不构成串行加速比。首次授权的 12 个独立语义复核目标已经用完，保留 [原复核记录](records/semantic-review.json)，本次仅做机械收尾，没有新增大规模语义标注。', '',
        '## 这轮能够支持的结论与后续问题', '',
        '本轮展示了质量与资源的取舍：Claude Code 的 Database 正确数最高，但已知 token 大幅高于 Pi；Codex 的 Codebase 全部通过，但 Database 低于 Pi No Memory，两个环境的结果不一致。Pi Notepad 在这次 Codebase 兼具较低用量和比 No Memory 多一道正确；Jaccard 少做业务步骤，但读取历史可能增加输入量。它们都值得作为后续比较的参照，当前没有“复杂记忆必然更好”的证据。', '',
        '若继续研究，最需要区分三个问题：同一 agent 在有/无记忆时的差异；同一批源轨迹下逐题与批次整合的真实成本；迁移后错误究竟来自过时经验、工具策略还是基础求解。前两项需要新的匹配对照和重复，第三项需要新的语义复核授权。本轮未启动这些额外实验，也不以 R=1 宣称稳定排名或统计显著。', '',
        '## 离线复算', '', '```powershell',
        '& ./.local/clbench-venv/Scripts/python.exe summarize_results.py',
        '& ./.local/clbench-venv/Scripts/python.exe analyze_results.py --corrected',
        '& ./.local/clbench-venv/Scripts/python.exe audit_results.py  # 三处已披露历史偏差，预期退出 1',
        '& ./.local/clbench-venv/Scripts/python.exe audit_codex_batching.py',
        '& ./.local/clbench-venv/Scripts/python.exe audit_closure.py  # 读取本地共享门状态，不调用模型',
        '& D:/anaconda3/python.exe plot_results.py --corrected --all-methods',
        '& ./.local/clbench-venv/Scripts/python.exe write_final_report.py',
        '```', '',
        '审计脚本不回写被测记忆、不修改成绩。原始材料在忽略追踪的 private-runs 中，公开记录提供去敏索引、摘要和哈希；没有把私有原始会话提交 Git。',
    ]
    (ROOT/'RESULTS_FINAL.md').write_text('\n'.join(lines)+'\n', encoding='utf8')
    print(str(ROOT/'RESULTS_FINAL.md'))


if __name__ == '__main__':
    main()
