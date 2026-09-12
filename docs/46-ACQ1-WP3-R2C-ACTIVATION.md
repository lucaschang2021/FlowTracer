# FlowTracer ACQ-1 WP-3 R2C Activation

状态：Accepted（仅 R2C Full Chromium controlled-egress 回归证据）

稳定基准：`main@df0c3512080f384dbd6c820d7627cbe721e37422`

执行角色：Backend / Architecture

固定工作目录：`D:\FlowTracer-wt\backend`

目标分支：`feat/acq1-wp3-r2c`

## 1. 准入结论

R1C 已由 PR #60 验收合并，candidate `787a0df0548e05431fa60426f48f239ba7195465`，P0/P1/P2=`0/0/0`。本文件仅激活 R2C：使用已合并 R1C 的锁定输入和完整 Chromium，重新执行 production-shaped controlled egress proxy/namespace 全矩阵。

本准入不包含 R3-R5、WP-3 正式实现、默认 API/worker/Compose、Router、RawItem Pipeline、Schema/migration、公开 API、Frontend、Integration、Release 或 PLUGIN-1。

## 2. 允许范围

- 仅新增 `backend/experiments/browser-r2c/`，并更新 `docs/42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md` 的 R2C 实际证据。
- 从已合并 `backend/experiments/browser-r1c/` 的 Dockerfile、锁文件、browser tree、SBOM/license 与验证器重建独立 R2C 候选镜像；使用唯一 tag、builder、network、container、volume/cache 和证据路径。
- 可复制并最小调整历史 `browser-r2/` harness 以指向 R1C 完整 Chromium，但不得覆盖或改写 `browser-r1/`、`browser-r2/`、`browser-r1c/`、`browser-r3/` 的历史资产。
- 仅使用离线 fixture、保留地址和唯一宿主 loopback control canary；不得访问真实目标站点、公网 DNS、凭据或登录态。禁止 global prune。

## 3. 身份与运行前硬门禁

R2C 候选必须在执行网络矩阵前证明：

1. Chrome for Testing 版本、revision、executable path、executable SHA-256、619-entry browser tree manifest、Debian lock、CycloneDX SBOM 与 license inventory 精确匹配已合并 R1C。
2. 规范化 filesystem identity 匹配 R1C `6ef0e9ecb34d0a72c2135282b06548f7bdac92be27f8df2444188216013bddea`；若重建元数据不同，必须解释且内容身份仍须一致。
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
