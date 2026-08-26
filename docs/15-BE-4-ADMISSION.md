# FlowTracer Alpha v0.1 BE-4 阶段准入许可

- Phase：BE-4 RSS、URL 采集与任务调度
- 状态：批准（本文件所在控制 PR 合并后生效）
- 前置验收：BE-3 PR #8 已经总控验收并合并至 `main`
- 基准：`docs/07-BE4-ACQUISITION-BASELINE.md`

## 正式范围

- 实现安全 fetcher、RSS/Atom 与单页 URL 适配器、Celery scheduler/dispatcher/worker。
- 实现手动采集、运行与 RawItem 查询 API、幂等、状态、计数、去重和安全化错误。
- 按 BE-4 基线完成 SSRF、逐跳重定向、DNS rebinding、超时、大小和 Content-Type 防护。
- 允许为 BE-4 必需的依赖、配置、迁移、测试和运行文档做最小修改。

## Git 与交付

- 本控制 PR 合并后，创建全新的 Backend Codex 任务。
- Backend 分支：`feat/be-4`，必须从最新 `origin/main` 创建。
- 完成后 commit、push、创建 PR，但不得 merge；阶段报告必须直接发送给总控任务。
- 同一最终 commit 由 Backend 执行一次全量门禁；总控在正式 Review 时独立复跑一次。

## 禁令

- 不创建 Document，不实现清洗、AI、评分、Embedding、通知、WebSocket 或 BE-5+ Pipeline。
- 不实现站点级深爬、登录态采集、反爬绕过、任意浏览器自动化或公网测试。
- 不修改已冻结 Auth、Radar、Source 语义；契约或数据库变化超出本基线时先停点并提交 ADR 请求。
- 未经总控书面许可不得进入 BE-5；Frontend、Integration、Release 继续未准入。

## 阶段报告

必须包含：变更范围、commit、迁移及回滚、测试与覆盖率、SSRF/并发/幂等证据、Docker/Celery 运行证据、接口/OpenAPI 变化、风险、PR 链接和下一阶段建议。
