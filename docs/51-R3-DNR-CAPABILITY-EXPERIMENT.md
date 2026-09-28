# R3 DNR WebSocket Capability Experiment — 控制包

状态：FROZEN DRAFT / NOT EFFECTIVE；仅在本控制包通过 Review、合并并获总控发送精确启动基准后生效。
当前 R3 仍 BLOCKED；不准入 R4，不宣称正式应用拦截实现。
来源基准：`origin/main@9e5ec8ccbe9308477d3ef0cd78859d0afa81b5e7`。
关联提案：[50](50-R3-WORKER-WS-NATIVE-GATE-PROPOSAL.md)；既有准入：[49](49-ACQ1-WP3-R3-REACTIVATION.md)。

## 1. 架构裁定与最小目标

现有 Frame JS WebSocket mock 不能证明 Worker 强制拒绝；真实原生 `Network.setBlockedURLs` 候选在一次 WSS Worker 诊断中无效。下一单一候选为 Chromium MV3 DNR 原生静态 WS block，不修改 Playwright/Chromium bundle，不禁用全部 Worker。

裁定仅受理一个能力实验：在真实 Scrapling DynamicFetcher、实际 Playwright 1.62.0、冻结完整 CfT 151.0.7922.34/persistent/headless/pipe 路径，证明 Page 和 Dedicated Worker 的 ws/wss 请求由不可合作绕过的浏览器规则拒绝。不得切 Stealth、直接 Playwright fetch、Selenium 或外部 CDP。

该机制属于现有 NetworkPolicy 的候选执行 adapter，不是新架构层、插件产品或 PLUGIN-1。其他 R3 面及 Shared/Nested/Service Worker 均保持待证；不以此能力实验替代九类矩阵。

## 2. 唯一扩展契约

实现文件限制为 `manifest.json`、`rules.json`、`observer.js`、`audit.html`、`audit.js`；只读目录 `/opt/flowtracer-r3-dnr`。代码只用于原生拒绝、可信就绪/匹配审计和有界证据读回，不得采集页面正文。

Manifest 精确字段：

```json
{
  "manifest_version": 3,
  "name": "FlowTracer R3 WS Deny Capability",
  "version": "0.1.0",
  "minimum_chrome_version": "151",
  "permissions": ["declarativeNetRequest", "declarativeNetRequestFeedback", "storage"],
  "background": {"service_worker": "observer.js"},
  "declarative_net_request": {
    "rule_resources": [{"id": "ws_default_deny_v1", "enabled": true, "path": "rules.json"}]
  }
}
```

不得添加 host_permissions、content_scripts、externally_connectable、web_accessible_resources、其他权限或远程脚本。`storage` 仅用于 extension-only `storage.session` 审计，不得使用 sync/local、用户数据或外网。

`rules.json` 精确语义（唯一规则，无其他条件/例外）：

```json
[{"id": 1, "priority": 1, "action": {"type": "block"}, "condition": {"resourceTypes": ["websocket"]}}]
```

禁止 allow/allowAllRequests、动态/会话规则、按域/tab/initiator 排除、responseHeaders 条件或控制 WS 白名单。

额外启动参数只准 `--load-extension=/opt/flowtracer-r3-dnr` 与 `--disable-extensions-except=/opt/flowtracer-r3-dnr`，通过现 extra_flags；保留原安全默认、完整 executable、代理、headless/persistent/pipe。只允许唯一该路径；若现冻结运行不接受，BLOCKED，不添加兼容/unsafe flags。

extension ID 不自行发明或预填。Backend 从实际路径/浏览器实例发现并验证，记入本次执行输入及可信审计；无意外非组件扩展。manifest/rules/observer/audit 五文件精确 SHA256 在离线产物报告中生成，由总控确认后才允许真实 session，不能用未定 hash 启动。

## 3. 运行输入与安全边界

R1E 镜像 authority 保持：manifest SHA `f8d8bd0b64dfac53e244b00f29fbc9f18ed44b94491323b3f49ba2af191912e8`；payload SHA `5f4cf5acdf06a86f9b8907375f6f8f239ecf18152762b889f1e254b01e447e3b`。镜像字节与新 mount/argv 的身份分别检查，不冒称原 authority 覆盖扩展。

新执行输入 manifest 包含五文件与 harness/validator/proxy/fixture 的 path/SHA、schema version、挂载路径/只读属性、完整批准 argv、session 名、context 模式、规则读回及实际 extension ID。候选副本在启动前和结束后比对；本次身份不修改历史 authority。任何必须改镜像/bundle的方案 STOP，另提 ADR/身份准入。

保持 UID10001、PID128、memory768m/CPU1、只读 root、现 tmpfs、cap-drop/no-new-privileges、既有内部拓扑/受控代理；不 host-network/privileged/Docker socket。扩展目录不得来自不可信 fixture/网页，也不改变共享 Browser/API/worker。

## 4. 就绪与 fail-closed 生命周期

外部监督必须在启动 DynamicSession 前启用，不只覆盖 page_action。真实 probe 容器启动至自然退出硬上限 120 秒；超时关闭/强制停止本次专属容器，结论 BLOCKED。该诊断监督不是 R4 已验收的证明。

