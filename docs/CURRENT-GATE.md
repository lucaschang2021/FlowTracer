# FlowTracer 当前阶段闸门

更新时间：2026-08-28。

- 当前稳定基准：`main@d30fcfd02d4d62e7b16282a004a74a19c8f7685f`；BE-7 PR #23 已完成独立验收并合并，BE-7 已完成。
- 当前阶段：PM-010，BE-8 稳定化与前端交接基线/准入待 Review 与合并。
- 准入：BE-8 尚未生效；本控制 PR 合并后，Backend 才可从最新 `origin/main` 创建 `feat/be-8`。
- 下游：Frontend、Integration、Release 均未准入。

后续任务开始时只读取：本文件、`docs/02-DELIVERY-BOARD.md`、`docs/20-BE8-STABILIZATION-HANDOFF-BASELINE.md`、`docs/21-BE-8-ADMISSION.md`、`docs/03-BACKEND-CONTRACT-BASELINE.md` 的 BE-8 补充、`docs/01-ARCHITECTURE-DECISIONS.md` 的 ADR-020，以及本次改动文件。无需回读全部历史基线。

BE-8 仅用于 Alpha 后端收尾：全链路离线闭环、全量回归、OpenAPI 导出与冻结、运行/迁移/测试文档、性能与安全基线、前端交接包和已知限制。不得新增业务能力、数据库 Schema/迁移、公开 Endpoint、评分规则、Provider、深爬、前端代码或 BE-8 以外范围；若发现必须改变冻结契约，立即停点并提交 ADR。

最终候选验收：locked sync、Ruff、format、Mypy、完整 Pytest（覆盖率不低于 85%）、空库 upgrade/downgrade/re-upgrade 与 Alembic 零漂移、Compose config、`git diff --check`；使用 Fake Analysis/Embedding Provider 和本地 Fixture 完成注册到 Notification/Memory 的离线闭环，验证 API/Worker 同镜像非 root、live/ready、Celery/Beat、OpenAPI、安全扫描与可重复启动。测试不得访问公网。

下一步：Review 并合并 BE-8 控制 PR；合并前 Backend 不得开始 BE-8。BE-8 完成并经总控验收后，Backend Alpha 才可关闭，并由总控另行决定是否准入 Frontend。
