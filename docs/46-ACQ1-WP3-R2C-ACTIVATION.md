# FlowTracer ACQ-1 WP-3 R2C Activation

状态：Suspended / BLOCKED（P1×1；等待 R1E deterministic account metadata）

稳定基准：`main@db9c4fad0ca826b472d18d85c69db53848cfcd94`

执行角色：Backend / Architecture

固定工作目录：`D:\FlowTracer-wt\backend`

目标分支：`feat/acq1-wp3-r2c`

## 1. 准入结论

R1C 已由 PR #60 验收合并；R1D 已由 PR #63 独立复审、Backend CI 验收并合并，candidate `a804a371ec99615278c2cd60f442dc58299ff7c5`，merge commit `db9c4fad0ca826b472d18d85c69db53848cfcd94`，P0/P1/P2=`0/0/0`。本文件仅重新激活 R2C：使用已合并 R1D 的锁定输入、完整 Chromium和可重建 Runtime Identity v2，重新执行 production-shaped controlled egress proxy/namespace 全矩阵。

本准入不包含 R3-R5、WP-3 正式实现、默认 API/worker/Compose、Router、RawItem Pipeline、Schema/migration、公开 API、Frontend、Integration、Release 或 PLUGIN-1。

## 2. 允许范围

- 仅新增 `backend/experiments/browser-r2c/`，并更新 `docs/42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md` 的 R2C 实际证据。
- 从已合并 `backend/experiments/browser-r1d/` 的 Dockerfile、锁文件、browser tree、SBOM/license、Runtime Identity v2 manifest 与验证器重建独立 R2C 候选镜像；使用唯一 tag、builder、network、container、volume/cache 和证据路径。
- 可复制并最小调整历史 `browser-r2/` harness 以指向 R1C 完整 Chromium，但不得覆盖或改写 `browser-r1/`、`browser-r2/`、`browser-r1c/`、`browser-r3/` 的历史资产。
- 仅使用离线 fixture、保留地址和唯一宿主 loopback control canary；不得访问真实目标站点、公网 DNS、凭据或登录态。禁止 global prune。

## 3. 身份与运行前硬门禁

R2C 候选必须在执行网络矩阵前证明：

1. Chrome for Testing 版本、revision、executable path、executable SHA-256、619-entry browser tree manifest、Debian lock、CycloneDX SBOM 与 license inventory 精确匹配已合并 R1D。
2. Runtime Identity v2 必须由当前候选生成完整逐路径 manifest，并与已合并 R1D 的 10,340-entry manifest 逐条、payload bytes、payload SHA-256 `06e891370ef3af86bda0bcf5539bb292e42ffdd3c6db3a55abc3023fc1e4761e` 及 manifest SHA-256 `8428859de54769e2faa0470f92c8ae8e0f94464b2003b98f0497b7fcc4bdd49a` 完全一致；只比较总摘要或排除审计文件均不构成通过。
3. Browser runtime 为 UID/GID 10001、read-only rootfs、drop ALL、no-new-privileges、非 privileged，并具有冻结的 PID、memory、CPU 与 `/tmp` 限值。
4. 真实 Scrapling `DynamicFetcher` 使用显式完整 Chromium executable、`retries=1` 与受控 `/tmp` HOME/XDG/profile；不得用 Patchright/Playwright 直调替代。

任一身份、路径、哈希、SBOM/license 或 DynamicFetcher 启动不一致，立即判定 BLOCKED，网络矩阵不得继续。

## 4. 必须回归的网络证据

