# ACQ-1 WP-8 Final 契约冻结（规划 + 验收映射）

状态：**FROZEN（规划冻结）+ IMPLEMENTED（final wrap-up，I1 唯一增量）**。规则以 `docs/29` WP-8、`docs/25-ACQ1-ACCEPTANCE.md` 与 `ADR-026` 为准；§7 记录落盘时的实现注记。
日期：2026-10-05。依据：`docs/29` WP-8、`docs/25` 全部章节、`GOVERNANCE-V2 §3`、`docs/02-DELIVERY-BOARD.md`；锚定产物：`backend/tests/test_acq1_final_e2e.py`、`backend/scripts/verify_fresh_startup.py`、`backend/scripts/secret_scan.py`、`backend/scripts/benchmark_offline.py`、`docs/68-ACQ1-CAPABILITY-MANIFEST.md`、`docs/69-ACQ1-FINAL-STAGE-REPORT.md`。

## 1. 范围（FROZEN）

WP-8 是本 ACQ-1 的唯一收尾增量：**不新增任何能力**。允许范围按 `docs/29`：缺陷修复、恢复/指标/性能收尾、完整离线 E2E、OpenAPI/Frontend handoff、运行文档与已知限制。**任何新增 Endpoint / Schema / 依赖 / 业务语义均越界并触发 STOP。**

本次交付物（唯一增量）：

1. **价值闭环离线 E2E**（`tests/test_acq1_final_e2e.py`）：路由驱动的智能闭环（采集→证据→变更→发现 checkpoint→RawItem→Document→Analysis→Embedding→通知）与机会闭环（采集→Snapshot→OpportunityItem→Hard Filter→Score→Action Payload→通知），并在同一套件内断言禁用能力（Browser 不可选、`allow_browser=True` fail-closed、RawItem writer 未切换、无 crawl 执行）。
2. **可重复启动验证**（`scripts/verify_fresh_startup.py`）：在唯一命名 `*_test` 隔离库上执行空库 upgrade→alembic check→downgrade base→re-upgrade→应用构造与 OpenAPI 冻结比对，精确清理。对应 `docs/25` §1 的 empty-db 循环与 §16 的"可从空环境按文档重复启动"。
3. **性能基线刷新**（`scripts/benchmark_offline.py` + `PERFORMANCE-BASELINE.md`）：组件级 p50/p95/max（Native 解析、Scrapling static、Extraction、版本证据、机会策略、Router 选择）与运行级采样（单 run 时长/峰值内存、budget_summary、fallback 频率）。**Dynamic Browser 与 Browser concurrency 标注 NOT MEASURED（disabled），不得虚报。**
4. **安全扫描**（`scripts/secret_scan.py` + 报告记录）：对 git 跟踪文件执行高信号秘密模式扫描（私钥、云厂商/代码托管/协作平台 token、带凭据连接串）。
5. **能力清单**（`docs/68`）：已验收能力 vs 禁用能力全表 + 证据指针；R3 离线增量位于分支 `feat/acq1-r3-fail-closed-offline`（未合并，R3 仍 BLOCKED）。
6. **最终阶段报告**（`docs/69`）：`docs/25` 全门禁矩阵、BE-1..BE-8 回归映射、P0/P1 状态、已知限制、交接清单、发现项处置。
7. **文档一致性修复**：`docs/02-DELIVERY-BOARD.md` 的 WP-3-B 行不再指向 main 上不存在的 `docs/55/56/59`（改为指向分支）；`docs/CURRENT-GATE.md` 更新为与仓库提交/看板事实一致（委托方确认模型），并如实记录该不一致的发现与处置。
8. **Handoff/运维/性能文档更新**：`FRONTEND-HANDOFF.md`（opportunities、通知 kind、枚举更新）、`ALPHA-OPERATIONS.md`（beat 任务、迁移 head、验证脚本、能力开关）。

## 2. 验收映射（docs/25，FROZEN）

