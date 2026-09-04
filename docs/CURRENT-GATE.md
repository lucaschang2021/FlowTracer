# FlowTracer 当前阶段闸门

更新时间：2026-09-04。

- 当前稳定基准：`main@f4b58c1ec0d20d075b98d5a9ca3d146d0b4deb56`；WP-2 实现 PR #39 与归档/Readiness PR #40 已合并。
- 已完成：ACQ-1 Preflight、Contract Freeze、WP-1（ACQ-1A + H0）与 WP-2（ACQ-1B + D-static）均已通过总控验收并合并。
- WP-2 验收：实现提交 `90c4645c95a96608a35565ca90b022dfb2f1f1a7`，merge commit `70a3b0462e9a9303ddb3f5be56c84ed5d2fead40`；286 passed、coverage 87.61%、P0/P1/P2 = 0/0/0。归档见 `docs/36-ACQ1-WP2-ACCEPTANCE.md`。
- 当前停点：ACQ-1 WP-3 Compatibility/Isolation Preflight 控制准入；本控制提交合并后只允许证据 Spike，WP-3 正式实现仍未准入。
- 实验准入：仅 `docs/38-ACQ1-WP3-PREFLIGHT-ADMISSION.md` 定义的固定 Backend worktree、新 Spike 分支、离线兼容性/隔离实验与 `docs/39-ACQ1-WP3-PREFLIGHT-EVIDENCE-PACKAGE.md`。
- 未准入：WP-3 正式实现及 WP-4..WP-8；生产 Browser、Router、Discovery、Change、Opportunity；PLUGIN-1；Frontend、Integration 与 Release。

WP-3 的阶段名称、顺序、允许范围和安全原则已由 `docs/22-ACQ1-MASTER-BASELINE.md`、`docs/23-ACQ1-ACQUISITION-CONTRACT.md`、ADR-023/026 与 `docs/29-ACQ1-WORK-PACKAGES.md` 冻结。但其实现前硬门禁要求的 Browser package/revision、系统依赖、独立镜像 digest、受控 egress 方案和容器资源精确限值尚无可复现实证；不得由 Backend 或总控凭空填写。

下一步：本控制提交合并后，按 `docs/38-ACQ1-WP3-PREFLIGHT-ADMISSION.md` 派发一次独立 Backend Spike，补齐 `docs/37-ACQ1-WP3-READINESS-BLOCKER.md` 所列证据。Spike 完成后 Backend 必须 STOP；总控另开任务独立审查，再另提 WP-3 Contract Addendum + 正式 Admission 控制 PR。任何阶段都不得把实验准入解释为 WP-3 实现准入。
