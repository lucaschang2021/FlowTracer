# FlowTracer Governance v2 — Adaptive Risk-Based Governance

状态：Governance v2 已合并；§12 为 FT-GOV-V2.1 治理修订。CONTROL_INTERRUPT 自总控收到指令立即生效；GOV-2.1 仓库 epoch 在本修订 exact-head 合并后生效。候选、操作控制与永久记录不得混报。

来源基准：`main@31fa751a3c074111f14b640a727a972eb996ef05`（PR #78）。合并后 main 是该来源的后代，不要求等于来源 SHA。本文件是治理语义的唯一现行核心文档，不是业务、Browser session 或下游 Admission。

## 1. Constitution

- G1 Product truth above process：治理服务产品价值、工程风险、安全与交付；没有真实风险对应的工作不得成为阻断项。
- G2 Risk-based blocking：只阻断真实 P0/P1 的受影响路径，不把局部失败扩大为无依赖节点的 veto。
- G3 Capability DAG over serial pipeline：按实际输入能力准入；Browser 是增强能力，不是所有产品路径唯一入口。
- G4 Evidence once：已验收 Evidence ID、input identity、acceptance result 在无影响性变化时复用。
- G5 One gate = one main invariant：R3 应用拦截、R4 失败围堵、R5 worker/queue 隔离；既有必要硬化仍是前提。
- G6 Freeze before execution：预先冻结 Objective、Threat、Invariant、Inputs、PASS、BLOCK，禁止逐 session 增肥合同。
- G7 Rebaseline instead of patch loop：连续两次受控执行未显著收敛，必须治理重评，不自动第三轮补丁。
- G8 Assurance proportional to use：当前 A1；历史较高等级证据保留，不自动提高所有未来门槛。
- G9 Measure governance tax：治理成本、重复证据和 blocker fan-out 必须可见；未知值不估算。
- G10 Governance must govern itself：治理系统必须持续证明自身产生的风险降低大于其引入的交付成本。

原架构冻结、后端、前端、集成、发布职责边界与 PR 纪律保留；取消的是 ACQ 内部错误的绝对串行依赖，不是取消契约冻结、真实依赖或书面准入。

## 2. Severity 与阻断范围

| 等级 | 风险 | 处置 |
| --- | --- | --- |
| P0 | 数据破坏、凭据泄漏、安全边界失效、核心闭环不可运行 | BLOCK 受影响能力及其真实依赖路径 |
| P1 | 核心能力严重错误、已声明安全 invariant 无法成立、下游真实依赖不存在 | BLOCK 受影响能力及其真实依赖路径 |
| P2 | 非核心缺陷、文档/观测完整性债务、有安全替代路径的问题 | RECORD + CONTINUE；明确 owner、影响与延期处置 |
| P3 | 体验或未来优化 | POST-v1.0 BACKLOG |

P2 只有证据能证明既有安全 invariant 被破坏时，才重分类为对应 P0/P1，记录 threat/invariant/证据及受影响路径；不得维持 P2 标签又无限期 blanket BLOCK。未知不是成功：关键安全事实未知且无法建立 invariant 时，按相关 P1 处理，不降为格式债务。

Architecture Contract 的层边界、禁止依赖、import safety、provider substitution 与 no-regression 均保留。`ARCHITECTURE.toml` 现有机器阈值未在本次修改：历史架构 debt 与新业务缺陷不得混报。若机器 gate 只因 P2 warning 拒绝，必须报告 finding、按本节裁定并作明确文档 disposition；不能跳过扫描、静默改 severity 或宣称扫描全绿。必要机器规则对齐只在后续独立授权的最小变更中执行，本控制包不授权代码/CI 改动。

## 3. Capability DAG 与 feature degradation

```text
Contract Freeze → WP1 Safety → WP2 RSS / Native / Static
                                   ↓
                                 WP4 Router ← Browser capability（optional）
                                   ↓
                                 WP5 Controlled Discovery
                                   ↓
                                 WP6 Version Evidence / Change
                                   ↓
                                 WP7 Opportunity
                                   ↓
                                 WP8 ACQ Closure
                                   ↓
                                 PLUGIN-1 → Frontend → Integration → Release
```

未正式验收的 Browser：`browser_dynamic = disabled`。这是准入/部署要求，不宣称本次已新增代码开关；不存在安全禁用路径时，该 Browser 路径不得上线。已有 RSS/Native/static 不得被 Browser 局部 blocker 停止使用。

合并后总控逐项 Dependency Re-evaluation，写明已验收输入、所需未实现依赖、disabled branch、rollback、scope、owner 与准入结论，再签发工作包：

| 能力 | 最小真实依赖 | 合并本包后状态 |
| --- | --- | --- |
| WP4 Static/Native Router | WP1 + WP2；安全策略/预算不变；Browser 分支禁用 | 可申请依赖重评，不自动准入 |
| WP5 Static Discovery | 已验收 Static Router + SitePolicy/硬预算 | 等待 WP4 与独立准入；Browser-dependent 部分暂停 |
| WP6 Change | 已验收静态输入 + Artifact/Snapshot 版本契约 | 等待对应输入与独立准入；不得跳过版本证据 |
| WP7 Opportunity | 已验收静态 Discovery/Change + 冻结评分/Action 人工确认契约 | 等待对应依赖与独立准入 |
| WP8 / PLUGIN / Frontend / Integration / Release | 各自产品、契约、集成和发布真实依赖 | 均未准入；不因 Browser 单点自动 blanket BLOCK |

ACQ Closure 对交付能力与禁用能力必须明确列表，不得把未验收 Browser 宣称为 ACQ 完成能力，也不得自行削减已冻结产品范围；任何范围裁定另经明确批准。本包不修改 API、Schema、Pipeline、评分、NetworkPolicy 或产品 scope。

## 4. Evidence-once 与历史保护

