# FlowTracer Alpha v0.1 架构决策记录

状态标识：`Accepted` 表示 Alpha 已采用；变更必须由总控记录影响后再批准。

## ADR-001：Alpha 使用模块化单体后端

- 状态：Accepted
- 决策：采用单个 FastAPI 服务加独立后台 Worker，不拆微服务。
- 理由：Alpha 的首要目标是验证完整数据闭环；模块化单体能保留边界，同时降低部署与联调成本。

建议模块：`auth`、`users`、`radars`、`sources`、`ingestion`、`intelligence`、`memory`、`notifications`。

## ADR-002：PostgreSQL 同时承担关系数据与向量存储

- 状态：Accepted
- 决策：PostgreSQL + pgvector；Alpha 不部署 Qdrant/Milvus。
- 理由：减少一个有状态服务，并保证用户、文档、Radar 和向量的一致性。
- 演进：独立向量库仅在数据规模或检索指标证明有必要时引入。

## ADR-003：后台任务采用 Redis + Celery

- 状态：Accepted
- 决策：采集、清洗、AI 分析、Embedding 和通知判定由 Celery Worker 执行，Redis 作为 Broker。
- 约束：任务必须带关联 ID、幂等键、超时、有限重试和失败记录。

## ADR-004：身份认证采用邮箱密码与 JWT

- 状态：Accepted
- 决策：邮箱密码注册；密码使用 Argon2id 哈希；短期 Access Token 加可撤销 Refresh Token。
- 约束：Alpha 不实现第三方 OAuth、组织和复杂 RBAC。

## ADR-005：AI 能力通过 Provider 接口隔离

- 状态：Accepted
- 决策：业务 Pipeline 依赖统一的摘要、分类、评分、Embedding 接口，不直接依赖厂商 SDK。
- Alpha：配置一个远程 LLM Provider 和一个 Embedding Provider；模型 Router 延后至 v0.5。
- 约束：记录模型、提示词版本、Token 用量、耗时和估算成本。

## ADR-006：采集范围受控

- 状态：Accepted
- 决策：Alpha 正式支持 RSS 与用户自定义的单页 URL；Scrapling 用于允许访问的 HTML 页面提取。
- 约束：阻止内网和本机地址，限制协议、重定向、响应大小和超时；尊重来源条款。
- 延后：站点级深度爬取、登录态采集、反爬绕过和任意浏览器自动化。

## ADR-007：REST 负责资源，WebSocket 负责在线事件

- 状态：Accepted
- 决策：CRUD、分页和查询通过 `/api/v1` REST API；WebSocket 只传递状态变化和通知事件。
- 约束：WebSocket 不是事实数据源，客户端重连后必须通过 REST 补齐数据。

## ADR-008：内容使用分层、可追溯模型

- 状态：Accepted
- 决策：分开保存抓取记录、原始内容元数据、标准化文档、AI 分析产物和向量。
- 去重：标准化 URL 作为弱标识，内容 SHA-256 作为强去重键。
- 约束：Prompt 或模型变化产生新分析版本，不覆盖旧产物。

## ADR-009：桌面通知由 Tauri 执行

- 状态：Accepted
- 决策：后端创建通知记录并发出事件，Tauri 客户端请求系统权限并显示原生通知。
- 约束：通知点击动作只能打开受支持的应用内路由或经过校验的来源 URL。

## ADR-010：Alpha 部署拓扑

- 状态：Accepted
- 决策：Docker Compose 运行 API、Worker、PostgreSQL 和 Redis；Tauri 作为宿主机桌面程序运行。
- 生产云环境沿用同一逻辑组件，但部署细节不属于 Alpha 必须项。

## ADR-011：BE-1 使用 CPython 3.13 与 uv 锁定依赖

- 状态：Accepted
- 决策：后端使用 CPython `>=3.13,<3.14`、`pyproject.toml` 与 `uv.lock`；不并行维护其他锁文件。
- 理由：当前工具链已有 Python 3.13，Celery 5.5、Scrapling 和 asyncpg 官方均支持 3.13；uv 提供跨平台精确锁定。
- 约束：Celery Worker 的验收环境是 Linux 容器，不以原生 Windows Worker 作为支持目标。

## ADR-012：BE-1 本地基础设施版本冻结

- 状态：Accepted
- 决策：PostgreSQL 16 + pgvector 0.8.6 使用 `pgvector/pgvector:0.8.6-pg16-bookworm`；Redis 使用 `redis:7.4.11-alpine3.21`。
- 拓扑：Compose 服务为 `api`、`worker`、`postgres`、`redis`，API/Worker 使用同一后端镜像。
- 约束：依赖服务必须有健康检查；API/Worker 等待 PostgreSQL 和 Redis healthy；不得使用 `latest`。

## ADR-013：BE-1 健康与可观测性契约

- 状态：Accepted
- 决策：Liveness 不访问外部依赖；Readiness 检查 PostgreSQL 与 Redis，并在异常时返回统一 503 错误。
- 追踪：API 接受或生成 UUID `X-Request-ID`；HTTP 与 Celery 日志使用结构化字段和 correlation ID。
- 详细规格：`docs/04-BE1-ENGINEERING-BASELINE.md`。

## ADR-014：BE-2 数据模型与认证契约冻结

- 状态：Accepted
- 决策：全部 Alpha 关系实体在 BE-2 一次性落地；字段类型、约束、索引、删除策略和枚举以 `docs/05-BE2-DATA-AUTH-BASELINE.md` 为准。
- 认证：密码使用 Argon2id；Access Token 使用 15 分钟 HS256 JWT；Refresh Token 使用 30 天可撤销、单次轮换的 opaque Token，数据库只保存 SHA-256。
- 约束：BE-2 只实现 Auth/User API；其他实体仅建立模型与迁移，不提前实现 BE-3+ 业务。

## 后续阶段前仍需补齐的工程规格

以下事项不改变 Alpha 架构初步冻结结论，但必须由总控在对应实现阶段准入前补齐，不得由 Backend 擅自决定：

- 采集与分析状态机、错误码、重试次数及死信处理。
- BE-3+ API 请求/响应模型、筛选和排序细节。
- WebSocket 鉴权、事件 Envelope、顺序与重复处理规则。
- 四维评分的范围、默认权重、阈值及解释字段。
- Prompt、模型输出 JSON Schema 和降级处理。
- 检索查询流程、Top-K、用户隔离及召回验收指标。
- 本地配置矩阵、端口、健康检查和可观测性字段。

