# ACQ-1 收口 Phase 3 阶段报告（WP-6 完整写路径）

Phase / Status：**Phase 3 COMPLETE（I2 写路径切换落成；委托方确认 + 可独立复核）**。
日期：2026-10-06。依据：`docs/71-ACQ1-CLOSURE-PLAN.md` §Phase 3、独立审核未完成清单 §4（完整 WP-6）、`docs/23` §10/§13/§14、`docs/63` §0/§17、ADR-040。
分支 `feat/acq1-closure-p3`；实现提交 `8dc1fb1`；no-ff 合并 `f5ba2c6`；本 traceability 提交记录以上哈希。

## 1. 逐项收口与证据

### 3.1 合格变化产生新下游输入（同源新版本产生新 RawItem）

- **实现**：RawItem 身份切换为**快照唯一**（`snapshot_id` + `UNIQUE(snapshot_id) WHERE NOT NULL`）；仅 **`created` / `content_changed`** 快照生成新 RawItem；`unchanged`/`metadata_changed`/`structure_changed` 仅保留 ChangeEvent 并计入 run 的 `duplicate_count`；内容回退复用既有快照且不再重复生成 item。旧三级去重由快照身份取代（entry 指向新 canonical → 新 artifact → 新 item）。evidence 先写、合格 item 随同一事务由 `persist_snapshot_items` 生成（repository 与 crawl 页提交共用）。
- **证据**（`tests/test_acq1_closure_p3.py`）：
  - `test_only_qualifying_snapshots_become_raw_items`（A→B→A→A：items [v1, v2]；第三次 content_changed 复用 v1 且**不新增** item；第四次 unchanged；事件序列 created/content_changed/content_changed/unchanged）；
  - `test_metadata_only_change_stays_an_event`（标题变化 → `metadata_changed`、items 保持 1）；
  - `test_crawl_pages_qualify_and_dispatch`（crawl 页同样按快照合格生成 item 并随 run dispatch：2 个 item、全部 dispatch）。

### 3.2 接入下游链路（变化 → 清洗 → 分析 → 情报 → 适用通知）

- **实现**：合格新 RawItem（含 crawl 页 `CrawlStepResult.raw_item_id` → `CrawlOutcome.raw_item_ids`）与既有 dispatch/清洗/分析/情报/通知管线**同路**；遗漏由既有 pending 扫描兜底。
- **证据**：`test_changed_observation_reaches_notification`（第二次 run 的 content_changed → 新 item → `clean_raw_item` → Document + PENDING Analysis → `run_analysis`（fake provider）→ `dispatch_notifications` 恰好 1 条 Notification，绑定该 Analysis）。

### 3.3 读取接口（前端可用 + OpenAPI 冻结）

- **实现**：`GET /api/v1/sources/{source_id}/changes`（分页 + `artifact_id`/`change_type` 过滤）与 `GET /api/v1/sources/{source_id}/artifacts/{artifact_id}/changes`；响应含 `previous/current` **有界** SnapshotRef（id/version/title/content_hash/quality/fetched_at）与 bounded field_diff；所有权经既有 source 加载器；OpenAPI 冻结快照已更新（`--check` 零漂移）。
- **证据**：`test_change_history_endpoints`（total=2 且倒序 [content_changed, created]；previous v1/current v2；字段集与 200 字符有界值；`change_type` 过滤=1；artifact 端点；`page_size` 分页；他源 404；不存在 artifact 404；非法 change_type 422；响应不含正文文本或内部 trace）。

### 3.4 序列验证（removed、重新出现、内容回退、连续重复观测）

- **实现**：removed 仍为“两次成功观测周期缺失”（miss_streak≥2，I1 冻结）；removed/重现不产生 item；连续重复观测 = unchanged。
- **证据**：`test_two_missing_cycles_remove_and_reappearance_restores`（两条目 feed → 单条目两次 → `removed` 事件、items 不变；重现同内容 → `removed_at` 清除、仍 2 items 无新快照）；`test_only_qualifying_snapshots_become_raw_items`（回退/重复观测见 3.1；快照始终 [1,2]）。