复用记录固定为 `Evidence ID | Input identity | Acceptance result | applicability | material change`。影响性变化包括 runtime/executable、网络拓扑、policy、validator 语义或证据来源可信性变化；只重新验证被影响的 invariant，不机械重跑全链。

| Evidence ID | 权威输入与已验收结果 | 本轮处置 |
| --- | --- | --- |
| R1 | PR #54；merge `34364d0082e4ecdbe4331d77a21ef6d25c2fca8a`；PASS | 原 SBOM/license/build/runtime 证据不改写 |
| R1C | PR #60；merge `df0c3512080f384dbd6c820d7627cbe721e37422`；PASS | 完整 Chromium 兼容 authority 保留 |
| R1D | PR #63；merge `db9c4fad0ca826b472d18d85c69db53848cfcd94`；PASS | Runtime Identity v2 历史 authority 保留 |
| R1E | PR #66；head `3636dd261ece31c046406aa7b2279f6f7bd7dad8`；PASS | payload SHA `5f4cf5acdf06a86f9b8907375f6f8f239ecf18152762b889f1e254b01e447e3b`；manifest SHA `f8d8bd0b64dfac53e244b00f29fbc9f18ed44b94491323b3f49ba2af191912e8` 保留 |
| R2C-A4 | PR #68；head `e4f636bd88ba8c298ca7b1ec1e074b5bcd1351e1`；merge `c584fd06ff136025dc6a0aba9815291b16682aa2`；PASS | controlled egress authority 保留 |

归档事实源：[历史证据包](42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md)。R3 只验证当前候选对适用 R1E/R2C authority 的绑定，并采集本次 application-policy-network 关联；历史 R2C 成功不能替代本次应用关联。无影响性变化不重复 SBOM/license/full-root 重建/DNS bypass/整个 egress matrix。

历史成功、失败、原始资产与 one-shot consumption 标记均保留；治理文档 supersede 不删除原始数据。docs/37、41、49 只增加历史标记，其原文保持原样。其他旧 R3 控制文本与本文件冲突的验收扩张/准入语义不再生效，但安全限制和原始事实保留。

## 5. R3 Rebaseline：唯一主 invariant

Objective：真实 Scrapling DynamicFetcher 请求由 application policy 控制且没有 network bypass。

Threat：请求绕过 NetworkPolicy/SitePolicy/scope/累计预算；误归因或伪造观察导致安全误判；timeout 被包装为成功。

Invariant：真实驱动的允许与拒绝请求都有可信 application event ↔ policy decision ↔ R2C network observation 关联；逐跳 redirect 与子资源不越界。

Inputs：精确 candidate commit、fixture/validator identity、适用 R1E runtime/R2C egress authority 引用、冻结 policy/scope/budget、唯一执行 ID 与清理归属。执行前固定输入；真实 session 仍需另行书面许可。本控制包不允许执行任何 session。

### R3-A Harness Integrity

一次证明 observation pipeline 可信、validator 能区分 PASS/FAIL、缺失/伪造/timeout 不冒充成功。通过后冻结输入身份；无影响性变化不对每个 surface 重做。

### R3-B Allowed Composite Fixture

单一离线 composite 尽可能覆盖 navigation、redirect、iframe、script、XHR、fetch。逐跳重新 policy-check，子资源执行同一安全边界。覆盖不能只靠 fixture 声明，必须记录实际事件与对应 policy/network 事实；必要小型补充 fixture 仅填覆盖缺口，不增加无关合同。

### R3-C Denied Composite Fixture

单一离线 composite 尽可能触发 WebSocket、download、popup、service worker。A1 不要求支持这些能力，可统一 DEFAULT DENY；证明可靠拒绝且未进入允许 forwarding path。不得只凭无网络日志推断成功，须有触发/拒绝的可信关联。

### R3-D Correlation

证明 application event、policy decision、network observation 可明确归因到本次真实 DynamicFetcher/目标 runtime；不要求超过完成安全判断所需的 Browser 内部 provenance 系统。mock/配置审阅不能替代真实驱动观察。

PASS：A harness credible AND B allowed composite controlled AND C denied composite fail-closed AND no bypass AND credible application/network correlation。

BLOCK：证据表明相关 P0/P1 threat 发生，或关键关联/拒绝/authority 绑定无法建立使 invariant 无法成立。普通格式、inventory 完美性、资源 percentile、扩展供应链复证不独立构成 R3 BLOCK。

既有非 root、namespace/controlled egress、只读 runtime、资源硬上限、执行超时、失败清理要求仍是执行安全前提。R4 的完整故障/资源证明不塞回 R3；必要安全监督不能以分 Gate 为由拆掉。

## 6. R4 / R5 职责

- R4：deadline、process reap、resource isolation 与 crash/OOM/hang 失败围堵；只证明 Browser 故障不会影响普通运行路径。样本/算法适配 A1 关键边界；不自动追求生产统计完美性。
- R5：专用 Browser worker/queue、普通 worker 互斥与 restart/failure containment。不能以 R3 PASS 推定 queue 隔离已通过。
- R3/R4/R5 均未通过或未准入的部分继续显式标注；正式 Browser 能力必须满足实际安全依赖并另签 Admission。

## 7. source_observation 裁定

分类 A：无法确认观察来自目标 Chromium/DNR，错误来源或伪造观察可能使应用关联判断无效 → P1，BLOCK R3 该能力路径。

分类 B：可信目标观察已足够建立 invariant，仅 inventory/provenance 格式或完美完整性未达自设标准 → P2，记录，不 BLOCK。

当前事实：session02 为 `source_observation/source_preflight_failed`；后续 session03（本任务之前已执行）为 `source_observation/inventory_navigation/source_inventory_navigation_failed`，baseline BLOCKED，enabled 未执行，runtime 未验证，target DENIED。结果文件 SHA `88e219c24e8f92de9677aa0fb13ca5423b923360fa0a12d13f2255c77ab0a664`。该失败未区分 page creation 与 navigation，也不证明 DNR 错误或伪造。

