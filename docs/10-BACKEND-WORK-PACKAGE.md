# FlowTracer Alpha v0.1 Backend 正式任务包

## 给 Backend 窗口的总指令

你负责 FlowTracer Alpha v0.1 后端开发。必须阅读并遵循：

- `docs/00-PROJECT-CONTROL.md`
- `docs/01-ARCHITECTURE-DECISIONS.md`
- `docs/03-BACKEND-CONTRACT-BASELINE.md`
- `docs/04-BE1-ENGINEERING-BASELINE.md`
- `docs/05-BE2-DATA-AUTH-BASELINE.md`
- 本任务包

按 Phase 顺序执行。每个 Phase 完成后停止并提交阶段报告，等待总控验收后再进入下一阶段。不得开发前端、上传 GitHub、引入未批准的数据库或微服务，也不得提前实现 v0.2+ 功能。

文档存在冲突时，停止冲突部分并报告，不得自行改变公开契约。允许在不改变契约的前提下补齐内部实现细节。

## 每阶段固定汇报格式

```text
Phase：
状态：完成 / 部分完成 / 阻塞
已完成：
变更文件：
数据库迁移：
测试命令与结果：
接口或契约变化：无 / 具体说明
风险与遗留：
下一阶段建议：
```

## Phase BE-0：工程盘点与实施计划

### 目标

在修改代码前确认工作区、总控文档、工具链和依赖条件。

### 任务

- 阅读全部总控和后端契约文档。
- 检查现有目录与 Git 状态，保护用户已有改动。
- 确认 Python、Docker、PostgreSQL/pgvector、Redis 可用性。
- 给出后端目录树、依赖清单和各阶段预计改动范围。
- 标记阻塞和需要总控决策的事项。

### 验收与停点

- 本阶段不安装依赖、不写业务代码、不创建迁移。
- 输出无歧义的实施计划、工具版本和潜在阻塞。
- 报告后停止，等待总控批准 BE-1。

## Phase BE-1：基础骨架与本地基础设施

> 本阶段必须遵循 `docs/04-BE1-ENGINEERING-BASELINE.md`；未获总控明确准入时不得开始。

### 目标

建立可启动、可测试、可迁移的 FastAPI 后端骨架。

### 任务

- 建立 `api`、`core`、`db`、`models`、`schemas`、`services`、`tasks`、领域模块与测试目录。
- 建立 Python 项目元数据和锁定依赖，明确 Python 版本。
- 实现分环境配置、结构化日志、`request_id` 和统一错误响应。
- 配置 SQLAlchemy 2.x async、Alembic、PostgreSQL + pgvector。
- 配置 Celery + Redis，本阶段只实现探活任务。
- 提供 API、Worker、PostgreSQL、Redis 的 Docker Compose 开发配置。
- 实现 `/api/v1/health/live` 与 `/api/v1/health/ready`。
- 建立 Pytest、异步测试数据库和统一测试命令。

### 验收与停点

- 新环境按说明可启动 API 和 Worker。
- Readiness 正确反映数据库与 Redis 状态。
- 空库执行 `alembic upgrade head` 成功。
- 测试通过且配置不含真实密钥；本阶段无业务 CRUD。
- 报告后停止，等待总控批准 BE-2。

## Phase BE-2：数据模型、迁移、认证与用户

> 本阶段必须遵循 `docs/05-BE2-DATA-AUTH-BASELINE.md` 与 `docs/13-BE-2-ADMISSION.md`；准入文件所在 PR 未合并时不得开始。

### 目标

落地全部 Alpha 实体，并完成安全的用户身份闭环。

### 任务

- 实现契约中的模型、约束、外键和必要索引。
- 创建可从空库升级的 Alembic 迁移。
- 实现邮箱规范化、注册、登录、刷新、登出和当前用户接口。
- 密码使用 Argon2id；Refresh Token 仅保存哈希并支持撤销。
- 实现 Access/Refresh Token 生命周期配置和用户资料更新。
- 测试重复邮箱、失效/撤销 Token、数据库约束和跨用户越权。

### 验收与停点

- Auth 与 User API 测试通过。
- Token、密码和密钥不出现在日志中。
- 迁移可重复执行，模型与迁移一致。
- 报告后停止，等待总控批准 BE-3。

## Phase BE-3：Radar 与 Source 管理

### 目标

完成用户配置 Radar 和信息来源的管理闭环。

### 任务

- 实现 Radar CRUD、分页、软删除、暂停与恢复。
- 实现 Source CRUD、URL 规范化、分页、软删除、暂停与恢复。
- 实现 Radar 与 Source 多对多绑定和解绑。
- 校验类型、分类、关键词、通知阈值和采集间隔。
- 测试对象所有权、跨用户越权和重复规范化 URL。
- 创建 `api` 类型 Source 时返回明确的 Alpha 不支持错误。

### 验收与停点

- Radar/Source API 与统一错误契约一致。
- 删除 Radar 不误删仍被其他 Radar 使用的 Source。
- OpenAPI Schema 可供前端使用。
- 报告后停止，等待总控批准 BE-4。

## Phase BE-4：RSS、URL 采集与任务调度

### 目标

建立可靠、受控、幂等的数据采集链路。

