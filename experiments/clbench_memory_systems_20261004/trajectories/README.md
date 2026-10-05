# 六组实验的逐题业务轨迹

按用户明确要求导出并提交的纯业务轨迹，共 **354 个 JSON 文件、7,864,387 字节（约 7.864 MB / 7.50 MiB）**。大小不包含本说明和索引。

- 353 道已评分任务：原样复制其 `legal-episode.json`，包含任务问题、助手文本、业务工具动作与返回、合法反馈。
- Hermes Codebase 第 16 题：仅保存 14 个已记录工具动作及返回，文件名为 `task-015.interrupted-actions.json`；这是部分轨迹，未评分，不补零、不补造缺失对话。
- 每个方法各有 Database 40 题、Codebase 19 个任务位置。文件名从 `task-000` 开始计数，对应第 1 题。

| 目录 | 已评分轨迹 | 中止动作轨迹 | 轨迹字节数 |
|---|---:|---:|---:|
| `no_memory/` | 59 | 0 | 1,495,048 |
| `notepad/` | 59 | 0 | 1,017,264 |
| `jaccard/` | 59 | 0 | 800,393 |
| `claude_code/` | 59 | 0 | 2,165,073 |
| `codex/` | 59 | 0 | 1,345,346 |
| `hermes/` | 58 | 1 | 1,041,263 |

每个方法下分为 `database/` 与 `codebase/`。例如 `codex/database/task-000.json` 是 Codex 的数据库第 1 题。

## 来源与边界

[manifest.json](manifest.json) 提供每个文件的 SHA-256、字节数、方法、环境、题号、结果和原始来源路径。导出文件与本地源文件逐字节一致；原始运行目录没有修改。

本目录的 `.gitattributes` 禁用 JSON 换行转换，使不同平台检出后的文件仍与索引中的字节数、哈希一致。

采用最终报告的结果选择：No Memory Codebase 第 14、17 题以及 Jaccard Codebase 第 19 题使用三次授权重跑的轨迹，包括成绩变差的重跑；索引标注 `authorized_rerun_selected` 和 `source_run_id`。未混入被替代的旧版本或验收调试轨迹。

这些文件是业务层的合法轨迹投影，**不等于框架完整原生逐消息日志**，不包含完整内部推理、记忆维护会话、原生状态快照、重复的 provider 请求/响应、数据库副本或 LLM judge 材料。Database 反馈保留对错和提交内容，不补入隐藏正确答案；Codebase 使用本轮已批准的官方可见测试口径。

导出前检查了各任务配置中的已知本地凭据及常见密钥/认证头格式，未发现命中。这些文件供离线审计使用，后续受测 agent 不应获得本目录，以免看到未来题的轨迹。

## 校验

在实验目录执行：

```powershell
.local/clbench-venv/Scripts/python.exe export_business_trajectories.py --verify
```

`--verify` 只需本目录及索引，不需要私有运行记录，不调用模型。重新导出需要本地 `private-runs/` 原始文件。有关成绩与分析，见[执行结果](../RESULTS_FINAL.md)和[全量分析](../FULL_ANALYSIS.md)。
