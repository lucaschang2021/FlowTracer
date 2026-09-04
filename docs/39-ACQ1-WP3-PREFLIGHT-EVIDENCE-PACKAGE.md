# FlowTracer ACQ-1 WP-3 Preflight Backend Evidence Package

状态：Pending Backend Spike Evidence

用途：本文件是 `docs/38-ACQ1-WP3-PREFLIGHT-ADMISSION.md` 授权实验的强制报告模板。当前不含任何实际 Browser 版本、revision、digest 或资源限值；空白项不构成事实，也不构成 WP-3 正式准入。

## 1. Identity 与可复现环境

| 字段 | 必填实际值 / 证据 |
| --- | --- |
| 基准 `origin/main` | 精确 SHA |
| Spike branch / commit | 精确名称与 SHA |
| 工作目录 | `D:\FlowTracer-wt\backend` |
| Host OS / architecture | 版本与架构 |
| Docker / Compose / build engine | 精确版本 |
| Base image | immutable digest，不只写 tag |
| Python | 精确版本与 ABI |
| Debian | Bookworm 精确 release/image identity |

## 2. Runtime、依赖与许可证

| 项目 | 锁定值 | 来源/命令 | 结果 | 证据路径 |
| --- | --- | --- | --- | --- |
| Python Browser package/extras | 未填即 BLOCKED | 官方/锁定来源 |  |  |
| 全部传递依赖 | 未填即 BLOCKED | lock 解析 |  |  |
| Browser engine/channel | 未填即 BLOCKED | runtime 输出 |  |  |
| Browser revision/build id | 未填即 BLOCKED | runtime 输出 |  |  |
| Debian system packages | 未填即 BLOCKED | package manifest |  |  |
| Browser/proxy image digest | 未填即 BLOCKED | inspect/OCI 输出 |  |  |
| 直接/传递依赖 license | 未填即 BLOCKED | license inventory |  |  |
| Browser/engine redistribution terms | 未填即 BLOCKED | 官方来源 |  |  |

必须附安装、导入、启动、渲染、版本匹配/不匹配、两次构建对比的完整命令与安全摘要。digest 只能来自实际构建或 registry/OCI 内容，不得由 tag、Dockerfile hash 或人工文本代替。

## 3. 候选镜像与构建结果

- Browser Dockerfile/entrypoint：
- Proxy image/config：
- 锁定输入：
- Build commands：
- 第一次 image ID/digest：
- 第二次 image ID/digest：
- 一致性判定与差异解释：
- SBOM/package manifest：
- 非 root UID/GID 证明：
- read-only rootfs、tmpfs、cap_drop、no-new-privileges、seccomp、PID/CPU/memory 配置与运行态证明：

## 4. 网络拓扑与 deny-by-default 证明

列出每个容器/namespace、network、可解析名称、允许目标/端口、拒绝边和谁执行 DNS/IP/端口复验。必须包含 Browser worker、Browser runtime、egress proxy、fixture、Redis、普通 worker；不得包含公网测试目标。

| 尝试 | 预期 | 实际命令/结果 | 判定 | 证据路径 |
| --- | --- | --- | --- | --- |
| Browser 经 proxy 到获准 fixture | allow |  |  |  |
| Browser 直连 fixture IP 绕过 proxy | deny |  |  |  |
| Browser 直连公网 IP/域名 | deny；不依赖真实站点响应 |  |  |  |
| Browser 使用系统 DNS | deny |  |  |  |
| Browser 到 host gateway/host network | deny |  |  |  |
| Browser 到 Docker socket | deny/不存在 |  |  |  |
| Browser 到未声明内部服务 | deny |  |  |  |
| Proxy 到私网/link-local/metadata/危险端口 | deny |  |  |  |
| 混合 A/AAAA 与模拟 DNS rebinding | deny |  |  |  |
| 每跳 redirect 复验 | deny unsafe hop |  |  |  |

任何一项未执行、只能依赖应用层拦截或结果不确定，整体 egress 结论为 `BLOCKED`。

## 5. Browser 子资源拦截矩阵

