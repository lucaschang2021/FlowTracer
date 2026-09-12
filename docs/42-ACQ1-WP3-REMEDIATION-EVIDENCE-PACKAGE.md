# FlowTracer ACQ-1 WP-3 Remediation Evidence Package

状态：R1/R2 Accepted（Headless Shell historical）；R3 BLOCKED；R1C Accepted；R2C BLOCKED；R1D Admitted / Pending；R4-R5 Pending

用途：本文件是 `docs/41-ACQ1-WP3-REMEDIATION-EVIDENCE-ADMISSION.md` 的强制证据模板。必须按 R1→R5 顺序填写实际值；`TBD`、估算、未执行、仅配置审阅、仅 mock 或未保存的口头观察均不构成通过证据。

## 1. Identity 与通用记录

| 字段 | 必填实际值 / 证据 |
| --- | --- |
| `origin/main` | R1 `4630ff137e64004fb45e2370419b1f66d2e8d0bc`（PR #53 merge commit）；R2 `b6275cd4633207d23cff047d2b612aa4893a2888`；R3 `a0d30140c8bdb6665b0833f4d60defadce9c9166`（PR #57 merge commit） |
| evidence branch / commit | R1 `feat/acq-1b-browser-remediation-evidence@89ed802f4f2ac608a260f68637f1aaf541cd3143`；PR #54 merge commit `34364d0082e4ecdbe4331d77a21ef6d25c2fca8a`；R2 `feat/acq-1b-browser-remediation-evidence@7c6e778e05c34bb8341d6898eea729de5dc311b2`；PR #56 merge commit `c5799082ba8e0ae5edf8ddfb861e24de784cdf93` |
| host OS / architecture | Microsoft Windows 11 家庭版中文版 `10.0.26200`（build 26200），x64 |
| Docker / Compose / BuildKit | client/engine 29.7.2；Compose v5.4.0；Buildx v0.36.1-desktop.1 (`83d819cf8237b52ef45a2a9857eeb83a7b10977f`)；专用 BuildKit v0.32.2，镜像 `moby/buildkit@sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8` |
| Python / Debian | CPython 3.13.15（GCC 12.2.0），Debian 12 Bookworm，`amd64` |
| 工作目录 | `D:\FlowTracer-wt\backend` |
| 公网访问 | R1 候选验证容器显式 `--network none`；R2 Browser/fixture 网络均为 `internal=true`，控制 canary 仅发布唯一宿主 loopback 端口且代码无 outbound，所有 DNS/target 均为离线合成数据；未访问真实目标站点 |
| 初始对象清单 | fix builder 容器 `buildx_buildkit_flowtracer-r1-final-fix-builder0`（仅 `docker-init`/`buildkitd`）、专用 state volume 同名后缀 `_state`、可回收专用 cache 2.88 GB；fix images `3440b61564a0...` / `258cf127308b...`；另有非本次对象 `flowtracer-r1-final-builder`，不触碰；无 R1 业务容器/network |

每个闸门统一记录：开始/结束时间、完整命令、exit code、关键计数、原始证据路径、失败/P0/P1/P2、创建对象、清理命令和清理后对象清单。

## 2. R1 — Locked image、SBOM/license 与复现

