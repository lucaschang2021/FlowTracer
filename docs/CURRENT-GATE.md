# FlowTracer 当前阶段闸门

更新时间：2026-09-04。

- 当前稳定基准：`main@70a3b0462e9a9303ddb3f5be56c84ed5d2fead40`；WP-2 实现 PR #39 已合并。
- 已完成：ACQ-1 Preflight、Contract Freeze、WP-1（ACQ-1A + H0）与 WP-2（ACQ-1B + D-static）均已通过总控验收并合并。
- WP-2 验收：实现提交 `90c4645c95a96608a35565ca90b022dfb2f1f1a7`，merge commit `70a3b0462e9a9303ddb3f5be56c84ed5d2fead40`；286 passed、coverage 87.61%、P0/P1/P2 = 0/0/0。归档见 `docs/36-ACQ1-WP2-ACCEPTANCE.md`。
- 当前停点：ACQ-1 WP-3（ACQ-1B Dynamic + H-browser）架构/契约准备；WP-3 尚未准入，Backend 不得开工。
- 未准入：WP-3..WP-8；Browser、Router、Discovery、Change、Opportunity；PLUGIN-1；Frontend、Integration 与 Release。

WP-3 的阶段名称、顺序、允许范围和安全原则已由 `docs/22-ACQ1-MASTER-BASELINE.md`、`docs/23-ACQ1-ACQUISITION-CONTRACT.md`、ADR-023/026 与 `docs/29-ACQ1-WORK-PACKAGES.md` 冻结。但其实现前硬门禁要求的 Browser package/revision、系统依赖、独立镜像 digest、受控 egress 方案和容器资源精确限值尚无可复现实证；不得由 Backend 或总控凭空填写。

下一步：按 `docs/37-ACQ1-WP3-READINESS-BLOCKER.md` 补齐兼容性与隔离证据，并由新的控制文档 PR 冻结精确值、签发 WP-3 Admission。该 PR 合并前，WP-3 不生效，不派发 Backend，不进入 Browser 实现。
