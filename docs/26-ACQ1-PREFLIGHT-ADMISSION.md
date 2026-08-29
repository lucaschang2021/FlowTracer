# FlowTracer ACQ-1 Preflight 准入

状态：已生效

前置基准：`main@f008eea0730f91e0bd04dc2a2661523f62cb06e1`

生效基准：`main@298b299cf2d16a58d9b4d4e8d0aabd4d26f90248`

控制 PR：#27（已 Review 并合并）

目标：新的 Codex 任务，仅执行只读 Preflight

## 前置事实

- Backend Alpha Core BE-1 至 BE-8 已完成独立验收。
- BE-8 PR #26 已合并，merge commit 为 `f008eea0730f91e0bd04dc2a2661523f62cb06e1`。
- ACQ-1 总控任务包已提供，但尚未形成经 Preflight 验证的实施基线。
- Frontend、Integration、Release 均未准入。

## 本次授权范围

只允许：

- 读取当前门禁、ACQ-1 任务包和直接相关的 BE-4/BE-8 契约与实现；
- 审查 Source、RawItem、CollectionRun、SafeFetcher、采集调度、幂等与补偿机制；
- 核对 Python 3.13、uv、Docker、Scrapling、浏览器运行时和现有依赖的兼容性；
- 设计 ACQ-1A 至 ACQ-1H 的实施顺序、任务拆分、Adapter Boundary 与离线测试矩阵；
- 评估数据库 Schema、迁移、公开 API/OpenAPI、Pipeline、依赖、Compose 和资源预算影响；
- 输出风险、阻塞、ADR 建议和 ACQ-1 Preflight Report。

## 明确禁止

- 不修改业务代码、模型、迁移、依赖锁文件、Compose 或公开契约；
- 不安装依赖，不启动 Docker/Browser，不访问真实目标站点，不运行全量测试；
- 不创建 `feat/acq-1` 或子开发分支，不 commit/push/创建实现 PR；
- 不实现 Scrapling、动态浏览器、Spider、Change Intelligence、Opportunity Radar 或 Action Payload；
- 不准入 Frontend、Integration 或 Release。

## Preflight 报告必须回答

1. 现有 Source `config`/metadata 是否能承载 Source Profile；若不能，提出 Schema 与迁移建议。
2. 统一 AcquisitionBackend / AcquisitionResult 如何与现有 RawItem Pipeline 接合。
3. Native、Scrapling、Dynamic/Advanced 的路由、降级和成本控制策略。
4. Browser 如何继承 SSRF、redirect、DNS rebinding、访问控制和站点政策边界。
5. Controlled Discovery 的 scope、depth、pages、duration、concurrency 与 browser budget。
6. Change Intelligence 的版本证据、指纹、噪声过滤和语义变化成本边界。
7. Opportunity/Freelance Profile、评分冻结点和人类确认边界。
8. ACQ-1A 至 ACQ-1H 的依赖图、阶段拆分、每阶段验收标准与回滚点。
9. 预计新增/修改文件、Schema/API/dependency/Compose 影响及兼容策略。
10. 离线 Fixture、动态本地站点、SSRF、并发、资源耗尽和 BE-1..BE-8 回归矩阵。

## 停点

Preflight 报告提交后必须停止。总控完成审查、解决契约缺口并签发 ACQ-1 正式准入前，不得开始编码或创建开发 PR。
