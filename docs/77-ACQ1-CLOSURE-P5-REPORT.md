# ACQ-1 收口 Phase 5 阶段报告（WP-8 整链验收与交接）

Phase / Status：**Phase 5 COMPLETE（整链验收证据与交接材料就绪；READY_FOR_FRONTEND 待审核方独立复核）**。
日期：2026-10-06。依据：`docs/71-ACQ1-CLOSURE-PLAN.md` §Phase 5、独立审核未完成清单 §6（WP-8 整链验收与交接）、`docs/25` §16、ADR-038–ADR-041。
分支 `feat/acq1-closure-p5`。

## 1. 逐项收口与证据

### 5.1 真实整链 E2E（配置 → Acquisition → Router → Discovery → Change → Opportunity → 持久化 → REST/事件）

- **实现/证据**：`tests/test_acq1_closure_p5.py::test_full_chain_offline_end_to_end`——Opportunity-family URL 源（discovery=same_domain）+ Radar/RadarSource 配置；单次 run 内：Router 接受 `native_http` → seed 抓取（attempt 1）→ Discovery 消费 frontier 抓取被发现的职位页（attempt 2）→ 两页的版本证据（artifact/snapshot/change event ×2，全部 `created`）→ Opportunity item ×2（seed 与 crawl 输出同路；crawl 项的 RawItem 随 run dispatch）→ 评估 → 评分/不可执行 payload/通知 ×2 → REST 读回（`/sources/{id}/changes` total=2；`/opportunities` active+act_now total=2；action-payload `requires_human_approval=true`；`/notifications` total=2）。全程离线确定性 fixture，无公网访问。

### 5.2 路径覆盖（失败、取消、恢复、所有权、并发、幂等、预算耗尽）

- **失败**：`test_chain_failure_leaves_no_partial_state`（seed 404 → run FAILED；artifact/item/RawItem 全为 0，checkpoint 未被触碰）。
- **取消/恢复**：`test_chain_cancel_and_resume_without_duplicates`（被爬页提交期间 run 被 requeue → 提交被拒、目标保留 frontier、零半成品；重新领取后完成，每页恰好一次 evidence，item/crawl 无重复，最终 2 项全部评分）。
- **并发**：`test_chain_two_concurrent_runs_dedupe`（双 run 并发：后到者 `checkpoint_conflict` 跳过 crawl；被爬页全局恰一次抓取；artifact/评分无重复）。
- **幂等**：`test_chain_double_dispatch_is_claim_guarded`（同一 run 双投递：恰好一个执行；单套 evidence/item/评分）。
- **预算耗尽**：`test_chain_budget_exhaustion_preserves_frontier`（max_requests=2：seed+robots 后以 `request_budget` 停止、被爬页零传输、frontier 完整保留、seed item 照常评分）。
- **所有权**：REST 侧由 Phase 3/4 测试覆盖（他源 404、payload 不可用 404）并在本 Phase 的整链读回中复核 header 授权路径。

### 5.3 独立验收证据（精确候选提交）

- **实现**：`backend/scripts/closure_acceptance.py`——在 backend 目录运行即记录候选提交哈希/分支/工作树清洁度，执行全量 pytest（覆盖率下限 87.61%）与全部静态门禁（ruff check/format、mypy strict、架构门、Alembic 漂移、OpenAPI 冻结、秘密扫描），并把每项结果（命令、耗时、输出尾部）写入与候选哈希绑定的 JSON 报告（`closure-acceptance-<commit8>.json`），仅当全部通过时退出码为 0。审核方无需依赖交付方屏幕输出即可复现。
- **证据**：本 Phase 候选上 `--no-tests` 全静态门禁 **ALL CHECKS PASSED**（报告已生成）；含测试的完整运行见 §4；候选提交哈希随 `docs/71` §9 溯源记录。（"交付方 438/… passed" 类报告不作为独立证据——审核方以本脚本在精确候选提交上的输出为准。）

### 5.4 前端契约冻结（OpenAPI、状态、错误、分页、筛选与适用事件）

- **实现**：OpenAPI 冻结快照随 Phase 3 重新冻结（blob `faff18501e…`，`ARCHITECTURE.toml` pin 同步），本 Phase 零漂移；`backend/FRONTEND-HANDOFF.md` 增补 Change 读取端点契约（路径/分页/`change_type` 与 `artifact_id` 过滤/有界响应字段/`previous`/`current` 语义）、Opportunity 生命周期说明（评测版本化最新分、`expired`/`removed` 转换）与已知限制更新；`test_contract_freeze` 路径集断言覆盖新增端点。
- **证据**：`test_contract_freeze`（路径/错误信封/回调）全绿；`export_openapi.py --check` 零漂移；`FRONTEND-HANDOFF.md` §REST inventory/§Change history endpoints/§Known Alpha limits。