| docs/25 门禁 | WP-8 证据 |
| --- | --- |
| §1 通用质量门禁（ruff/format/mypy/pytest+coverage/alembic check/empty-db 循环/OpenAPI --check/secret scan/git diff --check） | 最终候选 commit 一次全量执行，结果入 `docs/69`；`verify_fresh_startup.py` 覆盖 empty-db 循环；`secret_scan.py` 覆盖 secret scan |
| §2 Contract 与 Migration（零漂移、enum 重建、downgrade fail-fast） | `alembic check`；WP-7 迁移循环/守卫测试；`verify_fresh_startup.py` |
| §3 Native/RSS 回归 | 全量套件（test_acquisition、test_alpha_e2e 等）+ WP-8 E2E 智能闭环 |
| §4 Scrapling Static | 全量套件（test_acquisition_parsers/test_extraction）+ 基准中的 static 采样 |
| §5 Dynamic Browser | **未验收 → 明确禁用**；WP-8 E2E 断言 fail-closed；能力清单列 disabled |
| §6 SSRF 与访问控制 | 既有 test_security/test_safe_fetcher/test_acquisition_policy（全量套件）|
| §7 Router 与 Quality | 既有 router 套件 + WP-8 E2E（trace 闭合、无 Browser、安全终止）|
| §8 Adaptive Extraction | 既有 extraction 套件（九类 family、恶意输入）|
| §9 Controlled Discovery | 既有 discovery 套件 + WP-8 E2E（checkpoint 落盘、无 crawl、硬上限）|
| §10 Change Intelligence | 既有 change 套件 + WP-8 E2E（artifact/snapshot/change 证据）|
| §11 Opportunity | 既有 opportunity 套件 + WP-8 E2E（端到端闭环与 REST）|
| §12 Reliability 与资源耗尽 | 既有 lease/circuit/预算/并发套件（全量）|
| §13 Observability 与安全 | 既有保密断言（全量）+ secret_scan + 基准 metrics 数据 |
| §14 OpenAPI 与交接 | OpenAPI --check + `FRONTEND-HANDOFF.md` 更新 |
| §15 Performance Baseline | `benchmark_offline.py` + `PERFORMANCE-BASELINE.md` 更新（Browser NOT MEASURED）|
| §16 最终判定 | `docs/68`（能力清单）+ `docs/69`（全门禁矩阵、P0=0/P1=0、可重复启动、交接）|

## 3. 边界与非目标（FROZEN）

- 不新增 Endpoint/Schema/依赖/迁移；不改变任何既有 API/Schema/事件/评分/管线语义（发现缺陷时只允许修复，并在报告中列出）。
- 不批准 Browser（R3 真实执行仍需 B 阶段 lease）；不合并 R3 离线增量分支；不改 R1..R2C 已验收资产。
- 脚本仅为本仓库验证工具（离线、无网络、`*_test` 保护），不是产品能力。
- 性能数据只代表本机隔离 fixture，不作为 SLA/容量结论。
- 验收模式：委托方确认（无独立第三方）；如实标注。

## 4. 允许文件

`backend/tests/`（新增 E2E）、`backend/scripts/`（三个验证脚本）、`backend/PERFORMANCE-BASELINE.md`、`backend/FRONTEND-HANDOFF.md`、`backend/ALPHA-OPERATIONS.md`、`docs/02`、`docs/67..69`、`docs/CURRENT-GATE.md`。除此之外任何文件在 WP-8 均视为越界。

## 5. 回滚

回滚 = 恢复上述文档/脚本到最终候选前版本；不涉及迁移与业务数据（WP-8 无 Schema/数据变化）。

## 6. 停点

最终候选全门禁通过、报告提交后 STOP；是否进入 Frontend/Integration/Release 或独立复审由总控/委托方书面决定。

## 7. 实现注记（2026-10-05，final wrap-up）

1. **E2E 组织**：`test_acq1_final_e2e.py` 三个用例——`test_routed_intelligence_value_loop`（Route→证据/发现→文档管线→通知）、`test_opportunity_value_loop`（Route→机会→评分→Payload→通知→REST）、`test_disabled_capabilities_stay_closed`（Browser fail-closed、writer 未切换、无 crawl）。全部使用本地 fixture 与 Fake Provider，不访问公网。
2. **启动验证**：脚本自建 `flowtracer_wp8_<uuid>_test` 库（拒绝非 `*_test`），依次 `upgrade head → alembic check → downgrade base → upgrade head`，随后以 `create_app` + `export_openapi` 序列化比对冻结快照，最后 `DROP DATABASE` 精确清理。
3. **秘密扫描**：扫描 `git ls-files` 跟踪文本文件；允许清单限定于本仓库已知占位符文件（`.env.example`、CI 工作流、测试夹具）；事件内命中即 fail。
4. **基准**：组件级循环采样（sorted、median、nearest-rank p95、max）+ 运行级 N=5 次路由执行（含 tracemalloc 峰值），记录 budget_summary 与 fallback_count；Browser 标注 NOT MEASURED。
5. **CURRENT-GATE 处置**：发现该文件停留在 2026-10-02 的 GOV-2.1 候选状态、与看板/提交（WP-4..WP-7 已按委托方指示完成并合并）不一致；按委托方明确指示完成 WP-8，并在本文件与 `docs/69` 如实记录该不一致与处置（重写为当前事实，不改变任何既有安全边界）。
6. **悬空引用修复**：WP-3-B 看板行原引用 main 上不存在的 `docs/55/56/59`（该四份文档仅存在于未合并分支 `feat/acq1-r3-fail-closed-offline`），改为显式指向分支。
