# ACQ-1 收口 Phase 4 阶段报告（WP-7 机遇生命周期与重评）

Phase / Status：**Phase 4 COMPLETE（I2 生命周期与重评落成；委托方确认 + 可独立复核）**。
日期：2026-10-06。依据：`docs/71-ACQ1-CLOSURE-PLAN.md` §Phase 4、独立审核未完成清单 §5（WP-7 收口）、`docs/24`/`docs/65` §0/§12、ADR-041。
分支 `feat/acq1-closure-p4`；实现提交 `2eb60e4`；no-ff 合并 `e3eb0d0`；本 traceability 提交记录以上哈希。

## 1. 逐项收口与证据

### 4.1 真实输入（Discovery/Change 的真实输出接入 Opportunity）

- **实现**：`record_opportunity_items` 升级为 ChangeEvent 驱动——`created` 建档、`content_changed` **原位刷新**（facts + 快照身份 + 重新激活）、`removed` 转 `removed`；crawl 页提交（`write_crawl_page`）执行同一 ingest，被发现的页面（含 JSON-LD JobPosting）直接进入 Opportunity；非 Opportunity-family 源零影响。item 时间戳取快照 `fetched_at`（观测时钟）。
- **证据**：`test_content_change_refreshes_item_and_reevaluates`（同一 artifact 只有 1 个 item，事实被刷新、`updated_at` 前进）；`test_crawl_pages_feed_opportunity_items`（生产路由 + crawl：被爬页面 JSON-LD → item → 评分 → payload；seed 页以标题建档并按 `insufficient_data` 拒绝）。

### 4.2 生命周期与重评（评分版本化；唯一约束按需修订）

- **实现**：`opportunity_scores.evaluation_version`（默认 1）；唯一约束由三元组改为 `(opportunity_id, radar_id, score_version, evaluation_version)`（迁移 0009 + downgrade guard）；重评 `version = max+1`；待评判据 = “最新观测新于最新评分”（未变化 item 保持已评）；`removed` 由事件置位、`expired` 由派发前扫描按 deadline 置位（beat 60s 触达）、重现/内容变化置回 active。
- **证据**：`test_content_change_refreshes_item_and_reevaluates`（scores [1,2]、payload 2、notification 2；item 仍为 1）；`test_unchanged_observation_stays_scored`（未变化观测 → 0 重评，scores 仍 [1]）；`test_removed_then_reappearance_reactivates`（removed → 队列跳过 → 重现恢复 active 并重评 [1,2]）；`test_expired_items_leave_the_queue`（过期扫描置 expired、零评分零通知、直接评估返回 skipped）；`tests/test_opportunity.py::TestMigrationCycle`（0009 空态循环 + `evaluation_version>1` 拒绝降级）。

### 4.3 契约收口（REST、通知/适用事件、人工确认边界；OpenAPI 冻结）

- **实现**：零 API/Schema 变化（冻结快照与 blob pin 不变，`export_openapi --check` 零漂移）；状态闭集（active/expired/removed/rejected）经既有 `status` 过滤面呈现；Action Payload 键集与 `requires_human_approval=true` 不变；通知仍按 `(user, opportunity_score_id)` 部分唯一，随新评分产生。
- **证据**：`test_rest_status_filters_payload_boundary_and_ownership`（active/removed 过滤；payload 键集逐键冻结断言；`requires_human_approval=true`；响应无 raw HTML；他源 404；无评分 item 的 payload 404；无执行/投标/报价/付款字样）。

### 4.4 禁止项保持（FX 与外部执行不扩张）

- **实现**：非 USD 一律 `currency_unsupported` 拒绝（进入 Hard Filter 前无任何汇率查询、无 AI 调用、无 usage）；无 `fx_table`/`fx_version` 字段或外部执行适配器；自动投标/报价/沟通/合同承诺/资金操作维持永久禁止（无任何新增代码路径）。
- **证据**：`test_non_usd_never_converts_and_no_fx_surface`（EUR：Provider 调用 0、usage 0、payload 0、disqualifier `currency_unsupported`；profile schema 无 fx 字段）；ADR-041 明示边界。

## 2. 契约与文档

- ADR-041（I2 准入与语义冻结）；`docs/65` §0 状态更新 + 新增 §12 实现注记；`docs/71` Phase 4 标记完成；`docs/02` 看板更新。
- 迁移新增 1 个（`20261006_0009`）；公开 API/OpenAPI：**零变化**。

## 3. 门禁结果（Phase 4 候选）

- `ruff check .` / `ruff format --check .`：通过。
- `mypy app`（strict）：109 source files 无问题。
- 架构门：**`introduced=0 / P0=0`**（existing 129 / resolved 28）——期间修复 `routes/changes.py` 的 `models_persistence` 跨层导入（改用 `app.api.dependencies` 再导出 `User`，与 WP-7 路由同模式）。
- `alembic check`：零漂移（0009 已应用）；`export_openapi.py --check`：零漂移；`secret_scan.py`：通过。
- 新增测试：`tests/test_acq1_closure_p4.py` **7/7**；定向回归（opportunity/p3/final-e2e）49 项全绿。
- 全量套件与覆盖率见 §4。

## 4. 全量测试

Phase 4 候选全量执行（2026-10-06）：**494 passed**（487 基线 + 7 新增）/ **覆盖率 92.29%**（阈值 87.61%），226 warnings，639.22s。
配套门禁同批通过：`ruff check .`、`ruff format --check .`、`mypy app`（strict，109 files）、架构门 `introduced=0 / P0=0`（existing 129 / resolved 28）、`alembic check` 零漂移、`export_openapi.py --check` 零漂移、`scripts/secret_scan.py` 通过。

## 5. P0 / P1 / P2

- P0=0；架构门新引入=0；审核清单 §5（WP-7 收口：4.1-4.4）全部收口。
- 已知边界（记录，不阻碍本 Phase）：`rejected` 状态无自动转换（用户动作面未准入）；平台逐站点访问授权工作流、通知 WS 扩展、多币种 FX、外部执行适配器均按冻结边界**不扩张**；重评通知可能对同一机会的每次实质变化各发一条（由新 score 的资格判定约束，属冻结语义）。

## 6. 停点与下一步

Phase 4 完成 → **Phase 5（WP-8 整链验收：配置→Acquisition→Router→Discovery→Change→Opportunity→持久化→REST/事件全链 E2E；失败/取消/恢复/并发/幂等/预算路径；精确候选提交上的独立验收证据；前端契约冻结与交接补齐；READY_FOR_FRONTEND 判定）**。