### 5.5 交接补齐（接口示例、演示数据方法、真实能力限制）

- **交接材料**：`docs/70-ACQ1-DELIVERY-PACKAGE.md` 更新（迁移 `0001..0009`、500 项测试、`closure_acceptance.py`、收口基线表 §3、门禁表 §4.1、§8 收口执行记录、§10 独立复核入口）；`README.md`（中/英）口径更新；根交付总文档同步（bundle 重建 + 校验 + 真实克隆测试，见 §2）。
- **真实能力限制**：`FRONTEND-HANDOFF.md` §Known Alpha limits 与 `docs/61` §17/`docs/63` §17/`docs/65` §12 明确记录：crawl 目标 consume-once（已完成页不重爬、discovery 侧不做 miss-streak 移除判定）、`semantic-change-v1` 未启用、平台授权工作流与多币种 FX 不扩张、Browser 保持 disabled。

### 5.6 文档口径（WP-5/WP-6 局部 I1 不得写成整体收口）

- **实现/证据**：README（中/英）、`docs/00`、`docs/02`、`docs/CURRENT-GATE.md`、`docs/70` 与根交付总文档统一为"**收口执行完毕（Phase 0-5）；READY_FOR_FRONTEND 待审核方独立复核**"；`docs/71` §6 的 8 项判定条件逐条对应本报告与前置 Phase 报告；无任何文档将 I1 表述为整体收口。

## 2. 交付物重建与校验

- Git bundle：`git bundle create flowtracer-acq1-delivery.bundle --all`（含全部历史与分支）→ `git bundle verify` → 真实克隆（`git clone <bundle> <tmp>`）校验 main 与候选提交可达；zip 副本同步重建。见 §5 记录。

## 3. 门禁结果（Phase 5 候选）

- 全量套件 + 覆盖率：见 §4；`scripts/closure_acceptance.py --no-tests` 的静态门禁全绿（ruff/format/mypy/架构门/alembic/OpenAPI/秘密扫描）。
- 新增测试：`tests/test_acq1_closure_p5.py` **6/6**。

## 4. 全量测试

Phase 5 候选全量执行（2026-10-06）：**500 passed**（494 基线 + 6 新增）/ **覆盖率 92.29%**（阈值 87.61%），250 warnings，679.35s。该次运行在提交前的最终代码/测试内容上执行；其后仅有文档改动。
配套门禁：`ruff check .` / `ruff format --check .`（293 files）、`mypy app`（strict，109 files）、架构门 `introduced=0 / P0=0`（existing 129 / resolved 28）、`alembic check` 零漂移（head `20261006_0009`）、`export_openapi.py --check` 零漂移、`secret_scan.py` 通过，均由 `scripts/closure_acceptance.py --no-tests` 复现（ALL CHECKS PASSED）。

## 5. READY_FOR_FRONTEND 判定（docs/71 §6）

| # | 条件 | 状态 |
| --- | --- | --- |
| 1 | Phase 0 全部 P1/P2 修复完成并通过门禁 | ✅ `docs/72` |
| 2 | WP-4 收口（1.1-1.4）有生产路径证据 | ✅ `docs/73`（ADR-038）|
| 3 | WP-5 完整（2.1-2.6）与 WP-6 完整（3.1-3.5） | ✅ `docs/74`（ADR-039）、`docs/75`（ADR-040）|
| 4 | WP-7 收口（4.1-4.4） | ✅ `docs/76`（ADR-041）|
| 5 | WP-8 整链验收（5.1-5.2）通过 | ✅ 本报告 §1 |
| 6 | **审核方在精确候选提交上独立复核 P0/P1=0** | ⏳ 待审核方（交付方已提供 `closure_acceptance.py` 与候选哈希；交付方报告不构成独立证据）|
| 7 | 前端契约冻结（5.4）且交接补齐（5.5） | ✅ 本报告 §1 |
| 8 | 看板/文档口径与事实一致（5.6） | ✅ 本报告 §1 |

**结论：交付侧 1-5、7、8 全部满足；第 6 项按治理纪律只能由审核方执行——READY_FOR_FRONTEND 的最终判定权在审核方。**

## 6. 停点

收口计划（`docs/71`）Phase 0-5 执行完毕；交付包已按候选提交重建。下一步 = 审核方独立复核（§5.3/§3 脚本与哈希），通过后按 `docs/02` 推进 Frontend（FE-001）准入。
