# FlowTracer Alpha v0.1 BE-3 阶段准入许可

- Phase：BE-3 Radar 与 Source 管理
- 状态：批准（本文件所在 PR 合并后生效）
- 前置验收：BE-2 PR #6 已通过总控最终验收并合并至 `main`

## 1. 正式范围

- 实现 `docs/06-BE3-RADAR-SOURCE-BASELINE.md` 冻结的 Radar、Source、状态和绑定 API。
- 实现 URL 纯函数规范化、分页筛选、软删除、所有权和并发冲突处理。
- 补齐 OpenAPI、真实 PostgreSQL 集成测试与运行文档。
- 不访问来源网络，不创建采集任务，不实现 BE-4+ Pipeline。

## 2. Git 与交付

- Backend 工作分支：`feat/be-3`，必须从合并本准入文件后的最新 `origin/main` 创建。
- 完成后 commit、push、创建 PR；Backend 不得自行 merge。
- 完成后立即停止，并将完整阶段报告直接发送给总控任务。
- 未经总控书面许可不得进入 BE-4。

## 3. 禁令

- 不修改冻结的 BE-2 模型语义或 Auth 契约；需要迁移时先报告总控。
- 不实现 RSS/HTML 获取、SSRF 网络检查、调度、CollectionRun 或 RawItem 业务。
- 不引入 Alpha 范围外依赖、数据库或服务。
- 不批准 Frontend、Integration 或 Release 开工。