当前裁定：inventory 方法/格式失败本身为 P2 诊断债务；尚未取得可建立真实 application-policy-network 归因的证据仍为 P1 未决 invariant，R3 保持 BLOCKED。不能由 P2 推断 R3 PASS，也不能把未知宣称为已发现真实网络旁路。是否能用更小可信来源完成归因，待本包合并后冻结 harness 再决定，不再以 inventory 完美性为唯一许可入口。

## 8. Freeze / rebaseline / assurance

每 Gate 执行前冻结 Objective、Threat、Invariant、Inputs、PASS criteria、BLOCK criteria。新阻断必须映射既有 P0/P1 threat 且明确证据如何使 invariant 无效；其余进入 backlog/future assurance。未知结果与失败如实记录，不更改已消耗 session，不追认成功。

连续两次受控执行仍无显著收敛（没有关闭关键 threat 或产出足以决定主 invariant 的新事实），触发 `GOVERNANCE_REBASELINE_REQUIRED`，停止自动第三轮 patch。审查 acceptance 负重、scope creep、实现架构、evidence complexity、拆 Gate 与 feature-disable；总控重新冻结合同后才能另签执行许可。当前 R3 已触发，本包响应该触发，不授权继续补丁。

| 等级 | 目标与新增保证 |
| --- | --- |
| A0 Prototype | Does it work? |
| A1 Alpha（当前） | 受控安全价值；P0/P1 clear、核心 invariant、关键行为确定、rollback、E2E |
| A2 Beta | 更广兼容、恢复覆盖、运行证据、性能基线 |
| A3 Production | 强化供应链、扩展复现、长期可靠性、深入 provenance、完整观测 |
| A4 High Assurance | 特殊系统的形式化/近形式化、广泛 provenance、对抗验证 |

已完成且成本合理的 A2/A3 证据继续保留，A1 不降低 SSRF/凭据/运行隔离等核心安全 invariant。

## 9. Governance telemetry 与 FT-GOV-001

每阶段记录 Implementation Time、Review Time、Waiting Time、Governance Time、Docs-only PR Count、Evidence Reuse Count、Repeated Evidence Count、Blocked Downstream Nodes、Gate Iteration Count。统一时间单位 minutes；活动区间避免重复计入 Total Engineering Time，等待单列。明确数据来源和区间；没有可靠历史计时为 UNKNOWN。

`Governance Ratio = Governance Time / Total Engineering Time`（分母未知或为零则 UNKNOWN）；`Blocker Fan-Out = 不重复的下游 blocked capability 数`（列出节点及真实依赖，不能用 PR 数代替）。Ratio > 50% OR Iterations >= 3 OR Fan-Out >= 4 自动触发治理审查。

| Incident / phase | Implementation / Review / Waiting / Governance Time | Docs-only PR Count | Evidence Reuse / Repeated Count | Blocked Downstream Nodes | Gate Iteration Count | Ratio / fan-out |
| --- | --- | --- | --- | --- | --- | --- |
| FT-GOV-001 / 历史 R3 | UNKNOWN / UNKNOWN / UNKNOWN / UNKNOWN | UNKNOWN（未做完整 PR 审计） | UNKNOWN / UNKNOWN | 旧串行规则阻塞 WP4、WP5、WP6、WP7、WP8、PLUGIN、Frontend、Integration、Release | 至少 3：已记录 source session01/02/03；非全历史计数 | UNKNOWN / 9（旧规则节点集合） |
| 本次 Governance v2 | UNKNOWN / UNKNOWN / UNKNOWN / UNKNOWN | 待控制 PR 创建后记 1；当前 0 | 引用 5 组 authority；实际执行复证 0 | 本包不准入下游，待依赖重评，不能报解除完成 | 文档 rebaseline 1；Browser 执行 0 | UNKNOWN / UNKNOWN（待重评） |

FT-GOV-001：局部 R3 的 evidence expansion、serial dependency inflation、patch loop 与 assurance mismatch 增加交付成本。本轮先合并治理再决定能力准入，不新增遥测服务、Möbius Engine、数据库、runtime 或产品模块。未来 Möbius 仅保留案例：Gate Scope Creep、Evidence Duplication、False Hard Dependency、Blocker Fan-Out、Governance Tax；不是实施许可。

## 10. Authority、发布与停止

Governance v2（PR #80）已合并，supersede docs/37、41、49 的相冲突治理/验收语义。旧记录不提供当前执行权。CURRENT-GATE 与本文件 §12 的 live authority 优先；控制指令的即时撤销不等待 PR 合并。看板历史行不得反向覆盖现行裁定。

PR #79：DO NOT MERGE。除非另签只读重评 lease，证明文本完全符合 Governance v2、v2.1 与届时 main，否则应 supersede/close；本修订不执行该 PR 的修改、关闭或合并。

本包流程：审计 → 单一核心文档与现有文档同步 → 文档/架构一致性检查 → 独立治理 Review（P0/P1=0）→ 控制 PR → exact-head merge → STOP。纯文档不重复业务全量测试、不运行 Browser/Docker。合并后只可另申请 Dependency Re-evaluation，不自动运行 session 或 WP4。

SSRF/SitePolicy/预算、无公网测试、无凭据/登录态、无 CAPTCHA/访问控制绕过、namespace、非 root、只读、禁止 host network/privileged/Docker socket、NetworkPolicy 与精确清理全部保持；本次只有 Governance Simplification，没有 Safety Deregulation。

## 11. R3 composite 最小合同与离线实施包（2026-10-01）

来源：Governance v2 merge `35ae356d292c5300f39f99f0726c829ad270b744`。本节合同已由 PR #81 合并，离线产物 PR #82 已合并；以下实施权限描述是历史记录，不是持续 lease，已被 §12 撤销。技术 invariant 保留；不准入真实执行、API、Schema、依赖、镜像、业务 capability 或 WP4。

