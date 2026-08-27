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

## ADR-015：BE-3 Radar/Source 资源与 URL 身份契约

- 状态：Accepted
- 决策：Radar、Source 与绑定 API、分页筛选、状态转换、所有权、软删除及错误码以 `docs/06-BE3-RADAR-SOURCE-BASELINE.md` 为准。
- URL 身份：BE-3 使用确定性纯函数生成 `normalized_url` 并完成用户内去重，不访问网络；SSRF 与重定向逐跳校验仍属于 BE-4。
- 删除：Radar/Source 软删除并物理清理绑定，不级联删除另一侧资源。

## ADR-016：BE-4 受控采集、调度与幂等契约

- 状态：Accepted
- 决策：BE-4 的 REST、运行状态、调度、RawItem 去重、网络限制和错误码以 `docs/07-BE4-ACQUISITION-BASELINE.md` 为准。
- 安全：所有网络访问必须经过逐跳 SSRF 校验并绑定已验证 IP；Scrapling 只解析安全 fetcher 返回的内容，不自行联网。
- 可靠性：API 先持久化运行再投递，dispatcher 补偿遗留 queued 运行；scheduler 和 worker 必须能承受重复投递与多实例并发。
- 边界：BE-4 只产生 RawItem，不创建 Document；手动运行重试接口与后续 Pipeline 延后。

## ADR-017：BE-5 Intelligence Pipeline、Provider 与评分契约

- 状态：Accepted
- 决策：BE-5 的清洗、Document 全局强哈希去重、Analysis 状态机、Provider 接口、严格输出 Schema、评分/成本算法、Intelligence API 与错误码以 `docs/08-BE5-INTELLIGENCE-BASELINE.md` 为准。
- Provider：业务层只依赖统一 Protocol；Alpha 仅实现确定性 Fake Provider 与一个 Operator 配置的 OpenAI-compatible 远程 Provider，不引入模型 Router 或自动回退。
- 可靠性：RawItem、Document 和 Analysis 以数据库锁、唯一约束、dispatcher 与失联恢复实现至少一次投递下的幂等；远程 AI 调用不得发生在数据库事务内。
- 评分：模型只返回四维整数和解释；综合分、Recommendation、通知阈值资格及成本均由服务端以 Decimal 确定性计算。
- 边界：BE-5 完成后 Document 进入 `embedding`，不创建 DocumentChunk、向量、Notification 或 WebSocket 事件。

## ADR-018：BE-6 Vector Memory、持久授权与检索契约

- 状态：Accepted
- 决策：BE-6 的确定性切块、Embedding Provider、向量校验、HNSW cosine 索引、Bookmark 与 Memory Search 以 `docs/09-BE6-MEMORY-BASELINE.md` 为准。
- Provider：Embedding 与 Analysis 使用独立配置和 Protocol；Alpha 仅实现确定性 Fake 与一个 Operator 配置的 OpenAI-compatible Adapter，固定 1536 维，不引入 Router 或第二向量数据库。
- 可靠性：Chunk 集合原子写入；重复投递以 session advisory lock、Document 状态和唯一约束幂等。远程调用不得发生在数据库事务或行锁内。
- 权限：普通访问来自用户当前 Radar 的 completed Analysis；Bookmark 在创建时校验访问权，并形成该用户对 Document 的持久知识库授权。向量检索必须在 SQL 中应用所有权条件。
- 检索：PostgreSQL + pgvector 使用 cosine distance 与 HNSW `vector_cosine_ops`；Top-K 最大 50，结果以 Analysis 为单位稳定排序。
- 边界：BE-6 不创建 Notification、不发送 WebSocket 事件、不实现 BE-7+ 恢复接口。


## 后续阶段前仍需补齐的工程规格

以下事项不改变 Alpha 架构初步冻结结论，但必须由总控在对应实现阶段准入前补齐，不得由 Backend 擅自决定：

- WebSocket 鉴权、事件 Envelope、顺序与重复处理规则。
- 本地配置矩阵、端口、健康检查和可观测性字段。

