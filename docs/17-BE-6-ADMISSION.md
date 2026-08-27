# FlowTracer Alpha v0.1 BE-6 阶段准入许可

- Phase：BE-6 Vector Memory 与知识库接口
- 状态：批准（本文件所在控制 PR 合并后生效）
- 前置验收：BE-5 PR #14 已由总控验收并合并至 `main`，merge commit `23afb336f28e07761fdcc4f1c835d876f9ac3c42`
- 稳定基准：`main@23afb336f28e07761fdcc4f1c835d876f9ac3c42`
- 契约基准：`docs/09-BE6-MEMORY-BASELINE.md`

## 正式任务包

- 实现确定性切块、`EmbeddingProvider`、Fake 与单一 openai-compatible Adapter、逐调用 Usage 和安全错误边界。
- 实现至少一次投递下的 Document embedding dispatcher、并发串行化、Chunk 原子写入以及 `embedding -> ready|failed` 状态机。
- 新增 HNSW cosine 索引迁移，并完成 upgrade/downgrade/re-upgrade、索引定义与零漂移验证。
- 实现 Bookmark CRUD、Memory Search、用户隔离、Radar/日期/Bookmark 过滤、Top-K 上限，并为 Intelligence 响应增加 `bookmarked`。
- 允许为 BE-6 必需的配置、依赖、测试、Compose、OpenAPI 和运行文档做最小修改。

## Git、额度与汇报

- 本控制 PR 合并后，现有 Backend 任务必须在 `D:\FlowTracer-wt\backend` 从最新 `origin/main` 创建或重建 `feat/be-6`；不得修改其他 worktree。
- 完成后 commit、push、创建 PR，但 Backend 不得 merge；阶段报告必须直接发送给总控任务。
- 遵循 `AGENTS.md`：只读取 CURRENT-GATE、本阶段基线/准入、直接契约和改动文件；批量执行独立检查；先沙箱、实际失败后最小提权；成功日志仅报摘要。
- 同一最终 commit Backend 最多一次全量门禁；总控只在最终待合并 commit 独立执行一次。未变更 commit 不重复全量测试。

## 禁令与停点

- 不实现 Notification、WebSocket、CollectionRun retry、外部知识库同步或任何 BE-7+ 内容。
- 不引入 Qdrant、Milvus、Neo4j、Kafka、微服务、多模型 Router、Agent 或知识图谱。
- 不在事务/行锁内调用远程 Provider，不记录正文、查询、向量、API Key、Token 或连接串，不以 Python 后过滤替代数据库所有权约束。
- 不改变已冻结实体、1536 维、Feed 排序或 API 语义；确需改变时先停点提交 ADR 请求。
- 未经总控书面许可不得进入 BE-7；Frontend、Integration、Release 继续未准入。

## 阶段报告

必须包含：变更范围、commit、迁移循环/零漂移、测试与覆盖率、切块/向量证据、Provider 有界读取、安全脱敏、并发/幂等/恢复、HNSW 定义与检索结果、SQL 所有权隔离、Bookmark 授权生命周期、Docker/Celery 运行证据、接口/OpenAPI 变化、风险、PR 链接和下一阶段建议。
