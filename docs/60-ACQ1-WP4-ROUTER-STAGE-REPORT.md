# ACQ-1 WP-4 Router 阶段验收报告

状态：**ACCEPTED（委托方确认，无独立第三方角色）**（静态范围；Browser 仍 disabled）。
日期：2026-10-05。格式：`docs/29-ACQ1-WORK-PACKAGES.md` 阶段报告格式。
依据：`docs/58-ACQ1-WP4-ADMISSION.md`（已签发）、ADR-034、`docs/57`（含 §15 实现注记）。

> **验收口径说明（2026-10-05）**：本仓库标准流程要求"独立复审（P0/P1=0）"。当前环境无第二角色、且无可用远端（GitHub 不可推送），因此**无法执行独立第三方复审**。经委托方确认，本阶段以"开发角色自测证据 + 委托方确认"验收，明确**不声称独立复审已完成**。复审对象为本地 `main` 合并提交（见下 Commit 段）。后续任何具备独立角色的环境可对该 exact head 补做复审。

## Phase / Status

- Phase：ACQ-1C Router v1（静态/Native；`dynamic_browser`/`advanced_browser` 永不选择）。
- Status：实现 + 阶段验收完成；合并前需独立复审该 exact head。WP-5 未准入。

## Implemented

- **`acquisition_router.py`（纯策略，无 I/O）**：静态候选表（RSS/URL；browser 尾部 disabled，`allow_browser` fail-closed 为 `acquisition_browser_not_admitted`）、安全终态集合、质量门（`acceptable`）、Circuit 窗口与门（阈值 5，`900×2^(cf-5)` 秒、封顶 7200）、AutoThrottle（信号驱动、250ms 指数、封顶 30s）、run 级预算账本、封闭 decision trace（11 键）。
- **`acquisition_route.py`（执行路径）**：`execute_route_run` 入口；circuit 预检（open 未到期 → 无传输拒绝 `acquisition_circuit_open`）；顺序 stage 执行与降级；质量未达标且无下一 stage → `PARTIAL` + `acquisition_quality_unmet`（RawItem/quality 保留）；逐 stage attempt 行（ordinal/fallback_reason/`budget_used.trace`，`decision_version="router-v1"`）；成功/失败终结与事件发布、raw dispatch、结构化日志。
- **既有管线接线**：`acquisition.py` 增加 Circuit 打开窗口（此前 `circuit_open_until` 从不被写入）、策略类失败不计 `consecutive_failures`、扩展 `_attempt`/`_finish_failure`（ordinal/fallback_count/run_started_at/record_attempt）；`acquisition_run_repository.py` 新增 `record_attempt`/`circuit_facts`（ports 同步扩展 `SourceRuntimeFacts`）；`tasks/acquisition.py` 切换到 `execute_route_run`（RSS/NATIVE_HTTP 静态注册表）。
- **入口隔离**：既有单后端 `execute_run` 及其调用方/测试保持不变（零回归）。

## Changed Files

新增：`backend/app/services/acquisition_router.py`（241 行）、`backend/app/services/acquisition_route.py`（约 520 行）、`backend/tests/test_acquisition_router.py`（17 项）。
修改：`backend/app/services/acquisition.py`、`backend/app/services/acquisition_run_repository.py`、`backend/app/domains/acquisition_ports.py`、`backend/app/tasks/acquisition.py`、`backend/tests/test_acquisition_application_port.py`、`backend/tests/test_tasks.py`、`docs/01`、`docs/02`、`docs/57`、`docs/58`。
未触碰：公开 API/Schema/迁移、WP-1/WP-2 策略语义、前端与其它工作包。

## Commit / Branch / PR

- 分支：`feat/acq-1c-router`（基线 `86379a8`，父 `c338fbb` = origin/main 快照）。
- 本地提交：`d9a7c8f`（冻结+准入）→ `fc270bd`（实现）→ `55cf551`（报告）→ 合并 `91ef8d9`（本地 `main`）。
- 远端：**未推送**（本环境无可用远端写权限），无 PR。复审对象为本地 `main@91ef8d9` 的 exact head。

## Schema / Migration

无。Alembic `upgrade head` 幂等复核通过；无新表/列。

## Public API / OpenAPI

无变化；`test_contract_freeze` 全量套件内通过（OpenAPI 快照零漂移）。

## Pipeline / State Changes

- 新增 `CollectionRun.fallback_count` 写入路径（既有列）；`CollectionRun.backend` 记录实际接受/终结的 stage 后端。
- `SourceAcquisitionState`：策略类失败不再计入 `consecutive_failures`；`circuit_open_until` 按 §15.5 打开/清除。

## NetworkPolicy / SitePolicy

