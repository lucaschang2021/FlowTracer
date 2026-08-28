# FlowTracer Alpha v0.1 Backend 正式任务包

## 给 Backend 窗口的总指令

你负责 FlowTracer Alpha v0.1 后端开发。必须阅读并遵循：

- `docs/00-PROJECT-CONTROL.md`
- `docs/01-ARCHITECTURE-DECISIONS.md`
- `docs/03-BACKEND-CONTRACT-BASELINE.md`
- `docs/04-BE1-ENGINEERING-BASELINE.md`
- `docs/05-BE2-DATA-AUTH-BASELINE.md`
- `docs/06-BE3-RADAR-SOURCE-BASELINE.md`
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

> 本阶段必须遵循 `docs/06-BE3-RADAR-SOURCE-BASELINE.md` 与 `docs/14-BE-3-ADMISSION.md`；准入文件所在 PR 未合并时不得开始。

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

在不改变数据库 Schema 的前提下，为桌面端提供可恢复的 Notification 事实、按用户隔离的 WebSocket 在线事件与采集运行重试。

### 任务

> 本阶段必须遵循 `docs/18-BE7-NOTIFICATION-WS-BASELINE.md` 与 `docs/19-BE-7-ADMISSION.md`；准入文件所在控制 PR 未合并时不得开始。

- 按 active Radar 当前阈值、冻结优先级与既有唯一约束幂等创建 Notification，并以 60 秒 dispatcher 补偿遗漏。
- 实现 Notification 列表筛选、稳定分页、单条幂等已读和同一 UTC 时间的 read-all；严格所有权与统一 404。
- 实现只接受握手 Authorization Bearer Access Token 的 `/api/v1/ws`，覆盖 Token 到期、停用/删除用户、多连接与 4401。
- 使用现有 Redis 按用户隔离 Pub/Sub；每连接队列固定 100，Redis 或背压失败关闭 1013，禁止全局广播后在 Python 过滤。
- 在数据库提交后发布稳定 event ID 的 `collection.updated`、`analysis.completed`、`notification.created` 最小 Envelope；发布失败不回滚事实。
- 新增所有者 `POST /collection-runs/{run_id}/retry`，创建新的 manual queued run，以 `retry:<original_run_id>` 实现并发和重复请求幂等。
- 保持既有 Analysis retry 公开契约，补齐通知/事件衔接和完整回归；不得复制第二 Analysis retry Endpoint。
- 复用现有 Notification、CollectionRun、Analysis 与 Redis，不新增表、列、枚举或迁移；若确需 Schema 变化先停点提交 ADR。

### 验收与停点

- Notification 阈值/优先级边界、并发唯一、历史补偿、REST、所有权及 Broker/Redis 失败测试通过。
- WebSocket Header 鉴权、Token 到期、同用户多连接、两用户隔离、稳定 event ID、严格事件 Schema、100 队列背压与断线 REST 恢复通过。
- CollectionRun retry 的原运行不变、新运行链式幂等、并发、失败链、状态/Source/所有权和 503 补偿通过；Analysis retry 全回归。
- locked sync、Ruff/format/Mypy/Pytest 覆盖率不低于 85%、Alembic 零漂移且无迁移、Compose、真实 PostgreSQL/Redis/Celery、OpenAPI 与秘密扫描全部通过。
- API/Worker 同镜像且非 root；使用无 Beat Worker 完成 Celery pong、live/ready 与真实 Redis Pub/Sub 复验。
- 提交阶段报告后停止；未经总控书面许可不得合并或进入 BE-8。

## Phase BE-8：稳定化、契约冻结与前端交接

> 本阶段必须遵循 `docs/20-BE8-STABILIZATION-HANDOFF-BASELINE.md` 与 `docs/21-BE-8-ADMISSION.md`；准入控制 PR 未合并时不得开始。

### 目标

在不扩大 Alpha 范围的前提下，形成可供 Frontend 开工和 Integration 验收的稳定、可重复、可追踪后端基线。

### 任务

- 运行并修复 BE-1 至 BE-7 的单元、API、任务、迁移、安全和并发回归；P0/P1 清零。
- 新增一个完全离线的真实闭环测试：注册 -> Radar -> Source -> 采集 -> 清洗 -> Analysis -> Embedding -> Intelligence/Memory -> Notification，并验证 WebSocket 信号丢失后可通过 REST 恢复。
- 使用 Fake Analysis/Embedding Provider、本地 RSS/HTML Fixture 和隔离 PostgreSQL/Redis；测试不得访问公网。
- 导出并校验 OpenAPI JSON，冻结 REST、认证、错误 Envelope、分页、枚举和示例 Payload；不得新增公开 Endpoint。
- 验证空库 upgrade head、downgrade base、再次 upgrade head、Alembic 零漂移，以及 Compose 四服务可重复启动。
- 验证 API/Worker 同镜像非 root、Celery/Beat 周期任务、live/ready、秘密扫描、SSRF、幂等、重试和用户隔离。
- 提供前端交接包：OpenAPI、Endpoint/枚举/错误码清单、Token 生命周期、WebSocket Envelope/关闭码/REST 恢复、环境变量矩阵、运行命令和已知限制。
- 记录轻量性能基线与测量条件，不做无数据支持的大规模优化。

### 禁止变化

- 不新增数据库 Schema/迁移、业务 Endpoint、WebSocket 事件、评分规则、Provider、Pipeline 状态或依赖。
- 若发现冻结契约必须变化，立即停点并提交 ADR、兼容性分析与回归计划。
- 不开发 React/Tauri，不启动 Frontend、Integration、Release 或生产部署。

### 最终验收

- locked sync、Ruff、format、Mypy、完整 Pytest 覆盖率不低于 85%、迁移循环/零漂移、Compose 和 diff 检查全部通过。
- 完全离线的 Alpha 数据闭环可重复完成，数据库事实、WebSocket 信号与 REST 恢复行为一致。
- OpenAPI 与实现一致，交接包可由前端独立使用，运行手册可从空环境复现。
- 无已知 P0/P1；P2 必须有明确处置或书面接受。
- 提交 commit、PR 和阶段报告后停止；未经总控验收不得合并，Backend 不得自行关闭或批准 Frontend。

## 明确禁止事项

- 不开发 React/Tauri 页面。
- 不引入 Neo4j、Qdrant、Milvus、Kafka 或微服务。
- 不实现多模型 Router、知识图谱、团队/组织和企业权限。
- 不绕过站点安全、付费墙、验证码或访问限制。
- 不提交真实 `.env`、Token、API Key、用户数据或抓取正文样本。
- 不执行 GitHub 上传、Release 或生产部署。
- 不经总控批准改变公开 API、评分公式或实体语义。

