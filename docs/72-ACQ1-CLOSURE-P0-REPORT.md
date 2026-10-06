# ACQ-1 收口 Phase 0 阶段报告（P1/P2 缺陷修复）

Phase / Status：**Phase 0 COMPLETE（独立审核清单的 6 项缺陷全部修复；委托方确认 + 可独立复核）**。
日期：2026-10-06。依据：`docs/71-ACQ1-CLOSURE-PLAN.md` §Phase 0、独立审核未完成清单 §1。
分支 `fix/acq1-closure-p0`。

## 1. 逐项修复与证据

### 0.1 预算逐跳计费（P1）

- **实现**：新增 `FetchSession`（`safe_fetcher.py`）对**每个真实请求**计数：初始请求、每次重定向 hop、每次重试各计 1；`FetchResponse.redirects` 暴露实际 hop 数；`SafeFetcher.fetch` 在**发出下一个请求之前**执行 `session.check()`（请求数/字节/时长），超限即以 `acquisition_budget_exhausted` 终止且不发出请求；失败路径把 `requests_made` 挂到 `CollectionError`，路由以此为账本计费（`max(retry_count+1, requests_made)`，保守优先）。
- **生产路径接线**：`NativeAcquisitionBackend` 用 `request.remaining_budget` 构建 session；`budget_used["requests"] = max(session.requests_made, retries+1)`。
- **证据**（`tests/test_acq1_closure_p0.py`）：`test_redirect_hops_count_as_real_requests`（302×2→200：redirects=2、requests_made=3）；`test_request_budget_stops_before_the_next_request`（预算=2 → 传输层恰好被调用 2 次，第 3 次未发出）；`test_retry_and_hop_share_one_request_budget`（重试与 hop 共享请求预算）；`test_native_backend_bills_hops_from_the_production_path`（真实 Native 后端：requests=3、redirects=2）。

### 0.2 时间与字节预算硬执行（P1）

- **实现**：`FetchSession` 贯穿执行——每个等待（连接、读头、读体）的 timeout 收敛到 `min(固定上限, 剩余 deadline)`；读取循环按**剩余字节预算**截断（超限在读取中即以 `acquisition_budget_exhausted` 失败，而不是读满固定 5 MiB 再检查）；重试退避前检查剩余时长，不足则不重试；整个 fetch 的外层 timeout 收敛到剩余 deadline；body 读取重构为 `_BodyReadState` + `_read_chunked_body`/`_read_plain_body`（`_decode_body` 仅编排，低于基线函数长度）。
- **证据**：`test_expired_deadline_blocks_before_any_request`（deadline 已过 → 0 次请求）；`test_byte_budget_trips_during_read_not_after`（1024B 预算读到 4096B 流 → 预算错误）；`test_fixed_cap_still_reports_response_too_large_without_budget`（无预算时行为不变）；`test_deadline_bounds_retry_backoff`（剩余 0.5s < 2s 退避 → 不 sleep、直接预算终止）。

### 0.3 版本回退判断（P1）

- **实现**：`source_artifacts` 新增 `current_snapshot_id`（**最近一次观测状态指针**，迁移 `20261006_0007`，回填=最高版本快照）；`change_tracking` 一律与**指针指向的状态**比较，而不是最高版本号；事件 `previous/current` 也以观测状态为准；removed 事件引用指针；重现时按指纹分类。
- **证据**：`test_revert_then_repeat_is_unchanged`（A→B→A→A → `created, content_changed, content_changed, unchanged`；快照仅 [1,2]；指针=v1；第 4 次 materiality=0）；`test_revert_then_return_to_b_reuses_snapshot`（A→B→A→B → 第 4 次 content_changed、复用 v2、previous=v1）；`test_removed_then_reappear_same_state_is_unchanged`（removed 两周期后重现同内容 → unchanged 且清除 removed_at）。

### 0.4 实际限速与并行控制（P1）

