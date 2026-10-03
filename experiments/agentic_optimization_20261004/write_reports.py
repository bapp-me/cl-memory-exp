"""Evidence-led Chinese reports; aggregate denominators are explicit."""
from common_opt import *

NAMES = dict(lexical="关键词事件", hybrid_context="混合上下文", graph_walk="图导航",
             native_files="原生文件", native_shell="原生终端")


def initial_report():
    d0 = read(ROOT / "records/d0-initial.json")
    review = read(ROOT / "records/review-audit-initial.json")
    strict = sum(s["strict_valid"] for s in review["summary"].values())
    grounded = sum(s["fully_citation_grounded"] for s in review["summary"].values())
    lines = ["# 五种方案的细致指标分析：GLM 审查与证据复核", "",
        "日期：2026-10-04（香港时间）。分析已有五种方案各48次复杂题执行，共240条轨迹；没有为重算指标重跑任务。记忆来源仍是同一份48道简单题 No Memory 历史。", "",
        "一个具体例子：处理多个 DataFrame 并画相关性热图时，原生文件 agent 只读了一次历史，却做了11次 PYTHON、耗费148,245 tokens。GLM概括为“自测全部通过”，原日志实际有两次非零返回；最终评分还有 Axes 与矩阵返回类型的契约张力。因此，高成本不能全部叫检索浪费，失败也不能全部叫记忆误用。", "",
        "## 第7节框架", "",
        "已读旧版v1.5完整第7节，固定版本见 [原文快照](records/v1.5-section7.md)。按7.2.1分开结果状态、可多选机制标签和证据等级；按7.2.3区分直接记录、离线推导、语义审查和新干预。", "",
        "- D0：调用、工具、返回/曝光范围、评分、tokens/cache、时间、错误等可核验事实。",
        "- D1：GLM或主agent根据引用提出的条件适用性、误用、开销解释。引用存在不保证解释正确。",
        "- 新候选全量运行另列；历史R=1参照与可变模型别名不能提供严格同期随机对照或稳定因果结论。", "",
        "## 结果与完整效率", "",
        "每版48次执行、46题主评分，两题资产不可评分仍计成本。240条均完成运行；主评分成功119、失败111，资产不可评分10。正常答错、无效动作或预算耗尽不当作基础设施中断。", "",
        "| 方案 | 正确/46 | 46题tokens | 全48题tokens | PYTHON（46题） | 记忆调用（46题） |",
        "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for method in METHODS:
        s, a = d0["summary"][method]["eligible_46"], d0["summary"][method]["all_48"]
        lines.append(f"| {NAMES[method]} | {s['correct']}/46 | {s['total_tokens']:,} | {a['total_tokens']:,} | {s['python_calls']} | {s['memory_calls']} |")
    lines += ["", "已有冻结Jaccard为27/46、468,934计分题tokens、48次PYTHON；历史无记忆为18/46、162,418 tokens、52次PYTHON。五方案都没有全面超过该Jaccard观察值；历史对照限制保留。缓存/输出分项和逐题记录见 [D0机器表](records/d0-initial.json)。", "",
        "## 搜索、包装和实际可见性", "",
        "下表为全部48次运行。非正文字节包括来源路径、范围、哈希、标签、JSON结构，部分是必要导航信息，不是无用token比例。累计曝光是实际请求中重放的字节；缓存另计，不能由字节推断金额。", "",
        "| 方案 | 无主动调用题数 | 非正文返回占比 | 截断响应 | 空搜索响应 | 记忆error | 常驻累计曝光bytes | 动态累计曝光bytes |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for method in METHODS:
        r = d0["summary"][method]["all_48"]
        lines.append(f"| {NAMES[method]} | {r['no_active_memory_tasks']} | {r['non_content_fraction']:.1%} | {r['truncated_response_calls']} | {r['empty_search_calls']} | {r['memory_error_calls']} | {r['repeated_startup_payload_bytes']:,} | {r['accumulated_dynamic_memory_payload_bytes']:,} |")
    lines += ["", "终端的空搜索无法仅靠shell最终返回码统一识别，表中0是缺少统一total_matches字段下的观测计数，**不能当真实零空搜索**。没有搜索不等于需要搜索；原生两版已有启动索引/入口，不能把无动态调用题当作No Memory。", "",
        "对原生文件73次调用做只改变响应编码的离线回放，正文字符、文件/行范围与续读位置保持不变，返回字节432,968→326,265（−24.6%）。这只是机械可压缩性，不预测新agent一定少调用；另有第1轮实际验证。", "",
        "全量核验了参数、候选/路径、范围、截断、来源、实际请求映射、后续动作与成本。固定只读库没有writer、后台更新和真实遗忘，相应指标为not_applicable。真实recall、逐条记忆精确token/cache、模型内在使用不可由日志得到；终端脚本转换后的重复源字符为unknown。", "",
        "## GLM语义审查：覆盖与可靠性", "",
        f"Reviewer为GLM glm-5.3-flash/high，初始240包全量审查。240包均收到模型响应；{review['parsed']}包可解析，{240-review['parsed']}包JSON语法不合格，原始输出与usage保留，没有质量重试。{strict}/240通过严格字段与原始逐字引用检查；{grounded}包已有判断的引用可在原文或等价JSON字符串值中定位。后者不是语义正确率，也不代表所有要求字段齐全。", "",
        "JSON转义定位单列，未把修正后的引文冒充模型原文。行号偏移、缺字段、无依据标签可回查；语法不合格输出不补造判断，在语义汇总保留不可用分母。新输入/字段不同于旧DeepSeek批次，不能据通过率排名模型能力。", "",
        "| 方案 | 请求/应审 | 可解析 | 严格通过 | 已有判断引用全可定位 |",
        "| --- | ---: | ---: | ---: | ---: |"]
    for method in METHODS:
        r = review["summary"][method]
        lines.append(f"| {NAMES[method]} | 48/48 | {r['parsed']} | {r['strict_valid']} | {r['fully_citation_grounded']} |")
    lines += ["", "下表是**标签合法且引用可定位的GLM标签次数**，包含成功/失败及正面机制证据，不是对应机制造成失败的题数；可多选，不能相加。", "",
              "| 标签 | 关键词 | 混合 | 图导航 | 原生文件 | 原生终端 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for tag in TAGS:
        lines.append("| " + tag + " | " + " | ".join(str(review["summary"][m]["grounded_label_counts"].get(tag, 0)) for m in METHODS) + " |")
    lines += ["", "WRITE_ADMISSION和UPDATE_RETENTION的0来自只读设计，不证明一般写入/遗忘问题不存在。INFRA_PROTOCOL标签不等于基础设施中断终态。RETRIEVAL、USE_TRANSFER可描述检索/适配证据，不直接等于失败率。", "",
        "四项语义判断（源质量、表示保真、适用性、可见使用）与三个agentic字段（策略、失败边界、读取效率）的原始/引用可定位分布均在 [审查表](records/review-audit-initial.json)。原生文件多数被判为部分适用、搜索focused；这支持先区分条件适配、契约疑点与纯粹未命中，不支持精确recall主张。", "",
        "## 主agent复核与竞争解释", "",
        "对12个独立目标做了AI证据复核，非人工真值；覆盖高格式开销、业务执行离群点、不搜索控制和契约疑点。详见 [复核记录](records/primary-adjudication-initial.json)。", "",
        "- 47号题：一次记忆读取、11次PYTHON、两次错误，反驳“自测全部通过”；不把全部148,245 tokens归于检索。",
        "- 316号题：测试重新定义同名函数，评分成功不能强证明实际提交通过；原分数保留。",
        "- 280号题：题面要求填充空列表后算所有值，测试却期望原六个整数均值3.5；再加入五个整数时，11个整数总和不能为38.5。直接归为记忆适配错误过强。",
        "- 不搜索既有成功也有失败，没有调用本身不是检索失败。",
        "- 高非正文比例的成功题只证明有可检验的格式开销，不证明冗余读取已造成损害。", "",
        "## 从分析进入优化", "",
        "以保留自主选文件/表达式/范围的原生文件接口为主要参照。第1轮只缩短公共响应，把审计字段留在日志；第2轮只改变索引启动披露，完整索引仍可访问。假设/反驳门槛在各轮运行前冻结；[台账](records/round-budget.json)硬限最多3×48次，第三轮后终止实验。", "",
        "## 审查成本与复现", "",
        f"初始245个HTTP尝试：240个模型响应，加5个429失败。限流请求降低并发后各重发一次，payload相同、旧失败未删除。已知tokens {review['costs']['total_tokens']:,}，5次失败usage未知、不填零。审查与solver成本分开，金额未知。", "",
        "运行 audit_reviews_opt.py initial 可重新核验引用；adjudicate_initial.py 校验已写出的主agent复核证据。原始五方案的提交、分数、mask和轨迹不改写。", ""]
    (ROOT / "五方案细致指标分析.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    initial_report()
    print("Detailed initial-analysis report generated.")
