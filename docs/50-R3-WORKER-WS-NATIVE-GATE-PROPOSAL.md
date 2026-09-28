# R3 Worker WebSocket 原生拒绝机制提案

状态：PROPOSED / NOT ADMITTED。仅架构研究草案，不是 ADR 生效、实现准入或 R3 PASS。
日期：2026-09-28。
已核验本地来源：`origin/main@9e5ec8ccbe9308477d3ef0cd78859d0afa81b5e7`；R3 准入按 `49-ACQ1-WP3-R3-REACTIVATION.md`。

## 1. 当前裁定

- Backend 上报唯一 `flowtracer-r3-native-worker-ws-20260928-01` 阴性诊断；总控尚未独立读取原始证据，不把报告当独立验收。
- 在真实 Dedicated Worker 的 `Network.setBlockedURLs` ACK 后，WSS 仍触发 proxy deny。仅该冻结环境/命令候选无效，不泛化为所有 Chromium 机制无效。
- R3 仍 BLOCKED；R4-R5、正式 WP-3 及后续阶段均未准入。
- 不追认历史会话为 PASS，不修改历史 seal，不以 mock、fixture 自报或代理单层证据代替应用拦截。
- 不采纳默认禁止所有 Worker 作为未经批准的能力缩减。

### 1.1 执行路径来源更正

Backend 最新只读报告指出：冻结 Scrapling `fetchers/chrome.py` 的 DynamicFetcher 调用 `DynamicSession`，而 `_controllers.py` 使用 `playwright.sync_api`；`_stealth.py` 才使用 Patchright。按该报告，实际 DynamicFetcher 驱动为 Playwright 1.62.0。总控尚未独立核验这些源码行，但在证明相反前，停止将已安装 Patchright 1.62.3 当作实际调用路径。

实际待核验文件：`/usr/local/lib/python3.13/site-packages/playwright/driver/package/lib/coreBundle.js`，报告给出的冻结 SHA256 为 `3258d1cf334c6afc95f22aa9c292436cb976b391e0437f1359c83b84f0cb9d66`。不能用 Patchright bundle 代替此文件来证明默认 argv、控制通道或 Worker 行为。之前真实 CDP 命令 ACK 后仍抵达代理的阴性观测保留；仅修正驱动归属与静态推断来源，不重封历史证据。

Backend 还报告 `_controllers.py` 的 `page_setup` 异常会被捕获后继续 `page.goto`。因此扩展就绪检查仅在 page_setup 抛错的方案不满足 fail-closed。必须从真实驱动控制流证明外层终止整个 context/browser，或在导航前拒绝建立未通过安全预检的执行环境；目前尚未授权任何实现。

## 2. 单一候选及依据

候选是浏览器原生 Manifest V3 declarativeNetRequest（DNR）静态规则，动作为 `block`，资源类型为 `websocket`，无域、tab 或 initiator 排除。它是现有应用侧 NetworkPolicy 的候选执行机制，不是新产品插件系统，也不涉及 PLUGIN-1。

官方依据：

