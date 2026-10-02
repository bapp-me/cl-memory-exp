# 00–06 执行记录

依据仓库根目录 `Agent_Memory_Research_Plan_CN_v1.0_Final.md`。本目录是新实验，历史 memory_direction / memory_scope_fix 结果仅用于定位已有依赖和凭据，不计为本方案结果。

## 用户已确定的覆盖

- Model A：用户指定 DeepSeek V4.1 Flash；现有接口 ID `deepseek-flash`，本轮连接成功并核对官方 ID 映射；仍是可变别名。
- Model B：用户指定 GLM 5.3 Flash；现有接口 ID `glm-5.3-flash`。
- 6.5：1 × 3 × 1 × (24 + 40) = 192 次任务执行。
- 6.6：2 × 8 × 3 × 1 = 至多 48 次；复用正常分支须满足快照和配置一致性。
- 两项合计至多 240 次，不包括校准、canary、6.9 完整流与非代码检查。
- 不自动追加重复；6.8 中重复一致性条件暂不可判定。单次成本比仅描述，不视作两次重复都满足的否决证据。

## 当前验收状态

校准及第 6 节均已完成（按用户修订范围）：两组完整代码第一遍各 96 题，记忆组只读抽测 12 题，两组非代码各 8 题。详见 [第6节完成报告](第6节完成报告.md)。未执行原生完整第二遍，未启动第 7 节。完整实验过程见仓库根目录 `Agent_Memory_实验过程记录.md`。

| 范围 | 已完成 | 待完成 |
| --- | --- | --- |
| 00–03 | 范围、Pi 工具接入、隔离、持久状态审计 | 运行验收和最终状态审计已完成 |
| 04 | 单次 2×2 校准共 88 次、主模型选择 | Mem0 确认按低接入路径延至 baseline 集成 |
| 05 | 数据访问记录与开发/验证预留 | 验证环境的实际兼容验收属后续 baseline 阶段 |
| 06.1–6.4 | 两基准接入、正负评分检查；93 个有效代码参考任务通过 | 无 |
| 06.5 | 任务选择、配置与三题评分排除已冻结 | 已完成 192 次初筛 |
| 06.6–6.8 | 诊断目标、分支、历史选择规则预登记 | 已完成 16 个目标；保留默认 AgentCL 开发分工 |
| 06.9–6.10 | 两组完整第一遍、12 题记忆抽测、两组 BabyAI、访问登记及归档 | 用户修订范围无剩余任务；不声称完整原生第二遍 |

只运行 1 次独立重复；用户将 AgentCL 第二遍修订为记忆组 12 题只读抽测，不执行无记忆第二遍；不再宣称完整原生两遍协议。问题资产保留在任务流中，仅排除评分：pilot 分母 23/24、完整流 93/96。主要复杂任务指标另按有效复杂任务集合统计。

## 用户补充决定

校准也只运行 1 次；本轮预算暂不设上限，仍记录调用和费用；CL-Bench 屏蔽标准答案与参考 SQL，并明确报告反馈协议改动。密钥使用已找到的本地加密存储。完整实验过程持续写入仓库根目录的《Agent Memory 实验过程记录》。

## 环境检查

当前 Python 3.12.7，Node 22.20.0；PATH 未发现 Docker/uv。首次受限查询返回 E_ACCESSDENIED；提升权限后的只读查询确认存在 WSL2 Ubuntu，当前停止，后续检查其隔离能力。官方 CL-Bench 主框架要求 Python 3.13+；Database Exploration 本身使用 SQLite，需进一步确定最小依赖及原生 adapter 方案。AgentCL 的模型生成代码需真正受限执行环境，普通同用户子进程不能算权限隔离。

本地 Pi 可作为固定版本候选，已通过本轮工具接入和状态检查。官方最新源码版本与本地包版本分别记录，不混称。

## 复核入口

从仓库根目录执行 `python experiments/agent_memory_plan_20261002/preflight.py` 检查公开元数据和本地依赖，不读取密钥、不发模型请求。

执行 `python experiments/agent_memory_plan_20261002/prepare_manifest.py` 生成依赖对选择：按目标在原流中的位置等距选 12 对，再保留原顺序。诊断 8 个目标同样在看结果前等距选定。脚本核对完整配对和任务数；再次执行只核验，不覆盖原登记时间。

`records/agentcl-selection.json` 目前是任务选择登记，运行配置未冻结，不能直接称为可运行实验 manifest。没有复制/输出标准解或测试代码到 agent 目录。后续运行必须另行完成权限隔离。

## 一手来源

- [AgentCL 数据卡](https://huggingface.co/datasets/osunlp/AgentCL/blob/a01e2ca6e33fd07d9cf80e4bd69a5b3585d3400f/README.md)
- [Database Exploration 源码](https://github.com/pgasawa/continual-learning-bench/blob/5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26/src/tasks/database_exploration/task.py)
- [CL-Bench 运行依赖](https://github.com/pgasawa/continual-learning-bench/blob/5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26/README.md)

实际进度、token 和费用估算见 `records/run-index.json`，校准结果见 `records/calibration-decision.json`，状态审计见 `records/state-audit.json`。原始轨迹保存在本地 `runs/`（Git 忽略）；摘要与审计记录提交 Git。
