# ACQ-1 WP-7 Opportunity 契约冻结（含实现注记）

状态：**FROZEN（ADR-025 已 Accepted；ADR-037 本次追加）+ IMPLEMENTED（opportunity radar v1，I1 范围）**。冻结规则以 `docs/24-ACQ1-OPPORTUNITY-RADAR.md` 为准；§10 实现注记记录落到代码时的精确裁定。
日期：2026-10-05。依据：`docs/29` WP-7、`docs/24-ACQ1-OPPORTUNITY-RADAR.md`、ADR-025、`docs/25` §11、`GOVERNANCE-V2 §3`；锚定代码：`app/models/opportunity.py`、`app/models/notification.py`、`app/models/types.py`、`app/domains/opportunity_policy.py`、`app/providers/opportunity.py`、`app/services/opportunity_facts.py`、`app/services/opportunity_ingest.py`、`app/services/opportunity_evaluation.py`、`app/services/opportunity_payload.py`、`app/services/opportunity_queries.py`、`alembic/versions/20261005_0006_opportunity.py`。

## 0. 增量拆分（冻结）

- **I1（本增量，已实现）**：`radar_type=opportunity`、三表与迁移、Freelance v1 Hard Filter、`opportunity-score-v1`、Provider（fake + OpenAI-compatible）、Action Payload、Notification XOR 兼容扩展、REST 三端点、Celery 评估任务、本地 job 管线与并发幂等。
- **I2（生命周期与重评已准入并实现，2026-10-06，收口 Phase 4 / ADR-041；注记见 §12）**：版本变化（ChangeEvent）驱动的 item 生命周期与重评、crawl 输出接入、过期/移除转换。**仍不扩张**：平台逐站点访问授权工作流、通知 WS 事件（ADR-026 冻结）、多币种固定 `fx_table`/`fx_version`、Admin/Profile 编辑面、外部执行适配器。

## 1. 数据模型与 schema（FROZEN，docs/24 §2/§3）

- `opportunities`：精确列与 named CHECK（`budget_min`/`budget_max`/`budget_range`/`currency` 三大写字母/`skills` array/`client_metadata` object/`effort`/`status` 闭集）；`snapshot_id` 唯一；索引 `(user_id,status,created_at DESC,id)`、`(source_id,published_at DESC)`、`(deadline)`。
- `opportunity_scores`：8 维度 + overall 逐列 0..100 CHECK；`hard_filter_passed=false ⇒ 全维度与 overall 为 NULL`、`=true ⇒ 全非空` 两条 named CHECK；recommendation 闭集；`UNIQUE(opportunity_id, radar_id, score_version)`。
- `opportunity_action_payloads`：`jsonb_typeof(payload)='object'` 与 `pg_column_size(payload) <= 32768` named CHECK；`UNIQUE(opportunity_score_id, payload_version)`、`UNIQUE(payload_hash)`。
- Notification 兼容扩展：`analysis_id` 可空、新增 `opportunity_score_id`（FK `RESTRICT`）、exactly-one named CHECK `ck_notifications_fact_target_xor`、既有 `(user_id,analysis_id)` 唯一约束改部分唯一索引、新增 `(user_id,opportunity_score_id)` 部分唯一索引；既有 ID/状态/read_at/事件语义不变。

## 2. Freelance v1 Hard Filter（FROZEN 精确语义）

- Profile 默认值：`USD` allowlist、budget `[10.00, 80.00]`、effort ≤ `8`、delivery window ≤ `2` 天、`one_off` allowlist、meetings ≤ `1`、maintenance `false`。
- 必需字段：`title`、`description`、`source_url`、`currency`、且 budget 至少一端；缺失即 `insufficient_data` 唯一 disqualifier（短路）。
- 其余规则按固定顺序全量收集：`currency_unsupported` → `budget_out_of_profile` → `effort_over_profile` → `delivery_unsupported` → `delivery_window_out_of_profile` → `meetings_over_profile` → `maintenance_required` → `prohibited_content`。disqualifier 为闭集（`opportunity_policy.DISQUALIFIER_CODES`）。
- 边界冻结：budget `10.00`/`80.00` 通过，max `<10.00` 或 min `>80.00` 拒绝；单端存在时只按该端判定；effort `8.00` 通过、`8.01` 拒绝；delivery window = `deadline − published_at`，仅两端都存在的时检查，恰好 2 天通过、超过（含 1 秒）拒绝；meetings `1` 通过、`2` 拒绝；`maintenance_required=true` 拒绝、`NULL` 通过；缺失的可选字段（delivery/effort/meetings/deadline）不拒绝。
- `prohibited_content` 采用冻结关键词集（凭据/资金/绕过/恶意软件/垃圾/身份盗用等，见 `PROHIBITED_CONTENT_KEYWORDS`）；误报优先于风险，集内新增必须版本化裁定。
- 仅命中观察到的违规；非 USD 不做在线汇率查询（I1 无 FX）。

