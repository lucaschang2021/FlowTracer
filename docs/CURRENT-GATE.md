# FlowTracer 当前阶段闸门

更新时间：2026-09-05。

- 当前稳定基准：`main@3bc456e6b7f6e4f8a6a545276d255646c1db3c73`；该基准包含 WP-2 验收归档 PR #40、Architecture Governance AG-0 PR #42/#43、AG-1 PR #44 与 AG-2 PR #45。
- 已完成：ACQ-1 Preflight、Contract Freeze、WP-1（ACQ-1A + H0）与 WP-2（ACQ-1B + D-static）均已通过总控验收并合并。
- WP-2 验收：实现提交 `90c4645c95a96608a35565ca90b022dfb2f1f1a7`，merge commit `70a3b0462e9a9303ddb3f5be56c84ed5d2fead40`；286 passed、coverage 87.61%、P0/P1/P2 = 0/0/0。归档见 `docs/36-ACQ1-WP2-ACCEPTANCE.md`。
- Architecture Governance：AG-0 合同冻结与校准、AG-1 Executable Gate Foundation、AG-2 Intelligence 纯领域策略均已合并；AG-3 Acquisition Ports 与最小 DI 为当前阶段，目标分支 `feat/architecture-governance`，候选提交 `ce26640e3c2f994c8036b18a2c2b984dee045c53` 待创建 PR、Review 与验收合并，不得描述为已进入 `main`。
- 当前停点：AG-3 候选提交等待 PR 与总控验收；ACQ-1 WP-3（ACQ-1B Dynamic + H-browser）仍处于架构/契约准备阻塞，尚未准入，Backend 不得进入 Browser 实现。
- 未准入：Architecture Governance AG-4..AG-6；ACQ-1 WP-3..WP-8；Browser、Router、Discovery、Change、Opportunity；PLUGIN-1；Frontend、Integration 与 Release。

WP-3 的阶段名称、顺序、允许范围和安全原则已由 `docs/22-ACQ1-MASTER-BASELINE.md`、`docs/23-ACQ1-ACQUISITION-CONTRACT.md`、ADR-023/026 与 `docs/29-ACQ1-WORK-PACKAGES.md` 冻结。但其实现前硬门禁要求的 Browser package/revision、系统依赖、独立镜像 digest、受控 egress 方案和容器资源精确限值尚无可复现实证；不得由 Backend 或总控凭空填写。

下一步：先为 AG-3 候选提交创建独立 PR，完成架构门禁、兼容性与回归验收；合并前不得进入 AG-4。ACQ-1 WP-3 继续按 `docs/37-ACQ1-WP3-READINESS-BLOCKER.md` 补齐兼容性与隔离证据，并由新的控制文档 PR 冻结精确值、签发 WP-3 Admission；该 PR 合并前，WP-3 不生效，不派发 Backend，不进入 Browser 实现。
