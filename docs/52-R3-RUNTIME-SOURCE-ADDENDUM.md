# R3 runtime source addendum — proposed, OFFLINE ONLY

日期：2026-09-29。来源：`main@5b0f3cab93845265cf10e495e2301f124a3151de`。
状态：待独立 Review / 控制 PR 合并。本文不签发 Browser、Docker 或真实 session。
关联：[51 控制包](51-R3-DNR-CAPABILITY-EXPERIMENT.md)。R3 BLOCKED，R4 及全部下游未准入。

## 1. 必须修正的来源假设

官方 `MatchedRuleInfoDebug` 提供 `rule` 和 `request: RequestDetails`；该请求结构未声明 `timeStamp`。具有 epoch 毫秒 `timeStamp` 的 `MatchedRuleInfo` 是另一个结构，不能把它的字段移植到 debug request。现有 observer 读取 `request.timeStamp`，Node double 也构造该字段：这是离线模型的未证假设，不是冻结 Chrome 的运行证据。

不允许猜字段、用接收时刻冒称规则匹配时刻，或把 `getMatchedRules` 中无 request ID 的结果强行配成 request receipt。现有 v1 资产与失败记录保持原样。新源码、输入 hash 和定向测试须独立提交、Review；旧离线 ALLOW 不覆盖新实现。

## 2. 新诊断 receipt v2 的精确时间语义

保留 v1 的 17 个字段，`schema_version` 改为 `r3-dnr-receipt-v2`，新增唯一字段 `timestamp_source="trusted_observer_callback_epoch_ms"`。`timestamp` 为可信扩展同步进入真实 `onRuleMatchedDebug` callback 后、任何 await/排队/哈希前采集的原生 `Date.now()` epoch 毫秒，是**回执观察时刻**，不是 request 发出或规则匹配时刻。

捕获可信扩展 realm 的原生计时函数，不从 fixture 消息取时间；无 match callback 不能生成 receipt。缺 timestamp、非有限值、bool、额外字段、源标识不符、序列/epoch/内容改写均拒绝。实际 rule/request ID、四个固定安全指纹及原字段脱敏语义不变。审计 snapshot/collector/validator 必须明确支持 v2，不能静默把 v1 改解释为 v2。

请求仍必须为原生 WebSocket，不能 wrapper/mock。arm 的 epoch 起点、终态和结束点由已冻结 fixture 中受控浏览器计时点采集，并辅以可信 CDP/父监督采集顺序及独立 monotonic deadline。fixture 时间只描述应用行为，不成为 DNR authority。

接受条件仍严格 `start <= receipt_observed <= terminal <= end`，且请求预算不超过 5 秒；callback 晚于终态也是 NO-GO，不能把 terminal 改成 flush 时间、扩大 end 或加容差放行。无真实 terminal 不通过。epoch 单位、可信计时源、wall-clock 跳变/跨进程不一致检查和 monotonic 顺序必须写入实际证据；不能仅因均名为 epoch 就假定零误差同步。CDP monotonic 秒及宿主 monotonic 纳秒保留各自域，不能直接与 epoch 相减。关联不唯一、精度/时钟一致性无法证明均 UNKNOWN。

离线正反例至少覆盖真实 API 形状（无 request.timeStamp）、callback-before-await 时间冻结、晚到 callback、wall-clock 逆序、单位错误、float/bool/NaN、fixture 伪造来源、重复/丢失。通过仅说明模型可用，真实 Chrome 来源仍待单独许可实证。

## 3. 扩展 inventory 的有限读取例外

本文合并后，只允许实现一个候选读取适配：通过既有 trusted browser CDP pipe 在独占新 profile 的 `chrome://extensions/` 上调用**只读** `developerPrivate.getExtensionsInfo`，显式包含 disabled 与 terminated 项。此页面是诊断预检例外，不是采集目标；其他 `chrome://`、设置变更、安装/卸载/启停扩展、developer mode 切换、私增 permissions/flags/第二扩展均禁止。

