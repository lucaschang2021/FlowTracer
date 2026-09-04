# FlowTracer ACQ-1 WP-3 Compatibility/Isolation Preflight 准入

状态：Accepted（仅兼容性与隔离 Spike；本控制提交合并后生效）

前置基准：`main@f4b58c1ec0d20d075b98d5a9ca3d146d0b4deb56`

执行角色：现有 Backend 角色；完成后直接向总控汇报并 STOP

固定工作目录：`D:\FlowTracer-wt\backend`

目标分支：`feat/acq-1b-browser-preflight-spike`

Phase：WP-3 Compatibility/Isolation Preflight / Spike（不是 WP-3 正式实现）

## 1. 准入结论

本文件只准入一个可丢弃、离线、证据导向的 Browser 兼容性与隔离实验，用于补齐 `docs/37-ACQ1-WP3-READINESS-BLOCKER.md` 的精确事实。它不签发 WP-3 正式 Admission，不允许实现 Dynamic/Advanced Browser adapter，不改变 `main` 已有生产能力。

WP-3 正式实现继续为 **NO / BLOCKED**。只有 Spike 证据经总控另开任务独立审查，并由后续 WP-3 Contract Addendum + 正式 Admission 控制 PR 冻结精确值且合并到 `main` 后，才可另行派发 WP-3。

## 2. 开工输入

Backend 开始时只读取：

- `docs/CURRENT-GATE.md`
- 本文件与 `docs/39-ACQ1-WP3-PREFLIGHT-EVIDENCE-PACKAGE.md`
- `docs/37-ACQ1-WP3-READINESS-BLOCKER.md`
- `docs/29-ACQ1-WORK-PACKAGES.md` 的通用规则与 WP-3 段落
- `docs/22-ACQ1-MASTER-BASELINE.md` 的 Browser 范围、固定原则与阶段顺序
- `docs/23-ACQ1-ACQUISITION-CONTRACT.md` 的 Browser backend、NetworkPolicy/Browser 隔离与资源段落
- `docs/25-ACQ1-ACCEPTANCE.md` 的 Dynamic Browser、SSRF/访问控制、资源耗尽与性能段落
- ADR-023、ADR-026、ADR-029、ADR-030
- 当前 Python 3.13/Debian Bookworm 构建基线，以及实验直接涉及的依赖、Docker/Compose、worker/queue、fixture 和脚本文件

不得回读或改写无关历史文档与业务模块。

## 3. 唯一实验目标

Spike 必须从官方或锁定来源形成可复现证据，并回答以下问题：

1. Python 3.13 + Debian Bookworm 下可用的精确 Browser Python package/extras、完整传递依赖、Browser engine/revision、系统依赖和许可证是什么；安装、导入、启动、渲染与版本不匹配时的实际结果是什么。
2. Browser 专用候选镜像能否由锁定输入重复构建；两次构建的内容身份如何比较；实际 image ID、repo digest 或可验证 OCI digest 是什么。不得预写或推断 digest。
3. 候选运行时能否使用专用 queue/worker，并证明普通 worker 不消费 Browser task；候选必须 `prefetch=1`、默认 `concurrency=1`，任何提高到 2 的建议均须有测量证据且不得在 Spike 中成为生产默认。
4. 候选容器能否以非 root、read-only rootfs、`cap_drop`、no-new-privileges、受限 seccomp、无特权、无 Docker socket、无 host network 运行，并对 CPU、memory、PID、tmpfs/临时磁盘施加可验证限制。
5. deny-by-default 网络拓扑能否确保 Browser 只能到受控 egress proxy、Redis 与明确必要的内部 fixture 服务；不能直连公网、系统 DNS、host network、Docker socket 或未声明内部服务。
6. 受控 proxy 能否逐目标重新执行 DNS、全部 A/AAAA、IP、协议、端口与 redirect 校验；应用层能否覆盖 navigation、redirect、iframe、script、XHR/fetch、WebSocket、download、popup 与 service worker。任何拦截面无法证明时必须 fail closed，并记录为正式 WP-3 阻塞项。
7. 在本地离线恶意 fixture 下，crash、OOM、无限脚本、popup storm、redirect loop、跨 scope、私网/metadata 目标、DNS rebinding 模拟、WebSocket、download 与 service worker 尝试是否只失败当前实验任务且不影响普通 worker。

## 4. 允许修改

仅在固定 Backend worktree 的新 Spike 分支中允许：

- 实验性依赖声明与锁文件；
- Browser 专用候选 Dockerfile、entrypoint 与 Compose test/Spike override；
- 受控 egress proxy 的候选配置；
- 专用实验 queue/worker 的最小配置；
- 本地离线 fixture、恶意 fixture、测量/验证脚本；
- `docs/39-ACQ1-WP3-PREFLIGHT-EVIDENCE-PACKAGE.md` 或同等 Backend 证据附件。

