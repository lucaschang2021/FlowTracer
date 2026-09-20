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

## ADR-019：BE-7 Notification、WebSocket 在线事件与恢复契约

- 状态：Accepted
- 决策：BE-7 的 Notification 资格/优先级、REST、WebSocket 鉴权与事件、CollectionRun retry 及 Analysis retry 回归以 `docs/18-BE7-NOTIFICATION-WS-BASELINE.md` 为准。
- 事实与信号：数据库是唯一事实源；Notification 和重试运行先提交再投递，WebSocket 仅提供 best-effort 在线信号，发布失败不得回滚事实，断线后以 REST 恢复。
- 隔离：WebSocket 只接受握手 `Authorization: Bearer` Access Token；Redis Pub/Sub 按用户隔离，禁止广播后在 Python 客户端过滤；每连接队列固定上限 100。
- 幂等：Notification 使用既有 `(user_id, analysis_id)` 唯一约束；CollectionRun retry 使用 `retry:<original_run_id>` 链式幂等键；事件 ID 对同一次事实变化稳定。
- Schema：复用现有 Notification、CollectionRun、Analysis 与 Redis，不新增表、列、枚举或迁移；实现发现必须变更 Schema 时先停点提交 ADR。
- 边界：BE-7 不实现 Tauri 原生通知、外部推送、邮件、持久事件总线/Outbox、Kafka、团队权限或 BE-8 内容。

## ADR-020：BE-8 只做稳定化、契约冻结与前端交接

- 状态：Accepted
- 决策：BE-8 不增加 Alpha 业务能力；只验证 BE-1 至 BE-7 的完整闭环，修复缺陷，导出并冻结 OpenAPI，完善运行/迁移/测试文档，形成前端交接包与已知限制清单。
- 契约：数据库 Schema、迁移链、公开 REST/WebSocket、评分规则、Provider 与 Pipeline 语义默认冻结。实现若证明必须变化，先停点提交 ADR、兼容性和回归计划。
- 验证：使用 Fake Analysis/Embedding Provider、本地 RSS/HTML Fixture、隔离 PostgreSQL/Redis 完成无公网端到端闭环；空库迁移、Compose、Celery/Beat、WebSocket、权限、安全与可重复启动均须形成证据。
- 交接：以导出的 OpenAPI JSON、Endpoint/枚举/错误码清单、WebSocket 样例、环境变量矩阵和运行手册作为 Frontend 的唯一后端基线。
- 边界：BE-8 不开发 React/Tauri，不进行 Integration/Release，不引入新数据库、中间件、深爬、Router、团队权限或 v0.2+ 能力。

## ADR-021：ACQ-1 成为 Frontend 前置阶段并先执行 Preflight

- 状态：Accepted（仅 Preflight 准入）
- 决策：在 Backend Alpha Core BE-1 至 BE-8 完成后，新增 ACQ-1（Universal Adaptive Acquisition & Opportunity Discovery Engine）作为 Frontend 的硬依赖；Frontend 不得在 ACQ-1 验收和 Acquisition Contract 冻结前启动。
- Preflight：正式实现前必须只读审查现有 Acquisition、Source/RawItem/CollectionRun、SafeFetcher、依赖和运行环境，提交 ACQ-1A 至 ACQ-1H 的实施顺序、契约影响、测试矩阵、资源预算和风险。Preflight 通过不等于正式编码准入。
- 架构：Source Family 是 Acquisition/Extraction Profile；RSS、Native HTTP、Scrapling HTTP、Dynamic/Advanced Browser 必须位于统一 Adapter Boundary 后，输出统一 AcquisitionResult，并继续进入既有 RawItem Pipeline。
- 安全：所有 Backend 必须共享 SSRF、重定向、协议/端口、DNS rebinding、站点政策、资源预算和访问控制边界；Browser 不得绕过 SafeFetcher 安全意图，禁止 CAPTCHA、登录墙或付费墙绕过。
- 机会边界：Opportunity Radar 只负责发现、结构化、筛选、评分、通知和生成 Action Payload；自动投标、合同/价格/工期承诺、资金处理和外部 Agent 执行不属于 ACQ-1。
- 变更控制：现有 Schema、公开 API、Pipeline 或评分无法承载需求时，必须先提交独立 ADR、迁移和兼容性计划；不得在 Preflight 或实现分支中隐式扩张。

## ADR-022：ACQ-1 使用统一 Acquisition Adapter 与强类型 Source Profile

