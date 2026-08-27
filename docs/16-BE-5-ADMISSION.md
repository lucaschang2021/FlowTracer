# FlowTracer Alpha v0.1 BE-5 阶段准入许可

- Phase：BE-5 清洗、AI 分析、评分与成本
- 状态：批准（本文件所在控制 PR 合并后生效）
- 前置验收：BE-4 PR #11 已由总控验收并合并至 `main`，merge commit `7955906259a64f34bc91f4db1eec30e807f3f29c`
- 稳定基准：`main@7955906259a64f34bc91f4db1eec30e807f3f29c`
- 契约基准：`docs/08-BE5-INTELLIGENCE-BASELINE.md`

## 正式任务包

- 实现 RawItem 清洗、Document 强哈希去重、Radar 绑定展开及幂等 Analysis Pipeline。
- 实现 `AnalysisProvider`、确定性 Fake Provider 和单一 `openai_compatible` Provider；严格输出 Schema、有限重试、repair、超时、响应上限与秘密脱敏。
- 服务端计算四维综合分、Recommendation 和通知阈值资格；写入版本、Provider/Model 与逐调用 AIUsageRecord。
- 实现 pending dispatcher、失联 running 恢复、人工 Analysis retry，以及 Intelligence 列表/详情 API 和 OpenAPI。
- 允许为 BE-5 必需的配置、依赖、测试、Compose 和运行文档做最小修改。预期不新增迁移；需要迁移时必须先停点报告。

## Git 与汇报

- 本控制 PR 合并后，在现有 Backend 任务中从最新 `origin/main` 创建或重建 `feat/be-5`；固定工作目录仍为 `D:\FlowTracer-wt\backend`，不得修改其他 worktree。
- 完成后执行 commit、push、创建 PR，但 Backend 不得 merge；阶段报告必须直接发送给总控任务。
- 同一最终 commit 由 Backend 最多执行一次全量门禁；总控只在最终待合并提交上独立执行一次。失败后只运行受影响定向检查，最终候选再统一门禁。
- 批量执行独立只读检查；先在沙箱运行，只有实际权限或网络失败后才申请最小提权；成功日志仅保留摘要。

## 禁令

- 不实现 Embedding、DocumentChunk、向量索引/检索、Bookmark、Notification、WebSocket 或 BE-6+。
- 不实现多模型 Router、自动模型选择、Agent、知识图谱、微服务或公网自动测试。
- 不记录 Prompt、正文、原始模型输出、API Key、Token 或连接串；不在数据库事务中等待远程 AI。
- 不改变冻结评分公式、版本字符串、公开 API、实体语义或数据库 Schema；确需改变时先提交 ADR 请求。
- 未经总控书面许可不得进入 BE-6；Frontend、Integration、Release 继续未准入。

## 阶段报告

必须包含：变更范围、commit、迁移/零漂移、测试与覆盖率、清洗/去重证据、Provider 与严格 Schema 证据、评分/成本边界、并发/幂等/恢复证据、安全脱敏、Docker/Celery 运行证据、接口/OpenAPI 变化、风险、PR 链接和下一阶段建议。
