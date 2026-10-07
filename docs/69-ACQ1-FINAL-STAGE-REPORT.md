# ACQ-1 WP-8 Final 阶段报告

> 历史边界说明：本报告记录 2026-10-05 的 WP-8 I1 候选与当时能力快照。其后的 Phase 0-5 收口实现、500 passed / 92.29% 交付方候选证据及当前状态见 `docs/71`–`docs/77`；本文中“无 crawl”“I2 未切换”等断言仅描述当时快照，不得作为当前候选状态。

Phase / Status：ACQ-1-WP8 **FINAL — ACCEPTED（委托方确认，无独立第三方角色）**；分支 `feat/acq-1h-final`。
日期：2026-10-05。报告后 STOP（等待总控/委托方决定独立复审、Frontend 准入或发布路径）。

## 1. Implemented（唯一增量，无新能力）

- **价值闭环离线 E2E**（`tests/test_acq1_final_e2e.py`，3/3）：路由智能闭环、机会闭环、禁用能力断言。
- **可重复启动验证**（`scripts/verify_fresh_startup.py`）：隔离 `*_test` 库上空库 upgrade→check→downgrade base→re-upgrade，真实 uvicorn 启动 + liveness，冻结 OpenAPI 比对，精确清理。
- **秘密扫描**（`scripts/secret_scan.py`）：git 跟踪文件高信号模式（私钥/云与托管 token/凭据 URL），含植入自检；仓库 CLEAN。
- **性能基线**（`scripts/benchmark_offline.py` + `PERFORMANCE-BASELINE.md`）：组件级与运行级 p50/p95/max、峰值内存、预算与 fallback；Browser 统一 NOT MEASURED。
- **能力清单**（`docs/68`）：已验收 vs 禁用（含 R3 分支状态与 fail-closed 门）。
- **文档一致性修复**：WP-3-B 看板行不再指向 main 上不存在的 `docs/55/56/59`（改为显式指向分支 `feat/acq1-r3-fail-closed-offline`）；`CURRENT-GATE.md` 重写为当前事实。
- **Handoff/运维文档**：`FRONTEND-HANDOFF.md`（opportunities 端点、Notification `kind`/`opportunity_id`、枚举与错误码、已知限制）、`ALPHA-OPERATIONS.md`（迁移 head、beat 任务、验证脚本）、`PERFORMANCE-BASELINE.md`。

未实现任何 Endpoint/Schema/依赖/迁移/业务语义变化（WP-8 边界，`docs/67` §1）。

## 2. Changed Files

新增：`backend/tests/test_acq1_final_e2e.py`、`backend/scripts/{verify_fresh_startup,secret_scan,benchmark_offline}.py`、`docs/67`、`docs/68`、`docs/69`。
修改：`backend/PERFORMANCE-BASELINE.md`、`backend/FRONTEND-HANDOFF.md`、`backend/ALPHA-OPERATIONS.md`、`docs/02-DELIVERY-BOARD.md`、`docs/CURRENT-GATE.md`。

## 3. Commit / Branch / PR

分支 `feat/acq-1h-final`；实现+文档 commit `123ae18`；no-ff merge 到 `main`：`afd7b72`；本 traceability commit 记录以上哈希。本地 Git（无 GitHub 远端可用；委托方确认模式）。

## 4. 最终门禁矩阵（docs/25 §1，最终候选一次执行）

| 门禁 | 结果 | 证据 |
| --- | --- | --- |
| ruff check / format --check | ✅ 274 files | 本机执行 |
| mypy app | ✅ 100 source files | 本机执行 |
| pytest + coverage | ✅ **438 passed / 92.16%**（阈值 87.61%） | 本机执行（真实 PG16 + Redis 7.4 容器） |
| alembic check | ✅ 零漂移 | 本机执行 |
| empty-db upgrade / downgrade / re-upgrade | ✅ 全链通过（真实 PG16） | `scripts/verify_fresh_startup.py` |
| docker compose config | ✅ | `docker compose -f infra/compose.yaml config --quiet` |
| OpenAPI export --check | ✅ 与冻结快照一致 | `scripts/export_openapi.py --check` |
| secret scan | ✅ CLEAN（含植入自检） | `scripts/secret_scan.py` |
| git diff --check | ✅ clean | 本机执行 |
| uv sync --locked | ⚠ 未在本机执行（无 uv 环境）；依赖以已安装版本运行，`pyproject.toml`/`uv.lock` 在 WP-8 未变更 | 如实记录，CI 环境以锁定同步 |
| 架构门 check | ✅ introduced=0 / P0=0（existing 130 / resolved 27） | `architecture_gate check` |

## 5. docs/25 §2–§16 映射

- §2 Contract/Migration：零漂移、enum 重建与 downgrade guard 由 WP-7 测试 + fresh-startup 覆盖；§3 Native/RSS、§4 Scrapling static、§6 SSRF/访问控制、§7 Router/Quality、§8 Extraction、§9 Discovery、§10 Change、§11 Opportunity、§12 Reliability、§13 保密断言、§14 OpenAPI 均由全量套件按既有验收矩阵覆盖（见各 WP 报告与 `tests/`）。
- §5 Dynamic Browser：**未验收 → disabled**；E2E 断言 fail-closed（`acquisition_browser_not_admitted` / `acquisition_mode_unsupported`），不虚报。
- §15 Performance：组件级 Native parse p50 0.062–0.118 ms、Scrapling static 1.665 ms、Extraction 0.814–1.587 ms、版本证据 0.010 ms、机会策略 0.014 ms、Router 选择 0.002 ms；运行级 p50 81.9 ms / p95 126.6 ms、峰值 ≈124 KB、fallback 0/10、预算 requests=1/pages=1/bytes=3143；Browser NOT MEASURED。
- §16 最终判定：见 §7–§9。