| 面 | 本地 fixture | 应用层结果 | Proxy/网络结果 | Policy/scope/budget | fail-closed 证明 | 判定 |
| --- | --- | --- | --- | --- | --- | --- |
| navigation |  |  |  |  |  |  |
| redirect |  |  |  |  |  |  |
| iframe |  |  |  |  |  |  |
| script |  |  |  |  |  |  |
| XHR/fetch |  |  |  |  |  |  |
| WebSocket |  |  |  |  |  |  |
| download |  |  |  |  |  |  |
| popup |  |  |  |  |  |  |
| service worker register/update/fetch |  |  |  |  |  |  |

ACQ-1 v1 的 WebSocket 与 download 保持默认拒绝。某一面无法同时证明应用层和网络层约束时，该面以及正式 WP-3 均保持 `BLOCKED`。

## 6. 专用 queue/worker 隔离

| 字段 | 候选实际值 / 证据 |
| --- | --- |
| Queue name |  |
| Task route |  |
| Worker command |  |
| Prefetch | 必须为 1 |
| Concurrency | 默认 1；最多 2 仅作为有测量支撑的建议 |
| Healthcheck |  |
| 普通 worker 拒收 Browser task | 命令与结果 |
| Browser worker 拒收普通业务 task | 命令与结果 |
| crash/OOM 对普通 worker 的隔离 | 命令与结果 |

Spike task 不得写入生产 Router、RawItem 或业务 Pipeline。

## 7. 资源测量与候选限值

记录测试主机、采样工具、采样间隔、warm/cold 条件、fixture、重复次数与原始数据路径。

| 场景 | n | wall-clock | CPU | peak memory | peak PID | tmpfs/disk | pages/contexts/popups | limit-hit 结果 |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| 单页正常 JS |  |  |  |  |  |  |  |  |
| 单 run 上限 |  |  |  |  |  |  |  |  |
| 单 worker 稳态 |  |  |  |  |  |  |  |  |
| 无限 JS/慢页面 |  |  |  |  |  |  |  |  |
| popup storm |  |  |  |  |  |  |  |  |
| crash/worker kill |  |  |  |  |  |  |  |  |
| OOM |  |  |  |  |  |  |  |  |

每项给出原始 min/max；只有样本量足够且算法注明时才报告 p50/p95。候选限值必须逐项写出测量依据、安全余量、拒绝/回收行为和遗留进程/context/tmpfs 检查。没有实际测量时写 `BLOCKED`，不得估算。

## 8. 离线恶意 Fixture 与结果

至少包含：正常 JS、unsafe navigation、跨 scope redirect、iframe/script/XHR/fetch 私网目标、WebSocket、download、popup storm、service worker、redirect loop、模拟 DNS rebinding、metadata/link-local/IPv4/IPv6、访问控制、无限 JS、超大 DOM、crash 与 OOM。逐项记录 fixture identity/hash、命令、exit code、关键计数、预期/实际结果与证据路径。

测试不得访问真实目标网站。若工具可能尝试公网，先用网络层 deny 证明并以本地保留地址/fixture 验证，不以第三方服务是否可达作为结论。

## 9. 命令、结果、失败与旁路

- 完整命令清单与执行顺序：
- 每项 exit code / pass-fail / 关键计数：
- 未执行项及原因：
- 观察到的旁路、flaky、平台差异：
- P0 / P1 / P2：
- 无法证明而 fail-closed 的面：

失败必须保留，不得只提交最终成功日志。敏感环境变量、代理凭据、完整 URL query、正文与完整 DNS 答案不得进入证据。

## 10. 清理、回滚与结论

- 本次创建的容器/network/volume/cache 清单：
- 清理命令与清理前后对象清单：
- 未清理对象及原因：
- 关闭 Spike profile/queue 后 RSS/Native/static 基线不变的证明：
- License 结论：
- Compatibility 结论：
- Isolation 结论：
- 正式 WP-3 仍阻塞的事项：
- 建议候选值（非正式契约）：

允许的最终建议仅为：`READY FOR INDEPENDENT CONTROL REVIEW` 或 `BLOCKED`。无论哪一种，Backend 都必须 STOP；不得自行创建 WP-3 正式实现分支、续做 Addendum、push、PR 或 merge。