### 任务

- 实现 RSS 解析与单页 URL HTML 提取适配器。
- Scrapling 只用于契约允许的页面提取范围。
- 实现定时和手动采集；API 仅创建任务并返回运行 ID。
- 实现 CollectionRun/RawItem 状态、计数、错误记录和查询接口。
- 实现 URL、external ID 和内容 SHA-256 去重。
- 实现超时、响应大小、重定向、Content-Type 限制和指数退避。
- 完整实现 SSRF 防护，每次重定向重新校验。
- 采集测试使用本地 Fixture 或 Mock，不依赖公网。

### 验收与停点

- RSS 与 URL Fixture 均能产生 RawItem。
- 相同输入重复执行不会产生重复 Document。
- 测试证明私网、本机和非法协议不可访问。
- 失败运行可查询、可重试且错误信息安全。
- 报告后停止，等待总控批准 BE-5。

## Phase BE-5：清洗、AI 分析、评分与成本

### 目标

完成 Raw Content 到结构化 Intelligence 的可追踪 Pipeline。

### 任务

- 实现清洗、去重、分类、摘要、四维评分和推荐流程。
- 使用 AI Provider 接口，业务层不直接绑定厂商 SDK。
- 使用严格 JSON Schema 校验模型输出，处理结构错误、超时和限流。
- 实现冻结的评分公式、推荐区间和通知阈值。
- 保存 Pipeline/Prompt 版本、Provider、Model、Token、耗时和估算成本。
- 状态转换必须幂等，并保存安全化失败原因。
- 默认测试使用 Fake Provider；真实 Provider 仅用于显式集成测试。

### 验收与停点

- 固定输入可通过 Fake Provider 稳定生成 Analysis。
- 分数边界、公式、Recommendation 和阈值测试通过。
- 同版本重试不重复生成 Analysis。
- 模型超时、限流、非法 JSON 和部分失败均有测试。
- 报告后停止，等待总控批准 BE-6。

## Phase BE-6：Vector Memory 与知识库接口

### 目标

完成文档向量化、用户隔离检索、Feed 和收藏能力。

### 任务

- 实现可配置的文本切块策略并记录顺序。
- 通过 Embedding Provider 生成 1536 维向量并写入 pgvector。
- 实现相似度检索以及 Radar、日期过滤。
- 实现 Bookmark CRUD、Intelligence Feed、详情和 Memory Search。
- 检索结果返回分数、标识和必要摘要，不返回无权限正文。
- 测试向量维度、空内容、重复切块、用户隔离和 Top-K 上限。

### 验收与停点

- 完整分析后的 Document 进入 `ready`。
- 用户只能检索自己的 Radar 可访问内容。
- Feed 过滤、排序和分页稳定。
- 不产生悬空访问或跨用户泄漏。
- 报告后停止，等待总控批准 BE-7。

## Phase BE-7：通知、WebSocket 与恢复

### 目标

为桌面端提供可靠的高价值事件和后台任务恢复能力。

### 任务

- 达到 Radar 阈值时幂等创建 Notification。
- 实现通知列表、单条已读和全部已读。
- 实现带 Access Token 鉴权的 `/api/v1/ws`。
- 发送 `collection.updated`、`analysis.completed`、`notification.created`。
- 实现统一 Event Envelope 和事件 ID。
- 实现采集运行和分析的所有者手动重试接口。
- 确保 WebSocket 断线不影响事实数据，REST 可以恢复状态。

### 验收与停点

- 同一 Analysis 不会产生重复通知。
- 未认证 WebSocket 被拒绝，跨用户事件不可见。
- 断线重连可通过 REST 补齐。
- 重试具备所有权检查和审计日志。
- 报告后停止，等待总控批准 BE-8。

## Phase BE-8：稳定化与前端交接

### 目标

形成可供 Frontend 开工和 Integration 验收的稳定后端版本。

### 任务

- 运行并修复所有单元、API、任务、迁移和安全测试。
- 增加闭环测试：注册 -> Radar -> Source -> 采集 -> AI -> 向量 -> Feed -> Notification。
- 验证错误格式、分页、鉴权、超时、重试和幂等。
- 导出并核查 OpenAPI JSON。
- 完善启动、迁移、测试、Worker 和环境变量说明。
- 提供前端接口清单、枚举、示例 Payload 和 WebSocket 事件样例。
- 汇报性能基线，不提前做大规模优化。

### 最终验收

- 后端完整测试套件通过。
- 空数据库可迁移并启动。
- 使用 Fake AI Provider 可离线完成数据闭环测试。
- OpenAPI 与实现一致，无未记录的破坏性变化。
- P0/P1 后端缺陷为零。
- 总控通过后，Frontend 才获得正式准入。

## 明确禁止事项

- 不开发 React/Tauri 页面。
- 不引入 Neo4j、Qdrant、Milvus、Kafka 或微服务。
- 不实现多模型 Router、知识图谱、团队/组织和企业权限。
- 不绕过站点安全、付费墙、验证码或访问限制。
- 不提交真实 `.env`、Token、API Key、用户数据或抓取正文样本。
- 不执行 GitHub 上传、Release 或生产部署。
- 不经总控批准改变公开 API、评分公式或实体语义。

