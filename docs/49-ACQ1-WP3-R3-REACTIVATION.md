# FlowTracer ACQ-1 WP-3 R3 Reactivation

状态：待本控制 PR 合并后生效；仅 R3 Application interception matrix 证据

来源基准：`main@c584fd06ff136025dc6a0aba9815291b16682aa2`（R2C PR #68 merge commit）；本控制 PR 合并后的 `main` 必须是其后代

执行角色：Backend / Architecture；固定工作目录：`D:\FlowTracer-wt\backend`；目标分支：`feat/acq1-wp3-r3`

## 1. 准入依据与边界

R3 首次执行因 R1 Headless Shell 与 Scrapling DynamicFetcher 不兼容而 BLOCKED，原始失败证据保持不变。R1C 完整 Chromium、R1D Runtime Identity v2、R1E 跨日确定性账户与 R2C-A4 controlled egress 已分别通过独立复审、Backend CI 和合并；R2C-A4 P0/P1/P2=`0/0/0`。本控制 PR 合并后，仅重新准入 `docs/41-ACQ1-WP3-REMEDIATION-EVIDENCE-ADMISSION.md` 第 3 节的 R3，不追认旧 R3 为 PASS。

允许在新的 Backend 任务和独立 `feat/*` 分支中，仅新增隔离的 `backend/experiments/browser-r3/` R3 新会话 harness/fixture/proxy/验证器/证据，并填写 `docs/42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md` 的 R3 实际值。先盘点并保护原有 R3 失败现场及未跟踪文件，使用唯一新会话名和证据路径；不得覆盖、移动或改写 R1/R2/R1C/R1D/R1E/R2C 与旧 R3 的资产。可最小复用已合并 R1E runtime 和 R2C-A4 受控拓扑，但不得降低 NetworkPolicy、镜像身份、容器权限或资源限值。

本准入不包含 R4-R5、WP-3 正式实现、默认 API/worker/Compose、Router、RawItem/Document Pipeline、Schema/migration、公开 API、PLUGIN-1、Frontend、Integration 或 Release。禁止真实目标站点、公网测试依赖、凭据/登录态、CAPTCHA/反访问控制绕过、host network、privileged、Docker socket、global prune。

## 2. R3 必证矩阵

对 navigation、redirect、iframe、script、XHR/fetch、WebSocket、download、popup、service worker register/update/fetch 逐面记录：本地 fixture、预期与实际、应用 event/hook、R2C 网络/proxy 观察、policy/scope/budget、fail-closed 结果。每面必须同时具有真实 DynamicFetcher 驱动的应用层拦截证据和受控出口网络层证据；不能使用 mock、仅配置审阅或 R2C 的历史网络结果替代本次双层观察。

WebSocket 与 download 默认拒绝，且请求不得抵达 proxy 的允许转发路径。redirect 每跳复验；popup、iframe、script、XHR 和 service worker 的衍生请求也必须处于同一策略/预算边界。任一面缺失、旁路、hang、无法归因或只有单层证据，即判定 R3 BLOCKED 并停止。

真实 Scrapling `DynamicFetcher` 必须使用显式完整 Chromium executable，在隔离环境中证明启动、页面渲染、确定性终止与安全失败；不得以 Patchright/Playwright 直调替代。候选镜像/运行时身份必须与已合并 R1E authority 及 R2C-A4 证据一致。

## 3. 验收、清理和停点

- 记录完整命令、exit code、矩阵逐项原始事件、镜像/进程身份、拓扑、开始/结束时间、创建对象与精确清理结果；证据不得包含秘密、正文或完整 URL query。
- 验证器机器拒绝缺失请求面、单层证据、WebSocket/download 放行、timeout 冒充成功、身份/计数不一致；测试与证据仅使用本地 fixture、保留地址和合成 DNS。
- 唯一命名并精确清理本次 builder、image、container、network、volume/cache、loopback 端口和 Browser 进程；保护既有 Docker 对象与历史文件，不执行全局清理。
- 长构建/全量测试/外部提交前检查两档额度；任一剩余比例不高于 5% 即停点保留现场。
- 通过时唯一允许结论为 `R3 PASS — READY FOR INDEPENDENT REVIEW`。Backend 必须向总控提交阶段报告并停止，不得自行 commit、push、PR、merge 或进入 R4。总控独立复审并完成 R3 PR 合并后，才可另行签发 R4 准入；R1→R5 全部验收后仍需独立 WP-3 Contract Addendum 与正式 Admission。