所有产物均为候选实验资产，不是生产配置。实验不得改变默认 Compose 启动路径；除显式 Spike profile/override 外不得启动 Browser 服务。

## 5. 明确禁止

- 不修改公开 REST/WebSocket/OpenAPI，不修改数据库 Schema/migration。
- 不修改 RawItem、既有 writer/去重/终态或 Document/Analysis/Embedding/Notification Pipeline。
- 不实现或修改 Router/fallback、Discovery、Change Intelligence、Opportunity、Profile 正式 Browser 开关或生产 Dynamic/Advanced adapter。
- 不放宽 WP-1 NetworkPolicy、SitePolicy、scope、资源预算或访问控制；不加入 CAPTCHA、登录墙、付费墙、robots 或平台限制绕过。
- 不访问真实目标网站，不使用公网作为测试依赖，不采集真实内容，不引入凭据、Cookie、Authorization、代理凭据或登录态。
- 不使用 host network、privileged、Docker socket、系统 DNS 旁路或 Browser 直连；无法证明 deny-by-default 时立即停止相应实验路径。
- 不 push、创建/评论 PR、merge、发布或修改其他 worktree；这些动作仍需总控另行授权。

## 6. 必须执行的证据矩阵

### 6.1 Runtime 与构建

- 记录锁定前后的解析命令、精确 package/extras/transitive versions、Python/OS/architecture、engine/revision 与系统包清单。
- 记录候选 Browser 与 proxy 镜像的 Dockerfile/lock 输入、构建命令、实际 digest、重复构建比较和不一致原因。
- 记录所有直接与传递依赖许可证、Browser/engine 再分发条款来源和未解决项；未证实即阻塞。

### 6.2 隔离与网络

- 提供容器、network、proxy、fixture、Redis、Browser worker 和普通 worker 的拓扑与精确 allow/deny 边。
- 对直连 IP、域名、系统 DNS、host gateway、host network、Docker socket、未声明内部服务分别给出可执行否定证据。
- 对 navigation、redirect、iframe、script、XHR/fetch、WebSocket、download、popup、service worker 分别记录应用层结果、proxy 结果、预算/策略结果和无法覆盖时的 fail-closed 行为。

### 6.3 资源与故障隔离

- 在声明的测试主机与镜像上测量单页、单 run、单 worker 的 wall-clock、CPU、峰值 memory、PID、tmpfs/临时磁盘，以及 page/context/popup 数量。
- 给出原始测量、重复次数、p50/p95/max（样本不足时不得伪报分位数）、安全余量计算和候选限值；文档阶段不得凭经验填写精确生产值。
- 验证 limit hit、Browser crash、worker kill、OOM 与清理回收；普通 API/worker 必须保持隔离，遗留进程/context/tmpfs 必须可检测。

### 6.4 Queue 与离线 fixture

- 冻结候选 queue 名称、task route、worker command、prefetch、concurrency、healthcheck 与任务拒收证明，但不得接入生产 Router/Pipeline。
- 所有核心测试使用本地 fixture 网络；至少覆盖正常 JS 渲染及上述全部子资源、SSRF、redirect、访问控制与资源耗尽场景。

## 7. 报告与判定

报告必须按 `docs/39-ACQ1-WP3-PREFLIGHT-EVIDENCE-PACKAGE.md` 填入实际值、命令、结果与证据路径。`TBD`、估算值、未运行命令、仅配置审阅或仅应用层 mock 不构成通过证据；未知项必须明确标为 `BLOCKED`。

Spike 只可得出：兼容/不兼容、已证明/未证明、候选限值及风险。不得声称“WP-3 已准入”“生产就绪”或“安全已完成”。出现网络旁路、Docker socket/host network 可达、普通 worker 消费 Browser task、无法 fail closed 或许可证不明，按 P0/P1 报告并立即停止扩张。

## 8. 交付、清理与停点

- 交付包含：changed files、Spike commit、锁定依赖、镜像 digest、拓扑、资源测量、命令/结果、失败/旁路、许可证、清理与回滚证明、P0/P1/P2。
- 清理必须停止并移除 Spike 容器/network/volume/cache 中本次明确创建的对象，保留代码与证据；不得删除共享或不明对象。列出清理前后对象清单。
- 回滚为关闭/移除 Spike profile 与专用 queue，使现有 RSS/Native/static 能力保持原样；安全策略不可回滚。
- Backend 完成后立即 STOP，并直接向总控汇报。总控必须另开审查任务；审查通过也只能进入后续 Contract Addendum + 正式 Admission 控制 PR，不得在原任务续做 WP-3。
