# FlowTracer Alpha v0.1 BE-7 Notification、WebSocket 与恢复契约基线

## 1. 阶段目标与数据库边界

BE-7 仅实现 Notification、WebSocket 在线事件、CollectionRun retry，并复核既有 Analysis retry。BE-6 PR #19 已验收并合并至 `main@6502b5960a75d666b4bdf2e2cefbeee20979012d`；BE-8、Frontend、Integration、Release 仍未准入。

本阶段复用既有 Notification、CollectionRun、Analysis 与 Redis，不新增表、列、枚举或迁移。实现中若发现必须改变 Schema，必须停点提交 ADR 与影响分析，不得擅自创建迁移。

不实现 Tauri 原生通知、外部推送、邮件、持久事件总线/Outbox、Kafka、团队权限或任何 BE-8 内容。数据库是事实源；WebSocket 只提供 best-effort 在线信号。

## 2. Notification 资格、优先级与幂等

仅当以下条件同时成立时创建 Notification：

- Analysis.status 为 `completed`，且 `radar_score` 非空。
- 关联 Radar 属于目标用户、未软删除且 `status=active`。
- `radar_score >= Radar.notification_threshold`，阈值使用判定当时数据库中的当前值。

优先级只由 `radar_score` 决定，且必须先满足用户阈值：

- `radar_score >= 95`：`critical`。
- `85 <= radar_score < 95`：`high`。
- `radar_score < 85`：`normal`。

既有 `(user_id, analysis_id)` 唯一约束是最终幂等防线；并发、重复投递和 dispatcher 重扫只能产生一条 Notification。字段固定为：

- `title`：安全截断的 `Document.title`。
- `content`：`Analysis.summary`；无 summary 时安全回退 `Analysis.reason`。
- `reason`：`Analysis.reason`。
- `url`：`Document.canonical_url`。

不得存储正文、Prompt、向量、Source config、Token 或其他秘密。Analysis 完成事务提交后才投递通知判定；Broker/Redis 失败不得回滚 Analysis。每 60 秒 dispatcher 扫描符合资格且尚无 Notification 的 completed Analysis，以 `FOR UPDATE SKIP LOCKED`、唯一约束或等效数据库机制补偿历史与遗漏。

Notification 创建提交后才发布 `notification.created`；事件发布失败不得回滚 Notification。

## 3. Notification REST

全部 Endpoint 位于 `/api/v1`，要求 Bearer Token、严格 Schema、统一 ErrorEnvelope 与 OpenAPI 声明。

- `GET /api/v1/notifications?page=1&page_size=20&status?&priority?`：`page >= 1`、`page_size` 为 1..100；按 `created_at DESC, id DESC` 稳定排序；只返回当前用户数据。
- `POST /api/v1/notifications/{notification_id}/read`：返回 200 和 Notification 对象；首次设置 `status=read`、`read_at=当前 UTC`，重复请求保持原 `read_at`。
- `POST /api/v1/notifications/read-all`：单事务更新当前用户全部 unread，使用同一个 UTC 时间，返回 `{updated_count, read_at}`。

跨用户访问与不存在统一返回 404 `resource_not_found`，不得泄露对象存在性。不提供 Notification 删除 Endpoint。

## 4. WebSocket 鉴权、连接与背压

Endpoint 固定为 `/api/v1/ws`。只接受握手 Header `Authorization: Bearer <Access Token>`；不接受 query 或 cookie Token，不得在 URL、错误或日志中回显 Token。

缺失、无效、过期、错误 type/issuer/audience 的 Token，以及停用或软删除用户，均以关闭码 4401 结束连接。已连接 Token 到期时最迟在到期点关闭 4401。

允许同一用户建立多个连接。API 进程通过现有 Redis 使用按用户隔离的 Pub/Sub channel；禁止先向所有连接广播再由 Python 客户端过滤，跨用户事件不可见。

Redis/PubSub 临时不可用，或每连接固定上限 100 的有界队列溢出时，关闭连接 1013。事实数据不得受影响，客户端通过 REST 恢复。

