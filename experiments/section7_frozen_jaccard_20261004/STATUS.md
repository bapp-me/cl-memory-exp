# 冻结简单题库 Jaccard：48 题执行与结果审计完成

用户已授权唯一分支：48 道复杂题、Jaccard 原样 top-3、已有 No Memory 简单题库只读、R=1。用户另要求高并发，正式配置为最多 48 个独立任务/模型请求、8 个本机 Python/评分沙箱槽位。

配置、源库和全部 48 题注入已冻结；只读写回拒绝、来源隔离和 WSL 环境 fixture 通过。详细边界见 [协议](PROTOCOL.md)。

首次启动在获取 API key 时失败，尚未进入任务运行或调用 provider。随后定位为账户上下文错误：提权进程是 BAPP/fucak（SID 尾号 1003），旧密钥受 Codex 沙箱账户 BAPP/codexsandboxonline（尾号 1007）的 DPAPI 保护。普通执行环境成功加载原密钥，无需更换或新提供 key。全部失败的凭据检查均未发出模型请求。

## 正式启动方式

在普通 Codex 沙箱环境执行 `python -X utf8 experiments/section7_frozen_jaccard_20261004/launch.py first`，随后使用 `remaining`。仅 WSL broker 使用提权运行，因为普通账户无权直接启动 WSL。付费入口只用于本次明确授权的 48 题。

新增 `launch.py check` 只检查凭据，不调用模型；它支持进程环境、用户/系统环境变量和原加密文件，均捕获读取结果且不打印密钥。普通环境的检查已成功。`launch.py first/remaining` 继续使用已冻结 runner，不改变实验条件。

48 题均已完成，99 个模型请求，usage 未知数 0；原口径正确 27/46，有效目标 tokens 468,934、PYTHON 48 次，全部执行 tokens 504,199。实测 API 并发峰值 47，后 47 题约 92.95 秒完成。原始基线 7,924 个文件哈希未变，冻结库与所有真实请求的来源检查通过。

见 [完整报告](冻结简单题库Jaccard补跑报告.md) 和 [机器结果](records/results.json)。被动 payload 校验已在 `audit.py` 支持 Pi 的文本块用户消息；首题没有因此重跑，原 runner/配置/模型输入未变。