## 6. BE-1..BE-8 回归

全量 438 项无失败，覆盖 BE-1（工程/健康/配置）、BE-2（数据/认证/安全）、BE-3（Radar/Source）、BE-4（采集/RSS/Native/边界）、BE-5（智能/分析/提取/质量）、BE-6（记忆/分块）、BE-7（通知/WS）、BE-8（稳定化/完整 E2E/契约冻结）。基线文件：`docs/04`–`docs/09`、`docs/18`、`docs/20`。P0/P1 无回归。

## 7. 价值闭环验证（"验证用户价值闭环"）

- **智能闭环**（`test_routed_intelligence_value_loop`）：Router 决策（native_http、闭合 trace、无 Browser）→ 版本证据（Artifact/Snapshot/`created` 事件）→ Discovery checkpoint（2 条 in-scope frontier、**无 crawl 执行、恰 1 attempt**）→ RawItem → Document → Analysis → Embedding → 通知（`kind=intelligence`）。
- **机会闭环**（`test_opportunity_value_loop`）：机会采集 → Snapshot → OpportunityItem（JSON-LD 显式字段）→ Hard Filter → score 86.55/act_now → Action Payload（`requires_human_approval=true`）→ 通知（`kind=opportunity`）→ REST（列表/详情/action-payload）。
- **禁用闭环**（`test_disabled_capabilities_stay_closed`）：Browser fail-closed、无 Browser 候选、`raw_items` 无 `snapshot_id`（I2 未切换）。

## 8. 可重复启动（"可从空环境按文档重复启动"）

`verify_fresh_startup.py` 在真实 PG16 上：建唯一 `flowtracer_wp8_<id>_test` → `upgrade head` → `alembic check` → `downgrade base` → `upgrade head` → uvicorn 启动 + `/health/live` 200 → OpenAPI 冻结比对 → `DROP DATABASE (FORCE)`；全部 passed。文档入口：`ALPHA-OPERATIONS.md` Quick Start 与 Verification scripts。

## 9. P0 / P1 / P2

- P0=0；P1=0（架构门引入 0；WP-8 未新增业务代码）；P2=0 新增（无新模块；脚本均在 600 行内且不属于 app 层预算）。
- 遗留 P2（既有基线，带 disposition）：架构门 existing P2×16，语义未变。
- 如实记录：`uv sync --locked` 未在本机执行（§4）；不接受为验收替代。

## 10. Known Limitations（交付侧）

- Browser（Dynamic/Advanced）disabled、R3 BLOCKED；R3 离线增量在分支未合并。
- I2 未做：crawl 执行、RawItem writer 切换/读取 API、机会版本重评与平台授权、多币种 FX。
- 并发评估同一 (opportunity, radar) 可能重复 AI 调用（结果幂等、有界），见 `docs/65` §6。
- 无 WS 扩张（机会通知经 REST）；无 Frontend/Integration/Release。
- 本地 Git 无 GitHub 远端；全部验收为委托方确认。

## 11. 发现与处置（超出原计划的事实）

1. **`CURRENT-GATE.md` 与仓库事实不一致**（停留于 2026-10-02 GOV-2.1 候选，未反映 WP-4..WP-7 已按委托方书面指示完成并合并）。处置：依委托方明确指示完成 WP-8 并将该文件重写为当前事实（委托方确认模型），不改变安全边界、R1..R2C 证据与 R3 BLOCKED 判定；本报告 §10 与 `docs/67` §7 如实记录。
2. **悬空文档引用**：看板 WP-3-B 行引用 main 上不存在的 `docs/55/56/59`。处置：改为显式指向分支 `feat/acq1-r3-fail-closed-offline`（四份文档与离线增量均在该未合并分支）。
3. WP-8 之前遗留的 WP-6 迁移 S608 已在 WP-7 修复（`docs/65` §10）；WP-6 迁移循环测试的 head 适配亦已完成。

## 12. Handoff 清单（交接用）

- 总览：`docs/02-DELIVERY-BOARD.md`；能力与禁用：`docs/68`；本报告：`docs/69`。
- 契约链：`docs/23`（采集）、`docs/24`（机会）、各 WP 契约（32/35/57/61/63/65）。
- 运行：`backend/ALPHA-OPERATIONS.md`（Quick Start、脚本、迁移 head、beat 列表）。
- 前端：`backend/FRONTEND-HANDOFF.md` + `backend/openapi/flowtracer-alpha-v0.1.json`（blob `1544614955…`）。
- 性能：`backend/PERFORMANCE-BASELINE.md`。
- 治理：`GOVERNANCE-V2.md`、`CURRENT-GATE.md`（本报告合并后与事实一致）。
- 复现全部门禁：见 §4 表（除 `uv sync` 与 CI 专属步骤外均本机可跑）。

## 13. Recommendation & Next Phase Admission Recommendation

- 建议：以委托方确认模式验收本最终候选；如需提高置信度，安排一次独立复审（对照 `docs/68/69`）。
- 下一步由委托方书面决定：① Frontend（FE-001）准入准备；② R3 真实执行 lease（解锁 Browser 分支）；③ PLUGIN-1 / 发布路径。WP-8 之后 ACQ-1 后端范围已按 `docs/29` 收尾，无未报告的未准入后端能力。
