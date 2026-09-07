# FlowTracer 当前阶段闸门

更新时间：2026-09-07。

- 当前稳定基准：`main@81a9739c986eaef50fa43ba9a7d32689bceddf03`；该基准包含 WP-2 验收归档 PR #40、Architecture Governance AG-0 PR #42/#43、AG-1 PR #44、AG-2 PR #45、AG-3 PR #47、AG-4 PR #49、AG-5 激活 PR #50 与 AG-6 激活 PR #51。
- 已完成：ACQ-1 Preflight、Contract Freeze、WP-1（ACQ-1A + H0）与 WP-2（ACQ-1B + D-static）均已通过总控验收并合并。
- WP-2 验收：实现提交 `90c4645c95a96608a35565ca90b022dfb2f1f1a7`，merge commit `70a3b0462e9a9303ddb3f5be56c84ed5d2fead40`；286 passed、coverage 87.61%、P0/P1/P2 = 0/0/0。归档见 `docs/36-ACQ1-WP2-ACCEPTANCE.md`。
- Architecture Governance：AG-0 至 AG-6 全部完成，Architecture Governance Pass 整体结项。AG-5 Conditional Memory Policy 以 no-code characterization audit 收口；AG-6 在 `main@81a9739c986eaef50fa43ba9a7d32689bceddf03` 完成 no-code Final Compatibility Gate 并判定 PASS，无新增代码或 commit。
- AG-5 结论：Memory ownership/bookmark/filter、cosine distance、稳定排序与 top-k 保持在 PostgreSQL/pgvector SQL；六位量化不单独抽取；当前没有 retention contract，不新增或虚构 retention。
- AG-6 证据：Architecture `existing=130 / introduced=0 / resolved=27 / P0=0 / P1=114 / P2=16`，`EX-001/EX-003/EX-004/EX-007` 全部关闭；356 passed、coverage 88.12%（不低于 87.61%）；OpenAPI check、Alembic 空库 upgrade/downgrade/re-upgrade、current `20260830_0004`、alembic check、Compose、Ruff 与 Mypy 均通过，无 API/Schema/ACQ 漂移。
- 当前停点：恢复到 ACQ-1 WP-3 readiness/compatibility preflight。`docs/37-ACQ1-WP3-READINESS-BLOCKER.md` 仍为权威阻塞事实；Preflight 控制 PR #41 仍为 OPEN，尚未进入 `main`，其提案不得当作已生效准入，更不构成 WP-3 Browser 实现准入。
- 未准入：ACQ-1 WP-3..WP-8；Browser、Router、Discovery、Change、Opportunity；PLUGIN-1；Frontend、Integration 与 Release。ACQ-1 WP-3 仍处于架构/契约准备阻塞，Backend 不得进入 Browser 实现。

WP-3 的阶段名称、顺序、允许范围和安全原则已由 `docs/22-ACQ1-MASTER-BASELINE.md`、`docs/23-ACQ1-ACQUISITION-CONTRACT.md`、ADR-023/026 与 `docs/29-ACQ1-WORK-PACKAGES.md` 冻结。但其实现前硬门禁要求的 Browser package/revision、系统依赖、独立镜像 digest、受控 egress 方案和容器资源精确限值尚无可复现实证；不得由 Backend 或总控凭空填写。

下一步：只读复核并处理现有 WP-3 Preflight 控制 PR #41；即使 Preflight 后续获准，也仅允许按明确范围收集 readiness/compatibility 证据。WP-3 实现仍须基于实际证据形成新的 Contract Addendum/ADR 与独立 Admission PR，并在合并后才可准入。PLUGIN-1 继续排在 ACQ 全部完成之后；Frontend、Integration 与 Release 保持未准入。