- 状态：Accepted
- 决策：业务层只依赖 AcquisitionRequest/Backend/Result；RSS、Native、Scrapling、Dynamic 与 Advanced 均为 Adapter。Source 使用稳定列、版本化非秘密 Profile 与独立运行状态。
- 兼容：legacy Source 默认 `generic_web/auto/single_page/acq-source-v1`；现有 config 在兼容窗口保留但不承载秘密或高频状态。
- 路由：Native First；Router 只能在质量、预算与 SitePolicy 允许时升级。Advanced 不包含访问控制绕过。
- 规格：`docs/22-ACQ1-MASTER-BASELINE.md`、`docs/23-ACQ1-ACQUISITION-CONTRACT.md`。

## ADR-023：Browser 必须独立运行并通过强制受控出口

- 状态：Accepted
- 决策：Browser 使用独立镜像、专用 Celery queue、低并发和强制 egress proxy；网络命名空间禁止 Internet 直连、系统 DNS、host network 与 Docker socket。
- 覆盖：navigation、redirect、iframe、script、XHR/fetch、WebSocket、download 与 popup 均受 NetworkPolicy、SitePolicy、scope 和预算约束。
- 安全：不能证明无旁路时 Dynamic/Advanced 不准入；安全策略不能通过 fallback、Profile 或 allowlist 降级。
- 构建：package、Browser revision、系统依赖和镜像 digest 必须精确锁定并离线验收。

## ADR-024：ACQ-1 引入 Artifact、Snapshot 与 ChangeEvent 版本证据层

- 状态：Accepted
- 决策：SourceArtifact 表示稳定条目，AcquisitionSnapshot 保存可审计版本，ChangeEvent 保存观测变化；RawItem 继续作为 qualifying change 的既有下游入口。
- 去重：新 RawItem 以 snapshot identity 唯一；legacy `(source_id, external_id)` 约束通过 expand/backfill/switch/contract 收缩，不能直接删除。
- 证据：content、metadata、structure 指纹分别版本化；AI semantic summary 必须引用 old/new snapshot，不能替代确定性证据。
- 删除：一次访问失败不判 removed；需连续成功观测缺失或权威 404/410。

## ADR-025：Opportunity 使用独立事实、评分与 Action Payload 契约

- 状态：Accepted
- 决策：新增 `radar_type=opportunity`、OpportunityItem、OpportunityScore 与不可执行 Action Payload；不复用现有 Analysis radar_score 语义。
- 评分：`opportunity-score-v1` 由服务端 Decimal 公式计算，维度、缺失值、currency、Hard Filter、Recommendation 和通知映射以 `docs/24-ACQ1-OPPORTUNITY-RADAR.md` 为准。
- 人类确认：自动投标、报价、工期/合同承诺、沟通、付款和外部 Agent 执行禁止进入 ACQ-1。
- 合规：平台名称不等于采集授权；访问限制触发 Stop/Report/Human Action。

## ADR-026：ACQ-1 分阶段迁移并保持 BE-8 Pipeline 兼容

- 状态：Accepted
- 决策：Schema 采用 expand/backfill/dual-write/switch/contract；运行回滚优先回退应用并保留扩展 Schema，禁止静默丢失多版本证据。
- 分期：A+H0 → B+D-static → B-dynamic+H-browser → C → E → F → G → H-Final，每阶段单独准入、PR、Review 与停点。
- API：Source 新字段向后兼容；Opportunity enum 和新 Endpoint 在 Frontend 前重新冻结 OpenAPI；现有 WebSocket 事件不在 ACQ-1 隐式扩张。
- 验收：以 `docs/25-ACQ1-ACCEPTANCE.md` 和 `docs/29-ACQ1-WORK-PACKAGES.md` 为准。

## ADR-027：WP-1 Profile v1 采用封闭 Schema，安全策略只能收紧

- 状态：Accepted（本控制提交合并后生效）
- 决策：`acq-source-v1` 的枚举、Profile 字段、默认值、边界和数据库 named CHECK 以 `docs/32-ACQ1-WP1-CONTRACT-ADDENDUM.md` 为准；未列出的字段和枚举值一律拒绝。
- 扩展：`family_options` 在 v1 对九类 Source Family 均为严格空对象。未来需要 family-specific 配置时必须发布新的 `profile_version` 和兼容迁移，不得在 v1 中放行任意 JSON。
- 安全：NetworkPolicy 是 Operator 控制的内部不可覆盖策略，不进入 Source Profile 或公开 API。Source SitePolicy 与 ResourceBudget 只能在全局/Operator 上限内收紧，不能放宽网络 deny、访问控制、端口、地址、redirect 或资源上限。
- 运行状态：Source health 与 AcquisitionAttempt 只使用 Addendum 冻结的终态值；错误细分继续使用安全 `error_code`，不通过增加临时状态绕过状态机。