### 11.1 依赖重评与本次唯一目标

Backend 只读重评确认：WP1/WP2 已有 AcquisitionBackend/ContentFetcher/Repository ports、Network/SitePolicy、ResourceBudget、lease fencing、Attempt/State 与 quality 观测；Native backend 仅接受 auto/native。WP4 静态输入不依赖 Browser，但 Router v1、family/profile 决策、Browser-disabled 降级、累计 budget、Circuit half-open、域级 AutoThrottle 尚未冻结或交付。本包不将“依赖可满足”混同“WP4 已准入”，不偷偷实现永远 Native 的替代产品。

本次只解决 R3-A–D 的可执行最小证据链设计/离线实现；不继续修补库存页作为许可入口。R3 主 invariant 与 §5 相同：真实 DynamicFetcher application policy 控制、无 bypass、可信 application-policy-network 关联。R4/R5 完整故障/queue 验收不塞入本包。

### 11.2 冻结输入与证据关联合同

独立实验使用 `r3-composite-v1`，每次真实执行必须由后续总控许可固定 candidate SHA、input manifest SHA、fixture/validator SHA、唯一 execution ID、具体镜像 ID、适用 R1E/R2C authority 与拓扑/限值。当前均未签发真实 session；不得生成虚构执行结果。

最小 evidence graph 由以下四类记录组成（实验内部，不是公开 DTO）：

- Binding：execution ID、candidate/input identity、实际 runtime identity、policy/version、适用 authority 引用。仅代码中的常量或调用方 Boolean 不是实际 identity 证明。
- Trigger：surface、actor（page/worker 等实际类型）、唯一 trigger ID、受控 fixture route ID、parent/hop 关联及实际触发结果；只声明已触发不算事实。
- Decision：对应 trigger/request 映射、allow/deny、封闭 reason code、NetworkPolicy/SitePolicy/scope/budget 检查结论及预算消耗。传输实现自己的 request ID 不得被假设等于 DNR/CDP ID。
- Observation：与上两类可核对的 runtime event、专属 proxy/fixture 观测、允许转发/拒绝事实及执行结束/清理结论；证据源及映射由可信 host/harness 取得，页面或测试 double 不能给自己签发真实观察 authority。

必须形成明确、一一可解释的关联，允许 vendor ID 通过显式映射关联，不要求跨进程时钟完美同构。时间仅用于各自时钟域的有界执行/顺序校验；不能只凭“时间相近”归因。未知关键映射、错误源、重复冲突 ID、跨执行/跨请求 receipt、缺失 trigger/decision、timeout 冒充成功均拒绝。历史 receipt v1/v2 不改写，新 validator 不静默接受其未经证明的假设。

日志/结果只含受控 route ID、封闭字段与安全摘要；不含正文、原始 URL query、凭据、完整 argv/原始 inventory、DNS 全集。JSON 严格拒绝未知字段、重复键、非有限数与非法类型；具体内部封闭 schema 与 reason 列表在离线候选代码中一次实现并接受独立 Review，不追加公开产品字段。

### 11.3 固定最小 fixture / validator 矩阵

| 子门禁 | 必须验证 | 不足以宣称通过的证据 |
| --- | --- | --- |
| A Harness | 完整阳性样例可接受；缺失/错误源/跨执行/重复/伪造标记/timeout 样例拒绝；入口无许可不执行 | fake 样例通过不能证明 Browser 运行通过 |
| B Allowed | 同一 composite 内实际 navigation、逐跳 redirect、iframe、script、XHR、fetch；每项有 Trigger→Decision→Network 关联；相同 policy/scope/累计 budget | fixture HTML 包含代码、配置审阅、只有最终正文 |
| C Denied | WebSocket（page 与 dedicated worker）、download、popup、service worker register/update/fetch 对应默认拒绝/阻断前置能力；证明触发→拒绝且无允许 forwarding | 空 proxy 日志、timeout、JS error 单独出现、未执行触发 |
| D Correlation | 本次真实 DynamicFetcher 与 authority 绑定；子资源/worker 拒绝可归因；结果明确区分 application denial 与 proxy 独立兜底 | 直接 Playwright 代替驱动、旧 R2C 结果、库存页格式完整性 |

对默认拒绝 service-worker/popup 等前置能力，若其创建/注册已可靠拒绝，衍生能力记 `PREVENTED_BY_DENIED_PARENT` 并绑定实际 parent denial；不得伪造 update/fetch 请求，不能仅记 NOT_TESTED 就覆盖该 surface。必要小型 fixture 只填本矩阵实际覆盖缺口。

真实 `DynamicFetcher.fetch` 安装 page_setup 策略后正常驱动 navigation/page_action；当前 about:blank setup 中关闭并抛 completion 的 source preflight 只能保留历史诊断，不能作为 B/C。`chrome://extensions` 不是强制前置。若实现依赖 DNR，必须以实际绑定的可信 extension/runtime 观察支持其决策，不能因为移除库存页就假定扩展有效；允许满足同一 invariant 的更小可信观察机制。

R1E/R2C 只作无影响性变化的 authority 复用与当前绑定验证；不重建镜像、不复跑 SBOM/license/DNS/整个 egress 矩阵。保留 R2C 的 namespace/受控 proxy/local-fixture 限制；fixture 例外不能扩展为真实 URL、外网、任意私网或危险端口许可。

### 11.4 受控实施范围、权限与停点

执行角色：原 Backend；唯一 worktree `D:\FlowTracer-wt\backend`。新离线阶段不得丢弃 Plan A：`collector.py/probe.py/supervisor.py/test_runtime_adapters.py` 四份 dirty 改动及历史 untracked 全保留。不得自动 stash/reset/rebase/switch 到覆盖脏文件的 checkout。