## 3. Opportunity Score v1（FROZEN）

- `overall = fit*0.25 + expected_value*0.20 + completion_probability*0.20 + effort_efficiency*0.15 + time_to_delivery*0.10 + (100−competition)*0.04 + (100−ambiguity)*0.03 + (100−risk)*0.03`；Decimal、`ROUND_HALF_UP` 两位、clamp 0..100。
- 维度严格整数 0..100；bool/float/字符串/NaN/Infinity/超范围/未知字段/空或含控制字符的 reason 一律拒绝整个结果。
- 缺失值：正向维度（fit/expected_value/completion_probability/effort_efficiency/time_to_delivery）默认 `0`，负向（competition/ambiguity/risk）默认 `100`；缺失项写入 reason 后缀 `(missing dimensions defaulted: ...)`。
- 推荐带：`≥85 act_now`、`≥70 review`、`≥50 watch`、否则 `dismiss`。Hard Filter 未通过 → 8 维与 overall 为 NULL、recommendation=`dismiss`。
- 通知资格（事务内复验）：hard filter 通过 ∧ `overall ≥ max(85, radar.notification_threshold)` ∧ `risk ≤ 30` ∧ `ambiguity ≤ 40` ∧ item `status=active` ∧ deadline 未过（`deadline > now`）∧ Radar active、未删除、归属正确。priority 沿用既有 `notification_priority` 带（≥95 critical、≥85 high、否则 normal）。

## 4. Evaluation Provider（FROZEN，`opportunity-eval-v1`）

- 业务层依赖 `app.domains.provider_ports.OpportunityEvaluationProvider`；I1 只实现确定性 Fake 与单一 OpenAI-compatible Provider。
- Hard Filter 在远程调用前执行；未通过零 AI 调用、零成本、零 usage 记录。
- 每对 (opportunity, radar) 最多 3 次真实调用（repair 共享该预算）；invalid output 一次 repair；可重试错误退避 2/4 秒；总时长上限 120 秒；调用不发生在任何数据库事务或锁内。
- 每次调用写 `AIUsageRecord`（`analysis_id=NULL`、`task_type="opportunity_evaluation"`、provider/model/token/cost/duration/success/error），Prompt 与原始输出不落日志。
- 请求仅含 bounded Opportunity 事实（description ≤8000 字符、skills ≤50×80、金额/日期/时长字符串化）与 Radar goal/skills/keywords；不含 Source config、用户 profile、Cookie、Token、Browser trace。

## 5. Action Payload（FROZEN，`opportunity-action-v1`）

- 字段：`payload_version / opportunity_id / source{platform,url} / title / description / budget{min,max,currency} / skills / deadline / score{overall,dimensions,recommendation,reason} / risk / source_url / recommended_action / requires_human_approval / context{profile_version,score_version,radar_id} / generated_at`。
- `requires_human_approval` 恒为 `true`；money 与 overall 序列化为字符串；`payload_hash = sha256(canonical JSON(sort_keys))`；canonical 长度 ≤32768 字节（描述上限 4000 字符保证最坏 CJK 情形仍在 jsonb CHECK 之内）。
- 不可变：写入用 `ON CONFLICT DO NOTHING`，只能由新 `payload_version` 产生新行；未通过 Hard Filter 不产生 payload；读取（REST）取最新 `generated_at`。无任何执行能力。

## 6. 管线、配对与幂等（FROZEN I1 口径）

