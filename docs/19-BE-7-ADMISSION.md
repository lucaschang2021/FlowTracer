# FlowTracer Alpha v0.1 BE-7 阶段准入许可

- Phase：BE-7 Notification、WebSocket 与恢复
- 状态：批准（本文件所在控制 PR 合并后生效）
- 前置验收：BE-6 PR #19 已由总控验收并合并至 `main`
- 稳定基准：`main@6502b5960a75d666b4bdf2e2cefbeee20979012d`
- 契约基准：`docs/18-BE7-NOTIFICATION-WS-BASELINE.md`

## 正式任务包

- 实现 Notification 资格、优先级、字段、幂等创建、60 秒补偿 dispatcher、列表/筛选/分页、单条已读与 read-all。
- 实现 `/api/v1/ws` Header Access Token 鉴权、到期关闭、用户隔离 Redis Pub/Sub、多连接、有界队列与 4401/1013 关闭语义。
- 在数据库提交后发布稳定 event ID 的 `collection.updated`、`analysis.completed`、`notification.created` 最小事件。
- 实现 `POST /collection-runs/{run_id}/retry` 的新运行链式幂等、状态/Source/所有权边界、先提交后投递及 503 补偿。
- 保持既有 Analysis retry 公开契约，补齐 Notification/事件衔接与回归。
- 允许为 BE-7 必需的服务、API、任务、测试、OpenAPI、Compose 和运行文档做最小修改。

## 数据库与安全边界

- 复用现有 Notification、CollectionRun、Analysis 与 Redis，不新增表、列、枚举或迁移；如实现发现必须改变 Schema，立即停点提交 ADR。
- 数据库是唯一事实源；WebSocket 为 best-effort 在线信号，发布/Broker/Redis 失败不得回滚已经提交的事实。
- WebSocket 只接受握手 Authorization Bearer Token；不接受 query/cookie Token，禁止广播后在 Python 客户端过滤用户。
- 不记录或发送正文、summary、Prompt、Source config、Token、向量、payload、连接串或内部异常堆栈。

## Git、额度与汇报

- 本控制 PR 合并后，创建新的 Backend BE-7 任务，在 `D:\FlowTracer-wt\backend` 从最新 `origin/main` 创建或重建 `feat/be-7`；不得修改其他 worktree。
- 遵循 `AGENTS.md` 的 Usage、模型质量、只读范围、单次全量门禁与最小提权纪律。
- 完成后 commit、push、创建 PR，但 Backend 不得 merge；阶段报告必须直接发送给总控任务。

## 禁令与停点

- 不实现 Tauri 原生通知、外部推送、邮件、Outbox、持久事件总线、Kafka、团队权限或 BE-8+ 内容。
- 不新增数据库 Schema、迁移或第二套 Notification/Analysis retry Endpoint。
- 不以 WebSocket 代替 REST 事实恢复，不承诺持久投递或全局顺序，不跨用户广播。
- 未经总控书面许可不得进入 BE-8；Frontend、Integration、Release 继续未准入。

## 阶段报告

必须包含：变更范围、commit、数据库无迁移/零漂移、测试与覆盖率、Notification 阈值/并发/补偿、REST 所有权、WebSocket 鉴权/到期/隔离/背压、事件稳定 ID 与发布失败、CollectionRun retry 链式幂等、Analysis retry 回归、真实 Redis Pub/Sub、Docker/Celery、OpenAPI/秘密扫描、风险、PR 链接和下一阶段建议。
