# FlowTracer ACQ-1 WP-3 Preflight BLOCKED Report

状态：Final / BLOCKED

事实基准：`main@b7cd7b1ce6e1d36bd7607c75f9883367cce6e623`

执行分支：`feat/acq-1b-browser-preflight-spike`

执行结果：分支 base/HEAD 均为 `b7cd7b1ce6e1d36bd7607c75f9883367cce6e623`；工作树 clean；无代码、commit、push 或 PR。

Phase：WP-3 Compatibility/Isolation Preflight（不是 WP-3 正式实现）

## 1. 最终结论

Preflight 按 fail-closed 原则判定 **BLOCKED**。发现 `P0 × 1`、`P1 × 5`、`P2 × 2`；P0/P1 未清零，因此不得冻结 Browser package、engine revision、系统依赖、镜像 digest、proxy 方案、资源限值或 queue/runtime 契约，也不得签发 WP-3 正式 Admission。

本次只形成了局部概念验证。候选镜像与本次全部可识别的临时容器、network、volume 等资源已精确删除；既有用户数据、共享资源与其他 worktree 未被触碰。BuildKit cache 因无法精确归属而不计入可审计清理结论。

## 2. 已证明的事实

- 双 internal network 的 deny-by-default 拓扑概念验证通过。
- 在本次实验范围内，未发现 Browser 直连 fixture、metadata、未声明服务、系统 DNS、host gateway 或 Docker socket 的旁路。
- 候选资产均为可丢弃实验产物，没有进入默认 API/worker、生产 Compose、业务 Pipeline 或 `main`。
- 清理完成后，Backend 分支回到 `base=HEAD=b7cd7b1ce6e1d36bd7607c75f9883367cce6e623` 且工作树 clean；无代码或 Git 交付物遗留。

这些事实只证明局部拓扑概念，不证明生产级受控 egress、完整应用拦截、可重复镜像、Browser runtime、队列隔离或资源安全。

## 3. 未证明与缺陷分级

### P0 × 1

1. **download 默认拒绝缺少双层证明。** download 请求抵达候选 proxy，未形成应用层与 proxy/网络层同时拒绝的完整证据。正式 WP-3 必须保持 download 默认拒绝；该缺口直接阻塞准入。

### P1 × 5

1. **应用拦截矩阵 hang。** 验证过程缺少自身 hard timeout、process-group kill、Browser context/page 回收与遗留进程检查，无法证明失败被限定在单任务内。
2. **DynamicFetcher 实际启动未证明。** 仅有候选或配置层观察，未形成精确 runtime 启动、渲染与失败行为证据。
3. **专用 queue/worker 隔离未执行。** 未证明普通 worker 拒收 Browser task、Browser worker 拒收普通业务 task，也未验证 `prefetch=1`、`concurrency=1`、health/restart 与 crash/OOM 隔离。
4. **不可变双构建链未完成。** durable lock、SBOM/license inventory、两次 `--no-cache` 构建与内容身份对比均未完成，不能冻结 image digest 或依赖集合。
5. **Chromium/engine 再分发许可证未完整核验。** Browser engine 与全部直接/传递依赖的许可证和再分发条件仍不完整。

### P2 × 2

1. **资源样本不足。** 只有 `n=1`，不能报告稳定的 min/max、分位数、安全余量或生产资源限值。
2. **BuildKit cache 归属不精确。** 现有环境无法把 cache 精确归属到本次实验，不能把 cache 清单或大小作为可审计结论。

## 4. 不得冻结的候选事实

本次任何 Browser package/version/extras、engine/channel/revision、Debian system package、Dockerfile/base image、image ID/digest、proxy 实现/版本、queue 名称、task route、资源限值、超时值或并发建议均为未验收候选值，不是 FlowTracer 契约。

尤其是候选 proxy 不支持正式要求的 HTTPS CONNECT 与完整 DNS rebinding 策略，不能作为生产实现或受控 egress 基线。不得从已删除镜像、一次运行、配置审阅、日志片段或 BuildKit cache 推断正式值。

## 5. 解阻条件

只有 `docs/41-ACQ1-WP3-REMEDIATION-EVIDENCE-ADMISSION.md` 定义的 R1→R5 顺序闸门全部以实际证据通过，且 `docs/42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md` 无 `TBD`、估算或仅配置审阅项后，才可申请独立总控复核。

即使 R1→R5 全部通过，也只代表证据具备评审条件。总控仍须另开任务审查，并另提 WP-3 Contract Addendum + 正式 Admission 控制 PR；该 PR 合并前，WP-3 正式实现保持 **NO / BLOCKED**。

## 6. 范围与停点

- 不准入 Dynamic/Advanced Browser adapter、Router/fallback、Discovery、Change Intelligence、Opportunity 或业务 Pipeline。
- 不修改公开 REST/WebSocket/OpenAPI、Schema/migration、评分规则、Frontend、Integration 或 Release。
- 不允许 CAPTCHA、登录墙、付费墙、robots、Source scope、NetworkPolicy 或资源预算绕过。
- WP-4..WP-8、PLUGIN-1、Frontend、Integration 与 Release 继续未准入。

本报告归档后保持停点；下一步仅可按新的顺序化 remediation evidence 控制文件执行更小的证据/原型阶段。
