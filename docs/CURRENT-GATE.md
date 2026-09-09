# FlowTracer 当前阶段闸门

更新时间：2026-09-09。

- 当前稳定基准：`main@a0d30140c8bdb6665b0833f4d60defadce9c9166`；该基准包含 WP-3 Remediation Evidence 控制 PR #53、R1 证据 PR #54、R2 证据 PR #56 与 R3 激活 PR #57。
- 已完成：ACQ-1 Preflight、Contract Freeze、WP-1（ACQ-1A + H0）与 WP-2（ACQ-1B + D-static）均已通过总控验收并合并。
- WP-2 验收：实现提交 `90c4645c95a96608a35565ca90b022dfb2f1f1a7`，merge commit `70a3b0462e9a9303ddb3f5be56c84ed5d2fead40`；286 passed、coverage 87.61%、P0/P1/P2 = 0/0/0。归档见 `docs/36-ACQ1-WP2-ACCEPTANCE.md`。
- Architecture Governance：AG-0 至 AG-6 全部完成，Architecture Governance Pass 整体结项。AG-5 Conditional Memory Policy 以 no-code characterization audit 收口；AG-6 在 `main@81a9739c986eaef50fa43ba9a7d32689bceddf03` 完成 no-code Final Compatibility Gate 并判定 PASS，无新增代码或 commit。
- AG-5 结论：Memory ownership/bookmark/filter、cosine distance、稳定排序与 top-k 保持在 PostgreSQL/pgvector SQL；六位量化不单独抽取；当前没有 retention contract，不新增或虚构 retention。
- AG-6 证据：Architecture `existing=130 / introduced=0 / resolved=27 / P0=0 / P1=114 / P2=16`，`EX-001/EX-003/EX-004/EX-007` 全部关闭；356 passed、coverage 88.12%（不低于 87.61%）；OpenAPI check、Alembic 空库 upgrade/downgrade/re-upgrade、current `20260830_0004`、alembic check、Compose、Ruff 与 Mypy 均通过，无 API/Schema/ACQ 漂移。
- Preflight 结论：`docs/38-ACQ1-WP3-PREFLIGHT-ADMISSION.md` 准入的证据 Spike 已执行并按 fail-closed 判定 **BLOCKED**；执行分支 `feat/acq-1b-browser-preflight-spike` 的 base/HEAD 均为 `b7cd7b1ce6e1d36bd7607c75f9883367cce6e623`，工作树 clean，无代码、commit、push 或 PR，候选镜像与全部临时资源已精确删除。
- 阻塞缺陷：P0×1（download 默认拒绝无双层证明）；P1×5（hang/回收、DynamicFetcher runtime、双 worker queue 隔离、durable lock/SBOM/双构建、Chromium/engine license）；P2×2（仅 `n=1` 资源样本、BuildKit cache 归属不精确）。完整记录见 `docs/40-ACQ1-WP3-PREFLIGHT-BLOCKED-REPORT.md`。
- R1 结论：PR #54 已通过独立复审与 Backend CI 并合并；R1 P0/P1/P2=`0/0/0`。两次锁定 no-cache 构建、规范化文件系统身份、SBOM/license、301-entry tree、非 root/read-only/network-none 离线运行与精确清理证据完整。
- R2 结论：PR #56 已通过独立复审与 Backend CI 并合并；R2 P0/P1/P2=`0/0/0`。Browser 与独立 control-client 对相同 host-gateway endpoint 的相反可达性、A/AAAA DNS canary、受控 CONNECT/redirect/rebinding 策略、真实运行态硬化与精确清理均形成机器可验证证据。
- 当前停点：WP-3 正式实现继续 BLOCKED。仅准入 R3 Application interception matrix 证据阶段；R4-R5 必须继续等待各自上游 PASS，见 `docs/44-ACQ1-WP3-R3-ACTIVATION.md`。
- 未准入：WP-3 正式实现及 WP-4..WP-8；生产 Browser、Router、Discovery、Change、Opportunity；PLUGIN-1；Frontend、Integration 与 Release。

WP-3 的阶段名称、顺序、允许范围和安全原则已由 `docs/22-ACQ1-MASTER-BASELINE.md`、`docs/23-ACQ1-ACQUISITION-CONTRACT.md`、ADR-023/026 与 `docs/29-ACQ1-WORK-PACKAGES.md` 冻结。但其实现前硬门禁要求的 Browser package/revision、系统依赖、独立镜像 digest、受控 egress 方案和容器资源精确限值尚无可复现实证；不得由 Backend 或总控凭空填写。

下一步：在新任务中执行 R3，对 navigation、redirect、iframe、script、XHR/fetch、WebSocket、download、popup、service worker register/update/fetch 逐项形成应用拦截与 R2 网络层双层离线证据。任一 hang、遗漏、旁路或单层证明即 STOP；R3 经独立复审并合并前不得进入 R4。R1→R5 全部通过也只可申请独立总控复核；仍须另提 WP-3 Contract Addendum + 正式 Admission 控制 PR 并合并后，才可进入正式实现。
