# FlowTracer ACQ-1 WP-3 R1E Deterministic Account Metadata

状态：Accepted（仅 R1E 系统账户确定性与 Runtime Identity v2 新 authority；本控制 PR 合并后生效）

前置基准：`main@aac317d5ad1bf6f041c5a75d4ce2da2479bb14ba`

执行角色：Backend / Architecture

固定工作目录：`D:\FlowTracer-wt\backend`

目标分支：`feat/acq1-wp3-r1e-deterministic-account`

## 1. 问题与裁定

R2C-A2 在网络矩阵前安全停止。Runtime Identity v2 的 10,340 个路径中仅 `/etc/shadow` 字节不一致；只读诊断确认 `useradd` 将 UTC 构建日写入 `flowtracer` 账户的 `sp_lstchg`。R1D 两次构建同日，因此没有证明跨日可重建性。

不得排除 `/etc/shadow`、忽略该差异、放宽 manifest、直接替换 authority，或改写 R1D/R2C-A2 的失败证据。本阶段采用 ADR-033 的确定性账户元数据修复。

## 2. 唯一允许范围

- 仅新增 `backend/experiments/browser-r1e/`，并更新 `docs/42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md` 的 R1E 实际证据。
- 从已合并 `browser-r1d/` 派生隔离包；不得修改或覆盖 `browser-r1/`、`browser-r2/`、`browser-r1c/`、`browser-r1d/`、`browser-r2c/` 或 `browser-r3/`。
- 在创建 UID/GID 10001 的锁定非密码 `flowtracer` 账户后，显式固定 `sp_lstchg=0`。允许等价、可审计且不产生密码凭据的标准工具命令。
- 增加不输出 shadow 内容的 fail-closed 结构验证：账户恰好一条、字段数恰好 9、密码字段保持锁定状态、字段 3 精确为 `0`；日志不得包含完整 shadow 行或密码字段内容。
- 最终 runtime 的项目脚本仍只允许 `entrypoint.py` 与 `runtime_probe.py`；审计工具不得进入 final filesystem。
- 不得修改业务代码、默认 Compose、Schema/migration、公开 API、Router、RawItem Pipeline、Frontend、Integration、Release 或 PLUGIN-1。

## 3. 新 Authority 验证

1. 相同锁定输入执行两次独立 `--no-cache --pull=false --platform=linux/amd64` 构建；必须各自产生完整 Runtime Identity v2 manifest。
2. 两份 manifest 必须逐条、payload bytes、payload SHA-256 与 manifest SHA-256 完全一致；`/etc/shadow` 必须包含在 identity 中，不得特殊排除或规范化其内容。
3. Chrome for Testing `151.0.7922.34` / r1234、619-entry browser tree、Debian 206、CycloneDX 231、license 206/206 与 notices 必须实际复验且保持一致。
4. 两个镜像均须重复 UID/GID 10001、network none、read-only rootfs、drop ALL、no-new-privileges、非 privileged、PID 128、memory 768 MiB、CPU 1、`/tmp` 256 MiB。
5. 两个镜像均须真实执行 Scrapling `DynamicFetcher` 的 loopback render 与安全失败，验证受控 HOME/XDG/profile、Crashpad UID/GID/mode、进程及临时目录零残留。
6. 保存命令、exit code、完整 manifests、差异报告、原始日志、保护资产和精确清理结果；旧 R1D authority 与 R2C-A2 BLOCKED 证据必须前后字节一致。

## 4. 验收与停点

- 任一账户结构、锁定状态、`sp_lstchg`、manifest、browser/SBOM/license、runtime 或清理不一致，判定 BLOCKED 并立即 STOP。
- 长构建前检查可靠额度；任一窗口剩余比例小于或等于 5% 时保存现场并停点。
- 所有证据必须 Git 可见且不被 ignore；只清理本阶段唯一归属对象，禁止 global prune。
- 通过时唯一结论为 `R1E PASS — READY FOR INDEPENDENT REVIEW`。Backend 不得自行 commit、push、PR、merge或开始 R2C/R3。
- R1E 经独立复审并合并后，总控另行重新激活 R2C；R3-R5 与正式 WP-3 继续 BLOCKED。