允许只在全新 `backend/experiments/browser-r3/composite_v1/` 实施：`contract.py`、`fixture.py`、`collector.py`、`harness.py`、`validator.py`、`supervisor.py`、`test_composite.py`、`execution-inputs.json`、`execution-plan.json`、`README.md`。若路径已存在且不是本任务资产，STOP 报告，不覆盖。先从当前分支确认基准可读与差异范围，提交仅精确白名单；若旧脏文件使候选闭包不能隔离，报告具体冲突，不自动清理。

可以复用 Git 中 R1E/R2C 和既有 fixture/ports 的权威字节/接口；不能导入依赖未提交 Plan A 的 runtime 模块而漏记 identity。新 candidate 与旧 source diagnostic 保持隔离，无影响性的旧试验测试不重复。

工作树保全例外：若切到最新 main 会覆盖旧 dirty 文件，本阶段允许在原 `feat/acq1-wp3-r3-internal-source@0de2d5658832b667aa00a5a8e73350a06b285bbb` 上创建隔离 `feat/acq1-r3-composite-offline` 分支，只提交十个新文件；这是离线 artifact 暂存，不是旧 branch 获得业务准入。独立审查以父提交→新提交的精确增量为范围。发布前由 GitHub 角色在自己干净工作树从最新 main 建发布分支，仅 cherry-pick 该单一 artifact commit 并验证十文件 diff/原文身份，不能把旧未合并 source commits 或 dirty 资产带入 PR。移植后精确 head 再复核，输入 hash 若受影响则如实重验，不重写 Backend 历史或重复无变化测试。

允许确定性代码和 mock/fixture byte 的定向离线测试；模块 import 与默认 CLI 不启动外部 I/O，真实启动函数无精确 host 许可保持 NO-GO。禁止依赖安装、Docker/build/Browser/CDP/真实 session、网络、共享 infra、业务测试全量、旧 runtime/authority 修改、App/REST/Schema/Pipeline/评分变更。测试假数据必须标 SYNTHETIC，不能产出 R3 PASS。

离线 PASS 条件：A–D 完整 schema/矩阵与可信来源接线计划；负例覆盖上节拒绝条件；全部输入 hash 闭包；无 import I/O/默认启动；安全/允许范围/现有资产无回归；独立 Review P0/P1=0。结果只可称 `OFFLINE HARNESS READY`，真实 R3 仍 BLOCKED。P2 文档债务记录继续，不增加库存页/来源完美性新硬门槛。

Backend 完成一次定向测试后提交精确离线 candidate 并报告，未经后续总控许可不 push/PR/执行。总控独立复核代码/hash/negative matrix → 冻结 runtime Inputs/Objective/Threat/Invariant/PASS/BLOCK → 另签唯一 session 执行许可。连续两次不收敛触发 §8，不能自动第三轮补丁。

### 11.5 历史遥测与下一动作（不提供续权）

本最小阶段计时从新任务开始记录，未知为 UNKNOWN；review/wait/implementation/governance 分列。PR #81/#82 已合并；输入无影响性变化时复用 PR #82 离线证据，不重跑。旧 Backend 不再执行本节工作包；R3 runtime、R4/R5、正式 WP3/WP4+ 均未准入。

### 11.6 R3 host binding 最小补充合同（2026-10-02，控制 PR 合并后可申请新 lease）

来源：`main@673f4b8f30bd1f7229510a1db8872e680b5a1fee`（GOV-2.1 PR #83）。只读 preflight 报告是部分结论，不伪称全部审查通过。被遗漏的直接依赖已由总控 Git 对象核对：`dnr_runtime/contract_v2.py` 导入的是 `dnr_offline/contract.py`；FLAGS 为 `--load-extension=/opt/flowtracer-r3-dnr` 与 `--disable-extensions-except=/opt/flowtracer-r3-dnr`。不得在 composite 的同名顶层 `contract/collector` namespace 中直接导入旧 runtime；不读取或覆盖旧 dirty 字节。

复用资产：`a3980682b7fd306f130250978c3ef6dade224233`，父 `fba06dfa20bde0385d2e6a36408b11ffca48809e`。这是未发布、未正式验收的旧 artifact identity，不是 authority。九文件增量可作为输入，须在新 lease 下审查被修改的闭包；历史 R1E/R2C 与 PR #82 未变证据不重复。

#### H1：下一最小实现边界

下一工作包只可申请 **一次离线 implementation increment + 一次受影响定向 verification**：绑定 host approval 输入校验、两段 runtime identity、独立 parent deadline/owned cleanup 的具体 adapter。不得同时滚入 native observer、TLS fixture/proxy 实现、真实执行或第二轮 repair。Allowed Files 仍为 §11.4 的 composite_v1 十文件，核心改动限定 contract/collector/harness/supervisor/test/manifest/plan/README；fixture/validator 只有直接必要兼容改动才可列入新 lease。

