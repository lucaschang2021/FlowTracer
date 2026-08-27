# FlowTracer 当前阶段闸门

更新时间：2026-08-27。

- 当前稳定基准：`main@23afb336f28e07761fdcc4f1c835d876f9ac3c42`；BE-5 PR #14 已验收并合并。
- 当前阶段：Backend Phase BE-6 准入控制，Vector Memory 与知识库接口。
- 准入：BE-6 尚未生效；需先合并包含 `docs/09-BE6-MEMORY-BASELINE.md` 与 `docs/17-BE-6-ADMISSION.md` 的 PM-008 控制 PR。
- 当前控制分支：`chore/pm-be6-admission`；控制 PR 合并后 Backend 目标分支为 `feat/be-6`。

后续任务开始时只读取：本文件、`docs/02-DELIVERY-BOARD.md`、`docs/09-BE6-MEMORY-BASELINE.md`、`docs/17-BE-6-ADMISSION.md`、`docs/03-BACKEND-CONTRACT-BASELINE.md` 的 BE-6 补充、`docs/01-ARCHITECTURE-DECISIONS.md` 的 ADR-018，以及本次改动文件。无需回读全部历史基线。

最终候选验收：`py -m uv sync --locked`、Ruff、format、Mypy、Pytest（覆盖率不低于 85%）、隔离测试库迁移循环与 Alembic 零漂移、Compose config、`git diff --check`；补充 Fake Embedding 无公网、HNSW 定义、真实 PostgreSQL/Redis/Celery、无 Beat Worker、live/ready、同镜像非 root、SQL 所有权与 Bookmark 生命周期复验。

下一步：总控完成 PM-008 控制 PR；合并前 Backend 保持停点。合并后现有 Backend 任务从最新 `origin/main` 建立 `feat/be-6`，完成 commit、push、PR 后直接向总控汇报并停点。BE-7、Frontend、Integration、Release 均未准入。
