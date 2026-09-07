# FlowTracer ACQ-1 WP-3 Remediation Evidence Admission

状态：Accepted（仅顺序化证据/原型；本控制 PR 合并后生效）

前置基准：`main@b7cd7b1ce6e1d36bd7607c75f9883367cce6e623`

执行角色：Backend；每个闸门结束后记录证据，任一失败立即 STOP

固定工作目录：`D:\FlowTracer-wt\backend`

目标分支：`feat/acq-1b-browser-remediation-evidence`

Phase：WP-3 Remediation Evidence（不是 WP-3 正式实现）

## 1. 准入结论

本文件只准入一个比原 Preflight 更小、严格按 R1→R5 顺序执行的离线证据/原型阶段，用于关闭 `docs/40-ACQ1-WP3-PREFLIGHT-BLOCKED-REPORT.md` 的 P0/P1/P2。它不准入正式 WP-3，不允许接入默认 API/worker、业务 Pipeline 或生产 Compose。

五个闸门不得并行、跳过或用后续结果替代前序失败。每个闸门必须先把实际值和证据填入 `docs/42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md`；任一必填项缺失、失败或只能用 `TBD`/估算/配置审阅支持时，立即 STOP，不得开始下一闸门。

## 2. 通用边界

仅允许为证据阶段创建可丢弃的实验性依赖锁、Browser/proxy 候选镜像、专用 Compose override/profile、离线 fixture、验证脚本、专用实验 queue/worker 配置及证据附件。所有资产必须与默认运行路径隔离，并可精确清理和回滚。

禁止：公开 API/OpenAPI、Schema/migration、RawItem/Document/Analysis/Embedding/Notification Pipeline、Router/fallback、Discovery、Change Intelligence、Opportunity、Frontend、Integration、Release 变化；禁止真实网站、公网测试依赖、凭据/登录态、host network、privileged、Docker socket、系统 DNS 旁路和访问控制绕过。

## 3. 顺序闸门

### R1 — Durable locked Browser image、SBOM/license 与双构建复现

必须先完成并证明：

- 锁定 Browser Python package/extras、全部传递依赖、engine/channel/revision、Debian system packages、base image digest 与构建工具版本；
- 生成可审计 SBOM 和直接/传递依赖 license inventory，完整核验 Chromium/engine 再分发条款；
- 在相同声明环境从锁定输入执行两次独立 `--no-cache` 构建，记录命令、实际内容身份、差异及原因；
- 候选镜像可持久重建，但不进入默认 Compose 或 registry 发布流程。

任一依赖、license、revision、digest 或双构建结果不完整即 STOP。

### R2 — Production-shaped controlled egress proxy/namespace

仅在 R1 通过后执行。必须证明：

- Browser namespace 只能到受控 proxy、Redis 与声明的离线 fixture；无公网、系统 DNS、host gateway、host network、Docker socket 或未声明服务旁路；
- proxy 支持并正确约束 HTTPS CONNECT；每次目标与每次 redirect 都重新解析和校验全部 A/AAAA、最终 IP、scheme、port 与 policy；
- DNS rebinding、混合安全/不安全答案、私网/link-local/metadata、危险端口、直连 IP/域名与 proxy 绕过均 fail closed；
- 仅使用本地 fixture/保留地址形成否定证据，不访问真实公网目标。

任一旁路、CONNECT/逐跳复验/DNS rebinding 缺口或仅应用层 mock 即 STOP。

### R3 — Application interception matrix

仅在 R2 通过后执行。对 navigation、redirect、iframe、script、XHR/fetch、WebSocket、download、popup、service worker register/update/fetch 逐项提供应用层与 R2 网络层的双层证据。

WebSocket 与 download 必须默认拒绝；请求不得抵达允许转发路径。每项都必须记录 fixture、预期、实际、event/hook、proxy 观察、policy/scope/budget 与 fail-closed 结果。任一面 hang、遗漏、旁路或单层证明即 STOP。

### R4 — Hard deadline、强制回收与重复资源样本

仅在 R3 通过后执行。必须证明：

- harness 自身具有 hard deadline；超时或失败执行 process-group kill，并回收所有 Browser process/context/page/popup/tmpfs；
- crash、worker kill、OOM、无限脚本、超大 DOM、popup storm、redirect loop 均只失败当前实验任务，普通 API/worker 不受影响；
- 对正常、上限与故障场景进行多次重复采样，记录 `n`、原始值、min/max；只有样本量和算法足够时才报告 p50/p95；
- CPU、memory、PID、tmpfs/disk、wall-clock、page/context/popup 候选限值均有测量、安全余量与 limit-hit/reap 证据。

遗留进程/资源、`n=1`、估算限值或无法归属的关键测量即 STOP。

### R5 — Dedicated queue 与双 worker 互斥

仅在 R4 通过后执行。必须使用专用实验 queue 和两个真实 worker 证明：

- Browser worker 固定 `prefetch=1`、`concurrency=1`，具有可验证 healthcheck 与 restart 行为；
- 普通 worker 不消费 Browser task，Browser worker 不消费普通业务 task；
- queue route、task identity、worker command 和拒收行为均有运行态证据；
- Browser task crash/OOM/restart 不影响普通 worker，重启后无重复进程、锁或临时资源泄漏。

不得将实验 task 接入生产 Router/RawItem/Pipeline。任一互斥、health/restart 或故障隔离缺口即 STOP。

## 4. 验收与清理

- 五个闸门必须按顺序各自给出命令、exit code、关键计数、证据路径、失败与清理结果。
- 成功日志不得覆盖失败记录；敏感值、正文、完整 URL query、凭据与秘密不得进入证据。
- 每个闸门只清理本次精确创建的容器、network、volume、image/cache 和进程；不得触碰共享或不明资源。
- 任一闸门失败后保留安全摘要和证据，恢复默认 RSS/Native/static 基线，直接向总控报告并 STOP。

R1→R5 全部通过后的唯一允许结论是 `READY FOR INDEPENDENT CONTROL REVIEW`。这不等于 WP-3 已准入；Backend 必须 STOP，等待总控独立审查和后续 Contract Addendum + 正式 Admission PR。
