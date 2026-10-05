# ACQ-1 WP-4 Router 契约 Addendum（草案 / 规则冻结提案）

状态：**DRAFT — NOT FROZEN**。本文件补齐现行闸门点名的缺口："仍缺降级/预算/Circuit/Throttle 等精确规则"。所有 `PROPOSED` 值须经总控 ADR 冻结后才成为合同；`FROZEN` 项引用既有已冻结事实，不得改。
日期：2026-10-05。依据：`docs/29` WP-4、`docs/23` 采集契约、`GOVERNANCE-V2 §3`（Capability DAG）、ADR-022/023/026；锚定代码：`app/services/acquisition_policy.py`、`app/services/acquisition_types.py`、`app/models/entities.py`、`app/schemas/resources.py`。

## 1. 范围与非目标

- **范围**：`feat/acq-1c-router` 的 Router v1——静态后端选择、顺序降级、Circuit、AutoThrottle、decision trace、安全错误与指标。真实依赖 = WP-1 + WP-2（已合并）。
- **非目标（FROZEN）**：不实现 Browser/Discovery/Change/Opportunity；不放宽 WP-1 NetworkPolicy/SitePolicy/预算；不新增公开 API/Schema 字段（仅冻结字段）；`browser_dynamic = disabled`。

## 2. 后端与选择（FROZEN 枚举 + PROPOSED 规则）

`BackendName`（FROZEN）：`rss`、`native_http`、`scrapling_http`、`dynamic_browser`、`advanced_browser`。

- **可用后端（PROPOSED）**：
  - `SourceType.RSS` → 候选 `[rss]`
  - `SourceType.URL` → 候选 `[native_http, scrapling_http]`
  - `dynamic_browser`/`advanced_browser`：**Router 永不选择**（未准入）。若 `acquisition_profile.allow_browser=true`：整次以 `acquisition_browser_not_admitted` 拒绝（fail-closed），不静默降级为 Browser。
- **decision_version（PROPOSED）**：`router-v1`，写入每个 `AcquisitionAttempt.decision_version`。
- **Native success 零 Browser**：任何成功 run 的运行期不得实例化任何 browser 后端（可机器断言：无 dynamic/advanced 后端构造记录）。

## 3. 降级 / Fallback（PROPOSED）

- **顺序**：按第 2 节候选列表顺序尝试；最多降级 `len(candidates)-1` 次（当前为 1）。
- **触发**：当前后端 attempt 以 `retryable` 失败，或返回质量不达标（第 4 节）。
- **不触发**：`network_policy_denied`、`site_policy_denied`、`acquisition_budget_exhausted`、`acquisition_browser_not_admitted` 为终态，不降级。
- **幂等**：同一 run 内 fallback 幂等（同 `idempotency_key` 不产生重复 attempt）；`CollectionRun.fallback_count` 与 `AcquisitionAttempt.fallback_reason` 记录每次降级。
- **预算**：降级的目标尝试**累计计入**同一 run 预算（不重置）。

## 4. 质量阈值（PROPOSED）

- 质量来源：`extraction-quality-v1` 的 `quality_score`（Decimal 4dp）与 `quality_bucket`（`low`/`marginal`/`acceptable`，由 WP-2 冻结）。
- **成功阈值（PROPOSED）**：attempt 质量达到 `acceptable` 桶方计为成功；`marginal`/`low` 记为质量失败并触发降级（若还有候选），否则 run 记 `partial` 并保存 `CollectionRun.quality_score`。
- **状态聚合**：`SourceAcquisitionState.quality_ewma`（既有 0.8/0.2 EWMA）用于健康判定；阈值不改变 WP-2 打分算法。

## 5. Circuit Breaker 状态机（PROPOSED）

枚举（FROZEN）：`healthy`、`degraded`、`unhealthy`、`circuit_open`；字段 `SourceAcquisitionState.circuit_open_until`、`consecutive_failures`、`last_error_code`、`version`。

| 转移 | 条件（PROPOSED） |
| --- | --- |
| healthy → degraded | `consecutive_failures ≥ 2` 或连续 3 次质量低于 `acceptable` |
| degraded → unhealthy | `consecutive_failures ≥ 4` |
| unhealthy → circuit_open | `consecutive_failures ≥ 5`；置 `circuit_open_until = now + open_seconds` |
| 任意 → healthy | 一次成功（重置 `consecutive_failures = 0`） |
| circuit_open →（半开） | 到期后**单次**探测尝试；成功→healthy/degraded，失败→重新 open |

- **计入失败的分类（PROPOSED）**：仅 `retryable` 失败计入 `consecutive_failures`；策略/预算类终态**不**计入、**不**开 Circuit。
- **open_seconds（PROPOSED，待冻结）**：`900 * 2**min(open_count, 3)`，上限 7200（指数退避，封顶 2h）。`open_count` 为连续打开次数，成功后归零。
- **并发（PROPOSED）**：Circuit 状态更新与 attempt 记录须在 run 级/源级行锁下进行，避免并发 run 竞争；更新使用 `SourceAcquisitionState.version` 乐观保护。

