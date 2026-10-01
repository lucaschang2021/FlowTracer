# FlowTracer 当前阶段闸门

更新时间：2026-10-01。

## 现行治理切换（本控制 PR 合并后生效）

- 阶段：Governance v2 CONTROL REBASELINE — GOVERNANCE ONLY；唯一核心治理文档 [GOVERNANCE-V2](GOVERNANCE-V2.md)。来源 `main@31fa751a3c074111f14b640a727a972eb996ef05`（PR #78）；合并后的 main 应为来源后代，不要求相等。
- BE-1..BE-8、AG-0..AG-6、ACQ WP-1/WP-2 完成；R1/R1C/R1D/R1E/R2C 已验收证据原样保留。PR #77/#78 是离线候选交付，不是 R3 PASS。
- R3：**BLOCKED / GOVERNANCE_REBASELINE_REQUIRED**；新的合同只验真实 DynamicFetcher application policy、无网络旁路与可信关联。现有 source_observation/inventory 失败不证明旁路，也不证明成功：inventory 完美性债务 P2；安全归因尚未建立为 P1 未决。
- Browser dynamic **disabled**；R4/R5、正式 WP-3 未准入。已有执行硬化/资源上限/监督、NetworkPolicy 和受控出口不降低。
- WP-4..WP-8、PLUGIN-1、Frontend、Integration、Release **仍未准入**。Browser 不再自动 veto 静态能力；合并后仅可申请 Static/Native Capability DAG 的 Dependency Re-evaluation，须另签实际工作包。
- 当前 Backend R3 offline patch 停点并保留未提交资产；本治理阶段不执行任何 Browser/Docker/session，不继续 patch loop。任务前已消费的 session01/02/03 历史事实与标记保留，不追认成功或重试。
- PR #79 暂不合并；治理合并后重评 README，过时则 supersede。交付看板旧串行行作为历史记录，本节及 GOVERNANCE-V2 是现行准入语义，不得从旧行反推许可。
- 必读：本文件、GOVERNANCE-V2、00 总控基线、22 Master、29 Work Packages；历史 37/41/49 只在审计时引用，不回读全套。
- 本阶段验收：8 个指定 Markdown 文件白名单；历史 37/41/49 去除新增标记后与来源 Git blob 原文一致；R1..R2C 资产无 diff；相对链接/安全约束/准入/架构一致性、git diff --check；独立治理 Review P0/P1=0。不重复业务全量测试，不运行 Docker。
- 合并后 **STOP**；不得自动执行 R3 或 WP-4。下一步：总控另行依赖重评与精确 Admission。

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
