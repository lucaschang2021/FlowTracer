# FlowTracer ACQ-1 Backend Work Packages

状态：Frozen

执行角色：现有“协作后端开发”Backend 角色；任务由总控直接下达并接收报告。

## 通用规则

- 每个工作包由总控单独书面准入；Backend 完成后直接向总控报告并 STOP。
- 开工从最新已合并 `origin/main` 创建指定 `feat/*` 分支；不得复用前一阶段脏工作树。
- 开发期定向测试；最终 commit 只运行一次全量门禁。未变更 commit 不重复全量测试。
- push、PR 与 merge 仍需明确授权；Backend 不自行 merge 或准入下一阶段。
- 任一 Schema、API、Pipeline、评分或 NetworkPolicy 偏离冻结文档，立即提交 ADR 请求，不得自行决定。
- 所有网络核心测试离线；不得访问真实目标平台。

## WP-1：ACQ-1A + H0

目标分支：`feat/acq-1a-h0`

输入：Master/Acquisition Contract、ADR-022/023、BE-8 模型。

允许：

- Source 强类型字段与严格 Profile Schema；
- SourceAcquisitionState、AcquisitionAttempt；
- CollectionRun lease/heartbeat/stale recovery；
- NetworkPolicy、SitePolicy、ResourceBudget 纯逻辑与 Native 接口；
- expand migration、兼容 Source API、配置/文档与测试。

允许文件：`backend/app/{models,schemas,services,api/v1/routes,tasks,core}` 中与 Source/Acquisition 直接相关文件、`backend/alembic/versions/`、对应 Backend tests、`backend/.env.example`、Backend 运行文档；不得修改 Intelligence/Memory/Notification 业务语义。

禁止：Scrapling/Browser、Router fallback、Discovery、Change、Opportunity。

验收：legacy backfill/default、所有权、公开 config 无秘密、租约并发、stale recovery、零漂移、OpenAPI 兼容、BE-4 回归。

回滚：应用回到 legacy writer；保留扩展表/列，不丢数据。

## WP-2：ACQ-1B + D-static

目标分支：`feat/acq-1b-static`

允许：统一 AcquisitionBackend/Request/Result、现有 RSS/Native adapter、Scrapling static parser adapter、quality v1、family extractor、attempt 记录。

允许文件：`backend/app/services/acquisition*`、新增 `backend/app/adapters/acquisition/` 与 `backend/app/services/extraction*`、依赖清单/锁文件、对应 tests 与 Backend 文档；基础设施只允许静态依赖构建所需的 Dockerfile 最小变更。

依赖：精确锁定 Scrapling parser 依赖；不得下载或启用 Browser。

验收：Native/RSS 全回归、本地 static fixtures、Adapter 等价、quality 边界、解析证据、无网络 parser、依赖/license/锁文件可重复。

回滚：Profile 切回 legacy/native adapter。

## WP-3：ACQ-1B Dynamic + H-browser

目标分支：`feat/acq-1b-browser`

允许：独立 Browser 镜像/worker/queue、egress proxy、Dynamic/Advanced adapter、Browser pool 与资源隔离。

允许文件：新增 Browser adapter/worker/network policy 模块、Browser 专用 Dockerfile/entrypoint、`infra/compose.yaml` 及测试 override、配置/锁文件、对应 tests 与运行手册；不得改变 API/普通 worker 的运行权限或放宽网络。

前置硬门禁：NetworkPolicy threat model 与 egress 方案已在 WP-1 落地；package/browser revision/system dependency/image digest 锁定兼容实验通过。

验收：所有 Browser 子资源 SSRF、无直连、非 root/只读 rootfs/资源限制、crash/OOM 隔离、本地 JS fixture、访问控制停止、同镜像可重复构建。

回滚：关闭 Browser queue 和 Profile 能力；Native/RSS 保持可用。安全策略不可回滚。

## WP-4：ACQ-1C Router

