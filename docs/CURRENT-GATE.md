# FlowTracer 当前阶段闸门

更新时间：2026-08-29。

- 当前稳定基准：`main@f008eea0730f91e0bd04dc2a2661523f62cb06e1`；BE-8 PR #26 已独立验收并合并，Backend Alpha Core BE-1 至 BE-8 已完成。
- 当前阶段：ACQ-1 Preflight（工程盘点与实施计划）。
- 准入：只批准 ACQ-1 Preflight；允许只读审查现有 Acquisition、Source、RawItem、CollectionRun、SafeFetcher、依赖与运行环境，并提交 ACQ-1A 至 ACQ-1H 实施计划、契约影响和风险报告。
- 未准入：ACQ-1 正式编码、依赖安装或升级、数据库迁移、公开 API/Schema 变更、Scrapling/Browser 引入、Frontend、Integration 与 Release。

后续 ACQ-1 Preflight 任务开始时只读取：本文件、`docs/02-DELIVERY-BOARD.md`、`docs/26-ACQ1-PREFLIGHT-ADMISSION.md`、用户提供的 ACQ-1 总控正式任务包、现有 BE-4 Acquisition 相关实现与契约，以及本次审查直接涉及的文件。无需回读全部历史基线。

Preflight 必须核对：

- BE-8 最终合并基准与工作树状态；
- Source / RawItem / CollectionRun 现有契约和数据库承载能力；
- SafeFetcher 的 SSRF、重定向、端口、响应大小、超时与 DNS rebinding 边界；
- RSS、Native HTTP、解析、调度、幂等、补偿与 Celery/Redis 现状；
- Scrapling、动态浏览器、Python 3.13、Docker 镜像及锁定依赖的当前兼容性；
- ACQ-1A 至 ACQ-1H 的拆分、依赖顺序、预计 Schema/API/dependency 影响、离线测试矩阵、资源预算和主要风险。

发现现有冻结 Schema、公开 API、Pipeline、评分或安全边界无法承载 ACQ-1 时，不得自行修改；必须在 Preflight 报告中提出 ADR、迁移和兼容性建议，等待总控单独冻结。

下一步：在新的 Codex 任务中执行 ACQ-1 Preflight，完成报告后停点。总控验收 Preflight、冻结 Acquisition/Opportunity 契约并签发正式实施准入前，不得创建 ACQ-1 开发分支或开始编码；Frontend 仍为 ACQ-1 的硬依赖下游阶段。
