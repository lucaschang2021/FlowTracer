# FlowTracer ACQ-1 WP-3 R2 Activation

状态：Accepted（仅 R2 remediation evidence）

稳定基准：`main@34364d0082e4ecdbe4331d77a21ef6d25c2fca8a`

执行角色：Backend / Architecture

固定工作目录：`D:\FlowTracer-wt\backend`

目标分支：`feat/acq-1b-browser-remediation-evidence`

## 1. 准入结论

R1 已由 PR #54 验收合并，P0/P1/P2=`0/0/0`。依据 `docs/41-ACQ1-WP3-REMEDIATION-EVIDENCE-ADMISSION.md` 的顺序门禁，本文件仅激活 R2 Production-shaped controlled egress proxy/namespace 证据阶段。

本准入不包含 R3-R5、WP-3 正式实现、默认 API/worker/Compose、Router、RawItem Pipeline、Schema/migration、公开 API、Frontend、Integration、Release 或 PLUGIN-1。

## 2. 允许范围

- 在 `backend/experiments/` 内创建可丢弃的 proxy/Browser/fixture harness、专用 Compose override、策略配置、验证脚本和证据。
- 复用 R1 锁定输入；若必须重建实验镜像，只能按 R1 锁定版本与 digest，并在长步骤前复核额度。
- 仅使用本地 fixture、保留地址与否定目标，不访问真实公网网站，不使用凭据或登录态。
- 所有容器、network、volume、image/cache 必须唯一命名、可归属并精确清理；禁止 global prune。

## 3. 必须证明

1. Browser namespace 只可访问受控 proxy、声明的 Redis 和离线 fixture；禁止系统 DNS、host gateway、host network、Docker socket和未声明服务。
2. Browser 对 fixture/IP/域名的直接连接与 proxy 绕过均失败。
3. proxy 的 HTTPS CONNECT 在每次目标和每次 redirect 上复验 scheme、port、全部 A/AAAA 与最终连接 IP。
4. DNS rebinding、混合安全/不安全答案、loopback/private/link-local/metadata/multicast/reserved/unspecified、危险端口均 fail closed。
5. 正向允许路径和所有拒绝路径必须同时具有网络层实证；仅配置审阅或应用 mock 不构成通过。
6. 证据不得记录秘密、完整 URL query、正文或真实目标站点数据。

## 4. 验收与停点

- 将命令、exit code、拓扑、allow/deny 边、DNS 执行者、原始证据、创建对象和清理结果填入 `docs/42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md` 的 R2 区域。
- 任一旁路、CONNECT/redirect/rebinding 缺口、无法归属对象、真实公网访问或仅单层证明，判定 BLOCKED 并立即 STOP。
- 通过时唯一允许结论为 `R2 PASS — READY FOR INDEPENDENT REVIEW`；不得自行进入 R3、commit、push、PR 或 merge。
- 总控独立复审 R2 并合并证据前，R3 不生效；WP-3 正式实现继续 BLOCKED。
