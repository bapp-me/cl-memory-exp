# 复现短任务记忆生命周期 fixture

本目录是合成协议检查，不运行 benchmark 或真实模型。Node v22.20.0、npm 10.9.3、Windows；Pi 四包 1.0.0、pi-hermes-memory 0.9.10、better-sqlite3 13.0.3、tsx 4.21.0。完整传递依赖固定在 runtime-package-lock.json。

从本目录执行（PowerShell）：

```powershell
New-Item -ItemType Directory -Force .runtime
Copy-Item runtime-package.json .runtime/package.json
Copy-Item runtime-package-lock.json .runtime/package-lock.json
Push-Location .runtime
npm ci --ignore-scripts --no-audit --no-fund --cache ../.cache/npm
Pop-Location
node sdk_fixture.mjs single
node sdk_fixture.mjs many_tools
node sdk_fixture.mjs foreground
node sdk_fixture.mjs dispose_six
node sdk_fixture.mjs shutdown_six
node sdk_fixture.mjs flush_one
node sdk_fixture.mjs correction
node sdk_fixture.mjs review_hold
node sdk_fixture.mjs review_abort
node sdk_fixture.mjs flush_parse_fail
node sdk_fixture.mjs fallback_success
node sdk_fixture.mjs consolidate
node sdk_fixture.mjs overflow_grace
node --import ./.runtime/node_modules/tsx/dist/loader.mjs component_fixture.mts
node audit.mjs
```

本机在 ignore-scripts 下可直接使用 better-sqlite3，不代表所有 OS/Node ABI 都可；native module 加载失败应先报告环境限制，不应误算为记忆效果失败。npm ci 会访问公开包源；fixture 执行期仅允许自身本机假服务端口。固定 key `fixture-not-a-secret` 只用于该假服务，不读取真实凭据。

audit.mjs 的完整源码比较还依赖前轮 `.cache/pi-hermes-memory` 的固定源码。新 checkout 若无该缓存，可在 `../memory_ecosystem_20261003/.cache/` 中克隆公开 `https://github.com/chandra447/pi-hermes-memory` 到 `pi-hermes-memory`，并 checkout `c93e2885e57e79ae907cf3d718f9633d066b0217`。只检查本次列出的 12 个文件，经 CRLF 统一后和 npm 文件对照；不要求 Git 与 npm gitHead 相同。

每次执行生成独立 `.runtime/<scenario>-随机值`；父子共享该场景的隔离配置/记忆，绝不使用个人 Pi home。记录输出会覆盖 `records/<scenario>`，要保留已提交证据时请在另一个 checkout 复现，或先另存 records。运行时间、PID、端口、路径、Markdown 日期和哈希可变化；核心断言是请求角色/数量、写入与取消状态。

fixture 不修改 npm 插件；用真实加载器、工具、store、shutdown 和 child。仅模型回复/usage 是脚本指定。component fixture 用原生可注入 completeSimple seam，观察器故障也是注入，不是 SQLite 损坏试验。没有收费 provider、真实 token/金额/延迟、真实记忆语义、跨平台和全部重试路径的结论。

目录包含原始请求体、主会话事件、进程日志、内存文件快照和结果。最终记录 93 个本机请求；这个数字不包括前期调试与为补充进程观测而重放的 fixture。所有合成值都不能当作性能结果。13 组集成与 4 个组件断言共 17 项，不能称为 17 次统计独立效果实验。

原始调试失败保存在 records/fallback_attempt1 和 records/consolidate_attempt1；它们不属于最终通过集合。组件脚本首轮 .ts 的 CommonJS/top-level-await 解析错误在真正执行前发生，后改 .mts，未对生产代码作兼容补丁。
