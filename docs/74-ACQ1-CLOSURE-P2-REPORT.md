# ACQ-1 收口 Phase 2 阶段报告（WP-5 完整抓取执行）

Phase / Status：**Phase 2 COMPLETE（I2 crawl 执行落成；委托方确认 + 可独立复核）**。
日期：2026-10-06。依据：`docs/71-ACQ1-CLOSURE-PLAN.md` §Phase 2、独立审核未完成清单 §3（完整 WP-5）、`docs/61` §0/§5/§6/§7、ADR-039。
分支 `feat/acq1-closure-p2`。

## 1. 逐项收口与证据

### 2.1 消费 frontier（真实 SafeFetcher 路径；每页 attempt 记录）

- **实现**：worker 注入 `discovery_transport=SafeCrawlTransport(SafeFetcher())`；`execute_route_run` 在 seed 阶段成功后消费 frontier（无 transport 时保持 I1 规划语义不变）。每个目标经与主阶段同一安全管道抓取（NetworkPolicy/SitePolicy/预算/逐跳计费/站点限速全部复用，无旁路），成功后提交「attempt 行 + 版本证据 + checkpoint 替换」的单一 CAS 事务。
- **证据**：`test_crawl_consumes_frontier_through_real_fetcher`（seeded plan → 3 页全部抓取一次；attempts [seed, a, b, c]（requested_url=页面 URL、`decision_version=discovery-crawl-v1`）；frontier 清空、`counters.crawled=3`、`fetched_count=4`、crawl 摘要 `pages_fetched=3/requests_used=4/complete=true`）；`test_recrawl_classifies_unchanged_without_false_removals`（第二次 run：seed `unchanged`、无 removed、快照不新增）。

### 2.2 robots / domain policy（获取并执行 robots、crawl delay）

- **实现**：robots 逐 origin 经同一 transport 获取（`text/plain`、≤512 KiB、≤2 请求、不重试）；`fetched` 遵守（disallow → 跳过该目标并保留 frontier；`Crawl-delay` 作为间距下限经 Phase 0.4 SiteGate 执行）；`missing`(404/410)/`unavailable` 按 `robots_mode` 分流：`respect` 视为无规则继续，`deny_if_unavailable` 整体拒绝（`robots_unavailable`，frontier 保留、零页面请求）。
- **证据**：`test_robots_disallow_skips_target_and_delay_executes`（disallow 目标零请求；`robots_skipped=1`；Crawl-delay 2s 被执行（实测排队 ≥1900ms）；目标保留在 frontier）；`test_robots_availability_modes`（404/503 × respect/deny 四象限：respect 均继续，deny 均 `robots_unavailable` 且 frontier 三条完整保留）。

### 2.3 逐跳复核（scope/SitePolicy/SSRF）

- **实现**：验证器在每个请求（含 redirect hop）前执行 `NetworkPolicy.validate` + `EffectiveSitePolicy.validate_target` + `scope_allows`；越界 hop 在传输前被拒（fail-closed）。
- **证据**：`test_redirect_is_rechecked_against_scope_and_ssrf`（302 → 未批准域被 `site_policy_denied` 拒绝且 else 域零传输；302 → 环回地址被 `network_policy_denied` 拒绝且零传输；单目标失败不终止 run（PARTIAL、failed_count=2、目标保留可重试））。

### 2.4 有界遍历（跨页累计、超限前停止）

- **实现**：pages/requests/bytes/time 四账跨页累计；`budget_gap` 在每次请求前判定（robots 消耗后、页面请求前再次判定）；`max_depth=min(profile,3)` 以 `base_depth` 跨 crawl 层生效；`max_frontier_size`/`max_discovered_urls` 沿用 I1 冻结值；停止原因全部落入 `stopped_reason`。
- **证据**：`test_page_budget_is_cumulative_and_resumes`（max_pages=2：run1 恰抓 1 页后 `page_budget`、frontier 余 2；run2 恰好续抓 1 页且不重抓已消费页）；`test_request_budget_stops_before_exceeding`（max_requests=2：robots 消耗后即停、零页面请求）；`test_byte_budget_accumulates_across_pages`（恰可负担 1 页后字节边界停止）；`test_budget_gap_boundaries`（0/上限/超限三情形精确：`used==max` 即阻塞下一请求）；`test_depth_cap_spans_crawl_layers`（depth=2 的第二层被抓取、第三层不规划不抓取）。