| 项目 | 实际值 | 来源/命令 | 结果 | 证据路径 |
| --- | --- | --- | --- | --- |
| Browser package/extras | `scrapling[fetchers]==0.4.15`; Patchright 1.62.3; Playwright 1.62.0；Dockerfile frontend 与 target platform 均 digest/`linux/amd64` 固定 | `pyproject.toml`; `uv.lock`; `requirements.lock`; Dockerfile | PASS | `backend/experiments/browser-r1/` |
| 全部传递依赖与 lock hash | 22 个锁定外部 Python 包；uv `33df53e4853bf3c2c06050e8e30f1c538ac2d9f2320b5c2a1a121ff4d6d10b43`；requirements `93ecf377d3a0dba3abb0a6dbb818ffb566a496df528de70435fd9366da3c488b` | `uv lock`; `uv export --locked --no-emit-project --no-dev --format requirements-txt` | PASS | `backend/experiments/browser-r1/{uv.lock,requirements.lock}` |
| engine/channel/revision | Chrome for Testing headless shell 151.0.7922.34 / Chromium / r1234；FFmpeg r1011；301-entry path/type/mode/UID/GID/symlink/file-hash tree manifest | build-time `browser_tree_manifest.py --verify` | PASS | `browser-tree.manifest.json`; `evidence/build-comparison.md` |
| Debian system packages | Debian 12 snapshot `20260824T000000Z`，206 个精确版本，manifest SHA-256 `299a341b239c284c385ecac9d3882bdf29472b28421075b369009f998b54b83`；main/security 同 archive/timestamp/suite/component 切换为 HTTPS `snapshot-cloudflare.debian.org` 并分别经 APT/GPG 验证 | `dpkg-query -W`、官方等价入口 APT update 与构建期 `diff` | PASS | `backend/experiments/browser-r1/debian-packages.lock`; `evidence/{execution-ledger.md,main-snapshot-apt-diagnostic.json}` |
| base image digest | `python@sha256:c45a22ea000adfd9cda29364bbe7edd23001ce5cc2ad15857cfbf7766943b9ca`；Python 3.13.15；pip 26.2.1；Debian 12 | Dockerfile 与 runtime inspect | PASS | `backend/experiments/browser-r1/Dockerfile` |
| SBOM identity/hash | CycloneDX 1.6，231 components；真实 Chromium/FFmpeg executable hash 与独立 named notice hash；最终文件与两镜像生成流 SHA-256 均为 `ff1918f042833280e5e45b3f25da5159eed9b63e0c24d347b7f9628730eeadaa` | `generate_sbom.py`; `validate_sbom.py` | PASS | `backend/experiments/browser-r1/evidence/sbom.cdx.json` |
| dependency license inventory | 206/206 Debian package 有 license expression、raw header、持久 notice 相对路径和实际 SHA-256；仅单一已审阅标签映射精确 SPDX（5），其余使用 notice-backed `LicenseRef-Debian-Notice-*`（201）；两镜像生成流与落盘文件 SHA-256 均为 `bee9c30ae016be592521c383b9bb0be74f39892415ed28f9122d5b7ccced81da`；206 原始 notices 已保存且逐项 hash 复验 | `generate_sbom.py --debian-license-inventory`; `validate_sbom.py` | PASS | `evidence/{debian-license-inventory.json,debian-notices/}` |
| Chromium/engine redistribution terms | Chromium BSD-3-Clause + bundled third-party notices；FFmpeg LGPL-2.1-or-later；无 Widevine；实际 notices 持久保存；R1 不发布 registry | 精确版本官方来源与持久 notice | PASS | `evidence/{license-inventory.md,notices/}` |
| no-cache build 1 content identity | image `3440b61564a038df1397affe331ded16e42fc4b25de8c453b7ca129b567f01b9`；normalized content `2a255b61087479d73706e85601713398ed73387b53fb68690cd16dc75ae1a9c5` | dedicated BuildKit + `--no-cache --pull=false --platform=linux/amd64`; `image_identity.py` | PASS | `evidence/{build-comparison.md,execution-ledger.md}` |
| no-cache build 2 content identity | image `258cf127308b9bb825340f6cfbac17ddef62452f725fa24584acfeb3e288d12c`；normalized content `2a255b61087479d73706e85601713398ed73387b53fb68690cd16dc75ae1a9c5` | dedicated BuildKit + `--no-cache --pull=false --platform=linux/amd64`; `image_identity.py` | PASS | `evidence/build-comparison.md` |
| 双构建差异与解释 | OCI image/layer/timestamp/压缩大小因构建期 tar/OCI metadata 不同；路径、类型、mode、UID/GID、symlink target、文件字节的规范化身份及 SBOM 完全一致；两者均通过 browser-tree verifier 与 UID 10001、read-only rootfs、network none 离线渲染 | inspect + normalized identity + runtime probes | PASS | `evidence/build-comparison.md` |

R1 判定：`PASS — READY FOR INDEPENDENT REVIEW`。R1 P0/P1/P2=`0/0/0`。本次只完成 R1；R2-R5 未执行，WP-3 正式实现仍 BLOCKED。

R1 cleanup：已删除 `flowtracer-browser-r1:r1-final-fix-build1/2`、`flowtracer-r1-final-fix-builder` 及其可明确归属的 state volume/cache（清理前 2.88 GB）；清理后镜像、builder、容器、专用 volume 均不存在。固定 BuildKit 镜像 `sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8` 与非本次对象 `flowtracer-r1-final-builder` 已核验保留；未执行 global prune。

## 3. R2 — Controlled egress proxy/namespace

先附容器/network/namespace/proxy/Redis/fixture 的拓扑，以及每条 allow/deny 边、DNS 执行者和端口。