- HostApproval：沿用已提交 host 程序的固定 record digest、精确 candidate/Git raw input closure、image/R1E 引用、一次性 consumption、session ownership 校验方式。将旧 source-preflight/baseline-enabled 模式显式拒绝；不能将其 consumed record 改名复用。composite 的具体真实 record、execution ID、record 路径/digest、image ID、topology/mount/command 只有后续真实 lease 才冻结；缺任何适用输入即 NO_GO。离线 adapter 可以验证这些已声明输入，不得填造实际许可、生成可用 record、或接受 caller Boolean/环境变量绕过。
- 身份分两段：fetch 前仅核验 host-owned image/container/pinned input；page_setup 内在正常导航前取得实际 root Browser/executable/product/profile 与适用 extension/context 事实。此时缺失 target、错误 source、错误 runtime、旧库存页硬门槛或身份未建立即拒绝。不能在 Chrome 尚未启动时声称已有 browser identity，也不能以 `chrome://extensions` 页面完美性作为前置。
- 明确 host/driver ownership：独立 parent watchdog 不调用 Playwright 的跨线程同步对象。driver callbacks 与 CDP readback 在同一 driver-owning thread；对 async observer hash/storage 的 configure/snapshot/flush 采用有界 await，epoch 改变、丢失或 flush 未完成不能成功。H1 只建受检两段生命周期边界，不宣称 native ports 已绑定。
- deadline 分层：composite 总动作预算不超过 15s（包括 setup/action/correlation），单个 callback/读操作不超过剩余预算且至多 5s；独立 parent hard deadline 至多 120s，预留 host close/reap/absence 核验最多 30s。总 120s 包含清理，不能在超时后再无界等待。固定 lease 可采用更短限值，不可自行延长。
- owned cleanup：只针对 host 验证的 exact container ID/name/session label，记录 kill/wait/rm 与 absence（或已结束的终态）；错误 ownership 不得误删。`context.close()` 或 caller `closed=true` 不是最终证据。作用域内错误、安全拒绝与 cleanup 失败分别记录安全 code，任何关键 cleanup 未知不得 PASS；未知外部资源不清理。
- `launch_real/host_session` 保持 NO_GO。默认 CLI/import 无文件、网络、进程 I/O；测试只能注入明确 SYNTHETIC executor/host facts，不能调用 Docker/CDP/Browser。H1 结束只报告具体 adapter 的离线证据、未绑定 ports、精确 diff/hash，无 R3 PASS 或 ready-to-run session。

发布边界：Backend 不改变 main 或旧父历史，不自行 push/PR。保留四份 Plan A dirty/untracked；若必须沿原分支暂存，后续发布仍由 GitHub 在干净最新 main 分支仅移植明确 artifact 增量，核验全路径 raw blobs，不带入旧未合并 source parents。下一实施 lease 必须绑定实际 branch/HEAD 与适用本控制合并 SHA，不从本节推导无限续权。

#### H2：网络事实模型与 native 未决边界（不是本次实施许可）

opaque CONNECT proxy 无法观察 TLS 内的 request ID/正文；旧 proxy/fixture 原样日志不能满足逐请求关联。后续最小 adapter 采用：host 插入的有界 application request token → 受控 TLS fixture 实际请求/token/route/client socket → proxy 上游 local socket tuple + connection ID/epoch + validated destination。一个 keepalive tunnel 可承载多个请求；显式 join，不能以时间接近或要求“一请求一 CONNECT”代替。

proxy receipt 只证明 validated tunnel forwarding，不虚构解密/body count；正文实际字节计数由 fixture 发送完成事实取得。后续实验内部 schema 必须区分 connection 与 request，允许多个 request 引用同一 tunnel；不能继续把每个 proxy transport ID 强制唯一。application token、execution/actor/parent/route 与 fixture/tunnel 全部严格核对，错配/重放/丢失即拒绝。此处不授权公开 API、生产 proxy、MITM、真实私网/公网或扩大 SitePolicy。

native 仍未决：旧 extension 只 block WebSocket，observer 只接受旧 `websocket-r3.test:8443/dnr-(page|worker)-(ws|wss)`；不能把 composite 路由或四 R2C flags 当作 extension 已加载。可信 extension readback、ruleset、实际 worker actor 与 native receipt 必须绑定；旧 inventory 许可路径不整段复用。popup/SW 的创建/注册前置拒绝契约保持，不以 JS wrapper、异常、创建后 close 或空日志冒充。能否通过锁定 driver 的真实 context setting 满足 SW、如何阻断 popup 必须先取得具体接口/实现证据后由总控裁定，未决则该 runtime 路径 NO_GO。

H2 与唯一 composite 真实执行须分别签发新完整 lease；H1 完成不自动准入。不能为凑 PASS 降低原主 invariant，也不能把这些局部未决变成静态能力的全局 veto。

### 11.7 H2 接口审计与 callback fail-closed 补充（2026-10-02）

事实基准：PR #84 合同已合并 `a215051d2a2f53b41d9b22339f1bab52a27dbdf7`；PR #85 H1 OFFLINE ONLY 已合并 `1c7b15a7a285cd183a94ddca460f023163700a4c`，候选 `7f4a108ed4102f183837cb9189d4c95f81272ed8`，24/24 标准库离线测试与 Backend CI 通过。这些证据只覆盖离线 adapter，不是 R3 PASS 或真实执行许可。

新证据：原 Backend 的 `FT-GOV21-R3-H2-INTERFACE-01` 只读审计已结束。Scrapling 0.4.15 本地 `_controllers.py:155-162` 捕获 `page_setup` 的 `Exception` 后继续 `page.goto`，`:168-172` 同样捕获 `page_action` 异常。H1 的 `Rejected(ValueError)` 属于该捕获范围；身份拒绝可能先于 guards 安装，事后 `driver_incomplete` / finally cleanup 不能倒推此前无导航。此为源码层 P1 未决边界；入口 NO_GO，未观察或宣称实际泄漏。既有直接传播异常的 synthetic stub 不覆盖该控制流，旧通过证据不重复、不扩大结论。

#### 最小拒绝合同（立即控制，记录经本 PR 审查合并）

- SDK 会吞异常时，抛 `Rejected` 本身不是 enforcement。身份、setup、action、callback budget 或 native readback 拒绝须成为不可逆的本次执行拒绝状态；SDK 后续返回成功不能清除拒绝或产生 PASS。
- 身份/setup 拒绝必须在 SDK 可继续正常导航之前建立可证明的不可绕过拒绝边界，或确定终止精确 owned runtime；不能仅等待 15s watchdog、事后 close、JS wrapper、后置 `driver_incomplete` 或代理 deny。宿主终止未完成/ownership 不符/absence 未证实即 NO_GO，不能自行重试或删除外部资源。
- 下一设计必须明确 callback 到宿主监督器的拒绝传播、同线程 driver 限制、独立终止的 deadline 与 SDK catch-and-continue 顺序。不得用跨线程 Playwright 调用实现 watchdog；既有 15s/5s/120s（含最多 30s cleanup）上限不增加。
- targeted synthetic 验证必须准确模拟 SDK 捕获 callback Exception 后试图继续 goto/action 的分支；覆盖 setup 身份拒绝、action 拒绝、callback timeout、cleanup 失败、SDK 正常返回但拒绝已发生。只有证明拒绝不能被吞掉/转为成功，才可称该离线分支已修复；实际无导航/无出口仍需新许可下的真实证据。

