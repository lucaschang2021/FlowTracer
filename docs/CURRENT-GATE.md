# FlowTracer 当前阶段闸门

更新时间：2026-08-27。

- 当前稳定基准：`main@7955906259a64f34bc91f4db1eec30e807f3f29c`；BE-4 PR #11 已验收并合并。
- 当前阶段：PM-007，BE-5 Intelligence 契约冻结与准入控制。
- 准入：BE-5 仅在包含 `docs/08-BE5-INTELLIGENCE-BASELINE.md` 与 `docs/16-BE-5-ADMISSION.md` 的控制 PR 合并后生效；此前 Backend 必须停点。
- 当前控制分支：`chore/pm-be5-admission`，PR 待创建；Backend 目标分支为 `feat/be-5`。

后续任务开始时只读取：本文件、`docs/02-DELIVERY-BOARD.md`、`docs/08-BE5-INTELLIGENCE-BASELINE.md`、`docs/16-BE-5-ADMISSION.md`、`docs/03-BACKEND-CONTRACT-BASELINE.md`、`docs/01-ARCHITECTURE-DECISIONS.md` 中 ADR-017，以及本次改动文件。无需回读全部历史基线。

最终候选验收：`py -m uv sync --locked`、`py -m uv run ruff check .`、`py -m uv run ruff format --check .`、`py -m uv run mypy app`、`py -m uv run pytest -q`、使用隔离测试库执行 `py -m uv run alembic check`、`docker compose -f infra/compose.yaml config --quiet`、`git diff --check`；补充无公网 Fake Provider、真实 PostgreSQL/Redis/Celery、无 Beat Worker、live/ready、同镜像非 root 复验。

下一步：提交并通过 PM-007 控制文档 PR。合并后才可在现有 Backend 任务中从最新 `origin/main` 建立 `feat/be-5`，完成后直接向总控汇报。BE-6、Frontend、Integration、Release 均未准入。