启动只允许本地初始 about:blank 与扩展内部审计页。前置预检上限 15 秒，确认：只读文件 hash/实际扩展身份；唯一 enabled static ruleset；dynamic/session rules 为空；匹配 observer 已注册，审计 storage.session 对 content scripts 不暴露；系统侧读取实际扩展 context，非页面自报。

`page_setup` 异常会被 Scrapling 捕获后继续 goto，禁止只抛异常作安全拒绝。预检失败先锁存拒绝，显式关闭整个 persistent context/browser，并等待关闭成功；正常关闭预算 5 秒。未知/失败时由已启用外部监督终止本次 probe 进程/容器，不能 callback fallthrough。若现入口不能保证这一路径，离线实现 NO-GO，不开始真实 session。

只有就绪已证后才允许目标 fixture goto。Fetch retries 固定 1；外层不得把预检/策略失效重新启动为普通采集重试。规则异常、扩展卸载、审计连接/事件丢失、队列溢出均终止并 BLOCKED，不降级为 proxy-only。不为日志强制永久唤醒 service worker；睡眠/重启和原生规则执行分离，证据无法完整恢复时不能 PASS。

此实验不宣称已证明 Chrome 启动前所有后台流量受 DNR 管理；已有 egress 必须始终独立默认拒绝。是否满足首个不可信导航前静态规则生效必须由本次真实事件和负例证明。

## 5. 可信 receipt 与界限

仅 extension 内注册的 `onRuleMatchedDebug` 是规则匹配来源，via 实际扩展 audit context/现 trusted CDP pipe 读回；fixture runtime消息/console不作为 authority。

Receipt 固定字段：`schema_version="r3-dnr-receipt-v1"`、session、实际 extension ID、ruleset ID、rule ID、block action、resource type、浏览器 request ID、timestamp、sequence、observer epoch、safe request fingerprint，以及实际可提供的 tab/frame/document/initiator 字段。未知字段为 null 并说明；不得假造 Worker target 或填写 native_connect_calls=0。

原始 URL 仅在可信 observer 内暂存用于生成安全指纹，输出不含 query/fragment/秘密；fixture URL无query，仅唯一受控 path 区分 Page/Worker、ws/wss。CDP target/session/request另记，禁止假定两系统 request ID 相同；同一 arm/path/时间窗与活性序列必须唯一，歧义 BLOCKED。

审计集合最多 100 条，每条序列严格唯一；异步存储写入必须有完成/flush与有界等待，丢失/重复/epoch未解释/容量超限拒绝。Native rule执行不依赖observer持续在线；但缺receipt不能宣称本面通过。

## 6. 最小能力实验（第二阶段单独许可）

同一唯一 session、至多一个冻结构建，真实 DynamicFetcher。先离线产物/hash获总控确认，真实session不得自行提前启动。

- 正常 navigation 与 HTTP Worker脚本/生命周期证明环境活性；不使用 constructor-wrapper/mock-route/fixture策略if-throw。
- Page 与 Dedicated Worker 分别执行 ws 和 wss，共四个请求，源代码固定原生 `new WebSocket`；每请求终态等待上限 5 秒；Worker继续可响应pong并可正常terminate。
- 需要每个请求唯一系统DNR规则匹配receipt、应用error/close终态、没有目标proxy CONNECT/HTTP转发且fixture WS接收0。不得以error或ACK单独判断。
- baseline 能力对照独立context不加载候选扩展，ws/wss只能走已有proxy拒绝；不禁用proxy、不允许任何WS上游/relay。baseline必须显示真实尝试被拒绝，且无法满足DNR receipt条件；baseline不是可接受生产模式。
- 当前proxy仅支持CONNECT而无法形成受控ws明文拒绝时，不擅自放宽proxy/换端口；STOP提交精确差异裁定，缺ws证据不能外推。
- 独立proxy403控制、零上游/双向relay、身份/拓扑/确定自然终止/精确清理仍必需。
- 阴性/扩展未加载/预检失败即停止，不轮换方案或循环新session。阳性只允许 `CAPABILITY_OBSERVED — FORMAL_R3_UNPROVEN`，不允许 R3 PASS。

## 7. 离线与真实失败条件

离线必须拒绝：缺权限/额外权限或例外、ruleset不符、错hash、observer-only/mock-only、错/重复/歧义关联、规则缺失/卸载、page_setup关闭失败、caller重试、监督未先启动、超时、proxy allow/relay、fixture接收、无活性/receipt/终态。旧-05及原生CDP阴性记录仍BLOCKED，不重封。

Backend先完成隔离离线产物与定向测试，直接汇报五文件与所有新增执行输入hash/差异和失败关闭方案，STOP等待总控。正式驱动运行与结束gate由后续一次精确许可控制；未变化完整测试/历史双构建不重复。

## 8. 阶段纪律及文档来源

本控制包Review/合并不改变 R3 BLOCKED，不准入 R4、正式WP-3或生产DNR。新增hook/receipt仅能力诊断schema；正式validator接受该机制需单独安全审查与契约补充。无需变化的API/DB/Pipeline禁止改动。

资料：[DNR 权限/规则/反馈](https://developer.chrome.com/docs/extensions/reference/api/declarativeNetRequest)、[storage.session](https://developer.chrome.com/docs/extensions/reference/api/storage)。官方能力是设计依据，不是冻结环境实证。
