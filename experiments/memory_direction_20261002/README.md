# Memory 方向实验

开始日期：2026-10-02。目标是通过节制的小规模实验，筛选三个有实际问题复现、机制解释和剩余优化空间的方向。首先检验跨任务环境经验，再决定扩展方向；不预先把候选记为成功。

用户已授权使用提供的两个官方 API、安装必要工具及建立实验环境。密钥只保存在被 Git 忽略的本地加密配置中，不写入结果或提交。所有新增安装记录在 `安装清单.md`。

最终结果见 [三个方向的选题建议](最终选题建议.md)。已完成 3/3 个项目方向的小规模可行性验证：带适用条件的经验复用、检索完整性与可靠回退、记忆写入的收益与计算预算。推荐优先做第一个方向。证据支持具体问题与改进空间，尚未证明大规模泛化收益或论文新颖性。

历史过程见 [阶段 03](阶段03_Hermes与记忆更新压力测试.md)、[阶段 02](阶段02_原生入口与覆盖范围.md)、[阶段 01](阶段01_跨任务记忆初筛.md)。这些历史检查点中的 0/3 表示当时进度；当前结论以最终建议和 [方向登记](方向登记.md) 为准。

## 当前实验顺序

1. 核验 API 模型身份、余额或计费资料、工具调用兼容性。
2. 安装隔离的成熟 Agent，下载固定数据库并重算题目与反事实答案。
3. 完成 a 后明确要求保存经验；b/c 分别测试自主读取、直接提供经验，以及无跨任务经验对照。
4. 仅在小样本出现值得追踪的现象后扩大题目、重复数和模型覆盖。
5. 探索陈旧或跨范围经验、记忆检索与消费、BASM 相近的经验适用边界等候选。各方向都需要强基线和简单方案对照，不能用同一个故障换名字凑三个方向。

状态包括待验证、初步复现、值得继续、验证完成、否定、技术阻塞。当前三个方向均通过项目可行性筛选；方向二更偏工程，现成文件工具须作为强基线。未测试的算法或框架不计入完成数。

## 资源原则

首轮设置小调用批次与输出上限；记录失败请求、缓存 token、思考 token 和额外记忆开销。先用 SQLite 和本地隔离运行，不为了形式完整安装尚不需要的 Docker。预算阈值属于内部节流措施，不代表用户承诺的总额度。

模型与工具实际运行情况、数据版本、评分审计及正反结果持续保存在本目录。不会把文档接入成功或合成用例通过等同于方向已验证。

## 在当前环境复核

以下检查不调用模型：

```powershell
Set-Location 'D:\campus_re\experiments\memory_direction_20261002'
.\.venv\Scripts\python.exe analyze_runs.py
.\.venv\Scripts\python.exe analyze_text_memory.py
.\.venv\Scripts\python.exe build_selection_evidence.py
.\.venv\Scripts\python.exe usage_report.py
```

需要付费重跑时，可使用下面的原生文件回退条件。每次更换 `--run-id`，已有证据目录不允许覆盖。

```powershell
$labManifest = Get-Content -Raw installation-manifest.json | ConvertFrom-Json
$labPython = $labManifest.hermes.python_executable
& $labPython -X utf8 run_hermes_task.py --provider deepseek --run-id manual-recheck-001 --mode native --memory-from mab-ds-write2-wide-r1 --prompt-file fixtures/mab6k/query-0.txt --history-file fixtures/mab6k/history-2.json --archive-files --max-output-tokens 32768
```

每个历史运行的准确参数、prompt 和来源见其 `input.json`；HTTP 请求保留代理实际发出的参数。密钥配置仅适用于当前 Windows 用户，未提交到 Git。