- **Ingest**：acquisition 成功路径在 run 事务内、`record_version_evidence` 之后调用 `record_opportunity_items`；仅 `source_family=opportunity` 且 change_type=`created`；`snapshot_id` 唯一保证重放 no-op；无显式标题（JSON-LD 或候选标题）不产生 item。
- **提取**：仅确定性 JSON-LD `JobPosting`（含 `@graph`）与既有候选字段；`baseSalary.value.min/max`、currency 三字母大写、`datePosted/validThrough`（ISO/RFC）、`skills`（逗号或数组）、`deliveryType`、`estimatedEffortHours`、`requiredMeetings`、`maintenanceRequired`、`hiringOrganization.name`、`clientRating`（0..5）、`clientReviewCount`；`client_metadata` 为上述公开允许清单，缺失保持 NULL/缺省，不猜测。
- **配对与调度**：`opportunity.source_id ↔ radar_sources ↔ radar`（type=opportunity、active、未删除、owner 一致）；`dispatch_pending_opportunities` 处理无任意 score 的配对（每次 ≤10，beat 60s）。
- **幂等/并发**：score 三元组唯一 → 重复/并发评估恰好一份事实；冲突方返回 `skipped`（不写 payload/通知）；并发下 AI 调用可能重复但有界（文档化限制），结果幂等。通知按部分唯一索引 `ON CONFLICT DO NOTHING`。usage 记录在评估事务之外逐调用写入。
- I1 仅由 `created` 快照建 item；版本变化驱动重评/生命周期留 I2。

## 7. API（FROZEN，docs/24 §8）

- `GET /api/v1/opportunities`：`page/page_size(≤100)/radar_id/status/recommendation/min_score/currency/deadline`；稳定排序 `created_at DESC, id DESC`；最新 score 按（可选 radar）取 `scored_at DESC, id DESC`。
- `GET /api/v1/opportunities/{id}`、`GET /api/v1/opportunities/{id}/action-payload`（取最新 payload）。
- 所有权与不存在统一 404 `opportunity_not_found`；存在但无 payload → 404 `action_payload_unavailable`；schema `extra=forbid`；公开响应不含 raw HTML/Prompt/向量/router trace/秘密。
- OpenAPI 冻结：`RadarType` enum 新增 `opportunity`（生成型客户的兼容变化，随 Frontend handoff 记录）；`NotificationResponse` 新增 `kind` 与可空 `opportunity_id`，`analysis_id` 改为可空；WS 事件不扩张。

## 8. 迁移与 downgrade guard（FROZEN）

- `20261005_0006`：`ALTER TYPE radar_type ADD VALUE IF NOT EXISTS 'opportunity'`（PG12+ 允许于事务内执行；同一事务不使用该新值）；创建三表；notifications 扩建（先删旧唯一约束、改可空、加列、校验、部分唯一索引、FK `RESTRICT`）。
- downgrade 三重 guard（fail-fast，不静默丢数据）：任一机会表存在行；任一通知引用机会分数；任一 radar 使用 `opportunity`。空载时：逆序拆除 → 恢复 `(user_id, analysis_id)` 唯一约束与 NOT NULL → enum 重建（新建类型 → USING 转换 → 删旧 → 改名）。
- 循环（upgrade→downgrade→re-upgrade）与全部 guard 均有真实数据库测试证据。

## 9. 非目标（I1，FROZEN）

不实现：自动 Proposal/报价/工期/合同承诺、代表用户沟通、资金处理、接受合同、外部执行 Agent、平台自动访问授权、语义风险模型、多币种 FX、WS 事件扩张、I2 范围。

## 10. 实现注记（2026-10-05，opportunity radar v1）

