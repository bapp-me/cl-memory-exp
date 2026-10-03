# 第 7.2 节离线复核

本目录独立于冻结 baseline。`.gitignore` 忽略解压后的 `api/`、`packets/`，其原字节存于 `artifacts/review-evidence.tar.gz`。`reviews/` 是逐条可读 JSON，原始响应、格式错误、402、参数错误在归档中保留。

## 只复核审查结果（不需要 API key）

在仓库根目录，Python 3.11+：

```powershell
python -X utf8 experiments/section7_analysis_20261003/bundle.py --restore
python -X utf8 experiments/section7_analysis_20261003/audit_reviews.py
python -X utf8 experiments/section7_analysis_20261003/resolve_citations.py
python -X utf8 experiments/section7_analysis_20261003/adjudicate_priority.py
python -X utf8 experiments/section7_analysis_20261003/adjudicate_controls.py
python -X utf8 experiments/section7_analysis_20261003/write_report.py
```

恢复器先验证归档和每成员 SHA256，拒绝越界、非普通文件和不同内容覆盖；相同文件可重复复核。以上程序不调用外部模型、不执行提交代码，也不需要 WSL。`adjudicate_*` 将已记录的主 agent 判断和引用确定性写回派生记录，不是再进行一轮模型审查。

## 重算机械分析

需要先恢复原 7.1 registry 指向的 12 条 baseline 流，以及被冻结的 `.cache/agentcl-codeeval.json`。原始资产与来源参见仓库 `docs/REPRODUCING.md`、第 7.1 归档索引；这些材料没有被复制成新的“实验结果”。现有本机已恢复的环境可运行：

```powershell
python -X utf8 experiments/section7_analysis_20261003/analyze_d0.py
python -X utf8 experiments/section7_analysis_20261003/audit_scoring_surface.py
python -X utf8 experiments/section7_analysis_20261003/audit_babyai.py
python -X utf8 experiments/section7_analysis_20261003/verify_analysis.py
python -X utf8 experiments/section7_analysis_20261003/plot_d0.py
```

这些程序只读已有 JSON/JSONL/Python 源文本。没有导入旧实验 runner、执行 candidate code、重评分或联网模型调用。绘图额外需要 matplotlib。

## 付费入口和复现限制

`review.py` 才是外部模型调用入口。它读取 `DEEPSEEK_API_KEY` / `GLM_API_KEY`，本机可回退到原项目既有 DPAPI 加密凭据；不把密钥存入本目录。新机器建议使用环境变量。不要为离线审计启动它。

每阶段/案例已有 terminal 记录则跳过，只有明确登记的新 phase 才允许重发。`formal_balance_retry` 只接受原正式阶段 HTTP 402 的 14 条，对应用户明确充值后继续的授权；它不是默认自动重试政策。请求参数、证据包和提示词哈希全部保留，可变 API 别名不能保证未来得到相同权重/输出。

`repair_json.py` 是两项已逐字检查的缺括号修复；它不补写遗漏语义、不续写截断响应、不修改原 response。`records/syntax-repairs.json` 保存精确前后替换及哈希。

原始标签、引用定位通过率、主 agent 裁决三者分开。源码里的主 agent 判断已在本轮阅读证据后形成，重跑脚本只重现这些判断的记录。没有人类逐条签认，也没有 D2 干预。
