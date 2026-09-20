# FlowTracer Alpha v0.1 交付看板

## 当前阶段

**M0：架构初步冻结 — 已完成**

**当前阶段：R1E 已验收合并；R2C-A3 controlled egress 完整回归重新准入**

Architecture Governance Pass 已完成。R1E 已通过独立复审、Backend CI 与 PR #66 合并，`/etc/shadow` 保持纳入 Runtime Identity v2 且账户元数据跨日确定。当前仅重新准入 R2C-A3；R3、R4-R5、正式 WP-3、Frontend、Integration 与 Release 均未准入。

本次同步事实基准：`main@cac5b4e1908801ff4ed1a96c2388a0a71653d6ee`（R1E PR #66 merge commit）。

## 工作项

| ID | 工作项 | 负责人窗口 | 状态 | 依赖 | 验收产物 |
| --- | --- | --- | --- | --- | --- |
| ARC-001 | Alpha 范围与非目标 | 总控 | 完成 | - | `00-PROJECT-CONTROL.md` |
| ARC-002 | 核心技术决策 ADR | 总控 | 完成 | ARC-001 | `01-ARCHITECTURE-DECISIONS.md` |
| ARC-003 | 领域模型与 ERD | 总控 | 完成 | ARC-002 | `03-BACKEND-CONTRACT-BASELINE.md` |
| ARC-004 | Pipeline 状态机 | 总控 | 完成 | ARC-003 | `03-BACKEND-CONTRACT-BASELINE.md` |
| ARC-005 | REST API 契约 | 总控 | 完成 | ARC-003 | `03-BACKEND-CONTRACT-BASELINE.md` |
| ARC-006 | WebSocket 事件契约 | 总控 | 完成 | ARC-004 | `03-BACKEND-CONTRACT-BASELINE.md` |
| ARC-007 | AI 与评分规格 | 总控 | 完成 | ARC-003 | `03-BACKEND-CONTRACT-BASELINE.md` |
| ARC-008 | 安全与部署规格 | 总控 | 完成 | ARC-002 | `01-ARCHITECTURE-DECISIONS.md`、`03-BACKEND-CONTRACT-BASELINE.md` |
| ARC-AG0 | Architecture Governance 合同冻结与严重度校准 | Architecture / 总控 | 完成（已合并） | ARC-008 | PR #42、PR #43、`ARCHITECTURE.toml`、`ARCHITECTURE-GOVERNANCE.md` |
| ARC-AG1 | Executable Gate Foundation | Backend / Architecture | 完成（已验收、已合并） | ARC-AG0 | PR #44、machine baseline、Architecture CI/gate/tests |
| ARC-AG2 | Intelligence 纯领域策略与兼容委托 | Backend / Architecture | 完成（已验收、已合并） | ARC-AG1 | PR #45、`backend/app/domains/intelligence_policy.py` |
| ARC-AG3 | Acquisition Ports 与最小 DI | Backend / Architecture | 完成（已验收、已合并） | ARC-AG2 | PR #47、候选 `ce26640e3c2f994c8036b18a2c2b984dee045c53`、merge commit `190a71754a7a0f3a5de3e664bbfa77e4eea945bc`；Architecture Gate `existing=152 / introduced=0 / resolved=5 / P0=0`，Backend CI success |
| ARC-AG4 | Composition and Import Safety | Backend / Architecture | 完成（已验收、已合并） | ARC-AG3 | PR #49、候选 `78ddf49ed6ddf94204465cd16dd96163cb93d834`、merge commit `f1494c7f843782523f728913e08774331ec8163f`；Architecture Gate `existing=130 / introduced=0 / resolved=27 / P0=0`，CI run `34029206838` SUCCESS |
| ARC-AG5 | Conditional Memory Policy | Backend / Architecture | 完成（no-code characterization audit） | ARC-AG4 | Memory ownership/bookmark/filter、cosine distance、稳定排序、top-k 保持 PostgreSQL/pgvector SQL；六位量化不单独抽取；无 retention contract；无代码/commit/测试变更，`introduced P0/P1/P2=0` |
| ARC-AG6 | Final Compatibility Gate / Architecture Governance Pass 结项 | Backend / Architecture | 完成（no-code PASS） | ARC-AG5 | `main@81a9739c986eaef50fa43ba9a7d32689bceddf03`；Architecture `existing=130 / introduced=0 / resolved=27 / P0=0 / P1=114 / P2=16`；EX-001/003/004/007 关闭；356 passed、88.12%；OpenAPI/Alembic/Schema/ACQ/Compose/Ruff/Mypy 通过且零漂移 |
| PM-001 | Backend 执行任务包 | 总控 | 完成 | ARC-003..008 | `10-BACKEND-WORK-PACKAGE.md` |
| BE-0 | 工程盘点与实施计划 | Backend | 完成（已验收） | PM-001 | `11-BE-0-ACCEPTANCE.md` |
| PM-002 | BE-1 工程基线 | 总控 | 完成 | BE-0 | `04-BE1-ENGINEERING-BASELINE.md` |
| ENV-001 | Docker Desktop / WSL 2 环境 | 用户 / 总控 | 完成 | PM-002 | Docker/Compose/WSL 2/`hello-world` 复核通过 |
| PM-003 | BE-1 阶段准入 | 总控 | 完成 | PM-002、ENV-001 | `12-BE-1-ADMISSION.md` |
| BE-1 | 基础骨架与本地基础设施 | Backend | 完成（已验收、已合并） | PM-003 | PR #4、代码、空迁移、测试、Compose 与阶段报告 |
| PM-004 | BE-2 数据与认证基线及准入 | 总控 | 完成 | BE-1 | `05-BE2-DATA-AUTH-BASELINE.md`、`13-BE-2-ADMISSION.md` |
| BE-2 | 数据模型、迁移、认证与用户 | Backend | 完成（已验收、已合并） | PM-004 | PR #6、代码、迁移、测试、OpenAPI 与阶段报告 |
| PM-005 | BE-3 Radar/Source 基线及准入 | 总控 | 完成 | BE-2 | `06-BE3-RADAR-SOURCE-BASELINE.md`、`14-BE-3-ADMISSION.md`、PR #7 |
| BE-3 | Radar 与 Source 管理 | Backend | 完成（已验收、已合并） | PM-005 | PR #8、CRUD、绑定、URL 规范化、测试、OpenAPI 与阶段报告 |
| PM-006 | BE-4 采集基线及准入 | 总控 | 完成 | BE-3 | `07-BE4-ACQUISITION-BASELINE.md`、`15-BE-4-ADMISSION.md`、PR #10 |
| BE-4 | RSS、URL 采集与任务调度 | Backend | 完成（已验收、已合并） | PM-006 | PR #11、采集 Pipeline、测试、安全复审与阶段报告 |
| PM-007 | BE-5 Intelligence 基线及准入 | 总控 | 完成 | BE-4 | `08-BE5-INTELLIGENCE-BASELINE.md`、`16-BE-5-ADMISSION.md`、PR #12 |
| BE-5 | 清洗、AI 分析、评分与成本 | Backend | 完成（已验收、已合并） | PM-007 | PR #14、Document/Analysis、Provider、评分、Usage、Intelligence API、测试与阶段报告 |
| PM-008 | BE-6 Vector Memory 基线及准入 | 总控 | 完成 | BE-5 | `09-BE6-MEMORY-BASELINE.md`、`17-BE-6-ADMISSION.md`、ADR-018、PR #15 |
| BE-6 | Vector Memory 与知识库接口 | Backend | 完成（已验收、已合并） | PM-008 | PR #19、Chunk/Embedding、HNSW、Bookmark、Memory Search、测试与阶段报告 |
| PM-009 | BE-7 Notification/WebSocket/恢复基线及准入 | 总控 | 完成 | BE-6 | `18-BE7-NOTIFICATION-WS-BASELINE.md`、`19-BE-7-ADMISSION.md`、ADR-019、PR #20 |
| BE-7 | Notification、WebSocket 与恢复 | Backend | 完成（已验收、已合并） | PM-009 | PR #23、Notification、在线事件、CollectionRun retry、补偿调度、测试与阶段报告 |
| PM-010 | BE-8 稳定化与前端交接基线及准入 | 总控 | 完成 | BE-7 | `20-BE8-STABILIZATION-HANDOFF-BASELINE.md`、`21-BE-8-ADMISSION.md`、ADR-020、PR #24 |
| BE-8 | 后端稳定化与前端交接 | Backend | 完成（已验收、已合并） | PM-010 | PR #26、236 tests、OpenAPI 冻结、离线闭环、迁移/运行证据与前端交接包 |
| PM-011 | ACQ-1 Preflight 准入 | 总控 | 完成 | BE-8 | `26-ACQ1-PREFLIGHT-ADMISSION.md`、ADR-021 |
| ACQ-1-PF | ACQ-1 工程盘点与实施计划 | Backend / Architecture | 完成（已验收） | PM-011 | `27-ACQ1-PREFLIGHT-ACCEPTANCE.md`、ACQ-1A..H 计划、契约影响、测试矩阵与风险报告 |
| PM-012 | ACQ-1 Contract Freeze 准入 | 总控 | 完成 | ACQ-1-PF | `28-ACQ1-CONTRACT-FREEZE-ADMISSION.md` |
| ACQ-1-CF | Acquisition / Opportunity / Safety 契约冻结 | Architecture / 总控 | 完成（已验收、已合并） | PM-012 | PR #30、ADR-022..026、`22-ACQ1-MASTER-BASELINE.md`、`23-ACQ1-ACQUISITION-CONTRACT.md`、`24-ACQ1-OPPORTUNITY-RADAR.md`、`25-ACQ1-ACCEPTANCE.md`、`29-ACQ1-WORK-PACKAGES.md`、`30-ACQ1-CONTRACT-FREEZE-ACCEPTANCE.md` |
| PM-013 | ACQ-1 WP-1（ACQ-1A + H0）准入 | 总控 | 完成（已合并） | ACQ-1-CF | PR #31、`31-ACQ1-WP1-ADMISSION.md` |
| PM-014 | ACQ-1 WP-1 精确枚举/Profile/Policy Addendum | 总控 | 完成（已合并） | PM-013 | PR #32、ADR-027、`32-ACQ1-WP1-CONTRACT-ADDENDUM.md` |
| ACQ-1-WP1 | Source Contract、安全内核、预算与运行状态 | Backend | 完成（已验收、已合并） | PM-013、PM-014 | PR #33、`33-ACQ1-WP1-ACCEPTANCE.md`、Migration、Source API、lease recovery、Policy、264 tests/87.76% |
| PM-015 | ACQ-1 WP-2（ACQ-1B + D-static）准入 | 总控 | 完成（已合并） | ACQ-1-WP1 | PR #35、`34-ACQ1-WP2-ADMISSION.md` |
| PM-016 | ACQ-1 WP-2 quality v1 / writer / family-evidence 契约 Addendum | 总控 | 完成（已合并） | PM-015 | PR #37、ADR-028、`35-ACQ1-WP2-CONTRACT-ADDENDUM.md` |
| ACQ-1-WP2 | Static Adapter、Scrapling parser、quality v1 | Backend | 完成（已验收、已合并） | PM-015、PM-016 | PR #39、`36-ACQ1-WP2-ACCEPTANCE.md`、286 passed、87.61%、P0/P1/P2=0/0/0 |
| PM-017 | ACQ-1 WP-2 Stage Gate 验收归档 | 总控 | 完成（PR #40 已合并） | ACQ-1-WP2 | `36-ACQ1-WP2-ACCEPTANCE.md`、merge commit `70a3b0462e9a9303ddb3f5be56c84ed5d2fead40`、PR #40 merge commit `f4b58c1ec0d20d075b98d5a9ca3d146d0b4deb56` |
| PM-018 | ACQ-1 WP-3 架构/契约冻结与正式准入 | 总控 | 阻塞；未准入 | PM-017、WP-3 兼容性/隔离硬门禁 | `37-ACQ1-WP3-READINESS-BLOCKER.md`；等待 Spike 实证、独立审查及后续 Contract Addendum + Admission PR |
| PM-019 | ACQ-1 WP-3 Compatibility/Isolation Preflight 准入 | 总控 | 完成（PR #41 已合并） | PM-017、ADR-029/030 | `38-ACQ1-WP3-PREFLIGHT-ADMISSION.md`；只准入证据实验，不准入正式 WP-3 |
| ACQ-1-WP3-PF | Browser 兼容性、不可变构建、egress、queue/worker 与资源隔离 Spike | Backend | 已执行；BLOCKED | PM-019 | `40-ACQ1-WP3-PREFLIGHT-BLOCKED-REPORT.md`；P0×1/P1×5/P2×2，无代码/commit/push/PR，临时资源已清理 |
| PM-020 | ACQ-1 WP-3 Remediation Evidence 顺序闸门准入 | 总控 | 完成（PR #53 已合并） | ACQ-1-WP3-PF、ADR-031 | `41-ACQ1-WP3-REMEDIATION-EVIDENCE-ADMISSION.md`；仅 R1→R5 证据/原型，不准入正式 WP-3 |
| ACQ-1-WP3-R1 | Locked image、SBOM/license 与双 no-cache 构建证据 | Backend / Architecture | 完成（PR #54 已验收合并） | PM-020 | `42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md`；commit `89ed802f4f2ac608a260f68637f1aaf541cd3143`；merge `34364d0082e4ecdbe4331d77a21ef6d25c2fca8a`；P0/P1/P2=0/0/0 |
| ACQ-1-WP3-R2 | Production-shaped controlled egress proxy/namespace 证据 | Backend / Architecture | 完成（PR #56 已验收合并） | ACQ-1-WP3-R1 | `43-ACQ1-WP3-R2-ACTIVATION.md`、`42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md`；commit `7c6e778e05c34bb8341d6898eea729de5dc311b2`；merge `c5799082ba8e0ae5edf8ddfb861e24de784cdf93`；P0/P1/P2=0/0/0 |
| ACQ-1-WP3-R3 | Application interception matrix 证据 | Backend / Architecture | BLOCKED（P1×1） | ACQ-1-WP3-R2 | `44-ACQ1-WP3-R3-ACTIVATION.md`；DynamicFetcher 要求完整 Chromium，现有 R1 Headless Shell 不兼容 |
| ACQ-1-WP3-R1C | Full Chromium runtime compatibility remediation | Backend / Architecture | 完成（PR #60 已验收合并） | ACQ-1-WP3-R3 BLOCKED | `45-ACQ1-WP3-R3-RUNTIME-REMEDIATION.md`、`42-ACQ1-WP3-REMEDIATION-EVIDENCE-PACKAGE.md`；candidate `787a0df0548e05431fa60426f48f239ba7195465`；merge `df0c3512080f384dbd6c820d7627cbe721e37422`；P0/P1/P2=0/0/0 |
| ACQ-1-WP3-R1D | Runtime Identity v2 与 runtime/audit 边界修复 | Backend / Architecture | 完成（PR #63 已验收合并） | ACQ-1-WP3-R2C BLOCKED | ADR-032、`47-ACQ1-WP3-R1D-RUNTIME-IDENTITY.md`；candidate `a804a371ec99615278c2cd60f442dc58299ff7c5`；merge `db9c4fad0ca826b472d18d85c69db53848cfcd94`；P0/P1/P2=0/0/0 |
| ACQ-1-WP3-R1E | Deterministic account metadata 与跨日 Runtime Identity v2 修复 | Backend / Architecture | 完成（PR #66 已验收合并） | ACQ-1-WP3-R2C-A2 BLOCKED | ADR-033、`48-ACQ1-WP3-R1E-DETERMINISTIC-ACCOUNT.md`；head `3636dd261ece31c046406aa7b2279f6f7bd7dad8`；merge `cac5b4e1908801ff4ed1a96c2388a0a71653d6ee`；P0/P1/P2=0/0/0 |
| ACQ-1-WP3-R2C | R1C/R1D/R1E 完整 Chromium 上的 controlled egress 完整回归 | Backend / Architecture | 已重新准入；待执行 | ACQ-1-WP3-R1E Accepted | `46-ACQ1-WP3-R2C-ACTIVATION.md`；仅准入网络矩阵与证据，不含 R3 |
| ACQ-1-WP3-R4..R5 | 回收/资源与双 worker 隔离证据 | Backend | 未准入 | 前序 remediation gate 逐项 PASS | `41-ACQ1-WP3-REMEDIATION-EVIDENCE-ADMISSION.md`；不得并行或跳过 |
| ACQ-1-WP3 | Dynamic/Advanced Browser、隔离 worker/queue 与受控 egress | Backend | 正式实现未准入 | PM-018 后续正式 Admission PR 合并 | `29-ACQ1-WORK-PACKAGES.md`；不得由 Preflight 直接续做 |
| ACQ-1-WP4..8 | ACQ-1 后续工作包 | Backend | 未准入 | WP-3 起逐阶段验收 | `29-ACQ1-WORK-PACKAGES.md` |
| PLUGIN-1 | 用户指定的后续插件工作包 | 待定 | 待办、未准入 | ACQ-1 全部完成验收后、Frontend 前 | 尚无正式准入或架构基线；不得视为已实现 |
| FE-001 | 前端实现 | Frontend | 未准入 | ACQ-1 经总控验收并冻结 Acquisition Contract | 桌面端与前端测试 |
| INT-001 | 集成与缺陷修复 | Integration | 未准入 | ACQ-1、FE-001 | E2E 报告与缺陷闭环 |
| REL-001 | GitHub Alpha 发布 | Release | 未准入 | INT-001 | 仓库、CI、Tag、Release |

## 汇报格式

每次总控汇报固定包含：

1. 已完成。
2. 当前进行。
3. 风险或阻塞。
4. 下一步及阶段准入情况。

## 变更控制

- 新需求先进入范围评估，不直接插入开发任务。
- 影响数据库、API 或 Pipeline 的变更必须记录 ADR 或修订现有 ADR。
- 已通过阶段闸门后发生破坏性契约变更，必须同时给出迁移和回归测试计划。
- P0：核心闭环不可用或数据/凭据安全问题；P1：核心功能严重受损；P2：有替代路径；P3：体验优化。