1. **架构预算处置**：`entities.py` 基线 797 行且禁止增长 → Notification（连同 `NotificationPriority/NotificationStatus`）移入 `app/models/notification.py`、`enum_column/varchar_enum` 移入 `app/models/types.py`，`entities.py` 以 `as` 别名重新导出（净减 60 行）。新 API/schema 文件不新增 `models_persistence` 跨层指纹：route 经 `app.api.dependencies` 取重新导出的 `User`，schema 用 `Literal` 替枚举。
2. **证据交接**：`record_version_evidence` 返回 `EvidenceResult(events, writes)`（`EvidenceWrite` 含 artifact/snapshot/change_type/candidate）；acquisition `_record_success` 同事务调用 ingest（+2 行，函数 75 行 <80）。
3. **发现并修复 WP-6 遗留**：`20261005_0005` 含 S608（提交时 ruff 未覆盖到该行），已补 noqa；同时 WP-6 迁移循环测试适配 head=0006（显式 downgrade 目标 + 失败后恢复 head，避免共享测试库停留在旧 revision）。
4. **Notification XOR 与消息路径**：intelligence 派发使用部分唯一索引 + `index_where` 的 `ON CONFLICT`；列表/已读服务返回 `(Notification, opportunity_id)` 元组，`NotificationResponse.from_fact` 派生 `kind`。
5. **并发**：score `ON CONFLICT`（具名三元组）判定冲突 → `skipped`；payload 用 catch-all `ON CONFLICT DO NOTHING`（hash 冲突亦安全）；通知 `ON CONFLICT`（部分唯一）。
6. **payload 边界**：描述 4000 字符 + `payload_digest` 32 KiB 断言；Decimal 字符串化与 `sort_keys` canonical；payload 构建/摘要独立为 `app/services/opportunity_payload.py`（评估模块曾达 611 行触发新模块 P2 双告警，拆分后 <600）。
7. **Provider schema**：严格输出 schema 由 `_strict_output_schema()` 函数构造（新模块不允许模块级可变状态 P1）；OpenAI-compatible 路径以 MockTransport 单块流验证（拒绝 invalid usage、修复提示透传、请求体不含凭据）。
8. **测试运行环境**：Windows 本地 PG16（pgvector 0.8.6）+ Redis 7.4 容器；全量门禁与迁移循环均真实执行（非 dry-run）。
9. **OpenAPI 重新冻结**：`ARCHITECTURE.toml.gate.compatibility.openapi_blob` 由 `67d99e7c…` 更新为 `1544614955…`（ADR-026/doc/24 §6 要求的契约性 API 变更随后重新冻结，非静默漂移）；alembic_head 保持 Alpha 基线 `20260830_0004`（历史 revision 未改动，仅追加 0005/0006）。

## 11. 验收与证据

- 测试矩阵 `tests/test_opportunity.py`：**32/32**（硬过滤边界 6 + 评分/解析/资格 5 + 本地 job 全管线/调度 2 + 拒绝路径 1 + Provider 语义 3 + 资格与并发 3 + XOR 1 + REST 3 + 迁移循环守卫 1 + 任务/beat 1 + JSON-LD 提取 4 + Provider 替换 2）。
- 模型契约 `tests/test_models.py` 扩展（3 表、radar_type enum、XOR 部分唯一索引、新 CHECK/FK）；OpenAPI 快照重生成并经 `test_contract_freeze` 冻结路径校验。
- 定向回归（change/models/notifications/tasks/acquisition/intelligence/e2e）全绿；全量与覆盖率、架构门与 `alembic check` 见 `docs/66-ACQ1-WP7-OPPORTUNITY-STAGE-REPORT.md`。

## 12. 实现注记（2026-10-06，lifecycle & re-evaluation / I2 实值；ADR-041）

1. **Ingest（ChangeEvent 驱动）**：`record_opportunity_items` 处理 `created`（建档）/`content_changed`（原位刷新事实与 `snapshot_id`，重新激活 removed）/`removed`（`status=removed`，仅从 active 转换）；提取失败不猜测（保留上次事实或保持缺席）。item 的 `created_at/updated_at` 取快照 `fetched_at`（观测时钟）。
2. **crawl 接线**：`write_crawl_page` 在页面提交事务内执行同一 ingest（`CrawlStepResult` 不额外扩展），因此被爬页面（Discovery 输出）进入 Opportunity。
3. **评分版本化**：`opportunity_scores.evaluation_version`（默认 1）；唯一约束改为四元组 `uq_opportunity_scores_versioned`；重评 `evaluation_version = max+1`（竞争由约束仲裁，输者 skipped）；payload 与通知跟随新 score（每 score 至多一份）。
4. **重评判据**：待评 = 无评分或 `latest(scored_at) < item.updated_at`；未变化观测不重评（I1 幂等语义保持）。
5. **生命周期**：`expire_due_opportunities` 在派发前将 `active 且 deadline < now` 置 `expired`（beat 每 60s 触达）；移除事件置 `removed`；重现/内容变化置回 `active`（再由过期扫描复判）。`rejected` 保留闭集、无自动转换（用户动作面未准入）。
6. **迁移 0009**：加列 + 约束替换；downgrade guard（`evaluation_version > 1` 存在即拒绝）；空态循环与 guard 行为均有测试（`test_opportunity.TestMigrationCycle`）。
7. **禁止项保持**：非 USD → `currency_unsupported`（零 Provider 调用/零 usage/零汇率）；无 FX Profile 字段（schema 断言）；payload 键集与 `requires_human_approval=true` 冻结（REST 断言）。OpenAPI 零漂移（无 API 变化）。