WebSocket 不持久化、不保证全局顺序。客户端按 `event_id` 去重；断线重连后必须 GET REST 获取最新事实。

## 5. 事件 Envelope 与发布时序

Envelope 固定为 `{event_id,event_type,occurred_at,data}`：

- `event_id` 对同一次事实变化与重复发布必须稳定，可使用 UUIDv5 基于 `event_type + resource_id + status/updated_at` 生成。
- `occurred_at` 必须是带时区 UTC。
- `event_type` 仅允许 `collection.updated`、`analysis.completed`、`notification.created`。

`data` 必须严格最小化：

- `collection.updated={collection_run_id,source_id,status,fetched_count,created_count,duplicate_count,failed_count}`。
- `analysis.completed={analysis_id,document_id,radar_id,radar_score,recommendation}`。
- `notification.created={notification_id,analysis_id,priority}`。

不得发送正文、summary、Source config、Token、向量或错误堆栈。

所有事件只在对应数据库事务提交后发布：`collection.updated` 覆盖 queued、running 与终态变化；`analysis.completed` 只在 completed 提交后；`notification.created` 只在 Notification 提交后。发布失败只安全记录事件类型与资源 ID，不记录 payload/秘密，不回滚事实。

## 6. CollectionRun retry

新增 `POST /api/v1/collection-runs/{run_id}/retry`，要求当前用户拥有原运行关联的未删除且 active Source。

- 仅 `failed`、`partial` 原运行可重试；`queued`、`running`、`succeeded` 返回 409 `collection_run_not_retryable`。
- 暂停 Source 返回 409 `source_not_active`；跨用户或不存在统一返回 404 `resource_not_found`。
- 不重置或覆盖原运行。创建新的 `manual`、`queued` CollectionRun，`triggered_by_user_id=当前用户`。
- 内部 `idempotency_key=retry:<original_run_id>`；并发或重复请求返回同一新 run。该新 run 后续若为 failed/partial，可继续形成下一条 retry 链。
- 新 run 必须先提交再投递。成功返回 202，`Location` 指向新 run。
- Broker 失败返回 503 `collection_queue_unavailable`，但 queued run 保留并由既有 dispatcher 补偿。

Retry 日志只记录 user、resource、correlation 与 status，不记录正文、Source config 或内部异常。

## 7. Analysis retry 回归

既有 `POST /api/v1/analyses/{analysis_id}/retry` 公开契约不得破坏：

- `failed` Analysis 复用原记录进入 `pending`，并同步 `Document.status=analyzing`。
- `pending`、`running` 请求幂等；`completed` 返回 409。
- 队列失败时保留可恢复状态，由既有补偿机制继续处理。

BE-7 只补齐 Notification/事件衔接与回归，不创建第二个 Analysis retry Endpoint。

## 8. 测试与验收

- Notification：覆盖阈值 0、84.99、85、94.99、95、100，active/paused/deleted Radar，并发唯一、历史 dispatcher、Broker/Redis 失败、列表过滤/分页、单条已读、read-all 与所有权。
- WebSocket：覆盖 Header 鉴权矩阵、Token 到期、同用户多连接、两用户隔离、三个严格事件 Schema、稳定 event_id、重复处理、Redis 断开、100 队列背压和断线后 REST 恢复；使用真实 Redis，不访问公网。
- Retry：真实 PostgreSQL 覆盖并发重复、原 run 不变、新 run 幂等、失败链、状态/Source 边界、所有权、503 后 dispatcher；既有 Analysis retry 全回归。
- 最终候选执行 locked sync、Ruff、format、Mypy、Pytest（总覆盖率不低于 85%）、隔离测试库 Alembic 零漂移（预期无迁移）、Compose config、live/ready、真实 Redis Pub/Sub、无 Beat Worker、Celery pong、API/Worker 同镜像且非 root、OpenAPI 与秘密扫描。

Backend 完成后必须 commit、push、创建 PR，直接向总控提交阶段报告并停点。不得自行合并或进入 BE-8。