目标分支：`feat/acq-1c-router`

允许：Router v1、fallback、Circuit、AutoThrottle、decision trace、安全错误与指标。

允许文件：新增/修改 acquisition router、state/metrics services、Celery acquisition tasks、严格 schemas 与对应 tests；Schema/API 仅限冻结字段，不得新增 Browser/Discovery 能力。

验收：Native success 零 Browser、质量阈值、预算累计、access-control stop、fallback 幂等、历史状态并发与安全 trace。

回滚：全局 feature flag 固定到 Native/RSS；保留 attempt 历史。

## WP-5：ACQ-1E Controlled Discovery

目标分支：`feat/acq-1e-discovery`

允许：Frontier/checkpoint、四种 scope、link scoring、robots/domain policy、硬预算、取消与恢复。

允许文件：Discovery models/migration、services/tasks/schemas/API、Network/SitePolicy 集成、对应 tests 与文档；不得修改下游 Intelligence/Memory。

验收：scope escape、所有预算精确边界、frontier 并发去重、robots/crawl delay、redirect/Browser 子资源计费、无 unrestricted crawl。

回滚：禁用 discovery，只保留种子 URL；已发现事实不删除。

## WP-6：ACQ-1F Change Intelligence

目标分支：`feat/acq-1f-change`

允许：Artifact/Snapshot/ChangeEvent、RawItem snapshot identity、三类指纹、materiality、bounded diff、removed 判定、expand/backfill/switch migration。

允许文件：Version Evidence models/migrations、acquisition/change services/tasks/schemas/API、RawItem writer 兼容改动、对应 tests 与契约文档；Document 之后的 Pipeline 只允许回归修复。

验收：版本序列、噪声、附件、并发、legacy backfill、RawItem 兼容、旧/新 snapshot 证据、迁移循环与安全 downgrade guard。

回滚：shadow-write Change，关闭 qualifying change 下游；不删除 Snapshot。

## WP-7：ACQ-1G Opportunity

目标分支：`feat/acq-1g-opportunity`

允许：RadarType opportunity、OpportunityItem/Score/Action Payload、Freelance v1 Hard Filter、score v1、REST 与 Notification 兼容关联。

允许文件：Opportunity models/migrations/provider/schema/service/task/API、Notification XOR 兼容改动、严格 tests、OpenAPI/Backend 文档；不得实现外部执行或 Frontend。

验收：money/currency/缺失值、评分边界、所有权、幂等、Action human approval、公开平台访问控制、本地 job E2E、OpenAPI enum 兼容。

回滚：Profile shadow mode，不通知、不公开 Action Payload；普通 Radar 不受影响。

## WP-8：ACQ-1H Final

目标分支：`feat/acq-1h-final`

允许：缺陷修复、恢复/指标/性能收尾、完整离线 E2E、OpenAPI/Frontend handoff、运行文档和已知限制；不得新增能力。

允许文件：受影响 Backend/infra/tests、OpenAPI 快照、Frontend handoff 与运行/性能文档；任何新增 Endpoint/Schema/依赖均越界并触发 STOP。

验收：`docs/25-ACQ1-ACCEPTANCE.md` 全部门禁、BE-1..BE-8 回归、P0/P1=0、可重复启动、性能基线、安全扫描。

回滚：按最后已验收阶段 feature flags 禁用 ACQ-1 高阶能力；事实数据保留。

## 阶段报告格式

```text
Phase / Status
Implemented
Changed Files
Commit / Branch / PR
Schema / Migration
Public API / OpenAPI
Pipeline / State Changes
NetworkPolicy / SitePolicy
Security / SSRF
Concurrency / Idempotency / Recovery
Offline Tests / Full Tests / Coverage
Docker / Compose / Browser Runtime
Performance
Known Limitations
P0 / P1 / P2
Recommendation
Next Phase Admission Recommendation
```

报告后必须 STOP。
