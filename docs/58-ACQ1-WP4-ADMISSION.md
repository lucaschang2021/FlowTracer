# ACQ-1 WP-4 Router 阶段准入（已签发）

状态：**ISSUED / COMPLETE — READY FOR INDEPENDENT REVIEW**。实现与验收记录见 `docs/60-ACQ1-WP4-ROUTER-STAGE-REPORT.md`。
日期：2026-10-05。依据：`docs/29` WP-4、`ADR-034`、`docs/57-ACQ1-WP4-ROUTER-CONTRACT-ADDENDUM.md`、`GOVERNANCE-V2 §3`（Capability DAG）。

## 前置（已核对）

1. `docs/57` 由 ADR-034 冻结为合同；实现注记见 docs/57 §15；
2. WP-1、WP-2 已验收合并且无回归（本阶段全量回归见 docs/60）；
3. 静态真实依赖重评：WP-4 仅依赖 WP-1 + WP-2；Browser 分支 disabled；
4. 本阶段为静态范围，未启动 Browser/Docker/session。

## Task Authority Record（签发值）

```text
Task ID: FT-ACQ1-WP4-ROUTER-01
Control Epoch: GOV-2.1
Parent Goal: Deliver ACQ-1C static/native Router v1 without Browser
Exact Baseline: 86379a8 (feat/acq-1c-router freeze commit, parent c338fbb = main/PR #86)
Exact Branch: feat/acq-1c-router
Authorized Operation: One implementation increment + one affected targeted verification
Allowed Files: backend/app/services/acquisition_router.py (新增)
               backend/app/services/acquisition_route.py (新增)
               backend/app/services/acquisition.py / acquisition_run_repository.py (Router 接线)
               backend/app/domains/acquisition_ports.py (SourceRuntimeFacts + port 扩展)
               backend/app/tasks/acquisition.py (Router 接线)
               backend/tests/test_acquisition_router.py (新增) 与相关回归
               docs/57/58/60、ADR-034、看板
Allowed Tools: pytest/ruff/mypy/architecture_gate/openapi 检查；read-only Git/file checks
Forbidden Operations: Browser/Docker/session/dependency install；动态/高级后端启用；
               NetworkPolicy/SitePolicy/预算放宽；Discovery/Change/Opportunity；公开 API 新增未冻结字段
Max Iterations: 1 implementation increment + 1 targeted verification
Hard Deadline: 2026-10-05（本会话内完成）
Expected Evidence: 验收矩阵实值（docs/60 §5）；测试与覆盖率；OpenAPI/Alembic/Architecture Gate 零漂移；P0/P1/P2
Stop Condition: 任一安全终态被降级/重试、预算重置、Browser 被实例化、公开契约漂移或迁移失败 → 立即 STOP
Next Authority Owner: FlowTracer controller（Stage-Gate 后签 WP-5）
```

## 允许范围（按签）

- Router v1：静态后端选择、顺序降级、质量阈值与 decision version、Circuit 状态机、AutoThrottle、逐跳预算账本、封闭 decision trace、安全错误码与指标（全部按 `docs/57`）。
- 只使用既有冻结枚举与字段；无新表、无 migration。

## 禁止范围（按签）

- Browser/Docker/session、动态/高级后端启用、任何依赖安装；
- 放宽 WP-1 NetworkPolicy/SitePolicy/预算、绕过访问控制；
- Discovery/Change/Opportunity、PLUGIN、Frontend、Integration、Release；
- 公开 API 新增未冻结字段；生产配置变更。

## 验收矩阵（对齐 docs/29 WP-4，实值见 docs/60 §5）

| 项 | 通过条件 | 结果 |
| --- | --- | --- |
| Native success 零 Browser | 运行期无任何 browser 后端实例化 | PASS |
| 质量阈值与降级 | `acceptable` 计成功；否则按候选顺序降级；无候选记 partial 且保存 quality | PASS |
| 预算累计 | 跨 attempt/fallback 逐跳累计；超出即 `acquisition_budget_exhausted` 终态 | PASS |
| access-control stop | 安全终态不被降级/重试 | PASS |
| fallback 幂等 | 同 idempotency_key 不产生重复 attempt | PASS |
| Circuit 并发与状态机 | 状态转移/计数正确、行锁保护；安全终态不计入 consecutive_failures | PASS |
| trace 无泄漏 | 无 URL query/正文/headers/凭据 | PASS |
| 回归 | WP-1/WP-2/BE-4 全回归；OpenAPI/Schema 零漂移；P0/P1=0 | PASS（见 docs/60） |

## 回滚

feature flag 固定到 `rss`/`native_http`（任务可切回 `execute_run` 单后端路径）；保留 attempt 历史；安全策略不可回滚。

## 流程

实现完成于 `feat/acq-1c-router`；合并前需独立复审该 exact head。本记录不授权 push/merge 之外的任何下游阶段；WP-5 须另行准入。
