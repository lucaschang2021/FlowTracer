# FlowTracer ACQ-1 WP-3 R3 Activation

状态：Accepted（仅 R3 remediation evidence）

稳定基准：`main@c5799082ba8e0ae5edf8ddfb861e24de784cdf93`

执行角色：Backend / Architecture

固定工作目录：`D:\FlowTracer-wt\backend`

目标分支：`feat/acq-1b-browser-remediation-evidence`

## 1. 准入结论

R2 已由 PR #56 验收合并，P0/P1/P2=`0/0/0`。依据 `docs/41-ACQ1-WP3-REMEDIATION-EVIDENCE-ADMISSION.md` 的顺序门禁，本文件仅激活 R3 Application interception matrix 证据阶段。

本准入不包含 R4-R5、WP-3 正式实现、默认 API/worker/Compose、Router、RawItem Pipeline、Schema/migration、公开 API、Frontend、Integration、Release 或 PLUGIN-1。

## 2. 允许范围

- 仅在 `backend/experiments/browser-r3/` 创建可丢弃的 Browser/fixture/proxy harness、策略与验证脚本、证据附件；同步填写 `docs/42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md` 的 R3 区域。
- 复用 R1 锁定 Browser image 与 R2 受控 egress 设计，不放宽 NetworkPolicy、容器权限或离线边界。
- 仅使用本地 fixture、保留地址和合成 DNS；禁止真实目标站点、公网依赖、凭据、登录态和访问控制绕过。
- 所有容器、network、volume、image/cache 与进程必须唯一命名、可归属并精确清理；禁止 global prune。

## 3. 必须证明

对下列每个请求面分别记录 fixture、预期、实际、应用 event/hook、proxy/网络观察、policy/scope/budget 与 fail-closed 结果：

1. navigation；
2. redirect；
3. iframe；
4. script；
5. XHR/fetch；
6. WebSocket；
7. download；
8. popup；
9. service worker register/update/fetch。

每个请求面必须同时具有应用层拦截与 R2 网络层结果。WebSocket 与 download 必须默认拒绝，且请求不得抵达 proxy 的允许转发路径。任一请求面出现 hang、遗漏、旁路、无确定性归因或只有单层证明，R3 即 BLOCKED。

DynamicFetcher 必须在隔离 harness 中完成实际启动、页面渲染、确定性终止和安全失败输出；本阶段不得接入业务 Router、RawItem writer 或默认 Celery worker。

## 4. 验收与停点

- 将完整命令、exit code、矩阵结果、事件/网络证据、创建对象与清理结果写入 R3 证据目录和 `docs/42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md`。
- 验证器必须机器拒绝缺失请求面、单层证据、WebSocket/download 放行、hang/timeout 冒充成功、证据计数或身份不一致。
- 任一失败立即 STOP；不得用 mock、配置审阅或后续 R4/R5 结果补齐 R3。
- 通过时唯一允许结论为 `R3 PASS — READY FOR INDEPENDENT REVIEW`；不得自行进入 R4、commit、push、PR 或 merge。
- 总控独立复审并合并 R3 证据前，R4 不生效；WP-3 正式实现继续 BLOCKED。