## ADR-028：WP-2 冻结确定性质量观测，保持 legacy writer 不变

- 状态：Accepted（PR #37 已合并并生效）
- 背景：仅有八项质量权重不能唯一确定长度、密度、噪声和 JS shell 计算；Profile v1 不含阈值，无法由 Backend 自行决定低质量内容的写入行为。
- 决策：精确算法、九类 family 的通用提取支持、evidence/metadata/links 结构与资源上限以 `docs/35-ACQ1-WP2-CONTRACT-ADDENDUM.md` 为准。质量以精确有理数加权并仅最终 HALF_UP 四位。
- 兼容：WP-2 的 static parser 实际接入安全获取后的本地观测链，保留现有 RSS/Native RawCandidate/writer/去重/终态。所有质量桶均不触发过滤、重试或 Browser；质量列和 EWMA 只是观测，不影响 health/circuit。
- 家族：v1 对九类 SourceFamily 仅提供同一五字段通用静态提取，不猜领域字段，不放开 family_options。新增 family 专用语义需版本化裁定。
- 边界：Scrapling 是本地 parser，不是独立联网调用，不生成额外 Attempt，不替代 SafeFetcher。Evidence 是有限内部规则证据，不落入公开 metadata/日志；没有 Snapshot 迁移或新增公开 API。
- 后续：WP-4 准入前必须冻结质量驱动路由的 family/profile 表；不得借本文提前启用。本文不改变 Intelligence 评分规则。

## 后续阶段前仍需补齐的工程规格

以下事项不改变 Alpha 架构初步冻结结论，但必须由总控在对应实现阶段准入前补齐，不得由 Backend 擅自决定：

- 本地配置矩阵、端口、健康检查和可观测性字段。

## ADR-029：WP-3 Browser 准入必须以实际兼容性与隔离证据为前置

- 状态：Accepted（PR #40 已合并并生效）
- 背景：ADR-023 已冻结独立 Browser 与强制受控出口方向，但仓库尚无可复现的 package/browser revision/system dependency/image digest、egress 实现和精确资源限值。文档阶段不能凭空生成构建 digest 或兼容性证据。
- 决策：WP-3 保持未准入。缺口与证据要求以 `docs/37-ACQ1-WP3-READINESS-BLOCKER.md` 为准；只有新的控制 PR 基于实际兼容性/隔离证据冻结精确值并签发 Admission 后，Backend 才可开工。
- 安全：任何不能证明全部 Browser 子资源经过应用层拦截与受控 proxy 的方案 fail closed；不得以 Profile、allowlist、fallback 或 Advanced 模式放宽 NetworkPolicy、访问控制或资源预算。
- 交付边界：兼容性 Spike 如需依赖、镜像、Compose、代码或测试变更，必须另行书面准入；本 ADR 不授权 Browser 实现、Router、Discovery、Schema/API 变化或下游阶段。

## ADR-030：WP-3 Preflight 仅准入可丢弃的兼容性与隔离证据实验

- 状态：Accepted（仅 Spike；本控制提交合并后生效）
- 背景：ADR-029 要求用实际 Python 3.13/Debian Bookworm 兼容性、不可变构建、受控 egress、专用 worker/queue 与资源测量解除 WP-3 证据缺口；这些事实无法由纯文档审查产生。
- 决策：按 `docs/38-ACQ1-WP3-PREFLIGHT-ADMISSION.md` 在固定 Backend worktree 的独立 Spike 分支中，准入实验性依赖锁、Browser 专用候选 Dockerfile/Compose override、proxy/queue 候选配置、本地恶意 fixture、验证脚本及 `docs/39-ACQ1-WP3-PREFLIGHT-EVIDENCE-PACKAGE.md`。实验产物可丢弃且不进入默认生产路径。
- 安全：网络层必须 deny by default；Browser 无公网/系统 DNS/host network/Docker socket 直连。navigation、redirect、iframe、script、XHR/fetch、WebSocket、download、popup 与 service worker 任一拦截面无法证明时 fail closed，并保持正式 WP-3 阻塞。
- 边界：本 ADR 不准入 WP-3 正式实现，不允许公开 API、Schema/migration、RawItem/Pipeline、Router、Discovery、Change、Opportunity 或下游阶段变化。Spike 完成后 Backend 必须 STOP，由总控另开证据审查和后续 Contract Addendum/Admission 任务。

## ADR-031：WP-3 Preflight fail closed，Remediation Evidence 必须顺序执行

