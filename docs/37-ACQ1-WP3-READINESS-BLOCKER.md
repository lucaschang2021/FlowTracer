# FlowTracer ACQ-1 WP-3 Readiness Blocker

状态：BLOCKED / Not Admitted

基准：`main@fe99fac67f4489e273bcf9f40f839868ee9ec17f`（Architecture Governance Pass 收口 PR #52 merge commit）

Phase：WP-3 / ACQ-1B Dynamic + H-browser

候选实现分支：`feat/acq-1b-browser`（尚不得创建或派发）

## 1. 已冻结范围

WP-3 仅允许独立 Browser 镜像、专用 worker/queue、强制受控 egress、Dynamic/Advanced adapter、Browser pool 和资源隔离。所有 navigation、redirect、iframe、script、XHR/fetch、WebSocket、download 与 popup 必须同时受 NetworkPolicy、SitePolicy、scope 和累计预算控制。

WP-3 不允许 Router/fallback 决策、Discovery、Change Intelligence、Opportunity、Schema/migration、公开 REST/WebSocket/OpenAPI 变化、Frontend、Integration 或 Release；不得改变普通 API/worker 的运行权限，不得放宽 WP-1 NetworkPolicy。Dynamic/Advanced 也不得绕过 CAPTCHA、登录墙、付费墙、robots 或其他访问控制。

## 2. 已满足前置事实

- WP-1 NetworkPolicy、SitePolicy、ResourceBudget 与运行状态内核已验收合并。
- WP-2 static adapter、质量观测与通用提取已通过 Stage Gate 并由 PR #39 合并。
- ADR-023、ADR-026、Acquisition Contract §9、Acceptance Baseline §5/§6 与 Work Packages WP-3 已冻结 fail-closed 安全方向。

## 3. 阻塞的精确契约与证据

现有仓库不能复现以下硬门禁，因此不得把 WP-3 描述为已冻结或已准入：

1. Browser runtime：精确 Python package/extras、Browser engine、Browser revision、系统依赖清单及 Python 3.13/Debian Bookworm 兼容实验结果。
2. Immutable build：Browser 专用 Dockerfile 的锁定输入、可重复构建方法和最终 image digest。digest 必须来自实际构建产物，不能由控制文档预写。
3. Egress enforcement：受控 proxy 的具体实现/版本/配置；Browser 网络命名空间如何只连接 proxy、Redis 与必要内部服务；proxy 如何逐目标重做 DNS/IP/端口校验并阻止直连、系统 DNS、host network 与 Docker socket。
4. Application interception：对 navigation、redirect、iframe、script、XHR/fetch、WebSocket、download、popup 与 service worker 的完整拦截/默认拒绝矩阵，以及任何无法拦截子资源的 fail-fast 行为。
5. Resource limits：单页、单 run、单 worker 的 wall-clock、CPU、memory、PID、tmpfs/临时磁盘、popup/context/page 上限与 Browser pool 回收条件的精确数值。
6. Queue/runtime：专用 queue 名称、task route、worker command、prefetch=1、默认 concurrency=1/最大 2 的配置位置、健康检查、crash/OOM 隔离与普通 worker 不消费 Browser task 的证明。
7. Offline acceptance：本地 JS/redirect/iframe/XHR/WebSocket/download/popup fixture、恶意 DNS/SSRF fixture、访问控制停止与无公网测试拓扑的可执行矩阵。

## 4. 所需控制产物

后续必须先提交一份可复现的兼容性与隔离证据包，由总控独立核验后再形成新的 WP-3 Contract Addendum/ADR 与 Admission PR。证据包至少包含：

- 锁定文件和实际 Browser revision/system dependency 输出；
- Browser 与 egress proxy 镜像 digest、构建命令和环境标识；
- Compose/network 拓扑与 deny-by-default 证明；
- 精确配置/资源限值表；
- 上述离线 fixture 的最小兼容性结果；
- license、回滚和已知限制。

该证据包仅用于决定契约，不得顺带实现 Router、Discovery 或业务 Pipeline。`docs/38-ACQ1-WP3-PREFLIGHT-ADMISSION.md` 在其控制提交合并后，作为唯一例外书面准入固定 Backend worktree 中的独立证据 Spike，并要求按 `docs/39-ACQ1-WP3-PREFLIGHT-EVIDENCE-PACKAGE.md` 报告；本文件本身仍不授权该工作，也不授权正式 WP-3 实现。

## 5. Gate 结论

WP-3 Admission：**NO / BLOCKED**。

解除条件：新的控制 PR 基于实际证据冻结全部精确值并明确签发 WP-3 Admission，且该 PR 已合并到 `main`。在此之前不得创建正式实现分支、派发 WP-3 或进入 Browser 业务实现；只有 `docs/38-ACQ1-WP3-PREFLIGHT-ADMISSION.md` 控制提交合并后，才可在其固定 worktree/Spike 分支和禁止范围内安装实验性依赖、构建候选镜像并运行离线证据实验。WP-4..WP-8、PLUGIN-1、Frontend、Integration 与 Release 继续未准入。
