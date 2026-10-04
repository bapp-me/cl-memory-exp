# Jaccard 基线下的记忆访问方式综合报告

状态：报告与第三轮补充语义审查已完成。独立 HTML 面向没有项目背景的读者；本目录没有运行求解器、没有改变原三轮停止台账。补充审查也已关闭。

- [直接打开完整HTML报告](report.html)：独立离线文件，约1MB，含图表、逐题筛选、真实轨迹、完整提示词及评审输入输出。
- [对外分享包](jaccard-memory-report.zip)：11个白名单文件，包含报告与数据/引用复核附录；不含内部推理、凭据或工作区。
- [完整文字副本](report-complete.md)：含静态表与展开证据。
- [最终验收](records/report-acceptance.json) / [分享清单](records/share-manifest.json) / [浏览器检查](records/browser-check.json)。

本次新增授权：用户于2026-10-04明确选择“补做48条GLM审查，报告口径对齐”。只分析已存在的第三轮48条轨迹，复用前五方案完整提示词。GLM glm-5.3-flash/high、max_tokens24000、并发24；首条计入48，无质量重试，无自动传输重发。全部尝试和未知usage保留，金额未知。

运行后追加的传输修订：24并发波次出现19个真实HTTP429/1302，在途5个成功响应全部保留（含坏JSON），停止继续派发。并发降到4，仅允许真实429请求原样重发一次；最多48个语义案例、96个HTTP尝试，不扩大案例或重跑求解。原授权配置存于 records/review-authorization-original.json，修订及失败usage未知见 records/transport-recovery.json。无质量重试规则不变。

主体比较：冻结简单库Jaccard + lexical、hybrid_context、graph_walk、native_files、native_shell + 第三轮compact原生文件，共7种配置、336次既有求解执行。第1、2轮优化仅解释研究历程，既有历史No Memory单列。新报告不会把旧在线Jaccard的DeepSeek审查冒充冻结Jaccard的同口径GLM审查。

全部48条补充评审均收到模型回复，67HTTP尝试，19次429的usage未知，已知752,953 tokens。38条JSON可解析、5条严格结构/原引文通过、28条已有判断引用可定位；48条全部七项原文值可提取，不代表语义正确率。12个独立目标由主agent作证据复核，非人工真值。

特别披露：第三轮公共响应省略source IDs，补充评审包的detailed_source_ids为空。真实记忆文本始终可见；此空值是元数据缺失，不是来源未曝光。D0已通过实际曝光调用关联私有完整来源重建为44/46。原始评审包和输出没有改写，该字段不能独立支持缺失结论。

复核只读记录：build_data.py → audit_semantics.py → adjudicate_round3.py → render_report.py。check_report.mjs使用本机独立无头Chrome验证交互与响应式布局，不访问用户浏览器资料或外网；其依赖路径需按目标机器调整。accept_report.py做哈希、计量、停止规则与精确凭据扫描，生成限定分享包。私有原始API响应只留在研究目录，不进入分享包。
