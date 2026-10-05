# ACQ-1 WP-4 Router 阶段准入（草案）

状态：**DRAFT — NOT ISSUED**。本文件为总控签发 WP-4 Admission 提供草案模板；`«…»` 为待总控以届时事实填入的精确值。
日期：2026-10-05。依据：`docs/29` WP-4、`ADR-034`、`docs/57-ACQ1-WP4-ROUTER-CONTRACT-ADDENDUM.md`、`GOVERNANCE-V2 §3`（Capability DAG）。

## 前置（总控核对）

1. `docs/57` 已由 ADR-034 冻结为合同，精确值（阈值、Circuit 参数、AutoThrottle 参数、trace 落地、错误码命名）已裁定；
2. WP-1、WP-2 已验收合并且无回归；
3. 确认真实依赖重评：WP-4 静态范围仅依赖 WP-1 + WP-2；Browser 分支 disabled；
4. 额度窗口检查通过（5 小时 + 每周，>5%）。

## Task Authority Record（草案）

```text
Task ID: «FT-ACQ1-WP4-ROUTER-01»
Control Epoch: GOV-2.1
Parent Goal: Deliver ACQ-1C static/native Router v1 without Browser
Exact Baseline: «main@<exact-sha>»
Exact Branch: feat/acq-1c-router
Authorized Operation: One implementation increment + one affected targeted verification
Allowed Files: backend/app/services/acquisition_router.py (新增)
               backend/app/services/acquisition_policy.py / acquisition.py (接线，仅 Router 相关)
               backend/app/tasks/acquisition.py (Router 接线)
               backend/app/schemas/acquisition.py 或 resources.py (仅冻结字段)
               backend/tests/test_acquisition_router.py (新增) 与相关回归
               docs/57/58 与 OpenAPI 快照按需更新
Allowed Tools: uv/pytest/ruff/mypy/alembic(如 expand)/openapi export；read-only Git/file checks
Forbidden Operations: Browser/Docker/session/dependency install；动态/高级后端启用；NetworkPolicy/SitePolicy/预算放宽；Discovery/Change/Opportunity；公开 API 新增未冻结字段；production config；commit/push/PR/merge（除非另行授权）
Max Iterations: 1 implementation increment + 1 targeted verification
Hard Deadline: «由总控填»
Expected Evidence: 验收矩阵实值（后端选择/降级/质量阈值/预算逐跳/Circuit 状态机与并发/trace 无泄漏）；测试计数与覆盖率；OpenAPI/Alembic 零漂移；P0/P1/P2
Stop Condition: 任一安全终态被降级/重试、预算重置、Browser 被实例化、公开契约漂移或迁移失败 → 立即 STOP
Next Authority Owner: FlowTracer controller（Stage-Gate 后签 WP-5）
```

## 允许范围

- Router v1：静态后端选择、顺序降级、质量阈值与 decision version、Circuit 状态机、AutoThrottle、逐跳预算账本、封闭 decision trace、安全错误码与指标（全部按 `docs/57`）。
- 只使用既有冻结枚举与字段；如确需持久字段，仅 expand 迁移并附循环证据。

## 禁止范围

- Browser/Docker/session、动态/高级后端启用、任何依赖安装；
- 放宽 WP-1 NetworkPolicy/SitePolicy/预算、绕过访问控制；
- Discovery/Change/Opportunity、PLUGIN、Frontend、Integration、Release；
- 公开 API 新增未冻结字段；生产配置变更。

## 验收矩阵（对齐 docs/29 WP-4）

| 项 | 通过条件 |
| --- | --- |
| Native success 零 Browser | 运行期无任何 browser 后端实例化（可机器断言） |
| 质量阈值与降级 | 达到 `acceptable` 计成功；否则按候选顺序降级；无候选记 partial 且保存 quality |
| 预算累计 | 跨 attempt/fallback/redirect 逐跳累计；超限即 `acquisition_budget_exhausted` 终态 |
| access-control stop | 安全终态不被降级/重试 |
| fallback 幂等 | 同 idempotency_key 不产生重复 attempt |
| Circuit 并发与状态机 | 状态转移与计数正确、行锁/乐观保护下无竞争；安全终态不计入失败 |
| trace 无泄漏 | 无 URL query/正文/headers/凭据/原始 inventory |
| 回归 | WP-1/WP-2/BE-4 全回归；OpenAPI/Schema 仅冻结字段零漂移；P0/P1=0 |

## 回滚

feature flag 固定到 `rss`/`native_http`；保留 attempt 历史；安全策略不可回滚。

## 流程

本草案经总控核对前置、填入精确值并签发后，Backend 方可在 `feat/acq-1c-router` 开工；完成后 Stage-Gate 验收、独立复审、合并，随后方可评估 WP-5。本草案本身不授权任何实现或 push/PR/merge。