现上游 `ExtensionInfoGenerator` 遍历 enabled、disabled、blocklisted、terminated registry，但经过 `ShouldDisplayInExtensionSettings` 过滤。不能据此宣称所有安装对象均已枚举；themes、component 和部分 hosted apps 的过滤边界必须披露。运行时代码至少校验实际版本、trusted origin、明确 API 返回/错误、完整 enabled/disabled/terminated 选项、id/state/type/location 的准确类型和语义、唯一获准可执行非组件扩展；未知 location/type 不能自动按组件忽略。Target 列表仅辅助关联，不能代替 inventory。

冻结版本源码/内置 schema 的获取尚未完成，公开 HEAD/其他 tag 仅为候选机制依据。实现先以有来源的 schema 校验；未验证版本覆盖、过滤边界或读取失败就 UNKNOWN，禁止伪造“完整”标志。新 profile/唯一路径/argv/只读五文件/实际 origin 和 registry 结果须交叉核验；profile 中出现未知第三方资产即拒绝。baseline 也须证明没有候选扩展，不能只凭无 service-worker target 推断。

只有这一路诊断页面可在预检阶段加入原 about:blank/内部 audit 页集合；不因此取消 15 秒预检、5 秒确认关闭、120 秒父监督、默认拒绝出口、失败锁存和非返回终止。未获真实 session 许可，不运行该页面或 Browser。

## 4. 仅必要的编排闭包

后端限定在既有 dnr_runtime 文件及一份必要的固定答案 DNS adapter 内实现。先优先复用已 tracked R2C-A4 DNS/control 的纯接口与批准参数，不导入整包旧 runner，不依赖 45 个未跟踪历史输入。若非 root DNS bind 53 不成立，STOP；不得改 root、增加 cap、privileged 或擅增 sysctl。

TLS 仅用于既有本地 fixture，沿用已准入实验信任模式，不增 Chrome unsafe flags。列明生成程序/参数、public certificate hash 和临时 key 文件身份；key 不进 Git/日志。固定 image digest 与 R1E authority 分开核验，新源码/mount/argv/phase 不被旧镜像 authority 自动覆盖。

baseline 与 enabled 是一个获准 session 内的两个预定对照，不是失败自动重试；任一失败即停。只有正常导航/HTTP Worker/pong、Page/Worker 四种原生 ws/wss、严格可信 receipt、405/403 对照、零上游/relay/fixture WS、自然退出及精确清理共同满足，才能报告能力观察；永不直接报告 R3 PASS。

最终执行清单覆盖全部源码、DNS、控制客户端、TLS 生成输入、image/argv/mount/phase/profile/计时来源；静态 input hash 不代替实际 inspect、回执或生命周期实证。真实入口默认硬禁，完整源码/闭包经独立审查后，才由总控另签一次唯一 session 许可。

## 5. 验收与范围

本文只细化 R3 诊断来源，不改产品 API、数据库、评分、Pipeline 或 ACQ 产品语义。旧 receipt v1/五文件/hash/历史失败不重封；新 v2 必须独立冻结五文件 hash。离线实施包含 API-realistic doubles、source/clock/inventory 拒绝矩阵及既有 lifecycle/纯拒绝回归；未变完整门禁不重跑。

控制 PR 合并只准入上述离线实现，不准入真实运行。P0/P1/P2 归零、实际输入 hash 完整以及总控明确 session 许可缺一不可。无法补齐来源时报告缺口，不新增通用浏览器框架或无用户价值抽象。

## 来源（不是冻结运行证明）

- [Chrome DNR API：MatchedRuleInfoDebug / RequestDetails / MatchedRuleInfo](https://developer.chrome.com/docs/extensions/reference/api/declarativeNetRequest)
- [Chromium DNR WebIDL，公开 HEAD](https://chromium.googlesource.com/chromium/src/+/HEAD/extensions/common/api/declarative_net_request.webidl)
- [ExtensionInfoGenerator，公开 HEAD](https://chromium.googlesource.com/chromium/src/+/HEAD/chrome/browser/extensions/api/developer_private/extension_info_generator.cc)
- [developerPrivate getExtensionsInfo，公开 HEAD](https://chromium.googlesource.com/chromium/src/+/HEAD/chrome/browser/extensions/api/developer_private/developer_private_functions.cc)
- [UI inventory 过滤规则示例，tag 145.0.7602.1，非冻结 151](https://chromium.googlesource.com/chromium/src/+/refs/tags/145.0.7602.1/extensions/browser/ui_util.cc)
