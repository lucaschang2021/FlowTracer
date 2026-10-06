# ACQ-1 收口 Phase 1 阶段报告（WP-4 路由器收口）

Phase / Status：**Phase 1 COMPLETE（生产路径收口；委托方确认 + 可独立复核）**。
日期：2026-10-06。依据：`docs/71-ACQ1-CLOSURE-PLAN.md` §Phase 1、独立审核未完成清单 §2、ADR-038。
分支 `feat/acq1-closure-p1`。

## 1. 逐项收口与证据

### 1.1 生产路径有效选择与受控降级（不再以 patch 选择器取证）

- **契约变更（ADR-038）**：注册**受控静态重试阶段**（`scrapling_http`，stage 2、`static_retry`）——与主阶段一样**强制经 `SafeFetcher`**（NetworkPolicy/SitePolicy/逐跳计费/预算硬执行/站点限速全部复用），因此不存在旁路，满足 `docs/57` §15.1 原裁定的安全前提。候选表按**有效预算**门控：`max_pages ≥ 2 且 max_requests ≥ 2` 才产生 stage 2；默认 profile（`max_pages=1`）保持单阶段、§15.4 预算 fail-closed 语义不变。worker 固定装配 stage 2 后端；链构建时缺失的非主阶段按不可用跳过（主阶段缺失仍 `acquisition_no_backend` 终态）。
- **证据**（`tests/test_acq1_closure_p1.py`，全部**不打补丁**、经真实 `NativeAcquisitionBackend + SafeFetcher + 确定性本地 transport`）：
  - `test_selector_emits_static_retry_only_when_budget_allows`（纯策略：默认单阶段；预算允许两阶段；RSS 不受影响）。
  - `test_quality_gate_falls_back_through_production_chain`：质量未达标 → 降级到 stage 2 → `backend=scrapling_http`、`fallback_count=1`、attempts=[1,2]（attempt1 `acquisition_quality_unmet`，attempt2 `fallback_reason=quality_unmet`）、summary `stages=2/fallbacks=1`；**回退请求经过站点门**（记录到一次 ≈2000ms 间距，见 1.3）。
  - `test_chain_is_single_stage_under_default_profile`：默认 profile 下 stage 2 永不传输（`calls==0`、summary `stages=1`）。

### 1.2 降级/重试/重定向共享同一预算

- **实现**：Phase 0 的逐跳计费贯通到降级链——attempt1（1×302 + 1×503 + 1×200 重试）=3 requests、attempt2=1 request，账本 run 级累计；进入 stage 2 前预检"再发一个请求/一页是否可负担"，不可负担即 `acquisition_budget_exhausted` 终态且**不产生**该 stage 的 attempt 行。
- **证据**：`test_redirect_retry_and_fallback_totals_are_exact`（attempts requests=[3,1]，run 成功）；`test_budget_refuses_second_stage_before_transport`（`max_requests=3` 恰供 stage 1 → stage 2 传输数 0、attempt 行仅 1、run `acquisition_budget_exhausted`）。

### 1.3 Circuit 半开、并发保护与节流恢复（独立验证）

- **实现**：半开探测**原子化**——窗口到期后由 `claim_circuit_probe`（条件 UPDATE `circuit_open_until <= now` → 置 60s 探测租约）产生唯一探针；并发的其他 run 读取到未来窗口，直接以 `acquisition_circuit_open` 拒绝（无传输、无 attempt）。成功探针按既有语义清零并闭合；失败探针沿用指数退避重开窗口。
- **证据**：
  - `test_half_open_probe_success_closes_circuit`（到期窗口 → 单次探测传输 → `cf=0`、窗口清空、health healthy）；
  - `test_open_window_refuses_without_transport`（未到期 → 0 传输、错误码正确）；
  - `test_concurrent_half_open_probes_transmit_exactly_once`（探针 in-flight 时并发 run 被拒：`[True, False]`、transport 调用恰好 1 次）；
  - `test_throttle_applies_after_failure_and_recovers_after_success`（失败后自适应延迟实测 ≥0.9s 执行；成功一次后恢复 <0.5s）；
  - 既有 `test_circuit_open_blocks_before_transport` / `test_circuit_opens_after_repeated_retryable_failures` / `test_policy_denials_do_not_open_circuit` / `test_throttle_requires_real_signal` 全数保持。

### 1.4 Browser 保持不可达、不作为 Fallback

- **证据**：`test_browser_stays_unreachable_with_retry_enabled`（`allow_browser=True` → `acquisition_browser_not_admitted`；开启静态重试后候选仍不含任何 Browser 后端）+ 既有 fail-closed 套件。

## 2. 契约与文档

- ADR-038（注册受控静态重试阶段）；`docs/57` 新增 §16 收口注记（取代 §15.1"不注册为生产 stage"的裁定，安全前提不变）；`docs/71` Phase 1 标记完成。
- 公开 API/Schema/OpenAPI：**零变化**；默认 profile 行为零变化。

## 3. 门禁结果（Phase 1 候选）

- `ruff check .` / `ruff format --check .` / `mypy app`（strict，101 files）：通过。
- 架构门：`introduced=0 / P0=0`（existing 129 / resolved 28）。
- 新增测试：`tests/test_acq1_closure_p1.py` **10/10**；定向回归（router/discovery/tasks/lease/acquisition/final-e2e）全绿。
- 全量套件：见 §4。

## 4. 全量测试

Phase 1 候选全量执行（2026-10-06）：**466 passed**（456 基线 + 10 新增）/ **覆盖率 92.17%**（阈值 87.61%），94 warnings，437.64s。
配套门禁同批通过：`ruff check .`、`ruff format --check .`（278 files）、`mypy app`（strict，101 files）、架构门 `introduced=0 / P0=0`（existing 129 / resolved 28）、`alembic check` 零漂移、`scripts/export_openapi.py --check` 零漂移。

## 5. P0 / P1 / P2

- P0=0；架构门新引入=0；审核清单 §2 四项全部收口。
- 已知边界：跨 run 的全局 RPM 并行状态仍为实例级（跨 run 由 lease + 调度间隔约束），扩展点保留在 Phase 2 抓取执行器。

## 6. 停点与下一步

Phase 1 完成 → **Phase 2（WP-5 受控发现完整抓取执行：frontier 消费、robots/domain policy、逐跳 scope/SSRF 复核、有界遍历、取消/检查点/崩溃恢复、并发去重）**。