#### 其余接口事实与下一边界

Scrapling `_base.py:516-517` 与 `_controllers.py:85-88` 在创建 persistent context 前转发 `additional_args`，可作为 `service_workers='block'` 的参数入口源码证据；锁定 Playwright 1.62.0 本地 SDK 尚缺，接受参数、实际注册阻断及 extension worker 兼容性仍 UNKNOWN。popup 创建前 native 拒绝仍 UNKNOWN，不以事后 close/route.abort/JS 替换冒充。

旧 DNR rule 仅 WebSocket；observer 只接受旧 host/route，且 receipt 的 initiator 为 null。新 route、actual worker actor/ready/attempt/vendor-ID、规则 readback 与有界 flush 须实际绑定。旧 proxy/fixture 缺 tunnel ID、upstream local socket 与 fixture accepted socket/请求序号；§11.6 的逐请求 token/socket join 仍是待实施合同，不把 opaque CONNECT 当解密请求证据。

下一最小操作仅可另签：锁定 SDK 来源取证与 fail-closed 接口设计，或该设计审查后的单次离线实现/验证。此补充不准入 H2 大实现、Browser/Docker/session、R4/R5 或下游；不得重跑 PR #82/#85 未变证据。原 Backend 与 GitHub 已返回 STOP，旧 lease 均 EXPIRED。任何新任务继续适用 GOV-2.1 完整 record。

## 12. Governance v2.1 — Live Authority & In-Flight Task Control

CONTROL PACKAGE：`FT-GOV-V2.1`；来源 `main@335c6a2da418b2d3b2c4c70b59ee3d20d08c08cb`（PR #82 merge）。本节为现有治理的修订，不重做 v2，不建立平行治理体系，不实现 Möbius。

### 12.1 Authority is leased / 即时控制

**A task owns an operation, not the future. 任务只拥有当前获准操作的执行权，不拥有未来步骤的默认续权。**

Authority 必须 SCOPED、VERSIONED、REVOCABLE、EXPIRING AT CHECKPOINT。Parent Goal 是目标，不是无限期执行许可。Controller Operational Authority 自控制指令收到立即生效；Repository Governance Record 经独立 Review、PR、exact-head merge 永久记录。不得等待记录合并才停止旧任务。

本包接收即 `CONTROL_INTERRUPT=ACTIVE`，撤销旧 GOV-2.0、LEGACY-R3、PRE-GOV2 任务的后续操作权。修订合并后 `CONTROL_EPOCH=GOV-2.1`；合并前此值只是受控修订/快照 lease 的目标 epoch，不得宣称仓库 epoch 已切换。接收中断后旧任务已无续权，无论其 epoch 是否仍与未合并仓库文本相等。

每次操作前核对 epoch、Current Gate、当前 task authority、revocation/expiry、Allowed Next Operation 和精确输入。`task.control_epoch != current.control_epoch` 即 STALE_AUTHORITY → STOP；相等只是必要条件，不能覆盖撤销或过期。治理合同、总控裁定、风险等级变化：旧 authority 在下一安全 checkpoint REVOKED。Latest controller authority supersedes incomplete historical task goals。

### 12.2 In-flight 原子操作与 deadline

收到中断时逐任务标记 RUNNING_ATOMIC / CHECKPOINT_REQUIRED / AUTHORITY_REVOKED，并最终记录 STOPPED；不得仅依据旧 Goal、锁文件或等待意图推断进程仍活跃。

- 已启动且可安全中止：立即 graceful stop，保存 stdout、stderr、exit state、owned resources、working-tree diff、generated artifacts，进入 CHECKPOINT_REQUIRED。
- 中止会破坏文件或证据：只允许已启动、不可分割的当前动作完成，随后 STOP；不得开始下一条命令或借快照补修、测试、提交。
- 原子操作默认 hard deadline 为启动后 15 minutes。full suite、build、大型确定性验证、获准 Browser session 只有 lease 明示更长时限才可延长；无 long-run authority 不得持续数小时。超限由明确停止策略安全处理并报告，不自动创建替代 session。
- 保存与清理仅限已授权的保全范围；未知资源标 UNKNOWN，不借此启动 runtime 探测或删除用户资产。

### 12.3 Checkpoint preemption / no implicit continuation

执行链：Authority → Atomic Operation → Checkpoint → Authority Refresh / Revoke → Next Operation。每个原子动作结束必须重新核对并由总控签发下一 lease；未刷新即 EXPIRED。

“继续推进/收尾/核验、完成剩余工作、按照原计划、等 Backend 返回”均不构成 authority。没有明确 NEXT_OPERATION 与 STOP_CONDITION：NO_GO。任务不能以“原 Goal 未完成”继续收尾、修一下、测完或先出 candidate。

Machine-owned wait 只允许 command runner 等待已获准、有 deadline 的 pytest/build/CI/runtime。Model/Backend 不因命令结束自动执行 fix→test→fix。总控等待子任务只可记录状态、等当前获准原子结果，不延长子 authority；结果返回后 STOP → controller review → new authority。

每个 implementation lease 默认最多 1 implementation increment + 1 targeted verification，MAX_ITERATIONS=1。失败 REPORT + STOP。只有完整 lease 显式声明 bounded repair loop、MAX_ITERATIONS、deadline、每次 checkpoint 刷新才可有更多次数；不允许循环自续权。验证、发布、合并分别签发其 operation lease，不由 Goal 推导。

### 12.4 必填 Task Authority Record / 生命周期