| 测试 | 预期 | 实际命令/结果 | 判定 | 证据路径 |
| --- | --- | --- | --- | --- |
| 获准 HTTPS CONNECT 到 fixture | allow 且逐目标复验 | Browser 仅经 `198.51.100.20:18080` CONNECT `fixture-r2.test:8443`；双解析与 peer IP 一致性通过；4 个 allow events | PASS | `backend/experiments/browser-r2/evidence/{browser-probe.json,proxy-events.jsonl}` |
| 每跳 redirect A/AAAA/IP/port 复验 | unsafe hop deny | safe redirect 重新 CONNECT 成功；unsafe redirect 到 metadata 地址返回 403；`connect_revalidations=3` | PASS | `backend/experiments/browser-r2/evidence/{browser-probe.json,proxy-events.jsonl}` |
| 混合 A/AAAA / DNS rebinding | deny | mixed A/AAAA=`mixed_answer`；两次解析答案变化=`dns_rebinding` | PASS | `backend/experiments/browser-r2/evidence/proxy-events.jsonl` |
| 私网/link-local/metadata/危险端口 | deny | loopback/private/link-local/metadata/multicast/reserved/unspecified/port 22 全部 403；共验证 13 类 policy denial | PASS | `backend/experiments/browser-r2/evidence/proxy-events.jsonl` |
| Browser 直连 fixture/IP/域名 | deny | fixture、decoy、live host gateway canary、control-network canary 共 4 次均精确为 `ENETUNREACH` errno 101；validator 禁止 timeout、`ECONNREFUSED` 或其他 `OSError` | PASS | `backend/experiments/browser-r2/evidence/{browser-probe.json,control-client.json,topology.json}` |
| 系统 DNS / host gateway / host network | deny | 宿主 readiness attempt 1 收到 marker；独立 control client 经同一 `192.168.65.254:49175` 收到 marker，而 Browser 对该精确 endpoint 为 errno 101；DNS 精确记录 A/AAAA 各 1、AA=true、RA=false、upstream=0；无 host network | PASS | `backend/experiments/browser-r2/evidence/{browser-probe.json,control-client.json,dns-events.jsonl,topology.json}` |
| Docker socket / 未声明服务 | deny/不存在 | 实际 inspect：全部 8 服务 UID 10001、read-only、drop ALL、no-new-privileges、精确非 host NetworkMode；仅 host canary 有精确 loopback PortBinding；Docker socket 不存在 | PASS | `backend/experiments/browser-r2/evidence/{browser-probe.json,topology.json}` |
| Browser 绕过 proxy | deny | proxy 仅接受 CONNECT，absolute-form GET 返回 405；Browser 无 fixture/control network route；policy log 精确 4 allow/14 deny，process healthcheck 零污染 | PASS | `backend/experiments/browser-r2/evidence/{browser-probe.json,proxy-events.jsonl,topology.json}` |

R2 判定：`ACCEPTED`。R2 P0/P1/P2=`0/0/0`；独立复审、Backend CI 与 PR #56 合并均通过。cleanup 后 `127.0.0.1:49175` exclusive bind attempt 1 成功，R1 tag 经 inspect 保留为 `sha256:83464fd58248b3af79903c3d4ce3d33140f498bdfef4d9efec9c4552718a3eec`。实证命令、版本、对象与清理明细见 `backend/experiments/browser-r2/evidence/execution-ledger.md`。R3 已由独立控制文档准入；WP-3 正式实现仍 BLOCKED。

## 4. R3 — Application interception matrix

首次执行停点：`BLOCKED`，P0/P1/P2=`0/1/0`。唯一项目 `flowtracer-r3-exec-20260909-a` 在 7.155 秒内非超时失败；DynamicFetcher 寻找 `/opt/browser-r1/chromium-1234/chrome-linux64/chrome`，但 R1 镜像仅含 `/opt/browser-r1/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell`。DynamicFetcher 未真实启动，因此不得填写或继续下列矩阵。临时 containers/networks 均已归零，无新增 volume/image/cache，R1 镜像身份保持不变。

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

### 4.1 R1C / R2C 纠偏链

- R1C：在独立 `backend/experiments/browser-r1c/` 锁定完整 Chromium runtime，生成全新 manifest、SBOM/license、双 no-cache 构建和规范化身份；真实 DynamicFetcher 必须在无公网的进程内 fixture 上完成启动、渲染、终止与安全失败。
- R1C 不得覆盖、改写或复用 R1 tag/证据文件冒充新结果；实际 revision、path、digest、tree、SBOM hash 与 license notice 必须来自运行证据。
- R2C：R1C 验收合并后，必须用该精确镜像完整重跑 R2 controlled egress/namespace 证据；不得仅引用旧 Headless Shell 容器结果。
- R3 只有在 R1C、R2C 分别 PASS、独立复审并合并后，才可重新准入。