### 2.5 取消 / 恢复（claim 丢失即停、CAS、崩溃恢复）

- **实现**：checkpoint v2 携带 `crawl` 租约（run_id、300s、逐步续期）；每步 `commit_crawl_step` 为 claim 守卫的版本 CAS 单事务；无关写者的版本前进由 `cas_crawl_step` 在租约仍属本 run 时重试；claim 丢失在下一边界停止（不写、释放跳过）；崩溃恢复 = 同 run 重新 claim 后接管自身租约；stale worker 迟到写被 claim token 拒绝；attempt ordinal 按 `requested-if-free-else-max+1` 跨重入唯一。
- **证据**：`test_claim_loss_stops_the_crawl`（页面 b 抓取期间运行被 requeue：b 的提交被拒、c 零请求、frontier 保留 b/c、run 保持可再领取）；`test_crash_resume_no_refetch_no_loss`（b 处内部错误使 run 失败 → 重新领取后：已提交的 a 零重抓、b/c 各一次、ordinal 全唯一、frontier 清空）。

### 2.6 并发去重（双 worker 不重复抓取）

- **实现**：第一次 CAS 写入即取得 `crawl` 租约；另一 run 读到期未释放的租约时以 `checkpoint_conflict` 跳过 crawl（不传输、不写 checkpoint、不触碰 plan）。
- **证据**：`test_two_concurrent_runs_crawl_each_target_once`（run1 阻塞在页 a 抓取中时 run2 全程执行：run2 crawl `started=false/skipped_reason=checkpoint_conflict`、仅 1 条 seed attempt；全局每目标恰 1 次抓取、robots 恰 1 次）。

## 2. 契约与文档

- ADR-039（I2 准入与语义冻结）；`docs/61` §0 更新（I2 已准入并实现）、新增 §17 实现注记；`docs/71` Phase 2 标记完成。
- 公开 API/Schema/OpenAPI：**零变化**；迁移：**零新增**（checkpoint JSONB 复用，docs/61 §12.3）；默认（未注入 crawl transport）行为零变化——`test_acq1_final_e2e` 等既有断言不受影响。
- 新增模块：`discovery_pages.py`、`discovery_crawl.py`、`discovery_robots.py`（services）；`native_acquisition.SafeCrawlTransport`（providers）；端口扩展 `CrawlTransport`/`CrawlPageRecord`/`CrawlFetched`/`commit_crawl_step`/`claim_alive`/`crawl_checkpoint`。

## 3. 门禁结果（Phase 2 候选）

- `ruff check .` / `ruff format --check .`：通过（104 source files）。
- `mypy app`（strict）：104 source files 无问题。
- 架构门：**`introduced=0 / P0=0`**（existing 129 / resolved 28）——新模块全部低于 600 行预算，crawl 相关新函数均低于 80 行预算。
- 新增测试：`tests/test_acq1_closure_p2.py` **14/14**；定向回归（discovery/closure P0/P1/final-e2e）49 项全绿；`test_acquisition_discovery.py` 仅更新 checkpoint 版本断言（1→2，v2 语义）。
- `alembic check`：零漂移（无迁移）；全量套件与覆盖率见 §4。

## 4. 全量测试

Phase 2 候选全量执行（2026-10-06）：**480 passed**（466 基线 + 14 新增）/ **覆盖率 92.20%**（阈值 87.61%），194 warnings，574.42s。
配套门禁同批通过：`ruff check .`、`ruff format --check .`（104 source files）、`mypy app`（strict）、架构门 `introduced=0 / P0=0`（existing 129 / resolved 28）、`alembic check` 零漂移、`scripts/export_openapi.py --check` 零漂移、`scripts/secret_scan.py` 通过。

## 5. P0 / P1 / P2

- P0=0；架构门新引入=0；审核清单 §3（完整 WP-5：2.1-2.6）全部收口。
- 已知边界（记录，不阻碍本 Phase）：逐目标 Circuit 升级延后（run 级 Circuit 语义不变）；crawl run 暂停 miss-streak removed 判定（consume-once 非全量重复观测；feed/single-page 路径不变）；robots 每 run 重取；跨 run 全局 RPM 状态仍为实例级。B 类边界见 `docs/61` §17.10。

## 6. 停点与下一步

Phase 2 完成 → **Phase 3（WP-6 完整写路径：合格变化产生新下游输入、变化→清洗→分析→情报→通知接线、Change/Artifact 读取 API、序列验证、写路径切换与回填）**。
