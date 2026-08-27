# FlowTracer 当前阶段闸门

更新时间：2026-08-27。

- 当前稳定基准：`main@974c3adb2775286b9fd97ca00aeb69a0e42bccf3`；PM-007 控制文档 PR #12 已合并。
- 当前阶段：Backend Phase BE-5，清洗、AI 分析、评分与成本实现。
- 准入：BE-5 已批准；Backend 必须严格执行 `docs/08-BE5-INTELLIGENCE-BASELINE.md` 与 `docs/16-BE-5-ADMISSION.md`，完成后停点并直接向总控汇报。
- 当前进度同步分支：`chore/pm-be5-activate`；Backend 目标分支为 `feat/be-5`，PR 待开发完成后创建。

后续任务开始时只读取：本文件、`docs/02-DELIVERY-BOARD.md`、`docs/08-BE5-INTELLIGENCE-BASELINE.md`、`docs/16-BE-5-ADMISSION.md`、`docs/03-BACKEND-CONTRACT-BASELINE.md`、`docs/01-ARCHITECTURE-DECISIONS.md` 中 ADR-017，以及本次改动文件。无需回读全部历史基线。

最终候选验收：`py -m uv sync --locked`、`py -m uv run ruff check .`、`py -m uv run ruff format --check .`、`py -m uv run mypy app`、`py -m uv run pytest -q`、使用隔离测试库执行 `py -m uv run alembic check`、`docker compose -f infra/compose.yaml config --quiet`、`git diff --check`；补充无公网 Fake Provider、真实 PostgreSQL/Redis/Celery、无 Beat Worker、live/ready、同镜像非 root 复验。

下一步：现有 Backend 任务从 `main@974c3adb2775286b9fd97ca00aeb69a0e42bccf3` 建立 `feat/be-5` 并实施 BE-5；完成 commit、push、PR 后直接向总控汇报并停点。BE-6、Frontend、Integration、Release 均未准入。