#### R1C 实际证据（2026-09-13）

| 项目 | 实际值 | 判定 / 证据路径 |
| --- | --- | --- |
| 执行基准与范围 | `origin/main@fdcb4335982d69728adcfc29cfa422577a6ff43f`；分支 `feat/acq-1b-browser-remediation-evidence`；仅新增 `backend/experiments/browser-r1c/` 并更新本节，未改业务代码、默认 Compose、Schema/API/Pipeline 或 R1/R2/R3 | PASS；`backend/experiments/browser-r1c/evidence/versions.json` |
| 完整 Browser artifact | Google Chrome for Testing `151.0.7922.34` / Chromium r1234；精确 executable `/opt/browser-r1c/chromium-1234/chrome-linux64/chrome`，SHA-256 `0b20b130e7edd9dd51873be867761295fe0cfad490c2b9a64f95bd3cfc08fa71`；FFmpeg r1011 SHA-256 `460d44f3416005662f528d4b92e7b94ace924e8a0288106d3803b73c56eaadc8`；完整 tree 619 entries，manifest SHA-256 `197d911b97e67180aef120d7cffb974436dcbcbe4acce566809b6d0e1363390a` | PASS；`browser-tree.manifest.json`、`evidence/sbom.cdx.json` |
| Debian / SBOM / license | Debian snapshot 与 206-package lock 保持精确，lock SHA-256 `299a341b239c284c385ecac9d3882bdf29472b28421075b369009f998b54b83`；CycloneDX 1.6 共 231 components，SHA-256 `a8d6ae5e450b10bd40d90f6d56a0e69742479cfaff79398c0d2fb0696cfcf774`；206/206 Debian inventory 与 notices，inventory SHA-256 `bee9c30ae016be592521c383b9bb0be74f39892415ed28f9122d5b7ccced81da`；5 个精确 SPDX 标签，其余保持 notice-backed `LicenseRef-Debian-Notice-*` | PASS；`evidence/{sbom.cdx.json,debian-license-inventory.json,debian-notices/,notices/}` |
| 两次独立构建 | 唯一 builder/session `flowtracer-r1c-20260913-p1-runtime-dirs-*`；两次均为 `--no-cache --pull=false --platform=linux/amd64`；image IDs 分别 `sha256:72fa7e697fe4460d2012bcd7ebf5daee646a776bd2d4c6a9785949f908df8c23`、`sha256:bd7540f7ed6652f3ea7dc9e95e46cd1c44e80a462177a02b4714bfdf8e94dee5`；root-only inspection 的 normalized identity 均为 `6ef0e9ecb34d0a72c2135282b06548f7bdac92be27f8df2444188216013bddea`；两镜像 SBOM/inventory streams 相同；10 份原始 build 输出已无损改为 Git 可见 `.txt`，旧/新路径、bytes 与相同 SHA-256 由独立 proof 复验 | PASS；`evidence/{build1.txt,build2.txt,build-comparison.json}`、`log-rename-sha256.json` |
| root inspection 与 runtime 隔离 | identity inspection 明确 `--user 0` 且 network none/read-only/drop ALL/no-new-privileges；两个候选 runtime 均为 UID/GID `10001:10001`、network none、read-only rootfs、drop ALL、no-new-privileges、非 privileged、PID 128、memory 768 MiB、CPU 1、`/tmp` 256 MiB `rw,nosuid,noexec` tmpfs；外层 hard deadline 120 秒 | PASS；`evidence/build-comparison.json` |
| 真实 DynamicFetcher | 两镜像均由 Scrapling 0.4.15 `DynamicFetcher.fetch` 使用 `retries=1`、显式 full executable 与独立 `user_data_dir`；进程内 loopback fixture 实际渲染 `dynamic-rendered`，render 分别 2410/3762 ms；关闭后的 fixture 均安全失败为 `Error`，分别 3039/2058 ms；非 Patchright 直调、非参数验证失败 | PASS；`evidence/build-comparison.json` |
| Crashpad 与临时目录 | runtime-only `HOME=/tmp/flowtracer-r1c-home`、`XDG_CONFIG_HOME=/tmp/flowtracer-r1c-config`、`XDG_CACHE_HOME=/tmp/flowtracer-r1c-cache`；每次调用前由 UID10001 创建独立 mode 0700 目录并拒绝 symlink/越界；实际 database `/tmp/flowtracer-r1c-config/google-chrome-for-testing/Crash Reports`，UID/GID 10001、mode 0700；render/failure 前后 HOME/config/cache/profile 均验证 absent，Chrome/Crashpad process 均零残留 | PASS；`evidence/build-comparison.json` |
| 执行与清理 | `2026-09-13T00:48:10.354776+08:00` 至 `00:57:34.493990+08:00`，564.139 秒，53 条命令；最终 builder、2 containers、3 R1C tags、专用 volumes 全部不存在；未 global prune；历史 R1 builder/images/固定 BuildKit image 前后完全一致；受保护 R3 12 文件 SHA-256 前后完全一致；四个失败 attempt 均保留；R1C package 共 702 个实际文件且 702 个均 Git 可见；locale-independent UTF-8 ordinal/code-point package tree 共 95,463 payload bytes，SHA-256 `1983e42a55e2f896b88c4dd38cb113071026079a26cdb8167fb5f299af33699c`；package-local `.gitattributes` 禁止 EOL clean 转换并保留 text diff，原始 evidence whitespace 仅关闭 diff-check 告警、不改字节 | PASS；`evidence/{execution-ledger.json,cleanup.json,protected-docker-objects.json,protected-r3-sha256.json}`、`attempts/`、`log-rename-sha256.json`、`.gitattributes` |

