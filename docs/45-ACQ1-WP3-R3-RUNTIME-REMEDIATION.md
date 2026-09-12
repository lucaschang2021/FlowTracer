# FlowTracer ACQ-1 WP-3 R3 Runtime Remediation

状态：Accepted（仅 R1C Full Chromium compatibility evidence）

前置基准：`main@767f1357fb1cac4e3f3c8913b0a3167146dfe81a`

执行角色：Backend / Architecture

固定工作目录：`D:\FlowTracer-wt\backend`

目标分支：`feat/acq-1b-browser-remediation-evidence`

## 1. 问题与裁定

R3 唯一执行项目 `flowtracer-r3-exec-20260909-a` 证明：`patchright install --with-deps --only-shell chromium` 产生的 Headless Shell 可以支持 R1 基础 probe，但不能满足 Scrapling DynamicFetcher 对完整 Chromium executable 的实际要求。DynamicFetcher 在任何矩阵请求前安全失败；P0/P1/P2=`0/1/0`。

不得用 Patchright 直接调用、修改 executable 查找结果、软链接伪装 Headless Shell，或跳过 DynamicFetcher 来关闭该缺陷。裁定采用独立 R1C→R2C→R3 纠偏链，保留 R1/R2 原始证据不变。

## 2. R1C 唯一允许范围

- 仅新增 `backend/experiments/browser-r1c/`，并更新 `docs/42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md` 的 R1C 实际证据。
- 从 R1 的精确 Python、Scrapling、Patchright、Playwright、Debian snapshot 与构建工具版本出发，安装并锁定完整 Chromium；不得使用 floating package、browser channel、base image 或未记录系统依赖。
- 使用独立 tag、builder、cache、image 与证据路径；禁止覆盖 R1 tag、修改 R1 历史 artifact 或执行 global prune。
- 不得修改业务代码、默认 Compose、Schema/migration、API、Router、RawItem Pipeline、R2/R3 harness、Frontend 或 PLUGIN-1。

现有未提交 `backend/experiments/browser-r3/` 是已知失败现场，可保留但不得修改、暂存或纳入 R1C 产物。

## 3. 必须形成的实证

1. 完整 Chromium 的精确 engine/channel/revision、executable path、全部文件 tree/hash、系统依赖与持久 license notices。
2. 更新后的 CycloneDX SBOM 与直接/传递依赖 license inventory；组件和 executable hash 必须指向实际完整 Chromium，而非 Headless Shell。
3. 相同锁定输入下两次独立 `--no-cache --pull=false` 构建；比较规范化 filesystem identity、SBOM hash 与差异原因。
4. 两个候选镜像均以 UID 10001、read-only rootfs、drop ALL、no-new-privileges、network none 通过锁定检查。
5. 在无公网环境中真实调用 Scrapling DynamicFetcher，对进程内确定性 fixture 完成启动、渲染、确定性终止和安全失败；Patchright/Playwright 直接 probe 只能作为补充，不能替代 DynamicFetcher。
6. 所有命令、exit code、版本、对象、原始证据、失败记录和精确清理结果可机器验证；不得使用 TBD、估算、仅配置审阅或未保存观察。

## 4. 验收与停点

- 任一依赖/revision/path/hash/license/双构建/DynamicFetcher 实测不完整，R1C 即 BLOCKED 并立即 STOP。
- 长构建前必须检查额度；任一窗口剩余比例小于或等于 5% 时保留工作树并停止。
- 通过时唯一结论为 `R1C PASS — READY FOR INDEPENDENT REVIEW`；不得自行执行 R2C、继续 R3、commit、push 或 PR。
- R1C 经独立复审并合并后，总控另行签发 R2C 准入。R2C 必须用 R1C 精确镜像完整回归 R2 网络证据；通过前 R3、R4-R5 与 WP-3 正式实现继续 BLOCKED。
