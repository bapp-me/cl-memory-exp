# 跨任务效率迁移、writer scope 与 memory fix

本轮目标来自 `objective.md`。开始于 2026-10-02（Asia/Hong_Kong），实验与复验已完成：10 组 a/b/c/d，309 次运行记录，pi/Hermes 两套开源循环、两种 memory 协议、DeepSeek/GLM 两模型。当前判断：存在局部现象，但不足以支持“普遍负迁移/普遍不修复”的主项目立项。

优先阅读 [总结与研究判断](总结.md)、[逐组结果](逐组结果.md)、[完成审计](完成审计.md)。旧证据未修改，核验与修订见 [旧证据审计](旧证据审计.md)；版本、触发方式、成本和兼容边界见 [协议与环境](协议与环境.md)。

## 执行与预先约定

1. 审计旧 memory_before/after、写入调用、识错与恢复证据，保留成功修复反例。
2. 冻结 10 个有实质差异的任务族及独立 a/b/c/d；先校准 3 组再扩展。所有入选组保留，不因没有负迁移而删组。
3. 主模型固定 DeepSeek `deepseek-flash`、实际请求 thinking enabled / effort high / 单次输出 32768，记录每次请求。先跑 pi agent core；复用固定版本 Hermes，使用同一任务与可修改记忆协议做交叉校验。框架原生提示差异单列。
4. 两种统一可替换机制：自动载入的单文件记忆；模型主动 search/get 的结构化条目记忆。两者都可主动修改、删除，预算相同，不使用独立 embedding/reranker。它们是实验适配器，不冒充框架原生产品记忆。
5. a 首先自然执行并观察是否写入；如需统一 writer，对同一 a 轨迹追加独立结束写入机会。自然与强制触发分开。普通 writer 与 scope writer 只看相同 a 轨迹和证据，不看 b/c/d 或边界标注。
6. b/c 在新进程、新会话从同一冻结 M_a 副本启动；none 也具备相同任务工具。自然 c 不要求修复。后续 d 比较冻结 M_a 与 M_c；显式修复另设条件，并复测 b 的经验保留。
7. 主成本分别报告任务工具、记忆读写、错误、重复、token、延迟；质量是约束。保留所有失败、超时和环境故障，不把更快答错当收益。包括 writer/修复开销，费用只用可核验 usage 与价格，不能核验就记未知。
8. 关键案例配对重复；同 M_a 的 consumer 重复与重新运行 a 的 writer 随机性分开。第二模型只复核关键案例。合成任务只支持机制范围内的结论，不推算真实世界总体发生率。

## 数据与实现原则

新任务为可复现的确定性合成环境，覆盖 SQL 单位/覆盖/关联、API 分页/参数语义、构建配置、文件编码/结构、时间与用户状态。c 边界在可见文件、schema、响应或错误中可发现；无记忆也可完成。原始结果、完整记忆快照、工具结果、配置与版本均落盘。评分信息只在评测进程可见，任务工具不能越界读取。

旧证据保持原貌：`../memory_direction_20261002/`。复用其中加密凭据读取函数和隔离 Hermes，不复制或输出凭据。新增依赖只装到本目录。只提交本实验文件，保留仓库其他既有修改。

## 离线复算（不调用模型）

```powershell
Set-Location 'D:\campus_re\experiments\memory_scope_fix_20261002'
python -X utf8 -m unittest test_environment -v
python -X utf8 analyze.py
python -X utf8 report_tables.py
python -X utf8 review_opportunities.py
python -X utf8 audit_final.py
```

audit_final 会通过旧 get_secret 在内存中对交付文件做实际密钥扫描，但不会输出密钥或调用付费模型。HTTP 原始字节已无损 gzip，`results/http-archive-manifest.json` 保存解压内容长度与 SHA256。`results/scoreboard.json` 从完整 raw summary/工具记录复算；原始失败与初版评分都保留。

## 运行与恢复

现有环境已可运行，无需重新安装。若需恢复 pi 依赖，先把 `pi-package.json` 和 `pi-package-lock.json` 复制为 `.runtime/pi/package.json` 与 `package-lock.json`，再在该目录执行 npm ci（缓存使用本目录 .cache/npm，安装脚本关闭）。Hermes 使用旧实验 installation-manifest.json 中的固定源码/Python 路径；依赖版本已复制到本轮清单。

每个 paid run 的精确参数、提示、模型与种子来源在其 input.json；调度清单在 jobs。示例（会产生 API 费用，必须使用新的 run_id）：

```powershell
python -X utf8 run_task.py --run-id manual-recheck-01 --group 08_csv --stage c --memory file --memory-from main-pi-08-w
```

`batch.py jobs/<phase>.json` 最多两个并发，只跳过已有完整 summary，不覆盖旧运行，不自动重启不完整目录。跨 Agent 使用 --agent hermes，需以旧清单的 Hermes Python 运行；batch 自动选择该解释器。两套模型参数协议分开记录：默认 Anthropic 兼容入口；GLM 原生参数需 --provider glm --transport native。完整任务与评分可用 make_tasks.py 确定性重建，人工诊断种子由 make_manual_diagnostic.py 单独生成。

执行顺序：calibration → cal_writers → cal_consumers → sources/writers → main → guided_writers/guided/caution/search → cross_agent/ensure_read/manual → fix_followup/explicit_repair/explicit_followup/repair_retrieval → consumer_repeats/writer_repeats_*/natural_only/fix_repeats → hermes_repeats/hermes_repair/hermes_fix_followup → second_model → glm_native。这些 jobs 是证据清单，不是要求每次把整轮全部付费重跑。
