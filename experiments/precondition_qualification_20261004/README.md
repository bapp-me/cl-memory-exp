# 操作前提学习：资格检查工具包

日期：2026-10-04。目标：先检验“普通模型 + 完整合法历史 + 通用 preflight”是否仍存在可复现缺口，再决定是否开发可执行规则学习方法。

**入口：[实验指南](实验指南.md)。** 本目录是独立资格检查，不续跑旧 agentic-search 批次，不更改已有计划、成绩、评分 mask 或预算。当前只完成离线结构检查与脚本测试；没有真实 GLM 调用，没有端到端 agent 效果结论。

## 本地开始

在仓库根目录执行：

```powershell
cd experiments/precondition_qualification_20261004
python -X utf8 probe.py
python -X utf8 -m unittest -v test_tools test_qualification
python -X utf8 qualification.py init
```

需要 Python 3.10+，全部代码使用标准库。`init` 生成 `.local/cases/` 的待填模板，不会伪造事故、标签或调用模型。原始记录不足时应停在收集阶段。

**SQL 演示仅用于回归。** 48 个构造实例、一个机制族、0 个独立真实事故。简单规则已经解决它，当前输入也足够判断，不能据此证明记忆必要，更不建议继续为它大批调用模型。[离线实测](records/offline_probe_results.json)

## 文件导航

| 文件 | 用途 |
|---|---|
| `实验指南.md` | 数据准备、权限与凭据、dry-run、接口 smoke、48 次三组筛查、验收与停止 |
| `qualification.py` | 生成模板、结构/人工签认检查、冻结请求、显式执行、中文结果表 |
| `model_gate.py` | 默认 dry-run 的单步动作判定；支持 A/B/C 交错执行和逐请求账本 |
| `score_model_gate.py` | 独立离线评分；区分漏拦、误拦、inspect、无效、缺失与未知用量 |
| `probe.py` | 原可行性包的 SQL、规则枚举、评分器反例检查；不执行模型代码 |
| `test_tools.py`、`test_qualification.py` | 标准库单元/集成测试，只使用脚本化回环服务 |
| `VALIDATION_PROTOCOL_CN.md` | 资格筛查之后的机制验证和端到端实验边界 |
| `SOURCES.md` | 首次可行性核验的相关工作与证据限制；不是本次新综述 |
| `records/sync_acceptance.json` | 本次代码同步的测试、原包哈希与限制 |

本次本地测试：14 项通过。包含 65 次脚本化回环 HTTP 响应（16 成功 + 1 个 402 + 三组 48 次），这些不是模型调用。实际 provider 和 Windows 本机环境仍需本地验收；Linux 上的标准库测试不等于已验证 Windows/GLM。

## 安全与研究边界

`outputs/`、`.local/`、`runs/` 默认被 Git 忽略；其中可能存在私有评分、真实历史和敏感模型响应。分享前应脱敏并审查，不用 `git add -f` 批量上传。密钥只从现有安全入口放入进程环境，脚本不会扫描旧凭据目录。

资格检查通过只意味着可以继续有限验证，不等于方向有效或有新颖性。判定正确不等于 agent 执行正确；相关工作已覆盖前提学习、failure guards 和可执行策略验证，必须保留简单对照。