1. [DNR API](https://developer.chrome.com/docs/extensions/reference/api/declarativeNetRequest)：声明请求前规则评估、`websocket` 资源类型及阻断动作；调试匹配事件限 unpacked extension 的 feedback 权限。
2. [Chromium DNR browser tests](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/chrome/browser/extensions/api/declarative_net_request/declarative_net_request_browsertest.cc)：包含真实 WebSocket 阻断测试。该链接是移动 main，不是冻结 Chromium 151 源码或 Worker 覆盖证明。
3. [Chrome 团队 load-extension 公告](https://groups.google.com/a/chromium.org/g/chromium-extensions/c/1-g8EFx2BBY)：Chrome for Testing 保留该加载方式。它不证明冻结驱动的具体启动参数允许扩展。
4. [扩展 headless 测试说明](https://developer.chrome.com/docs/extensions/how-to/test/end-to-end-testing)：支持 new-headless 测试路径；不将文档中的历史默认值推定为冻结版本现状。

推论：有理由调查浏览器原生握手拒绝，而不是继续枚举 CDP 命令。尚不能断言冻结 runtime 支持或任意 Worker 全覆盖。

## 3. 必须先解决的可行性问题

Backend 仅静态核对当前锁定源码和本地既有产物；缺实际 Playwright bundle 时，先受控只读提取并按本次实际 runtime manifest 逐文件比对，不凭其他包同名文件判断：

1. DynamicFetcher 能否显式加载唯一只读本地扩展；锁定启动参数是否带有冲突的 disable-extensions 或 incognito/context 行为。
2. 静态规则是否在第一次目标导航和 Worker 首行为前生效；不能只依赖异步 listener 先后或合作式 Worker ready 握手。
3. 扩展与页面隔离，页面不能卸载、禁用或替换规则；规则健康检查失败或扩展被卸载必须关闭上下文，不能降级为 proxy-only。
4. `onRuleMatchedDebug` / 实际匹配查询是否能提供系统来源的 extension ID、ruleset/rule ID、request ID/type、时间、tab/frame/initiator（缺项明确标记）；不能假设 DNR ID 与 CDP ID 相同。
5. 原生规则强制阻断与诊断 receipt 的生命周期分开：不以 debug listener 存活充当阻断引擎生效，不遗漏事件冒充不存在请求。
6. page、Dedicated/shared/nested Worker、service worker 网络请求的覆盖必须分别实证；DNR 不覆盖 service-worker 本地合成响应/CacheStorage 的全部语义，不能替代整个 service-worker 矩阵。
7. 全局 `websocket` 拒绝不得意外阻断本地必要的自动化控制通道。优先现有本地 pipe；不能为解决控制通道问题添加任意 WS 放行。
8. 不新增依赖、下载第三方扩展、修改冻结 bundle、扩大容器权限或资源；现阶段不改任何 runtime 启动方式。

不能证明时输出具体 NO-GO，不为了使候选成立追加框架或泛化功能。

## 4. 后续提案验收条件（尚未授权执行）

若静态可行，先冻结最小 extension manifest/rules/receipt、启动与失败关闭顺序、路径与 SHA，再由总控签发独立有界实验许可。

- Browser 二进制/依赖和 R1E authority 不得暗改。新扩展须有单独可验证资产 manifest，且必须裁定是否属于 runtime 固定输入；若需新镜像身份则走重新冻结/复验，不能声称旧 authority 自动覆盖。
- 新启动参数和只读 mount 会改变受控执行配置，即使镜像字节不变也须独立审查，不按旧 R3 许可暗自引入。
- 唯一真实会话、确定退出与精确清理；当前 hardening 和 proxy 拒绝策略保持。
- 正向活性证明真实 DynamicFetcher 导航和未包装 Worker 正常执行；两种 ws/wss 的原生构造触发可信规则匹配和应用失败事件，目标无 proxy 转发、fixture 接收为零。
- 独立 proxy 403 负对照仍必需。应用预连接拒绝时主请求可以不抵达 proxy，不能强求双层同时处理同一连接。
- 候选缺失/规则未启用、错规则/关联、mock-only、receipt-only、proxy allowed/relay、fixture 接收、缺活性/终态/身份以及生命周期故障均必须拒绝。
- 能力 probe 阳性不等于九类 R3 矩阵通过；非合作性首行为和衍生执行域实证仍须完成。

## 5. 当前允许的下一步

仅 Backend 完成真实 Playwright 驱动来源核验，提交默认 argv/pipe、持久 context、扩展加载入口和 fail-closed 控制流依据。允许范围由总控单独消息限定；本提案本身不授权 Docker 资源操作。

随后由总控完成实验控制包：准确最小权限、唯一静态规则、观测来源与关联、首导航前生效/失败关闭顺序、执行输入 manifest 及身份归属、逐 actor 实证和阴性退出条件。尚未冻结的精确值不得由 Backend 自定。

禁止本提案自行触发构建、Browser 会话、依赖安装、runtime 或公开契约变更、commit/push/PR。

总控待核验报告后决定是否受理 ADR/实验准入；CURRENT-GATE 和既有阶段结论不变。

## 6. 报告精度补记

Backend 更正最新清理报告：继承字段实际为 `host_port_available=false`，对应未启用的 49274 host-canary。它不能当本 session 端口清理通过证据，也不能当该 session 的资源泄漏；须独立根据本 session 实际创建对象核验。这里记录报告更正，不回写历史 evidence。