- 状态：Accepted（仅证据/原型；本控制 PR 合并后生效）
- 背景：WP-3 Preflight 结果为 P0×1、P1×5、P2×2，未证明 download 双层默认拒绝、完整应用拦截、Browser runtime、可重复 locked image、license、资源回收与双 worker queue 隔离；局部网络拓扑概念验证不能替代生产证据。
- 决策：Preflight 归档为 BLOCKED。后续仅按 `docs/41-ACQ1-WP3-REMEDIATION-EVIDENCE-ADMISSION.md` 顺序执行 R1 locked image/SBOM/license/双构建、R2 controlled egress、R3 application interception、R4 deadline/reap/resource、R5 dedicated queue/two-worker isolation；任一闸门失败立即 STOP，不得跳跃或并行。
- 证据：所有实际值必须进入 `docs/42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md`；`TBD`、估算、一次样本、仅配置审阅或 mock 不构成通过。未经证明的 package、revision、digest、proxy、queue 或资源限值不得冻结。
- 边界：本 ADR 不准入正式 WP-3，不允许默认 API/worker、业务 Pipeline、公开 API、Schema/migration、Router、Discovery、Change、Opportunity 或下游阶段变化。R1→R5 全部通过也只可申请独立审查与后续 Contract Addendum/Admission。

## ADR-032：Browser Runtime Identity 必须排除审计工具漂移并保存逐路径清单

- 状态：Accepted（仅 R1D 证据修复；本控制提交合并后生效）
- 背景：R2C 从已合并 R1C 输入重建时，Chrome、browser tree、Debian inventory、SBOM 与 license 全部匹配，但 full-root identity 不匹配。只读诊断证明 R1C Dockerfile 将整个 `scripts/` 复制到最终镜像；R1C 运行通过后，审计用 `validate_sbom.py` 因可提交性和 Ruff 修复而改变字节，使已冻结的单一摘要无法由合并后的权威来源重建。
- 决策：新增 R1D Runtime Identity v2。最终 Browser runtime 镜像只允许包含明确列出的运行必需脚本；SBOM、license、manifest 与 package-tree validator 等审计工具必须通过独立 build/audit stage 或只读 build mount 执行，不得进入最终 runtime filesystem。不得仅修改或豁免旧 identity 期望值。
- 身份：R1D 必须在相同锁定输入下执行两次独立 no-cache 构建，并保存两个完整的逐路径 normalized filesystem manifest。manifest 统一记录 path、entry type、mode、UID/GID、symlink target 与普通文件 SHA-256；规范化算法必须语言环境无关、机器可执行且 fail closed。通过条件是两个 manifest 与摘要完全一致。
- 兼容：Chrome 版本/revision/path/executable SHA、619-entry browser tree、Debian 206 inventory、CycloneDX 231 components、license 206/206 与 R1C 完全一致；两个镜像均须重复 UID 10001 DynamicFetcher、read-only root、受控 `/tmp`/Crashpad 与清理验证。
- 边界：R1D 只生成隔离证据资产，不准入 R2C 网络矩阵、R3-R5 或正式 WP-3。R1D 独立复审并合并后，R2C 才能以 Runtime Identity v2 重新执行。

## ADR-033：Browser 系统账户元数据必须跨日确定

- 状态：Accepted（仅 R1E 证据修复；本控制提交合并后生效）
- 背景：R2C-A2 从已合并 R1D 输入次日重建时，Runtime Identity v2 的 10,340 个路径中仅 `/etc/shadow` 字节不一致。只读诊断确认 `useradd` 将构建日写入 `flowtracer` 账户的 `sp_lstchg`；R1D 两次构建发生在同一 UTC 日期，未暴露该跨日漂移。
- 决策：新增 R1E，派生独立 `browser-r1e/`，在创建 UID/GID 10001 的锁定非密码账户后显式固定 `sp_lstchg=0`，并以不输出 shadow 内容的结构断言验证账户唯一、字段数、锁定状态与确定值。不得排除 `/etc/shadow`、放宽 Runtime Identity v2、直接替换期望摘要或改写 R1D/R2C 失败证据。
- 验证：R1E 必须重新执行两次独立 no-cache 构建，生成完整逐路径 manifests 与新 authority；重复 Browser 619、Debian 206、SBOM 231、license 206/206、UID 10001、DynamicFetcher、Crashpad、runtime/audit 边界、历史资产保护与精确清理门禁。
- 顺序：R1E 独立复审并合并后，R2C 才能以新 authority 开启全新会话。R3-R5 与正式 WP-3 继续阻塞。

