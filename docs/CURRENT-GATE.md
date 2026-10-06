# FlowTracer 当前阶段闸门

更新时间：2026-10-06（独立审核后修订；此前版本为 2026-10-05 WP-8 收尾稿）。

## 当前状态：I1/阶段性交付；收口未完成（独立审核确认）；Browser 分支保持 disabled

- 事实基准：本地 `main` 的提交序列（WP-1..WP-8 已合并）见 `docs/69` §Commit 与看板。验收模式：**委托方确认（owner-confirmed，无独立第三方角色）**；收口阶段的独立验收由审核方在精确候选提交上执行（"438 passed"仅为交付方报告）。
- 已完成 **I1/实现范围**：WP-1（Source 契约/健康/lease）、WP-2（静态 adapter/quality）、WP-4（Router v1）、WP-5 I1（Discovery 规划与 Frontier）、WP-6 I1（版本证据 shadow-write）、WP-7 I1（Opportunity Radar）、WP-8 初版（价值闭环 E2E、可重复启动、性能基线、秘密扫描、能力清单、交接文档）。
- **收口未完成（2026-10-06，独立审核确认）**：未完成清单与逐阶段执行映射见 [`docs/71-ACQ1-CLOSURE-PLAN.md`](71-ACQ1-CLOSURE-PLAN.md)——修 P1（逐跳预算/时间字节硬执行/版本回退/真实限速并行）→ WP-4 生产路径收口 → 完整 WP-5（抓取执行/robots/有界遍历/取消恢复）→ 完整 WP-6（写路径切换/读取 API/序列验证）→ WP-7 生命周期收口 → WP-8 整链验收与交接；**READY_FOR_FRONTEND 未达成**（判定条件见收口计划 §6）。
- 仍禁用/阻塞：Dynamic/Advanced Browser **disabled**（`BROWSER_DYNAMIC_ENABLED=False`，`allow_browser=True` fail-closed）；R3 真实执行为 **BLOCKED**，须另签 B 阶段 lease；R4/R5 未准入。R3 离线增量位于分支 `feat/acq1-r3-fail-closed-offline`（docs/54/55/56/59 在该分支，**未合并**）。
- 未准入：PLUGIN-1、Frontend（FE-001）、Integration（INT-001）、Release（REL-001）。
- 执行权：当前无任何未决 lease/授权；任何新工作（含收口各阶段、R3 真实执行、Frontend 准入）须按 `GOVERNANCE-V2 §12` 另签完整 NEW TASK AUTHORITY。
- 能力与证据指针：`docs/68-ACQ1-CAPABILITY-MANIFEST.md`（I1 能力清单）、`docs/69`（阶段报告）、`docs/70`（交付包说明书）、`docs/71`（收口计划）。

## 历史操作记录（以下不提供 live authority）

