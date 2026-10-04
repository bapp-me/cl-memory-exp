# 原始来源与核查边界

以下来源与范围说明沿用 2026-10-04 首次可行性核验的交付包。本次代码同步未重新开展文献调研，也没有复现这些论文的模型实验；不把旧核查写成新验证。以下支持机制范围，不替本地原型或任何新方法背书。

1. **STAND: Self-Aware Precondition Induction for Interactive Task Learning**，arXiv:2409.07653v2，2026-02-04。重点：Introduction 的小样本、离散特征、错误复发；§3 多个一致规则及不确定性；Methods/Results 的范围。不是从任意 LLM 原始轨迹中无先验归纳全部规则的直接证据。
   https://arxiv.org/html/2409.07653v2
2. **MemGuard: Persisting Verifier Signals for LLM-Agent Memory Governance**，arXiv:2608.21867v1。重点：§3.3 准入和验证信息；§3.4 的 failure-guard path、适用性和 over-general 规则惩罚；附录的文本约束呈现。不能把 failure guards、准入或范围控制单独声明为新贡献。
   https://arxiv.org/html/2608.21867v1
3. **VeriGuard: Enhancing LLM Agent Safety via Verified Code Generation**，arXiv:2510.05156v1。重点：§3.1 请求和 agent specification；§3.2 约束生成、消歧、测试和形式验证；§3.3 运行时参数获取和拦截。形式验证对象为代码对指定约束的满足，不自动证明推断的需求正确。
   https://arxiv.org/html/2510.05156v1
4. **Daikon 官方项目**：动态发现 likely invariants，作为“从轨迹归纳断言早有经典工具”的背景。本次没有在数据上运行 Daikon。
   https://plse.cs.washington.edu/daikon/
5. **pandas.merge 官方文档**：`validate` 已有 `one_to_one`、`one_to_many`、`many_to_one` 等检查。单纯在数据关联前增加唯一性检查不是新功能。本文原型实际使用 SQLite；NULL 语义不要混用。
   https://pandas.pydata.org/docs/reference/api/pandas.merge.html
6. **用户仓库：GLM 凭据存储与跨对话记忆链路复盘**。本次通过连接器读取报告；没有访问原始本机会话、凭据值或 DPAPI 密文。报告支持操作前提曾被违反，不能单独证明需要复杂学习算法或定位压缩为原因。
   https://github.com/bapp-me/cl-memory-exp/blob/main/docs/GLM凭据存储与跨对话记忆链路复盘.md

本文没有据此宣称文献已穷尽。具体方法确定后仍需核对更接近的实现，但不应在证据不足时把“尚未找到”写成“没有人做过”。
