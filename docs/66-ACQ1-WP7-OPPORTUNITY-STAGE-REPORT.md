# ACQ-1 WP-7 Opportunity Radar 阶段报告

Phase / Status：ACQ-1-WP7 I1 **ACCEPTED（委托方确认，无独立第三方角色）**；分支 `feat/acq-1g-opportunity`。
日期：2026-10-05。报告后 STOP（等待总控复核与书面许可，未经许可不进入 WP-8）。

## Implemented

- `radar_type=opportunity`：真实 PostgreSQL enum 重建迁移（`ALTER TYPE ... ADD VALUE` + 三重 downgrade guard）。
- 三张事实表：`opportunities`、`opportunity_scores`、`opportunity_action_payloads`（全部 named CHECK/唯一约束/索引），模型独立为 `app/models/opportunity.py`。
- Freelance v1 Hard Filter（精确边界、闭集 disqualifier、prohibited 关键词集）与 `opportunity-score-v1`（Decimal 公式、ROUND_HALF_UP、缺失值默认、严格校验、推荐带、通知资格）。
- `OpportunityEvaluationProvider`：确定性 Fake + OpenAI-compatible（严格 JSON schema、bounded 请求、≤3 次调用/2-4s 退避/一次 repair/120s 上限、逐调用 AIUsageRecord、调用在事务外、硬过滤先于远程调用）。
- 确定性 JSON-LD `JobPosting` 提取（显式字段允许清单，无猜测；无显式标题不产生 item）。
- Action Payload（`requires_human_approval=true`、SHA-256、32 KiB 守卫、不可变）+ Notification XOR 兼容扩展 + REST 三端点 + Celery 评估任务（beat 60s）+ 本地 job 管线（Snapshot→Item→Hard Filter→Score→Payload→Notification）。

## Changed Files

新增：`alembic/versions/20261005_0006_opportunity.py`、`app/models/{opportunity,notification,types}.py`、`app/domains/opportunity_policy.py`、`app/providers/opportunity.py`、`app/services/opportunity_{facts,ingest,evaluation,payload,queries}.py`、`app/schemas/opportunity.py`、`app/api/v1/routes/opportunities.py`、`app/tasks/opportunity.py`、`tests/test_opportunity.py`、`docs/65`、`docs/66`。

修改：`app/models/entities.py`（enum + 重新导出，-60 行）、`app/models/__init__.py`、`app/domains/provider_ports.py`、`app/core/composition.py`、`app/services/{acquisition_run_repository,change_tracking,notifications}.py`、`app/api/{dependencies.py,v1/router.py}`、`app/api/v1/routes/notifications.py`、`app/schemas/notifications.py`、`app/tasks/celery_app.py`、`backend/openapi/flowtracer-alpha-v0.1.json`、`tests/{test_models,test_contract_freeze,test_acquisition_change}.py`、`ARCHITECTURE.toml`、`docs/{01,02}`。

## Commit / Branch / PR

分支 `feat/acq-1g-opportunity`；实现+文档 commit `53f2058`；no-ff merge 到 `main`：`bba30aa`；本 traceability commit 记录以上哈希。本地 Git（无 GitHub 远端可用；委托方确认模式）。

## Schema / Migration

- `alembic head = 20261005_0006`；`alembic check` 零漂移。
- 迁移循环（upgrade→downgrade→re-upgrade）真实数据库通过；三重 downgrade guard 全部有测试证据（机会表行 / 通知机会分支 / radar enum 使用），fail-fast 不静默丢数据。
- `tests/test_models.py` 冻结契约扩展（3 表、radar_type enum 含 opportunity、XOR 部分唯一索引、CHECK/FK/索引精确断言）。

## Public API / OpenAPI

- 新增 `GET /api/v1/opportunities`、`GET /api/v1/opportunities/{opportunity_id}`、`GET /api/v1/opportunities/{opportunity_id}/action-payload`。
- `NotificationResponse` 增加 `kind` 与可空 `opportunity_id`，`analysis_id` 可空；`RadarType` enum 增加 `opportunity`（生成型客户端兼容变化，按 ADR-026 重新冻结）。
- OpenAPI 快照重生成；`ARCHITECTURE.toml` 冻结 blob 由 `67d99e7c…` 更新为 `1544614955…`（契约性变更，非静默漂移）；`test_contract_freeze` 路径集合同步。
- WS 事件未扩张（ADR-026）；opportunity 通知通过 REST 拉取。