- PR #83 已 MERGED；精确 merge/main `673f4b8f30bd1f7229510a1db8872e680b5a1fee`。CONTROL_EPOCH=GOV-2.1 已生效。下面 FT-GOV-V2.1 候选记录已结束，仅作历史，不表示 epoch 仍待生效。
- 当前操作：总控只修订现有 [GOVERNANCE-V2 §11.6](GOVERNANCE-V2.md#116-r3-host-binding-最小补充合同2026-10-02控制-pr-合并后可申请新-lease)、本 gate 与看板，冻结 H1 最小 offline adapter 边界；此控制 PR 合并前不实施 H1。
- 只读审查已结束：Backend Preflight-02 部分报告因错误依赖路径停点。总控通过 Git tree 核实真实依赖为 `contract_v2.py → dnr_offline/contract.py`；这是路径核验错误，不是新增 R3 安全缺陷，不再重复整次 preflight。
- 来源资产 `a3980682b7fd306f130250978c3ef6dade224233` 仅供新 lease 审查/复用；旧 scope REVOKED。Backend 当前 STOPPED，fetch-only lease 与 preflight lease 均已结束。旧 dirty/untracked 全保留。
- R3 BLOCKED、Browser dynamic disabled / runtime NO_GO；R4/R5、正式 WP3/WP4+、PLUGIN、Frontend、Integration、Release 未准入。静态 DAG 不被 Browser 自动 veto，但仍需独立实际依赖准入。
- 当前验收：仅三文档差异、链接/边界一致性、v2/v2.1 回归、独立 P0/P1=0。不得跑 PR #82 或业务测试、Browser/Docker/CDP/session/install，不改业务/API/Schema/production config。
- 合并后总控可另签 H1（一次 offline increment + 一次 targeted verification），未绑定 native/tunnel ports 仍明确 NO_GO；失败 REPORT+STOP，不自续 repair/commit/push/下一增量。H2 和真实执行须另签许可。

```text
Task ID: FT-GOV21-R3-HOST-CONTRACT-01
Control Epoch: GOV-2.1
Parent Goal: Freeze minimum host binding needed for R3
Exact Baseline: 673f4b8f30bd1f7229510a1db8872e680b5a1fee
Exact Branch: codex/r3-host-binding-contract
Authorized Operation: One three-document contract increment and one document validation
Allowed Files: docs/GOVERNANCE-V2.md, docs/CURRENT-GATE.md, docs/02-DELIVERY-BOARD.md
Allowed Tools: apply_patch; read-only Git/file/link checks
Forbidden Operations: business/test/install/runtime/network publication/merge/old task continuation
Max Iterations: 1
Hard Deadline: 15 minutes from operation start
Expected Evidence: Scope/link checks, H1 boundary and unchanged safety invariant, no drift
Stop Condition: One validation result or failure/deadline/revocation; no implicit commit
Next Authority Owner: FlowTracer controller
```

## 历史：FT-GOV-V2.1 修订候选与已完成操作

## 当前最高控制：FT-GOV-V2.1

- 来源基准：`main@335c6a2da418b2d3b2c4c70b59ee3d20d08c08cb`，包含 PR #80 Governance v2、#81 composite contract、#82 offline harness。合并后的 main 是该基准后代，不要求等于父基准。
- `CONTROL_INTERRUPT=ACTIVE` 已于总控收到指令即时生效，不等 PR。仓库 epoch：GOV-2.1 **待本修订 exact-head 合并**；下面旧许可无后续执行权。唯一核心治理为 [GOVERNANCE-V2 §12](GOVERNANCE-V2.md#12-governance-v21--live-authority--in-flight-task-control)。
- 本阶段唯一范围：四份现有控制文档修订、独立治理 Review、控制 PR/精确合并；每一步另签有界操作 lease。不是旧工程 Goal 的恢复。
- Capability：R3 BLOCKED、Browser dynamic disabled / runtime NO_GO；Execution Authority：旧工程 NONE。原 Backend 与 GitHub 角色均 STOPPED、无活动命令，完整快照在 §12.5。Backend `a3980682b7fd306f130250978c3ef6dade224233` 仅是角色报告的中断前历史产物，未在本阶段验收/发布；不恢复收尾、测试或提交。
- 原始 dirty/untracked、历史失败与已消费 session 全保留；总控工作树既有 `backend/tests/test_error_paths.py` 删除改动及 `.r3-control/` 不纳入本 PR，不恢复/清除。
- PR #82 的离线证据按 evidence-once 引用，输入未变不重跑；OFFLINE HARNESS READY 不等于 R3 PASS。PR #79 DO NOT MERGE，须另签针对 v2/v2.1/current main 的重评或 supersede/close。
- 禁止业务/API/Schema/migration、Browser/Docker/session、依赖安装、production config、R4/R5、正式 WP3/WP4+、PLUGIN/Frontend/Integration/Release。v2 Risk/DAG/A1/安全 invariant 保持；本修订不授权下游。
- 必读：本文件、GOVERNANCE-V2、00-PROJECT-CONTROL、02-DELIVERY-BOARD 的本次范围；不回读整套历史。
- 验收：仅四文档 diff/链接/合同一致性、v2 回归、epoch/lease/checkpoint/revocation/等待/循环/状态分离、FT-GOV-002；独立 P0/P1=0。不重复任何业务或 PR #82 测试，不运行 runtime。
- 合并后声明 CONTROL_EPOCH=GOV-2.1 并 STOP。不自动恢复旧 Backend；未来任何工程须完整 NEW TASK AUTHORITY，泛称“继续”不是 operation lease。

### 当前修订操作 record（候选；后续步骤须重新签发）

```text
Task ID: FT-GOV-V2.1-DOC-01
Control Epoch: GOV-2.1 operational amendment; repository activation pending merge
Parent Goal: Record FT-GOV-V2.1 without restoring engineering authority
Exact Baseline: 335c6a2da418b2d3b2c4c70b59ee3d20d08c08cb
Exact Branch: codex/governance-v2-1
Authorized Operation: One governance-only documentation increment and one targeted document validation
Allowed Files: docs/GOVERNANCE-V2.md, docs/CURRENT-GATE.md, docs/00-PROJECT-CONTROL.md, docs/02-DELIVERY-BOARD.md
Allowed Tools: apply_patch; read-only Git/file/link checks
Forbidden Operations: business edits, tests, install, runtime, push/PR/merge, old task continuation
Max Iterations: 1
Hard Deadline: 15 minutes from this operation start; no self-extension
Expected Evidence: Four-document diff, v2 invariant preservation, scope/link checks, task snapshots
Stop Condition: Document check result or failure/deadline/revocation; no automatic repair/commit
Next Authority Owner: FlowTracer controller, under FT-GOV-V2.1 user package
```

已完成中断快照 lease（两个原角色，单次只读、15 minutes、无 runtime/测试/提交）已 EXPIRED。新 Review/commit/publication/merge record 必须绑定届时精确 SHA，不由上述 Parent Goal 自动推导。

## 历史控制记录（以下准入/下一步文字不再提供 live authority）

## 现行治理切换（本控制 PR 合并后生效）

### R3 composite 离线实施包（本次控制 PR 合并后才准入）

- 来源：`main@35ae356d292c5300f39f99f0726c829ad270b744`，Governance v2 PR #80 已合并；原来源 SHA 保留作历史，不要求 HEAD 与来源相等。
- 唯一新范围：[GOVERNANCE-V2 §11](GOVERNANCE-V2.md#11-r3-composite-最小合同与离线实施包2026-10-01) 的 `composite_v1/` 十文件离线 harness/validator/fixture；不继续库存页 patch loop，不准入真实 Browser/Docker/session。
- Backend 已只读确认 WP4 静态路径依赖 WP1/WP2；仍缺降级/预算/Circuit/Throttle 等精确规则，本包不准入 Router 或削减其产品目标。
- 原 Backend 在唯一 worktree 保留 Plan A 四份 dirty 与历史资产，只提交新白名单。离线通过只能为 `OFFLINE HARNESS READY`，不能称 R3 PASS。
- 本阶段验收：三现有 docs 白名单、diff/link/契约一致性、独立 Review P0/P1=0；不跑业务测试/Browser/Docker。合并后总控另发精确 Backend 离线任务，后续真实执行须审核实际 candidate/hash/plan 后另签唯一许可。
- PR #79 已按 Governance v2 重评为 README-only@`0217c8ea06ea0888e0c699816b6d8e3c368af7a1`，总控静态复核通过，仍 OPEN，等待人类直接合并确认；不追认合并。

- 阶段：Governance v2 CONTROL REBASELINE — GOVERNANCE ONLY；唯一核心治理文档 [GOVERNANCE-V2](GOVERNANCE-V2.md)。来源 `main@31fa751a3c074111f14b640a727a972eb996ef05`（PR #78）；合并后的 main 应为来源后代，不要求相等。
- BE-1..BE-8、AG-0..AG-6、ACQ WP-1/WP-2 完成；R1/R1C/R1D/R1E/R2C 已验收证据原样保留。PR #77/#78 是离线候选交付，不是 R3 PASS。
- R3：**BLOCKED / GOVERNANCE_REBASELINE_REQUIRED**；新的合同只验真实 DynamicFetcher application policy、无网络旁路与可信关联。现有 source_observation/inventory 失败不证明旁路，也不证明成功：inventory 完美性债务 P2；安全归因尚未建立为 P1 未决。
- Browser dynamic **disabled**；R4/R5、正式 WP-3 未准入。已有执行硬化/资源上限/监督、NetworkPolicy 和受控出口不降低。
- WP-4..WP-8、PLUGIN-1、Frontend、Integration、Release **仍未准入**。Browser 不再自动 veto 静态能力；合并后仅可申请 Static/Native Capability DAG 的 Dependency Re-evaluation，须另签实际工作包。
- 当前 Backend Plan A 停点并保留未提交资产；上节 composite 离线包合并前不实施。本阶段不执行任何 Browser/Docker/session，不继续库存页 patch loop。已消费的 session01/02/03 历史事实与标记保留，不追认成功或重试。
- PR #79 重评情况以上节为准；本控制包同步看板 Governance v2 DAG，不让旧串行行反向覆盖现行准入。
- 必读：本文件、GOVERNANCE-V2、00 总控基线、22 Master、29 Work Packages；历史 37/41/49 只在审计时引用，不回读全套。
- 本阶段验收：8 个指定 Markdown 文件白名单；历史 37/41/49 去除新增标记后与来源 Git blob 原文一致；R1..R2C 资产无 diff；相对链接/安全约束/准入/架构一致性、git diff --check；独立治理 Review P0/P1=0。不重复业务全量测试，不运行 Docker。
- 原 Governance v2 包合并后的 STOP 已执行；本次合并后仅可由总控签发上节离线实施包。不得自动执行 R3 session 或 WP-4。

## 历史阶段与证据（以下旧许可/串行语义已由上节 supersede）

- 本控制提交的来源基准：`main@c584fd06ff136025dc6a0aba9815291b16682aa2`；该基准包含 R2C-A4 受控出口证据 PR #68。控制 PR 合并后的 `main` 应为此提交的后代，不要求与父基准 SHA 相等。
- 已完成：ACQ-1 Preflight、Contract Freeze、WP-1（ACQ-1A + H0）与 WP-2（ACQ-1B + D-static）均已通过总控验收并合并。
- WP-2 验收：实现提交 `90c4645c95a96608a35565ca90b022dfb2f1f1a7`，merge commit `70a3b0462e9a9303ddb3f5be56c84ed5d2fead40`；286 passed、coverage 87.61%、P0/P1/P2 = 0/0/0。归档见 `docs/36-ACQ1-WP2-ACCEPTANCE.md`。
- Architecture Governance：AG-0 至 AG-6 全部完成，Architecture Governance Pass 整体结项。AG-5 Conditional Memory Policy 以 no-code characterization audit 收口；AG-6 在 `main@81a9739c986eaef50fa43ba9a7d32689bceddf03` 完成 no-code Final Compatibility Gate 并判定 PASS，无新增代码或 commit。
- AG-5 结论：Memory ownership/bookmark/filter、cosine distance、稳定排序与 top-k 保持在 PostgreSQL/pgvector SQL；六位量化不单独抽取；当前没有 retention contract，不新增或虚构 retention。
- AG-6 证据：Architecture `existing=130 / introduced=0 / resolved=27 / P0=0 / P1=114 / P2=16`，`EX-001/EX-003/EX-004/EX-007` 全部关闭；356 passed、coverage 88.12%（不低于 87.61%）；OpenAPI check、Alembic 空库 upgrade/downgrade/re-upgrade、current `20260830_0004`、alembic check、Compose、Ruff 与 Mypy 均通过，无 API/Schema/ACQ 漂移。
- Preflight 结论：`docs/38-ACQ1-WP3-PREFLIGHT-ADMISSION.md` 准入的证据 Spike 已执行并按 fail-closed 判定 **BLOCKED**；执行分支 `feat/acq-1b-browser-preflight-spike` 的 base/HEAD 均为 `b7cd7b1ce6e1d36bd7607c75f9883367cce6e623`，工作树 clean，无代码、commit、push 或 PR，候选镜像与全部临时资源已精确删除。
- 阻塞缺陷：P0×1（download 默认拒绝无双层证明）；P1×5（hang/回收、DynamicFetcher runtime、双 worker queue 隔离、durable lock/SBOM/双构建、Chromium/engine license）；P2×2（仅 `n=1` 资源样本、BuildKit cache 归属不精确）。完整记录见 `docs/40-ACQ1-WP3-PREFLIGHT-BLOCKED-REPORT.md`。
- R1 结论：PR #54 已通过独立复审与 Backend CI 并合并；R1 P0/P1/P2=`0/0/0`。两次锁定 no-cache 构建、规范化文件系统身份、SBOM/license、301-entry tree、非 root/read-only/network-none 离线运行与精确清理证据完整。
- R2 结论：PR #56 已通过独立复审与 Backend CI 并合并；R2 P0/P1/P2=`0/0/0`。Browser 与独立 control-client 对相同 host-gateway endpoint 的相反可达性、A/AAAA DNS canary、受控 CONNECT/redirect/rebinding 策略、真实运行态硬化与精确清理均形成机器可验证证据。
- R3 首次执行结论：**BLOCKED**，P0/P1/P2=`0/1/0`。R1 锁定镜像只包含 Chromium Headless Shell，而 Scrapling DynamicFetcher 实际要求完整 Chromium executable；DynamicFetcher 未能启动，矩阵未继续，失败项目与临时资源已精确清理。
- R1C 结论：PR #60 已通过独立复审与 Backend CI 并合并；候选提交 `787a0df0548e05431fa60426f48f239ba7195465`，merge commit `df0c3512080f384dbd6c820d7627cbe721e37422`，P0/P1/P2=`0/0/0`。完整 Chromium、双 no-cache 构建、规范化身份、SBOM/license、UID 10001 DynamicFetcher 与受控 Crashpad 目录证据完整。
- R2C 首次执行结论：**BLOCKED**，P0/P1/P2=`0/1/0`。Chrome、browser tree、Debian inventory、SBOM/license 均匹配 R1C，但 full-root normalized identity 无法由合并后的权威来源重建；网络矩阵未启动，临时对象已精确清理。
- R1D 结论：PR #63 已通过独立复审、Backend CI 并合并；candidate `a804a371ec99615278c2cd60f442dc58299ff7c5`，merge commit `db9c4fad0ca826b472d18d85c69db53848cfcd94`，P0/P1/P2=`0/0/0`。两次 no-cache 构建的 Runtime Identity v2 逐路径 manifest 字节一致，完整 Chromium、SBOM/license、UID 10001 DynamicFetcher、Crashpad、历史资产保护及精确清理证据完整。
- R2C-A2 结论：**BLOCKED**，P0/P1/P2=`0/1/0`。网络矩阵前的 Runtime Identity v2 门禁发现 10,340 个路径中仅 `/etc/shadow` 字节跨日漂移；Chrome、browser tree、Debian、SBOM/license 与 runtime/audit 边界均匹配，网络矩阵未启动，临时对象已精确清理。
- R1E 结论：PR #66 已通过独立复审、Backend CI 并合并；最终 head `3636dd261ece31c046406aa7b2279f6f7bd7dad8`，merge commit `cac5b4e1908801ff4ed1a96c2388a0a71653d6ee`，P0/P1/P2=`0/0/0`。`/etc/shadow` 保持完整纳入 identity，锁定非密码账户 `sp_lstchg=0`；双 manifest authority 为 payload SHA `5f4cf5acdf06a86f9b8907375f6f8f239ecf18152762b889f1e254b01e447e3b`、manifest SHA `f8d8bd0b64dfac53e244b00f29fbc9f18ed44b94491323b3f49ba2af191912e8`。
- R2C 结论：PR #68 已通过独立复审、Backend CI 并合并；最终 head `e4f636bd88ba8c298ca7b1ec1e074b5bcd1351e1`，merge commit `c584fd06ff136025dc6a0aba9815291b16682aa2`，P0/P1/P2=`0/0/0`。A4 双 no-cache 构建与 R1E 逐路径 Runtime Identity v2 完全一致；受控出口、旁路拒绝、真实 DynamicFetcher 和精确清理证据均通过。旧 A3 BLOCKED 证据保持不变。
- 当前停点：仅 R3 Application interception matrix 待本控制 PR 合并后重新准入；R4-R5 与 WP-3 正式实现继续暂停。见 `docs/49-ACQ1-WP3-R3-REACTIVATION.md`。
- R3 最新增量控制事项（2026-09-28）：Backend 报告 Worker WebSocket 的原生 CDP 候选阴性；R3 仍 **BLOCKED**。最小 DNR 能力控制包 PR #70 已 Review/合并，control `a95282098ccac934cd17577fbd5de22b6eb8d0f8`、merge `e55dd6deb7fd956b4fba5824331ebda1f0e8d7bd`；见 `docs/50-R3-WORKER-WS-NATIVE-GATE-PROPOSAL.md` 与 `docs/51-R3-DNR-CAPABILITY-EXPERIMENT.md`。收到总控精确启动基准后，仅可执行隔离离线产物/定向测试，真实 session 仍须总控确认执行输入 hash 后另行许可。不得把该实验或其阳性结果视为正式 R3 PASS；R4 及全部下游准入不变。
- 未准入：WP-3 正式实现及 WP-4..WP-8；生产 Browser、Router、Discovery、Change、Opportunity；PLUGIN-1；Frontend、Integration 与 Release。
- 2026-09-29 离线来源裁定：PR #74 已合并，merge commit `ff70c198acb74b764435485611ec67484bcc7262`；`docs/52-R3-RUNTIME-SOURCE-ADDENDUM.md` 的离线来源裁定已生效。修正 DNR debug request 时间假设，明确 v2 回执观察时间、有限只读 inventory 候选与编排闭包；不签发真实 Browser/Docker/session 许可，R3 仍 **BLOCKED**、runtime **NO-GO**，R4/R5 未准入。
- 2026-09-29 离线候选交付：PR #75 已通过独立离线 Review（P0/P1/P2=`0/0/0`）与 Backend CI 并合并；最终 head `59d3d2ffb9704fa3f548c69622abb3c2f6dd67f2`，merge commit `a0d917f088c5010a307533818beb0af54ffe76e8`。23 项静态输入哈希匹配 Git blob，原始输入清单 SHA256=`3bd0bea662db53716d5cc355ac96a56b8ae50270ab2e9cd58e0f67478e6917e7`。这仅是离线候选交付，不是原生 DNR/R3 PASS；独立 controller authority 尚未签发，实际入口仍禁用，R3 **BLOCKED**、runtime **NO-GO**、R4/R5 未准入状态不变。
- 内部来源预检：本控制 PR 合并后，`docs/53-R3-INTERNAL-SOURCE-PROBE.md` 只准离线接线；实际 session 须由总控另签精确许可。不得启动 Browser/Docker、访问采集目标或四臂验证；R3 仍 **BLOCKED**、runtime **NO-GO**，R4/R5 未准入。

WP-3 的阶段名称、顺序、允许范围和安全原则已由 `docs/22-ACQ1-MASTER-BASELINE.md`、`docs/23-ACQ1-ACQUISITION-CONTRACT.md`、ADR-023/026 与 `docs/29-ACQ1-WORK-PACKAGES.md` 冻结。R1C/R1D/R1E/R2C 已提供 Browser runtime、供应链身份和受控出口实证；应用拦截、强制回收/资源样本及双 worker 隔离仍分别等待 R3-R5，不得以已有证据推定通过。

历史下一步（不再是当前许可）：旧控制包曾要求 R3→R4→R5 串行证据，之后独立 WP-3 Admission。现行下一步仅依本文件顶部与 GOVERNANCE-V2，当前不运行任何 session 或下游工作包。
