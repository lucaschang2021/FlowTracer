# FlowTracer Governance v2 — Adaptive Risk-Based Governance

状态：CONTROL REBASELINE — GOVERNANCE ONLY；本控制 PR 合并后生效。

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

本文件合并前只是候选；合并后 supersede docs/37、41、49 的现行治理/验收合同，以及其他历史文档中相冲突的绝对串行/P2 blanket blocker 语义。旧记录作为历史事实，不得再次当作当前开工许可。CURRENT-GATE 给出现行准入，delivery board 的旧行只作归档，下一次同步不得反向覆盖现行裁定。

PR #79 暂不合并；本包合并后重新评估 README 内容，过时则 supersede，不现在追赶旧治理表述。

本包流程：审计 → 单一核心文档与现有文档同步 → 文档/架构一致性检查 → 独立治理 Review（P0/P1=0）→ 控制 PR → exact-head merge → STOP。纯文档不重复业务全量测试、不运行 Browser/Docker。合并后只可另申请 Dependency Re-evaluation，不自动运行 session 或 WP4。

SSRF/SitePolicy/预算、无公网测试、无凭据/登录态、无 CAPTCHA/访问控制绕过、namespace、非 root、只读、禁止 host network/privileged/Docker socket、NetworkPolicy 与精确清理全部保持；本次只有 Governance Simplification，没有 Safety Deregulation。
