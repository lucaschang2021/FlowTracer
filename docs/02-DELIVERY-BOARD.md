# FlowTracer Alpha v0.1 交付看板

## 当前阶段

**M0：架构初步冻结 — 已完成**

**当前阶段：BE-1 工程基线已冻结；等待 Docker/WSL 2 环境（BE-1 尚未准入）**

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
| PM-001 | Backend 执行任务包 | 总控 | 完成 | ARC-003..008 | `10-BACKEND-WORK-PACKAGE.md` |
| BE-0 | 工程盘点与实施计划 | Backend | 完成（已验收） | PM-001 | `11-BE-0-ACCEPTANCE.md` |
| PM-002 | BE-1 工程基线 | 总控 | 完成 | BE-0 | `04-BE1-ENGINEERING-BASELINE.md` |
| ENV-001 | Docker Desktop / WSL 2 环境 | 用户 / 总控 | 阻塞 | PM-002 | `docker version`、`docker compose version`、`hello-world` |
| BE-1 | 基础骨架与本地基础设施 | Backend | 未准入 | PM-002、ENV-001 | 代码、空迁移、测试、Compose 与阶段报告 |
| BE-2..BE-8 | 后端业务闭环与稳定化 | Backend | 未准入 | 前一 Backend Phase 经总控验收 | 代码、迁移、测试、OpenAPI 与阶段报告 |
| FE-001 | 前端实现 | Frontend | 未准入 | BE-8 经总控验收，后端契约稳定 | 桌面端与前端测试 |
| INT-001 | 集成与缺陷修复 | Integration | 未准入 | BE-8、FE-001 | E2E 报告与缺陷闭环 |
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

