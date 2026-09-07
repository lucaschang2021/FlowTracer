# FlowTracer 当前阶段闸门

更新时间：2026-09-07。

- 当前稳定基准：`main@a9545ae51cce8824769ca73d08e46d91b4dbec9c`；该基准包含 WP-2 验收归档 PR #40、Architecture Governance AG-0 PR #42/#43、AG-1 PR #44、AG-2 PR #45、AG-3 PR #47、AG-4 PR #49 与 AG-5 激活 PR #50。
- 已完成：ACQ-1 Preflight、Contract Freeze、WP-1（ACQ-1A + H0）与 WP-2（ACQ-1B + D-static）均已通过总控验收并合并。
- WP-2 验收：实现提交 `90c4645c95a96608a35565ca90b022dfb2f1f1a7`，merge commit `70a3b0462e9a9303ddb3f5be56c84ed5d2fead40`；286 passed、coverage 87.61%、P0/P1/P2 = 0/0/0。归档见 `docs/36-ACQ1-WP2-ACCEPTANCE.md`。
- Architecture Governance：AG-0 至 AG-4 均已验收并合并；AG-5 Conditional Memory Policy 已完成只读 characterization audit，以 no-code 结论收口，无代码、commit 或测试变更，`introduced P0/P1/P2=0`。
- AG-5 结论：Memory ownership/bookmark/filter、cosine distance、稳定排序与 top-k 保持在 PostgreSQL/pgvector SQL；六位量化不单独抽取；当前没有 retention contract，不新增或虚构 retention。
- 当前阶段：AG-6 Final Compatibility Gate 已正式准入，目标分支为 `feat/architecture-governance`。最终候选必须解决并验证 `EX-001/EX-003/EX-004/EX-007`，并比较 OpenAPI、Alembic head/Schema、ACQ contract、测试计数/coverage 与 Architecture `existing/introduced/resolved`；只在最终待合并提交执行一次完整门禁。
- 未准入：ACQ-1 WP-3..WP-8；Browser、Router、Discovery、Change、Opportunity；PLUGIN-1；Frontend、Integration 与 Release。ACQ-1 WP-3 仍处于架构/契约准备阻塞，Backend 不得进入 Browser 实现。

WP-3 的阶段名称、顺序、允许范围和安全原则已由 `docs/22-ACQ1-MASTER-BASELINE.md`、`docs/23-ACQ1-ACQUISITION-CONTRACT.md`、ADR-023/026 与 `docs/29-ACQ1-WORK-PACKAGES.md` 冻结。但其实现前硬门禁要求的 Browser package/revision、系统依赖、独立镜像 digest、受控 egress 方案和容器资源精确限值尚无可复现实证；不得由 Backend 或总控凭空填写。

下一步：Backend 在 `feat/architecture-governance` 完成 AG-6 Final Compatibility Gate，提交最终 Architecture/兼容性/回滚证据并停点；AG-6 验收前不得启动任何下游阶段。ACQ-1 WP-3 继续按 `docs/37-ACQ1-WP3-READINESS-BLOCKER.md` 补齐兼容性与隔离证据，并由新的控制文档 PR 冻结精确值、签发 WP-3 Admission；该 PR 合并前，WP-3 不生效，不派发 Backend，不进入 Browser 实现。