### 3.5 写路径切换（迁移、回填、兼容、downgrade guard）

- **迁移 0008**：`raw_items.snapshot_id`（FK RESTRICT）+ `uq_raw_items_snapshot`（部分唯一）+ legacy 索引重建为 `(source_id, external_id) WHERE external_id IS NOT NULL AND snapshot_id IS NULL`；**downgrade guard**：存在 snapshot 链接行即拒绝。
- **回填**：`change_backfill.backfill_source_evidence` 为 legacy item 建 v1 链（origin=legacy_backfill）并链接 `snapshot_id`；artifact 已存在时按内容指纹匹配链接；幂等。
- **模型面**：RawItem/RawItemStatus 移入 `models/raw_item.py`、TimestampMixin 上移 `models/types.py`（entities 737→680 行，净减，满足基线模块不得增长的门禁约束）。
- **证据**：`tests/test_acquisition_change.py::TestMigrationCycle`（0008→0004 空态循环 + 证据行守卫 + **链接行守卫**三段）；`test_legacy_items_are_linked_to_their_snapshots`（3 项分两批链接、二次调用 0、快照 origin 标记、幂等 id 集合）；`tests/test_models.py` 契约（新索引/部分谓词/FK）；`alembic check` 零漂移。
- **兼容验证（语义更新并注明）**：`test_acquisition.py` 三级去重计数 → 快照身份计数（(5,4,0,1)、items=5）；`test_acquisition_change.py::test_raw_item_write_path_unchanged` 重写为 I2 语义（列存在、链接、重复观测不新增）；`test_acq1_final_e2e.py` 能力断言翻转（列存在）。

## 2. 契约与文档

- ADR-040（I2 准入与语义冻结）；`docs/63` §0 状态更新 + 新增 §17 实现注记；`docs/71` Phase 3 标记完成。
- 公开 API：**新增 2 个读取端点**（OpenAPI 快照同步更新并提交）；迁移新增 1 个（0008）。
- `semantic-change-v1`（LLM 语义变化分类）**不在收口验收范围**、未启用（ADR-040 明示边界）；documents↔前代版本链接为记录外扩展点。

## 3. 门禁结果（Phase 3 候选）

- `ruff check .` / `ruff format --check .`：通过（149 files）。
- `mypy app`（strict）：109 source files 无问题。
- 架构门：**`introduced=0 / P0=0`**（existing 129 / resolved 28）——新模块全部低于 600 行、新函数低于 80 行预算；entities.py 净减行。
- `alembic check`：零漂移（0008 已应用）；`export_openapi.py --check`：零漂移（快照已更新）；`secret_scan.py`：通过。
- 新增测试：`tests/test_acq1_closure_p3.py` **7/7**；定向回归（models/shared/enforcement/change/final-e2e）全绿。
- 全量套件与覆盖率见 §4。

## 4. 全量测试

Phase 3 候选全量执行（2026-10-06）：**487 passed**（480 基线 + 7 新增）/ **覆盖率 92.25%**（阈值 87.61%），222 warnings，611.57s。
配套门禁同批通过：`ruff check .`、`ruff format --check .`（149 files）、`mypy app`（strict，109 files）、架构门 `introduced=0 / P0=0`（existing 129 / resolved 28）、`alembic check` 零漂移、`scripts/export_openapi.py --check` 零漂移（冻结快照已按 ADR-040 重新冻结）、`scripts/secret_scan.py` 通过。

## 5. P0 / P1 / P2

- P0=0；架构门新引入=0；审核清单 §4（完整 WP-6：3.1-3.5）全部收口。
- 已知边界（记录，不阻碍本 Phase）：`semantic-change-v1` 未启用；raw_items 与 documents 无显式前后代链接；Profile 级 metadata/structure 升级开关未启用；crawl consume-once 语义下 miss-streak 仅对 feed/单页路径生效（Phase 2 边界延续）。

## 6. 停点与下一步

Phase 3 完成 → **Phase 4（WP-7 机遇收口：Discovery/Change 的真实输出接入 Opportunity、生命周期与重评、REST/通知/人工确认契约收口；FX 与外部执行适配器保持不扩张）**。
