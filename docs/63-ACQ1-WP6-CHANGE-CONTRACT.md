# ACQ-1 WP-6 Change Intelligence 契约冻结（含实现注记）

状态：**FROZEN（ADR-036 Accepted）+ IMPLEMENTED（version evidence v1，I1 范围）**。冻结规则以 `docs/23` §10/§13（版本证据模型与 schema）为准；§15 实现注记记录落到代码时的精确裁定。
日期：2026-10-05。依据：`docs/29` WP-6、`docs/23-ACQ1-ACQUISITION-CONTRACT.md` §10/§13、ADR-024、`GOVERNANCE-V2 §3`；锚定代码：`app/models/evidence.py`、`app/services/version_evidence.py`、`app/services/change_tracking.py`、`app/services/acquisition_run_repository.py`、`alembic/versions/20261005_0005_version_evidence.py`。

## 0. 增量拆分（冻结）

- **I1（本增量，已实现：shadow-write 版本证据）**：`source_artifacts` / `acquisition_snapshots` / `change_events` 三表、三类指纹（content/metadata/structure）、噪声规范化、materiality 与 change_type 分类、bounded field diff、removed 判定、legacy backfill、迁移循环与安全 downgrade guard。**RawItem 写路径不变**（无 `snapshot_id` 列、无 writer 切换、无公开 API）。
- **I2（已准入并实现，2026-10-06，收口 Phase 3 / ADR-040；注记见 §17）**：RawItem writer 切换（`snapshot_id` 列 + 部分唯一索引重建 + 仅 qualifying Snapshot 生成 RawItem）、读取 API（`GET /sources/{id}/changes`、`GET /sources/{id}/artifacts/{artifact_id}/changes`）、notification 资格化下游（新 RawItem 与既有管线同路）。**`semantic-change-v1` 语义变化不在收口验收范围，未启用**（docs/71 §Phase 3 验收为 3.1-3.5；避免为收口扩张外部 AI 调用路径）。

## 1. 实体与 schema（FROZEN，docs/23 §10/§13）

- `SourceArtifact`：`(source_id, artifact_key)` 唯一；canonical URL、first/last seen、`removed_at`、safe metadata。
- `AcquisitionSnapshot`：artifact/run/version 序号、正文证据、metadata、结构摘要、三 SHA-256 指纹、extractor 版本、quality、fetched_at；`UNIQUE(artifact_id, version)`、`UNIQUE(artifact_id, content_hash, metadata_hash, structure_hash)`。
- `ChangeEvent`：artifact/run、previous/current snapshot、change_type、materiality、bounded field diff、detector 版本、occurred_at；`UNIQUE(collection_run_id, artifact_id)`；named CHECKs（created：previous NULL/current 非 NULL；removed：previous 非 NULL/current NULL；其余两者非 NULL；unchanged 允许相同）。
- change_type 闭集（I1 冻结）：`created` / `unchanged` / `content_changed` / `metadata_changed` / `structure_changed` / `removed`。

## 2. 三类指纹（FROZEN 语义 + §15 实值）

- **content**：NFC → CRLF→LF → 去零宽字符 → 去除 tracking query（`utm_*`/`fbclid`/`gclid`/`ref_src`）→ 逐行折叠空白并丢弃动态时间戳行（`last updated/updated/revision/更新时间/刷新时间` 前缀行与纯日期时间行）→ join 后 SHA-256。
- **metadata**：字段 allowlist `{title, author, published_at(UTC ISO), content_type}`，稳定 key 排序 canonical JSON 的 SHA-256。
- **structure**：语义块标签序列（`BLOCK_TAGS`，含 main/section/article/p/h1-h6/ul/ol/li/table 等，≤64）+ 附件 identity（host+path 小写、去 query，扩展名 allowlist，≤32 排序）的 canonical JSON SHA-256；**不含任何文本内容**，因此纯文本编辑不会移动结构维度；不保存完整 DOM。
- 导航/广告/DOM 级噪声移除在 I1 采用保守文本规则；更强的 DOM 级噪声区移除随 I2 评估，I1 不声称。

## 3. 分类与 materiality（FROZEN）

- 分类优先级：`content_changed` > `structure_changed` > `metadata_changed`；三指纹全同 → `unchanged`；无 prior → `created`。
- materiality（确定性权重，4dp）：content 0.6、structure 0.3、metadata 0.1，和值封顶 1.0；`created`=1.0、`removed`=1.0、`unchanged`=0.0。
- field_diff 有界：仅 allowlist 字段 + content/structure 标记；字段 ≤16、值截断 200 字符；created/removed/unchanged 为空。

## 4. removed 判定（FROZEN）

- **两次成功观测周期缺失**即判 removed（`miss_streak ≥ 2`，计数存于 artifact safe_metadata）；首次缺失仅累计 streak。
- 失败/被拒的 run 不触发判定（"访问失败不等于 removed"）。
- 重新出现即清除 `removed_at` 与 streak；是否产生新快照由指纹比较决定。
- 权威 404/410 的确认路径需要状态码贯通（当前 SafeFetcher 不暴露），**I1 不实现**，随 I2 评估。

## 5. legacy backfill（FROZEN I1 口径）

- 逐源回填既有 RawItems：`artifact_key = canonical_url or external_id or id`；生成 v1 Snapshot + `created` 事件；quality 记 `0.0000`，evidence 标记 `origin=legacy_backfill`。
- 幂等：已存在 artifact 的条目跳过；确定性顺序（created_at, id）；批大小有界。

## 6. 迁移与 downgrade guard（FROZEN）

