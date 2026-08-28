# FlowTracer 当前阶段闸门

更新时间：2026-08-28。

- 当前稳定基准：`main@a0a4af7d1bd9b7f7b9d613d78ce9a13fe367fcd3`；BE-7 控制文档 PR #20 已 Review 并合并，PM-009 已完成。
- 当前阶段：Backend Phase BE-7，Notification、WebSocket 与恢复实现（已准入，开发进行中）。
- 准入：BE-7 已正式生效；Backend 必须严格执行 `docs/18-BE7-NOTIFICATION-WS-BASELINE.md` 与 `docs/19-BE-7-ADMISSION.md`，完成后停点并直接向总控汇报。
- 当前激活同步分支：`chore/pm-be7-activate`；Backend 目标分支为 `feat/be-7`。

后续任务开始时只读取：本文件、`docs/02-DELIVERY-BOARD.md`、`docs/18-BE7-NOTIFICATION-WS-BASELINE.md`、`docs/19-BE-7-ADMISSION.md`、`docs/03-BACKEND-CONTRACT-BASELINE.md` 的 BE-7 补充、`docs/01-ARCHITECTURE-DECISIONS.md` 的 ADR-019，以及本次改动文件。无需回读全部历史基线。

最终候选验收：`py -m uv sync --locked`、Ruff、format、Mypy、Pytest（覆盖率不低于 85%）、隔离测试库 `py -m uv run alembic check`（预期无迁移）、Compose config、`git diff --check`；补充 Notification/Retry 并发幂等、真实 Redis Pub/Sub、WebSocket 鉴权/隔离/背压、OpenAPI/秘密扫描、无 Beat Worker、Celery pong、live/ready、API/Worker 同镜像非 root 复验，测试不得访问公网。

下一步：Backend 在新的 BE-7 任务中从最新 `origin/main` 建立 `feat/be-7` 并实施已冻结范围；完成 commit、push、PR 后直接向总控汇报并停点。BE-8、Frontend、Integration、Release 均未准入。
