# FlowTracer ACQ-1 WP-3 R1D Runtime Identity v2

状态：Accepted（仅 R1D runtime/audit boundary 与可重建身份证据；本控制 PR 合并后生效）

前置基准：`main@df078762cb46a334a4db4f581a47ad595f96475d`

执行角色：Backend / Architecture

固定工作目录：`D:\FlowTracer-wt\backend`

目标分支：`feat/acq1-wp3-r1d-runtime-identity`

## 1. 问题与裁定

R2C 首次执行在网络矩阵前的 identity 硬门禁安全停止。浏览器和供应链核心身份全部匹配，但 R1C full-root 摘要无法由合并后的权威来源重建。原因是 R1C Dockerfile 使用 `COPY scripts` 将运行脚本与审计验证器一起放入最终镜像；运行证据生成后，审计验证器发生了不影响浏览器/runtime 的格式与验证增强，导致摘要陈旧。

禁止直接将 R2C 单次重建摘要设为期望、删除失败记录、忽略差异或在没有逐路径证据时声称“只有一个文件不同”。本阶段采用 ADR-032 的 Runtime Identity v2。

## 2. 唯一允许范围

- 仅新增 `backend/experiments/browser-r1d/`，并更新 `docs/42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md` 的 R1D 实际证据。
- 从已合并 R1C Dockerfile/locks/scripts 派生新的隔离证据包；不得修改或覆盖 `browser-r1/`、`browser-r2/`、`browser-r1c/`、`browser-r2c/` 或 `browser-r3/`。
- 最终 runtime 镜像中的项目脚本必须是显式 allowlist，只允许 `entrypoint.py` 与 `runtime_probe.py`。browser-tree、SBOM、license、identity 与 package validator 必须在独立 build/audit stage 或只读 build mount 中执行，不得存在于最终 runtime filesystem。
- 不得修改业务代码、默认 Compose、Schema/migration、公开 API、Router、RawItem Pipeline、Frontend、Integration、Release 或 PLUGIN-1。

## 3. Runtime Identity v2

每个候选镜像必须生成并持久保存完整 normalized filesystem manifest。算法必须语言环境无关、可机器复验，并对 symlink/特殊 entry fail closed。每条至少包含：

- 规范化绝对 path；
- entry type；
- mode、UID、GID；
- symlink target（仅 symlink）；
- 普通文件原始 bytes 的 lowercase SHA-256。

路径按 UTF-8/Unicode code point ordinal 顺序排列，manifest 使用确定性编码并记录自身格式版本、entry count、payload bytes 与 SHA-256。两个独立构建必须各自产生 manifest，且逐条与摘要完全一致；只报告一个总哈希不构成通过证据。

## 4. 必须形成的证据

1. 相同锁定输入执行两次独立 `--no-cache --pull=false --platform=linux/amd64` 构建；builder、tag、container 与 cache 唯一可归属。
2. Chrome for Testing `151.0.7922.34` / r1234、executable path/SHA、619-entry browser tree、Debian 206 lock/inventory、CycloneDX 231 components 与 license 206/206 精确匹配 R1C。
3. 两个最终镜像的项目脚本清单恰好为 `entrypoint.py`、`runtime_probe.py`；验证器和生成器在最终文件系统中不存在。构建时验证仍须实际执行，不能因移出 runtime 而省略。
4. 两个镜像均以 UID/GID 10001、network none、read-only rootfs、drop ALL、no-new-privileges、非 privileged、PID 128、memory 768 MiB、CPU 1、`/tmp` 256 MiB 运行。
5. 两个镜像均真实调用 Scrapling `DynamicFetcher`，使用显式完整 Chromium、`retries=1` 与受控 HOME/XDG/profile，完成 loopback fixture 渲染、安全失败、Crashpad 受控路径及进程/目录零残留验证。
6. 保存全部命令、exit code、逐路径 manifest、差异报告、原始日志、失败记录、版本、对象清单和精确清理结果；保护 R1/R2/R1C/R2C/R3 文件哈希及历史 Docker 对象。

## 5. 验收与停点

- 任一 runtime 脚本越界、audit 工具进入最终镜像、双 manifest 不一致、browser/SBOM/license 漂移、DynamicFetcher 失败、临时目录/进程残留或对象无法归属，判定 BLOCKED 并立即 STOP。
- 长构建前必须读取可靠的 5 小时和每周额度；任一剩余比例小于或等于 5% 时保存现场并停止。
- 所有证据文件必须 Git 可见且不被 ignore；证据 package tree 使用落盘的 locale-independent 算法验证。敏感值、正文、完整 URL query 与凭据不得进入证据。
- 仅清理本阶段明确创建的对象；禁止 global prune，不得触碰用户卷或历史证据对象。
- 通过时唯一结论为 `R1D PASS — READY FOR INDEPENDENT REVIEW`。Backend 不得自行 commit、push、PR、merge或开始 R2C/R3。
- R1D 经独立复审并合并后，总控另行重新激活 R2C；R3、R4-R5 与正式 WP-3 继续 BLOCKED。
