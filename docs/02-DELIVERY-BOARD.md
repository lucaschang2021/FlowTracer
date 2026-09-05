# FlowTracer Alpha v0.1 交付看板

## 当前阶段

**M0：架构初步冻结 — 已完成**

**当前阶段：Architecture Governance AG-3（Acquisition Ports 与最小 DI）— 候选提交已完成，待 PR、Review 与验收合并；AG-4..AG-6 尚未准入**

ACQ-1 WP-3（ACQ-1B Dynamic + H-browser）兼容性与隔离证据仍未冻结，继续阻塞且未准入；Frontend、Integration 与 Release 同样未准入。

本次同步事实基准：`main@3bc456e6b7f6e4f8a6a545276d255646c1db3c73`。

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
| ARC-AG3 | Acquisition Ports 与最小 DI | Backend / Architecture | 候选完成；待 PR、Review 与验收合并 | ARC-AG2 | 目标分支 `feat/architecture-governance`；候选 `ce26640e3c2f994c8036b18a2c2b984dee045c53`，不得视为已进入 `main` |
| ARC-AG4..6 | Composition/import safety、后续边界治理与最终兼容门禁 | Backend / Architecture | 未准入 | ARC-AG3 验收合并后逐阶段准入 | `ARCHITECTURE.toml`、`ARCHITECTURE-GOVERNANCE.md` |
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
| PM-017 | ACQ-1 WP-2 Stage Gate 验收归档 | 总控 | 完成（PR #40 已合并） | ACQ-1-WP2 | PR #40、`36-ACQ1-WP2-ACCEPTANCE.md`、merge commit `70a3b0462e9a9303ddb3f5be56c84ed5d2fead40` |
| PM-018 | ACQ-1 WP-3 架构/契约冻结与准入 | 总控 | 阻塞；未准入 | PM-017、WP-3 兼容性/隔离硬门禁 | `37-ACQ1-WP3-READINESS-BLOCKER.md`；精确 package/revision/system dependencies/image digest、egress 与资源限值证据缺失 |
| ACQ-1-WP3 | Dynamic/Advanced Browser、隔离 worker/queue 与受控 egress | Backend | 未准入 | PM-018 控制 PR 合并 | `29-ACQ1-WORK-PACKAGES.md`；不得开工或派发 |
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