## Pipeline / State Changes

- acquisition 成功路径（legacy 与 Router 共用仓储）在同一事务内追加 opportunity ingest（仅 `source_family=opportunity` 且 `created` 事件；`snapshot_id` 唯一保证重放 no-op）。
- 评估任务对（opportunity × 所监控 opportunity radar）配对调度；score 三元组唯一 + 通知部分唯一 + payload 版本/hash 唯一保证幂等。
- `record_version_evidence` 返回 `EvidenceResult`（events + writes），RawItem 行为不变。

## NetworkPolicy / SitePolicy

无变化（本 WP 不触碰网络层）。平台来源必须由操作者显式配置为 Source；未引入任何平台自动访问。

## Security / SSRF

- Provider 请求仅含 bounded 事实 + radar goal/skills；测试断言请求体不含凭据/cookie/authorization。
- 公开响应不含 raw HTML/Prompt/向量/内部 trace；`extra=forbid` 严格 schema。
- Hard Filter 先于所有远程调用；未通过零 AI 调用/零成本。
- Action Payload 无凭据、无 Proposal 文本、无执行能力（`requires_human_approval=true` 恒真）。
- 所有权与不存在统一 404；已删除/暂停 Radar 不评分不通知。

## Concurrency / Idempotency / Recovery

- 并发评估恰好一份 score/payload/notification（测试：gather 两个评估 → `["scored","skipped"]`）。
- 重放评估为 no-op（0 追加行、0 额外调用）；usage 逐调用落账（`analysis_id=NULL`、`task_type=opportunity_evaluation`）。
- provider 失败不写半成品分数（下轮 beat 重试）；retryable 退避 2/4 秒实测；invalid output 一次 repair 实测（共享 3 次预算）。
- 已知有界限制：并发调度同一配对时可能发生重复 AI 调用（结果仍幂等），记录于 docs/65 §6。

## Offline Tests / Full Tests / Coverage

- `tests/test_opportunity.py`：**32/32**。
- 定向回归（change/models/notifications/tasks/acquisition/intelligence/e2e/gate）：全绿。
- 全量门禁：**435 passed / coverage 92.16%**（≥ 87.61 阈值；WP-6 为 403/92.17%）。
- `ruff check .`、`ruff format --check .`、`mypy app` 全绿；架构门 `introduced=0 / P0=0`（existing 130 / resolved 27）。

## Docker / Compose / Browser Runtime

无变化；Browser 分支保持 disabled（`BROWSER_DYNAMIC_ENABLED=False`，WP-3 未准入）。本地验证使用 PG16(pgvector 0.8.6) + Redis 7.4 容器。

## Performance

未做性能基线（WP-8 范围）；评估路径为单次 provider 调用 + 三次小事务，无 N+1。

## Known Limitations

- I1 只对首见（`created`）快照建 item；版本变化驱动的重评与 removed 生命周期在 I2。
- 并发调度同一配对可重复调用 AI（有界、结果幂等）。
- 单币种（USD）；无 FX 表。
- 平台访问授权工作流未实现（仅操作者显式 Source）。
- 通知无 WS 事件（ADR-026）。
- 本地 Git 无远端；合并与验收均为委托方确认模式。

## P0 / P1 / P2

P0=0；P1=0（架构门新引入为 0；发现并修复 WP-6 遗留 S608 一处）；P2=0 新增（拆分后模块/函数均在阈值内）。

## Recommendation

I1 满足 docs/24 与 docs/25 §11 的全部静态验收项；建议总控复核后按「委托方确认」验收，并保持 WP-3 分支 disabled。

## Next Phase Admission Recommendation

WP-8（Final）可在总控书面准入后启动（I1 范围：价值闭环、OpenAPI/Frontend handoff、运行文档、性能基线与缺陷修复）；WP-7 I2（平台授权工作流/版本驱动重评/FX）保持未准入。

## 发现与报告（超出原计划的事实）

- WP-6 提交的 `20261005_0005` 迁移含 S608（其提交时 ruff 未覆盖该行）——已修复并在 docs/65 §10 记录。
- WP-6 迁移循环测试原先以 `-1` 为增量目标，头部前进到 0006 后会降级错误层级并使共享测试库停留在旧 revision——已改为显式目标并恢复 head。