不变；无放宽。Router 只消费既有 `EffectiveSitePolicy`/`EffectiveResourceBudget` 保守交集。

## Security / SSRF

- `dynamic_browser`/`advanced_browser` 无任何实例化路径（候选表静态派生；测试断言候选后端集合不含 browser）。
- 安全终态（policy/SSRF/端口/预算/browser/circuit/no-backend）不降级、不重试、不计 Circuit。
- 预算跨 stage 逐跳累计；无传输的预算拒绝不产生 attempt 行（证据诚实性）。
- trace 封闭 11 键；测试断言无 `://`、`?`、`secret` 泄漏。

## Concurrency / Idempotency / Recovery

- 状态更新沿用行锁（`_update_source_state` `with_for_update`）；重复投递测试（并发两 worker）→ 恰一次成功、1 条 attempt。
- Circuit open 拒绝不改变计数；半开探测为到期后单次正常 run。

## Offline Tests / Full Tests / Coverage

- 新增 `test_acquisition_router.py`：**17/17**（含纯策略 6 项与 DB 集成 11 项）。
- 定向回归（lease/acquisition/app-port/profile-policy/resources/tasks）：**54/54**。
- **全量（单次门禁）：373 passed，覆盖 91.92%**（CI fail-under 87.61；本地 85）。

## Docker / Compose / Browser Runtime

- **未启动任何 Browser/Docker 容器用于本阶段功能验证**；未修改默认 Compose。
- 测试基础设施（本机）：Postgres `pgvector/pgvector:0.8.6-pg16-bookworm` 与 Redis `redis:7.4.11-alpine3.21` 容器仅用于跑测试套件，结束后清理。

## Performance

无回归观测变化；Router 增加常量级策略计算。AutoThrottle 仅在真实节流信号时引入有界延迟（≤30s）。

## Known Limitations

- 生产候选链当前为单 stage（`native_http`/`rss`）；多 stage 级联由受控替换测试覆盖，Browser 尾部落定后可直接启用（§15.1）。
- 质量连续低劣→degraded 的"质量 streak"计数未持久化（无列）；health 仅按失败计数，留待后续增量。
- 指标为 structlog 事件（无新依赖）；Prometheus 类指标未引入。
- 默认 `max_pages=1` 时不会进入第二 stage（预算 fail-closed 的正确表现，见 §15.4）。

## P0 / P1 / P2

- 本阶段：**0 / 0 / 0**（架构门 introduced=0；P0=0）。
- 架构门参考：`existing=130 / introduced=0 / resolved=27 / P0=0 / P1=114 / P2=16`（与 AG-6 一致，未新增）。

## 门禁复核更正（2026-10-05）

首次门禁检查时 `acquisition_route.py`（新增）与 `acquisition_attempts.py`（后续新增）**尚未被 Git 跟踪**，而架构门只扫描 `git ls-files` 结果，因此首轮 `introduced=0` 存在**未跟踪文件盲区**。提交后复跑门禁，如实暴露 6 项 introduced findings（新模块 627 行超限 ×2；新模块引入 `schemas`/`events` 跨层导入 ×4）。

处置（提交 `refactor(acq-1c): extract attempt helpers into tracked module`）：

1. 新增 `app/services/acquisition_attempts.py`（被跟踪模块，仅导入允许层），承载 attempt 持久化辅助；`acquisition_route.py` 由 627 行降至 478 行；
2. `acquisition_route.py` 移除 `schemas`/`events` 导入：profile 加载改为经 `acquisition.py`（历史豁免模块）的 `validate_source_profile`；事件发布与心跳辅助回迁至 `acquisition.py`；`select_candidates` 改用 `allow_browser: bool` 参数（`acquisition_router.py` 同步移除 schema 导入）。

复验：门禁在全文件被跟踪状态下 `introduced=0 / P0=0 / status=passed`；回归 36/36 通过。**教训（流程）**：门禁与 hash 闭包类检查必须在 `git add` 之后执行，或在检查前确认新增文件已被跟踪。

## Recommendation

`ACCEPTED（委托方确认）`。实现、自测与阶段门禁均通过；独立第三方复审因环境限制（无第二角色、无可写远端）未执行，已在文首明确记录，未声称其完成。复审对象：本地 `main@91ef8d9`。

## Next Phase Admission Recommendation

本阶段经委托方确认验收后，WP-5（Controlled Discovery）具备依赖重评资格：其真实依赖"已验收 Static/Native Router 与 SitePolicy/预算"已满足。按仓库纪律，WP-5 须**先冻结规则（文档）再准入实现**；建议下一步为 WP-5 契约冻结草案（`docs/61`），不含代码/迁移。WP-3/R3 状态不受本报告影响（仍 BLOCKED）。
