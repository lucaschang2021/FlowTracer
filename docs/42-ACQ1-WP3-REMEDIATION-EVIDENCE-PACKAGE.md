# FlowTracer ACQ-1 WP-3 Remediation Evidence Package

状态：Pending Sequential Evidence

用途：本文件是 `docs/41-ACQ1-WP3-REMEDIATION-EVIDENCE-ADMISSION.md` 的强制证据模板。必须按 R1→R5 顺序填写实际值；`TBD`、估算、未执行、仅配置审阅、仅 mock 或未保存的口头观察均不构成通过证据。

## 1. Identity 与通用记录

| 字段 | 必填实际值 / 证据 |
| --- | --- |
| `origin/main` | 精确 SHA |
| evidence branch / commit | 精确名称与 SHA |
| host OS / architecture | 精确版本与架构 |
| Docker / Compose / BuildKit | 精确版本 |
| Python / Debian | 精确版本与 ABI/release |
| 工作目录 | `D:\FlowTracer-wt\backend` |
| 公网访问 | 必须为否，并给出网络层证据 |
| 初始对象清单 | 容器/network/volume/image/cache/process |

每个闸门统一记录：开始/结束时间、完整命令、exit code、关键计数、原始证据路径、失败/P0/P1/P2、创建对象、清理命令和清理后对象清单。

## 2. R1 — Locked image、SBOM/license 与复现

| 项目 | 实际值 | 来源/命令 | 结果 | 证据路径 |
| --- | --- | --- | --- | --- |
| Browser package/extras | 未填即 BLOCKED |  |  |  |
| 全部传递依赖与 lock hash | 未填即 BLOCKED |  |  |  |
| engine/channel/revision | 未填即 BLOCKED |  |  |  |
| Debian system packages | 未填即 BLOCKED |  |  |  |
| base image digest | 未填即 BLOCKED |  |  |  |
| SBOM identity/hash | 未填即 BLOCKED |  |  |  |
| dependency license inventory | 未填即 BLOCKED |  |  |  |
| Chromium/engine redistribution terms | 未填即 BLOCKED | 官方来源 |  |  |
| no-cache build 1 content identity | 未填即 BLOCKED |  |  |  |
| no-cache build 2 content identity | 未填即 BLOCKED |  |  |  |
| 双构建差异与解释 | 未填即 BLOCKED |  |  |  |

R1 判定：`PASS / BLOCKED`。只有所有项都有可复现实际证据时才可进入 R2。

## 3. R2 — Controlled egress proxy/namespace

先附容器/network/namespace/proxy/Redis/fixture 的拓扑，以及每条 allow/deny 边、DNS 执行者和端口。

| 测试 | 预期 | 实际命令/结果 | 判定 | 证据路径 |
| --- | --- | --- | --- | --- |
| 获准 HTTPS CONNECT 到 fixture | allow 且逐目标复验 |  |  |  |
| 每跳 redirect A/AAAA/IP/port 复验 | unsafe hop deny |  |  |  |
| 混合 A/AAAA / DNS rebinding | deny |  |  |  |
| 私网/link-local/metadata/危险端口 | deny |  |  |  |
| Browser 直连 fixture/IP/域名 | deny |  |  |  |
| 系统 DNS / host gateway / host network | deny |  |  |  |
| Docker socket / 未声明服务 | deny/不存在 |  |  |  |
| Browser 绕过 proxy | deny |  |  |  |

R2 判定：`PASS / BLOCKED`。任何面仅有应用 mock 或配置审阅即 BLOCKED；只有 PASS 才可进入 R3。

## 4. R3 — Application interception matrix

| 面 | fixture | 应用 event/hook | proxy/网络结果 | policy/scope/budget | fail-closed | 判定 |
| --- | --- | --- | --- | --- | --- | --- |
| navigation |  |  |  |  |  |  |
| redirect |  |  |  |  |  |  |
| iframe |  |  |  |  |  |  |
| script |  |  |  |  |  |  |
| XHR/fetch |  |  |  |  |  |  |
| WebSocket | default deny |  |  |  |  |  |
| download | default deny |  |  |  |  |  |
| popup |  |  |  |  |  |  |
| service worker register/update/fetch |  |  |  |  |  |  |

另附 DynamicFetcher 实际启动、渲染、终止和失败输出。R3 判定：`PASS / BLOCKED`；任何 hang、遗漏或非双层证明即 BLOCKED，只有 PASS 才可进入 R4。

## 5. R4 — Deadline、回收与资源样本

- hard deadline / watchdog：
- process-group kill：
- context/page/popup/process/tmpfs 回收检查：
- crash / worker kill / OOM 隔离：

| 场景 | n | wall-clock | CPU | peak memory | peak PID | tmpfs/disk | pages/contexts/popups | limit-hit/reap |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| 正常 JS |  |  |  |  |  |  |  |  |
| 单 run 上限 |  |  |  |  |  |  |  |  |
| 无限脚本/超大 DOM |  |  |  |  |  |  |  |  |
| popup storm/redirect loop |  |  |  |  |  |  |  |  |
| crash/kill/OOM |  |  |  |  |  |  |  |  |

附原始样本、采样方法、重复次数、安全余量算法与候选限值。`n=1`、无原始值、伪造分位数、遗留对象或关键 cache 无法归属时为 BLOCKED。R4 只有 PASS 才可进入 R5。

## 6. R5 — Dedicated queue / two-worker mutual exclusion

| 字段 | 实际值 / 命令 / 结果 | 证据路径 |
| --- | --- | --- |
| 专用 queue / task route |  |  |
| Browser worker command |  |  |
| `prefetch=1` |  |  |
| `concurrency=1` |  |  |
| healthcheck |  |  |
| restart 行为 |  |  |
| 普通 worker 拒收 Browser task |  |  |
| Browser worker 拒收普通 task |  |  |
| crash/OOM 对普通 worker 隔离 |  |  |
| restart 后进程/锁/临时资源 |  |  |

R5 判定：`PASS / BLOCKED`。不得将实验 task 接入 Router、RawItem 或业务 Pipeline。

## 7. 最终清理、缺陷与建议

- R1→R5 顺序证明：
- 未执行项及原因：
- P0 / P1 / P2：
- 本次创建对象：
- 精确清理命令与前后清单：
- 未清理对象及原因：
- 默认 API/worker、RSS/Native/static 基线不变证明：
- 未冻结的候选值：
- 正式 WP-3 仍阻塞项：

允许的最终建议仅为 `READY FOR INDEPENDENT CONTROL REVIEW` 或 `BLOCKED`。无论结果为何，Backend 都必须 STOP；不得自行创建 WP-3 正式实现分支、续做 Addendum、push、PR 或 merge。
