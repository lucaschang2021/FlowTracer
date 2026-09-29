# R3 内部来源预检：最小收敛任务

日期：2026-09-29。控制来源：`main@ff70c198acb74b764435485611ec67484bcc7262`。
候选来源：`59d3d2ffb9704fa3f548c69622abb3c2f6dd67f2`；其离线来源/路径修复已独立 Review，P0/P1/P2=0/0/0。

本文合并后只准入下述离线接线，不签发实际 Docker/Browser session。最终代码与输入闭包独立审查后，总控另以精确 SHA、image、manifest digest 和唯一 session 签发一次运行许可。不得把来源未知转换为目标访问许可。

## 目的与退出条件

停止追加占位框架。补齐一个可执行、单次、无公网、无采集目标的内部预检，取得锁定浏览器的实际扩展可用性、inventory 读取限制、计时观测和退出证据。运行成功仅为 `SOURCE_OBSERVED`，不是 R3 PASS；读取失败如实 `UNKNOWN/BLOCKED`，不自动重试。诊断结果必须给出“可进入既有四臂验证 / 仍有明确缺口 / 当前 DNR 不可用”之一及证据，不以继续抽象代替结论。

## 唯一允许的运行形态（待另签精确许可）

- 保持锁定完整 CfT 151.0.7922.34、Playwright 1.62.0、既有 DynamicFetcher 与 R1E 双摘要；不得更换引擎、修改 driver/browser bundle。
- 只使用固定 `about:blank` 的 DynamicFetcher 诊断入口；若该入口会在内部自动添加外部 URL，则拒绝，不换为低层 Playwright 冒称 DynamicFetcher 已验证。
- 一个唯一 session 内预定 baseline 和 enabled 两个独占新 profile；各最多启动一次，任一失败立即结束，禁止失败重跑。enabled 只挂载 `extension-v2/` 五文件，不同时挂载旧 v1。
- 只访问 `about:blank`、已获准扩展 audit 内部页和 `chrome://extensions/`。不得启动 navigation fixture、HTTP Worker、四个 ws/wss arm、TLS 服务或真实站点。禁止额外 chrome 页、权限、开发者模式、unsafe flags、扩展安装/启停动作。
- Browser 容器 network=none、UID10001、只读根、cap_drop ALL、no-new-privileges、PID128、768MiB、1CPU、既有受限 tmpfs；不启动 proxy/fixture/Redis/DNS。临时目录仅 profile、Crashpad 和限定证据；不新增持久卷或开放端口。
- DNS 不再阻塞这个内部页诊断，状态保持未验证；后续完整网络矩阵仍须证明 UID10001 的 DNS 兼容。本任务不授权 sysctl、root 或 capability 变更。

## 必须完成的最小接线

在 [52 来源补充](52-R3-RUNTIME-SOURCE-ADDENDUM.md) 既有白名单内实现固定 source-preflight 模式；不新增通用 runner/签名/DI 框架。

1. supervisor 接通真实命令的受控窄入口和生命周期，不能留下“渲染命令即完成”的占位。运行前必须验证总控另签的独立批准记录及 manifest 原始摘要；尚无实际记录时仍硬拒绝，不得接入 test double、自封摘要、env 或任意 caller True。批准记录与源码闭包分离，不造成自哈希循环。
2. 固定真实镜像 ID、只读源文件、profile、argv、phase、session，现场 inspect 与批准值交叉核验；父120秒监督在 create/start 前启动，子15秒来源预检、5秒关闭继续生效。诊断全部关闭后目标权限始终为 UNKNOWN/DENIED。
3. collector 保存实际 `Browser.getVersion`、可用时的 `Browser.getBrowserCommandLine`、受控 origin、扩展 ID、静态 rules/readback 和 `developerPrivate.getExtensionsInfo` 返回的必要脱敏字段。API 缺失、lastError、版本/字段未知必须明确报告，不能猜值。
4. UI-filtered inventory 不是完整 registry；现场字段/方法存在也不是内置 schema 语义证明。没有冻结来源时，不输出 inventory_complete=True。不得扩大资源扫描、猜内部 schemaRegistry API 或重试网上源码下载。
5. 在 about:blank、audit 和可访问可信扩展 realm 中，用宿主 monotonic 前后界定原生 Date.now/performance.now/timeOrigin 的重复观测。保留各时钟域及延迟区间；不得假定零误差或把 about:blank 当作 fixture/HTTP Worker 的计时证明。
6. 采集完无论来源是否完整均关闭整个 persistent browser；确认 disconnected、自然退出、容器/子进程停止，按唯一 session label+对象 ID 清理并核验无残留。不得清理历史对象、开发卷、共享 BuildKit cache。

## 离线验收与实际许可

必须新增受影响定向 fake/拒绝测试：source-preflight 永不触发目标 goto/WS、baseline 不加载扩展、enabled 唯一 v2、network-none、未知来源可记录但无目标权限、每 phase 无重试、超时/关闭/清理失败不可成功。保留全部既有来源摘要/路径链拒绝。只运行一次最终受影响套件，更新 execution-inputs，保留历史字节；不重复未变业务全量或 Node 测试。

提交完整可运行代码、精确输入摘要、命令与资源闭包，经独立 Review 后由总控签发实际独立批准记录和唯一 session。现阶段不得启动实际 Browser/Docker。该精确许可只准内部来源预检，不准采集目标、四臂验证、R4/R5 或正式 WP-3。实证完成后由总控立即裁定下一步最小验证或不可行处置，不再增加无用户价值的证明层。

## 额度例外

用户本次明确允许 R3 紧急收尾用完剩余额度，覆盖 5% 提前停点线；不覆盖系统实际 usage-limit。实际耗尽时保存现场立即停止、不反复重试，不购买或使用 reset。其他阶段仍遵循 AGENTS.md。