```text
Task ID:
Control Epoch:
Parent Goal:
Exact Baseline:
Exact Branch:
Authorized Operation:
Allowed Files:
Allowed Tools:
Forbidden Operations:
Max Iterations:
Hard Deadline:
Expected Evidence:
Stop Condition:
Next Authority Owner:
```

核心字段缺失、输入不匹配、已过期或撤销：NOT ADMITTED。发布/Review lease 必须绑定精确 candidate SHA；真实执行还须绑定 manifest/plan/fixture/validator/runtime 等合同输入，不用分支名替代 identity。

生命周期：ISSUED → ACTIVE → RUNNING_ATOMIC → CHECKPOINT → EXPIRED；治理变化 → REVOKED；P0 → EMERGENCY_STOP；禁止 indefinite ACTIVE。每个子任务返回后总控明确 REVIEW、ACCEPT/REJECT、必要时 REBASELINE；只有 ISSUE NEXT AUTHORITY 才能续跑。总控不得把 Agent Goal 当作后台永久线程。

### 12.5 当前裁定 / task snapshot

Capability State ≠ Execution Authority。当前 `R3=BLOCKED`、`browser_dynamic=disabled / runtime NO_GO`，同时 `Engineering Execution Authority=NONE` 完全合法。安全 NO_GO 既不是旧 Agent 无限修 Browser 的授权，也不是静态 DAG 无依赖路径的全局 veto。

PR #80（v2）、#81（composite contract）、#82（offline harness）已合并，来源 main 为 `335c6a2da418b2d3b2c4c70b59ee3d20d08c08cb`。PR #82 仅为 OFFLINE HARNESS READY，不是 R3 PASS；输入未变不重复其测试。R1..R2C、已消费 session、旧 source/inventory/stub 资产仅保留为历史 evidence。

| 旧任务 / identity | 中断现场及保全 | 当前 authority |
| --- | --- | --- |
| Backend `01a02d1e-f890-7e01-ad25-04c8bc7f0d1f`；旧 turn `01a0f728-aad6-7600-9f50-9702bdc957e7` | STOPPED，无活动命令；`feat/acq1-r3-composite-offline@a3980682b7fd306f130250978c3ef6dade224233`；角色报告该 commit 先于中断，未独立验收/发布；四份 Plan A dirty + 历史 untracked 全保留；未报告本轮 owned runtime | 所有后续接线/实现/repair/test/commit/push/PR/诊断/runtime/准入 REVOKED；单次只读快照已结束 |
| GitHub `01a02e6a-c14c-7d13-97c8-f39b6dbea384`；快照 turn `01a0f73b-1b06-7c42-b881-a08cb9f68bd5` | STOPPED，无活动命令；`codex/r3-composite-offline-publication@0908f82bd36e21b9437187b199500395e04ee778`，clean；PR #79 未合并 | 旧发布/自动合并/README/等待续权 REVOKED；单次只读快照已结束 |
| 历史协作子 Agent | 2026-10-02 live team inventory 仅 `/root` running；历史 R1C/R1D/R3/review 名称不是 live handle | 旧 authority STALE；不重启已结束任务 |

Preserved running indivisible atomic operations：NONE（两个原角色已报告无活动命令）。未审查/重跑 `a398068...`；不得将其历史 commit 当作恢复许可。唯一当前工作为总控 FT-GOV-V2.1 governance-only，及逐 checkpoint 新签的独立治理 Review/发布 lease。其他工程 authority 为 NONE；外部未知 task 若试图继续 FlowTracer 也必须满足完整 record，不能继承旧 Goal。

### 12.6 FT-GOV-002 / Möbius 经验与交接

Incident：FT-GOV-002。Failure：治理已 supersede，旧运行任务仍持有隐含 Goal continuation。Observed：Backend 在旧任务下继续 wiring/stub/test closure，总控等待 final candidate。Root Cause：把 authority 建模为 goal-level persistent permission，而非 checkpoint-scoped revocable lease。Correction：Authority Epoch、Atomic-operation Lease、Checkpoint Preemption、Revocation、Stale-task Detection、No Implicit Continuation。

FT-GOV-001：Governance itself can overgrow。FT-GOV-002：Authority itself can become stale。未来 Möbius 的经验模型为 Goal → Authority Lease → Execution → Evidence → Checkpoint → Authority Refresh/Revoke → Gate；所需 Task Contract、Exact SHA、Evidence Authority、Epoch、Lease、Revocation、Dependency DAG、Stage Gate 只记设计经验，不增加产品、runtime 或模块。

上下文不足时，总控交接必须带 v2/v2.1、实际 epoch 与合并状态、精确基准、现行 gate、有效/撤销 lease、任务快照、证据及待办。新窗口/新总控不继承旧工程执行权；重新核验后另签完整 authority。

### 12.7 本次验收与最终 STOP

只改 GOVERNANCE-V2、CURRENT-GATE、00-PROJECT-CONTROL、必要 delivery board；无平行治理文档。控制步骤：即时中断 → 盘点/安全快照（不等 Goal）→ 修订现有文档 → 独立治理 Review（P0/P1=0）→ 控制 PR → exact-head merge → 宣告 GOV-2.1 → STOP。每一步是可撤销、有界 lease，前一步结束不自动授权后一步。

验收逐项核对：抢占旧 Goal、原子动作/deadline、Goal≠authority、epoch、stale 检测、checkpoint refresh、无隐式续权、等待不延权、patch-loop 上限、capability/authority 分离、FT-GOV-002、v2 risk/DAG/A1/evidence-once 保持、无业务/API/Schema/runtime 漂移、独立 P0/P1=0。

禁止 business/API/Schema/migration、依赖安装、production config、Browser/Docker/R3 real session、R4/R5/WP4+。不重复 PR #82 离线证据。合并后旧任务不恢复，任何工程恢复必须另签 NEW TASK AUTHORITY。本章不取消既有安全、质量、精确 PR/merge 或可靠额度 <=5% 停点纪律。