- **实现**：新增 `SiteGate`（`site_gate.py`，实例级、无模块状态）——每个请求经 `guard(host, crawl_delay_ms, requests_per_minute)`：**执行**爬虫延迟与 RPM 间距（`max(crawl_delay, 60_000/rpm)`）并且**同主机串行**（in-flight=1）；`_run_stage` 用 guard 包裹每个阶段请求；重试同样以站点间距为**下限**（`fetch_with_retries(min_delay=...)`，取 `max(2^n, 间距)`）；执行证据（配置值、enforced_in_flight、实际延迟列表）落入 `budget_summary["site_throttle"]`。
- **证据**：`test_crawl_delay_spacing_between_requests` / `test_rpm_spacing_dominates_when_longer_than_crawl_delay`（注入时钟：第二次请求实测等待 ≈1000ms/2000ms）；`test_same_host_requests_are_serialized`（并发探针峰值并发=1）；`test_routed_run_records_executed_throttle_evidence`（生产路由链落盘执行值）；`test_retry_waits_at_least_the_site_spacing_floor`（5s 间距下限 → 退避实际 5s）。

### 0.5 机会雷达筛选（P2）

- **实现**：`list_opportunities` 重写为**集合语义**——radar 过滤限定机会集合本身（存在该 radar 监控的 source 关联）；`recommendation`/`min_score` 改为 **EXISTS 子查询**（针对指定 radar 的评分过滤资格集合，剔除仅靠 join 行的过滤）；total 与 items 完全一致。
- **证据**：`test_radar_scope_and_score_filters_bound_the_set`（radar A → 仅其来源的 1 条；radar B → 仅未评分条目且 score=None；`recommendation=dismiss` → 0；total==len(items) 全场景）。

### 0.6 历史回填推进（P2）

- **实现**：`backfill_source_evidence` 改为 `(created_at, id)` 元组**游标推进**，循环直到空批或不满批；重复调用幂等。
- **证据**：`test_backfill_processes_more_than_one_batch`（5 条、批大小 2 → 一次调用全部 5 条；第二次调用 0）。

## 2. 迁移与兼容

- 迁移 `20261006_0007`（列 + FK + 回填），`alembic check` 零漂移；降级仅移除列，证据数据保护由 0005 既有守卫承担（空证据表才可通过）。
- `test_models.py` 冻结契约扩展 1 个 FK；`test_acquisition_change.py`/`test_opportunity.py` 迁移头断言更新为 `20261006_0007`。
- 公开 API/OpenAPI：**零变化**（`export_openapi.py --check` 通过）。

## 3. 门禁结果（Phase 0 候选）

- `ruff check .` / `ruff format --check .`：通过。
- `mypy app`（strict）：101 source files 无问题。
- 架构门：`introduced=0 / P0=0`（existing 129 / resolved 28——修复过程还顺带消解 1 条基线指纹）。
- `alembic check`：零漂移；空库循环（含 0007）由既有测试覆盖。
- 新增测试：`tests/test_acq1_closure_p0.py` **18/18**；全量套件与覆盖率见 §4。

## 4. 全量测试

Phase 0 候选提交全量执行：**456 passed / 覆盖率 92.13%**（阈值 87.61%；基线 438 项 + 新增 18 项）。ruff / format / mypy strict / 架构门（introduced=0、P0=0，另消解 1 条基线复杂度指纹并记入 `resolved_fingerprints` 台账）/ `alembic check` 零漂移 / OpenAPI `--check` 全部通过。

## 5. P0 / P1 / P2

- P0=0；架构门新引入=0；本 Phase 处理 4×P1 + 2×P2（审核清单 §1 全部）。
- 已知边界：跨 run 的全局 RPM/并行状态未落库（单 worker 串行 + 站点 guard 覆盖本次执行的每请求间距；跨 run 由 lease 与调度间隔约束）——记录为 Phase 2（抓取执行器）的扩展点。

## 6. 停点与下一步

按 `docs/71` 优先级，Phase 0 完成 → **Phase 1（WP-4 路由器收口：生产路径有效选择与受控降级证明、共享预算验证、Circuit 半开/并发/节流恢复独立验证、Browser 不可达保持）**。