1. Browser namespace 只可访问受控 proxy、声明的 Redis 与离线 fixture；禁止系统 DNS、host gateway、host network、Docker socket及未声明服务。
2. Browser 对 fixture/IP/域名、live host-gateway canary 和 control-network canary 的直接连接均以可验证的无路由结果失败；独立 control client 必须能访问同一精确 canary，排除目标未监听造成的假阴性。
3. proxy 的 HTTPS CONNECT 对首次目标和每次 redirect 重新验证 scheme、port、全部 A/AAAA 与最终 peer IP。
4. DNS rebinding、混合安全/不安全 A/AAAA、loopback/private/link-local/metadata/multicast/reserved/unspecified 与危险端口全部 fail closed。
5. proxy 仅接受冻结的 CONNECT 路径；absolute-form 请求及 proxy 绕过失败。正向 allow 与每类 deny 均须同时具有网络层和应用运行态原始证据。
6. 真实 DynamicFetcher 必须经受控 proxy 完成允许 fixture 的确定性渲染和安全失败；不得用 mock、仅配置审阅或 Headless Shell 历史结果替代。
7. 证据不得记录秘密、完整 URL query、正文或真实目标站点数据。

## 5. 验收、清理与停点

- 记录开始/结束时间、完整命令、exit code、拓扑、allow/deny 边、DNS 执行者、镜像/进程身份、原始证据、创建对象和清理结果。
- 每个容器、network、volume、image/cache 必须唯一可归属并精确清理；保护 R1/R2/R1C/R3 现有文件哈希和历史 Docker 对象，不得执行 global prune。
- 任一旁路、CONNECT/redirect/rebinding 缺口、DynamicFetcher 未真实启动、仅单层证明、真实公网访问、敏感信息或无法归属对象，判定 BLOCKED 并立即 STOP。
- 长构建前检查 5 小时和每周额度；任一剩余比例小于或等于 5% 时保存现场并停点。
- 通过时唯一允许结论为 `R2C PASS — READY FOR INDEPENDENT REVIEW`。Backend 不得自行 commit、push、PR、merge，也不得恢复 R3。
- R2C 经独立复审与证据合并后，总控另行签发 R3 重新准入。R3、R4-R5 与 WP-3 正式实现在此之前继续 BLOCKED。

## 6. 首次执行停点

首次执行只完成 identity 硬门禁：Chrome 151.0.7922.34、完整 executable/path/SHA、619-entry browser tree、Debian 206、SBOM 231 与 license inventory 均匹配；full-root normalized identity 不匹配，P0/P1/P2=`0/1/0`。依本文件第 3 节，网络矩阵未启动并已 STOP。

只读诊断确认旧期望在 R1C 运行后因审计验证器字节变化而陈旧，且旧证据没有逐路径 manifest，不能直接改写摘要或在 R2C 现场排除文件。该阻塞已由 ADR-032、`docs/47-ACQ1-WP3-R1D-RUNTIME-IDENTITY.md` 与 PR #63 的 Runtime Identity v2 证据关闭；本控制更新只重新激活 R2C，不改变首次失败记录。

## 7. A2 执行停点

R2C-A2 从 `main@aac317d5ad1bf6f041c5a75d4ce2da2479bb14ba` 重建候选并在网络矩阵前执行 Runtime Identity v2 硬门禁。10,340 个路径中仅 `/etc/shadow` 的原始字节 SHA 不一致；entry count、payload bytes、path/type/mode/UID/GID 与其他 10,339 项一致。Chrome 151.0.7922.34、619-entry browser tree、Debian 206、SBOM 231、license 206/206 与 final script allowlist 全部匹配。网络矩阵未启动，临时对象已精确清理。

只读诊断确认唯一变更来自 `useradd --create-home --uid 10001 flowtracer` 将 UTC 构建日写入 shadow 第 3 字段 `sp_lstchg`：R1D 为 epoch-day 20715，R2C-A2 为 20716。完整 shadow 行和密码字段未进入报告或证据。R2C 由此再次暂停；只有 ADR-033 与 `docs/48-ACQ1-WP3-R1E-DETERMINISTIC-ACCOUNT.md` 的 R1E 新 authority 独立验收并合并后，才能由新的控制 PR 再次激活。