## 6. AutoThrottle（PROPOSED）

- **上下限（FROZEN 来源）**：`EffectiveSitePolicy.crawl_delay_ms`、`requests_per_minute`、`max_parallel_requests` 取 source 与 operator 的**保守交集**（既有 `effective_site_policy`：delay 取 max、rpm/parallel 取 min）。
- **节流规则（PROPOSED）**：
  - 硬上限：单 run 内跨 attempt/pages 的实际请求速率 ≤ `effective RPM`；不因降级重置。
  - 自适应增延迟：出现 429/5xx 或 `latency_ewma_ms` 较基线翻倍时，实际 delay ×2，至多到 `max(crawl_delay_ms, 60_000)`。
  - 自适应回收：连续 N 次成功（PROPOSED N=5）后 delay 向 `crawl_delay_ms` 衰减（每步 ×0.5，不低于 floor）。
  - 与轮询：AutoThrottle **不得**缩短 `Source.poll_interval_minutes`（下限 15，FROZEN）。
- **并行**：实际并行度 ≤ `min(effective max_parallel_requests, 预算 max_concurrency)`。

## 7. 预算账本（PROPOSED）

- **计量口径**：`requests`、`pages`、`bytes`（响应体字节）、`duration_ms`。
- **作用域**：run 级累计，跨 attempt/fallback/redirect **逐跳**计入；redirect 每跳计 1 request；子资源按实际请求计。
- **执行**：每次请求前预留、请求后结算；`EffectiveResourceBudget.validate_usage` 超限即 `acquisition_budget_exhausted`（终态），已得部分结果按 `partial` 持久化，不丢弃证据。
- **记录**：`AcquisitionAttempt.budget_used`（JSONB）逐 attempt；`CollectionRun.budget_summary` 汇总。
- **Browser 关闭**：`max_browser_pages` 实际强制为 0（忽略 profile 非零值用于真实 Browser）。

## 8. Decision Trace（PROPOSED schema，封闭无泄漏）

每次 attempt 记录（`decision_version=router-v1`）：

```text
{ decision_version, source_id, run_id, ordinal, chosen_backend,
  candidates: [backend...], fallback_reason: str|null,
  checks: {network, site, scope, quality, budget, circuit} -> PASS|DENY|SKIP,
  usage: {requests, pages, bytes, duration_ms},
  outcome: succeeded|failed|blocked, error_code: str|null }
```

禁止：URL query、正文、headers、凭据、原始 inventory。trace 只落 `AcquisitionAttempt` 冻结字段与 `budget_used`/`fallback_reason`，不新增公开 API。

## 9. 安全错误码（PROPOSED 新增，复用既有）

- 复用（FROZEN）：`network_policy_denied`、`site_policy_denied`、`acquisition_budget_exhausted`。
- 新增（PROPOSED）：`acquisition_browser_not_admitted`、`acquisition_circuit_open`、`acquisition_quality_unmet`、`acquisition_no_backend`。
- 约束：错误 `safe_message` ≤500 字符，无敏感字段。

## 10. 指标（PROPOSED）

按源/后端：`attempts_total{backend,outcome}`、`fallbacks_total`、`circuit_open_total`、`budget_exhausted_total`、`quality_bucket{low,marginal,acceptable}`、`latency_ms` 直方图；Circuit/AutoThrottle 状态 gauge。

## 11. 验收（对齐 docs/29 WP-4）

Native success 零 Browser；质量阈值与降级；预算累计精确（逐跳/跨 attempt）；access-control stop；fallback 幂等；Circuit 状态机与并发安全；decision trace 无泄漏；回归 WP-1/WP-2 与 BE-4；P0/P1=0；OpenAPI/Schema 仅冻结字段零漂移。

## 12. 回滚与迁移

- 回滚：feature flag 固定到 `rss`/`native_http`；保留 attempt 历史；安全策略不可回滚。
- 迁移：预计无新表；若需 Circuit/Throttle 持久字段，仅在既有 `source_acquisition_states`/`collection_runs` 上 expand，附 upgrade/downgrade/re-upgrade 循环证据（如发生，触发 ADR）。

## 13. 待总控冻结项（OPEN）

1. 第 4 节成功阈值与第 5 节 Circuit 计数/退避参数、第 6 节 AutoThrottle 参数；
2. 第 8 节 trace 是否落在 `budget_used` JSONB 内或独立列；
3. 第 9 节新增错误码命名；
4. 是否允许 `scrapling_http` 在 WP-2 之外的调用路径（当前候选列表已含，需确认无 router 越权）。

## 14. 流程

本 Addendum 经总控 ADR/控制 PR 冻结后，方可签发独立 WP-4 Admission（精确 baseline/branch/允许文件/回滚），再由 Backend 实现并 Stage-Gate 验收。本草案本身不授权任何实现。