- expand 迁移 `20261005_0005`：创建三表（含 named uniques/CHECKs），**不触碰 `raw_items`**。
- 安全 downgrade guard：任一证据表存在行时拒绝降级（防证据丢失）；空表时 drop 三表。循环（upgrade→downgrade→re-upgrade）与守卫均有测试证据。

## 7. 非目标（I1，FROZEN）

不实现：RawItem 生成条件切换、公开 API/OpenAPI 变化、Notification 下游、语义变化 Prompt、浏览器相关路径、Discovery 状态读取（除既有 checkpoint 语义外）。

## 15. 实现注记（2026-10-05，version evidence v1）

1. **模块**：`app/models/evidence.py`（三模型；不修改 `entities.py`，规避门禁的基线模块增长规则）；`version_evidence.py`（纯提取：normalize/fingerprint/structure/classify/materiality/diff）；`change_tracking.py`（写路径 + missing 判定 + backfill）。
2. **写入口**：`SqlAlchemyAcquisitionRunRepository.finish_success → _record_success` 内、与 run 成功**同事务**调用 `record_version_evidence`；legacy `execute_run` 与 Router `execute_route_run` 共用该仓储路径，因此两条管线均已 shadow-write 覆盖（无 RawItem 行为变化）。
3. **版本语义**：version 计数**不同内容状态**；内容回退到既有状态时复用旧快照（不新增版本），仍记录 ChangeEvent（`content_changed`）。
4. **并发**：artifact 以 `INSERT ... ON CONFLICT DO NOTHING` + `SELECT ... FOR UPDATE` 串行化；version = latest+1 在锁内计算；`UNIQUE(run, artifact)` 保证每 run 每 artifact 至多一个事件。并发测试断言版本单调 [1,2] 与事件一条/run。
5. **FK 顺序**：无 ORM relationship，flush 顺序不可推断；写路径显式 `flush()` 保证 artifact→snapshot→event 的插入顺序（backfill 同样处理）。
6. **结构 vs 文本隔离**：早期草案把文本块哈希纳入结构摘要，导致 content 变化级联触发 structure 变化（materiality 0.9）；已改为纯标签/附件维度（现为 0.6）。
7. **版本常量**：`extractor-v1`（快照）、`change-detector-v1`（事件）。
8. **I2 接口预埋**：`AcquisitionSnapshot.evidence` 可承载读取 API 的展示证据；`raw_items.snapshot_id` 与索引重建留给 I2（测试断言该列尚不存在，防止影子实现）。

## 16. 验收与证据

- 测试矩阵 `tests/test_acquisition_change.py`：**12/12**（纯提取 5 + 版本序列/分类/并发/removed 4 + backfill/RawItem 兼容 2 + 迁移循环与守卫 1）。
- 定向回归（change/acquisition/lease/router/discovery）：**56/56**；全量与覆盖率见 `docs/64-ACQ1-WP6-CHANGE-STAGE-REPORT.md`。
- 架构门（跟踪后）`introduced=0`；`alembic check` 零漂移；ruff/format/mypy 全绿。

## 17. 实现注记（2026-10-06，RawItem writer switch / I2 实值；ADR-040）

1. **模块**：`models/raw_item.py`（RawItem + RawItemStatus；entities 重新导出，净减行）、`models/types.py`（TimestampMixin 上移）、`services/change_backfill.py`（legacy 回填与快照链接；`change_tracking.backfill_source_evidence` 保留为兼容入口）、`services/change_queries.py`（读取查询）、`schemas/changes.py`、`api/v1/routes/changes.py`。
2. **合格定义**：`created` / `content_changed` 生成 RawItem（`snapshot_id` 唯一）；其余 change_type 计入 run 的 `duplicate_count`；同一快照已拥有 item 时不再新建（内容回退场景）。旧的三级去重（external_id/canonical/content_hash）由快照身份取代：entry 指向新 canonical URL → 新 artifact → 新 item（`test_acquisition.py` 的计数断言已按此语义更新并注明）。
3. **迁移 0008**：`snapshot_id` 列 + FK `fk_raw_items_snapshot` + 部分唯一 `uq_raw_items_snapshot` + legacy 索引重建（WHERE 改为 `external_id IS NOT NULL AND snapshot_id IS NULL`）；**downgrade guard**：存在链接行即拒绝；空态循环（0008→0007→0006→0005→0004→head）与拒绝路径均有测试。
4. **回填**：逐 item 建立 v1 链（origin=legacy_backfill）并设置 `raw_items.snapshot_id`；artifact 已存在但 item 未链接时，按 `content_fingerprint(normalize(raw_text))` 匹配既有快照链接；二次调用返回 0（幂等）；计数语义 = 本次获得链接的 item 数。
5. **读取 API**：`GET /sources/{id}/changes`（artifact_id/change_type 过滤、分页）与 `GET /sources/{id}/artifacts/{artifact_id}/changes`；响应 `previous/current` 仅含 bounded `SnapshotRef`（id/version/title/content_hash/quality/fetched_at）；所有权经 `resources.get_source`；他源 404、非法 change_type 422；OpenAPI 冻结快照已更新（`export_openapi --check` 零漂移）。
6. **下游**：合格 item 与既有 dispatch/清洗/分析/通知管线同路；crawl 页的 item 由 run 成功时统一 dispatch（`CrawlStepResult.raw_item_id` → `CrawlOutcome.raw_item_ids`），遗漏由既有 pending 扫描兜底。
7. **兼容验证**：`test_acq1_final_e2e`/`test_acquisition`/`test_acquisition_change`/`test_models` 的 I1 断言按 I2 语义更新（列存在、计数、索引契约）；新增 `tests/test_acq1_closure_p3.py`（7 项：写路径/序列/读取 API/下游/回填）。
