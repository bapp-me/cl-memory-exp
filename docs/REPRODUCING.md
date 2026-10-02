# 复核与环境配置

## 1. 不调用模型的核验

在仓库根目录，使用 Python 3.11+（本次在 Windows/Python 3.12 验证）：

```powershell
python -X utf8 tools/verify_export.py
python -X utf8 experiments/agent_memory_plan_20261002/verify_freeze.py
python -X utf8 tools/restore_section6_runs.py
python -X utf8 tools/audit_section6_offline.py
```

导出核验验证原始导出文件的 SHA256；后续编辑这些文件会产生差异。归档恢复先验证归档 SHA256，拒绝路径越界、链接和内容冲突；相同文件可重复执行。恢复的 `runs/` 被 Git 忽略。离线入口从冻结 `core.py` 的 AST 读取原 `digest` / `memory_context` 纯函数，再执行原审计脚本，输出写入 `docs/verification/`，不修改历史证据。直接运行旧审计脚本会连带加载缺省 `.cache/clbench/task.py`，因此全新克隆应使用这个离线入口。

早期 scope 实验的无模型环境测试：

```powershell
Push-Location experiments/memory_scope_fix_20261002
python -X utf8 -m unittest test_environment -v
Pop-Location
```

## 2. Pi 依赖

本轮使用 Node.js 和已锁定的 `@earendil-works/pi-agent-core` / `pi-ai` 1.0.0。PowerShell 下运行：

```powershell
pwsh -File tools/setup_pi.ps1
```

安装脚本使用历史锁文件与 `npm ci --ignore-scripts`，只写入被忽略的 `.runtime/pi` 目录，不调用模型。

## 3. API 凭据

新机器使用环境变量 `DEEPSEEK_API_KEY` / `GLM_API_KEY`。不要把真实值写入版本控制、脚本或终端共享记录。仓库不附带任何可用凭据。

`tools/run_experiment.py` 在当前进程内将历史凭据函数替换为环境变量读取，再执行指定脚本；不改动原实验代码。它不会加载 `.env`，需要由终端或本地密钥管理工具设置环境变量。只有脚本实际请求凭据时才要求该变量存在。

```powershell
# 查看凭据包装器参数；没有指定脚本时不运行实验
python -X utf8 tools/run_experiment.py
```

本轮配置的官方入口：DeepSeek `https://api.deepseek.com` / `deepseek-flash`，GLM `https://api.z.ai/api/paas/v4` / `glm-5.3-flash`。这些是实验时的模型别名；后续运行必须重新核对其实际映射。

凭据包装器只适用于在本 Python 进程内调用模型的入口，例如已配齐运行环境后的 `run_stream.py`。旧批调度器会自行启动新的 Python 子进程，不继承函数替换；其子命令也必须显式通过该包装器启动，不能直接照搬旧批调度命令。

## 4. 付费复跑与沙箱限制

本轮在线代码执行是 **Windows + WSL Ubuntu 的专用隔离适配**，不是已验证的跨平台一键运行包。冻结 `core.py` 含原机器 `/home/fucak/.cache/agent-memory-plan-20261002` 路径；旧 Hermes 清单也记录原机器路径。未安装对应环境时，不要绕过沙箱直接执行模型代码。

完整复跑还需要：下载固定 benchmark 资产（`bootstrap_sources.py` / `prepare_database.py` 等）、恢复 Pi 依赖、准备 Python 3.10.22 运行时与 `requirements-codeeval-lock.txt`、启动 `sandbox_broker.py`、完成 canary 和验收。旧 Python 安装包 SHA256 在 `setup_code_runtime.sh` 中；缓存和上游第三方源代码不随仓库复制。

新机器若修改路径、adapter 或运行时，必须作为新配置记录变更，重新验收并使用新的 run ID；不能覆盖本轮证据或继续宣称完全相同的冻结配置。不要直接执行旧批量调度脚本来“试安装”：其中部分会产生 API 费用。`run_full_confirmation.py`、`run_readonly_subset.py` 等保留了本次运行的固定 ID，应先在新实验目录登记新配置。

仅离线复核无需 key、WSL、Pi 安装或下载基准数据。完整报告和原始证据可直接查阅。
