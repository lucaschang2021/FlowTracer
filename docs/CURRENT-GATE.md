# FlowTracer 当前阶段闸门

更新时间：2026-08-27。

- 当前稳定基准：`main@74facf7cd93c236c8be012c82232b299a7ca6912`；PM-008 控制文档 PR #15 已合并。
- 当前阶段：Backend Phase BE-6，Vector Memory 与知识库接口实现。
- 准入：BE-6 已批准；Backend 必须严格执行 `docs/09-BE6-MEMORY-BASELINE.md` 与 `docs/17-BE-6-ADMISSION.md`，完成后停点并直接向总控汇报。
- 当前进度同步分支：`chore/pm-be6-activate`；Backend 目标分支为 `feat/be-6`。

后续任务开始时只读取：本文件、`docs/02-DELIVERY-BOARD.md`、`docs/09-BE6-MEMORY-BASELINE.md`、`docs/17-BE-6-ADMISSION.md`、`docs/03-BACKEND-CONTRACT-BASELINE.md` 的 BE-6 补充、`docs/01-ARCHITECTURE-DECISIONS.md` 的 ADR-018，以及本次改动文件。无需回读全部历史基线。

最终候选验收：`py -m uv sync --locked`、Ruff、format、Mypy、Pytest（覆盖率不低于 85%）、隔离测试库迁移循环与 Alembic 零漂移、Compose config、`git diff --check`；补充 Fake Embedding 无公网、HNSW 定义、真实 PostgreSQL/Redis/Celery、无 Beat Worker、live/ready、同镜像非 root、SQL 所有权与 Bookmark 生命周期复验。

下一步：现有 Backend 任务从最新 `origin/main` 建立 `feat/be-6` 并实施 BE-6；完成 commit、push、PR 后直接向总控汇报并停点。BE-7、Frontend、Integration、Release 均未准入。
