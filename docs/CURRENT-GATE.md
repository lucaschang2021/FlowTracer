# FlowTracer 当前阶段闸门

更新时间：2026-09-06。

- 当前稳定基准：`main@f1494c7f843782523f728913e08774331ec8163f`；该基准包含 WP-2 验收归档 PR #40、Architecture Governance AG-0 PR #42/#43、AG-1 PR #44、AG-2 PR #45、AG-3 PR #47 与 AG-4 PR #49。
- 已完成：ACQ-1 Preflight、Contract Freeze、WP-1（ACQ-1A + H0）与 WP-2（ACQ-1B + D-static）均已通过总控验收并合并。
- WP-2 验收：实现提交 `90c4645c95a96608a35565ca90b022dfb2f1f1a7`，merge commit `70a3b0462e9a9303ddb3f5be56c84ed5d2fead40`；286 passed、coverage 87.61%、P0/P1/P2 = 0/0/0。归档见 `docs/36-ACQ1-WP2-ACCEPTANCE.md`。
- Architecture Governance：AG-0 至 AG-4 均已验收并合并。AG-4 候选 `78ddf49ed6ddf94204465cd16dd96163cb93d834` 由 PR #49 合并；验收证据为 Architecture Gate `existing=130 / introduced=0 / resolved=27 / P0=0`，Backend CI run `34029206838` SUCCESS。
- 当前阶段：AG-5 Conditional Memory Policy 已正式准入并处于审计进行中，目标分支为 `feat/architecture-governance`。只有 characterization 证据能把相似度 clamp、六位量化、稳定排序与 ownership/bookmark filter 表达为纯输入输出规则时，才抽取最小 ranking/filter policy；否则以“无需变更”的审计提交或无代码停点结束。
- AG-5 边界：SQL user authorization 与 pgvector distance 继续归 persistence 所有，不得为纯化把全量结果拉入 Python；当前没有 retention policy，禁止虚构、抽象或实现 retention。
- 未准入：Architecture Governance AG-6；ACQ-1 WP-3..WP-8；Browser、Router、Discovery、Change、Opportunity；PLUGIN-1；Frontend、Integration 与 Release。ACQ-1 WP-3 仍处于架构/契约准备阻塞，Backend 不得进入 Browser 实现。

WP-3 的阶段名称、顺序、允许范围和安全原则已由 `docs/22-ACQ1-MASTER-BASELINE.md`、`docs/23-ACQ1-ACQUISITION-CONTRACT.md`、ADR-023/026 与 `docs/29-ACQ1-WORK-PACKAGES.md` 冻结。但其实现前硬门禁要求的 Browser package/revision、系统依赖、独立镜像 digest、受控 egress 方案和容器资源精确限值尚无可复现实证；不得由 Backend 或总控凭空填写。

下一步：Backend 在 `feat/architecture-governance` 按条件式合同完成 AG-5 characterization 审计，仅在证据充分时抽取最小纯 policy，完成后提交独立验收并停点；验收合并前不得进入 AG-6。ACQ-1 WP-3 继续按 `docs/37-ACQ1-WP3-READINESS-BLOCKER.md` 补齐兼容性与隔离证据，并由新的控制文档 PR 冻结精确值、签发 WP-3 Admission；该 PR 合并前，WP-3 不生效，不派发 Backend，不进入 Browser 实现。
