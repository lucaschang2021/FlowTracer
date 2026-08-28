# FlowTracer BE-8 阶段准入

状态：待控制 PR 合并后生效
准入基准：`main@d30fcfd02d4d62e7b16282a004a74a19c8f7685f`
目标分支：`feat/be-8`

## 准入条件

- BE-7 PR #23 已独立验收并合并。
- `docs/20-BE8-STABILIZATION-HANDOFF-BASELINE.md`、ADR-020、交付看板和契约补充位于同一控制 PR。
- 只有本控制 PR 合并后，Backend 才可从最新 `origin/main` 创建 `feat/be-8`。

## 授权范围

仅授权 Alpha 后端稳定化、完全离线闭环测试、缺陷修复、OpenAPI 导出/校验、运行与迁移文档、前端交接包、已知限制和轻量性能基线。不得新增业务能力、Schema/迁移、Endpoint、事件、评分、Provider、Pipeline 状态、依赖或前端代码。

## 执行要求

- 开始时只读取 CURRENT-GATE、本准入文件、BE-8 baseline、BE-8 契约补充和本次相关文件。
- 开发期优先定向测试；最终候选 commit 仅执行一次完整门禁。
- 所有数据与服务使用隔离测试环境；测试不得访问公网或破坏开发卷。
- 任何契约差异、迁移需要、P0/P1、安全或数据一致性风险立即停点。
- commit、push、PR 后直接向总控报告；不得自行 merge、批准 Frontend、进入 Integration 或 Release。

## 验收产物

- 完全离线 Alpha 闭环与全量回归证据。
- OpenAPI JSON 与前端交接包。
- 空库迁移循环、零漂移、Compose/Celery/Beat/健康检查证据。
- 安全、权限、并发、幂等、性能、已知限制和复现步骤。
- 精确 commit、PR 与阶段报告。