R1C package tree 的机器可解析声明：`R1C_PACKAGE_TREE_V1 files=702 payload_bytes=95463 sha256=1983e42a55e2f896b88c4dd38cb113071026079a26cdb8167fb5f299af33699c`。算法递归包含 `browser-r1c/` 下全部普通文件，不读取 Git ignore、扩展名或 locale，也无隐式排除；symlink/其他 entry type fail closed。相对路径统一 `/` 后按 Unicode code point 排序，每个文件以原始 bytes 计算 lowercase SHA-256，再将 `<relative-path> <lowercase-content-sha256>\n` 编码为 UTF-8（无 BOM、最后一行保留 LF）并串接取最终 SHA-256。轻量复验命令：`py -3.13 -B backend/experiments/browser-r1c/scripts/validate_sbom.py backend/experiments/browser-r1c/evidence --package-tree-doc docs/42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md`。

R1C 判定：`ACCEPTED`。R1C P0/P1/P2=`0/0/0`；独立复审 ALLOW，Backend CI 通过，candidate `787a0df0548e05431fa60426f48f239ba7195465` 已由 PR #60 合并为 `main@df0c3512080f384dbd6c820d7627cbe721e37422`。该结论只关闭 R1C；R2C 由独立准入文件激活，R3 继续暂停。

#### R2C 完整 Chromium controlled egress 回归

执行基准：`main@df0c3512080f384dbd6c820d7627cbe721e37422`。准入与停点规则见 `docs/46-ACQ1-WP3-R2C-ACTIVATION.md`。

R2C 首次执行在 identity 硬门禁处判定 BLOCKED，P0/P1/P2=`0/1/0`：Chrome 版本/path/SHA、619-entry browser tree、Debian 206、SBOM 231 与 license inventory 均匹配，但 merged-authoritative source 重建得到的 full-root identity 与 R1C 运行期摘要不一致。网络、proxy、fixture 与 DynamicFetcher 矩阵均未启动；本次对象已精确清理。

只读诊断证明 R1C 最终镜像复制了审计用 `validate_sbom.py`，该文件在 R1C 运行完成后因可提交性/Ruff 修复改变字节；旧证据未保存逐路径 full-root manifest，不能诚实反演或现场缩窄旧期望。因此 R2C 暂停，不得直接把单次重建摘要写成新基线。

#### R1D Runtime Identity v2

R1D 准入与验收规则见 ADR-032 和 `docs/47-ACQ1-WP3-R1D-RUNTIME-IDENTITY.md`。实际证据必须保存在独立 `backend/experiments/browser-r1d/`，不得覆盖 R1C 或 R2C 失败现场。

R1D 必填：最终 runtime 脚本 allowlist、审计工具不进入 runtime 的证明、两个独立 no-cache 镜像的逐路径 normalized manifests/摘要、R1C browser/SBOM/license identity、两个镜像的真实 DynamicFetcher/Crashpad/硬化/清理结果、历史资产保护哈希。通过前 R2C、R3 与 R4-R5 均暂停。

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
