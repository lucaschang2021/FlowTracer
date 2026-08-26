# FlowTracer 当前阶段闸门

更新时间：2026-08-26。

- 当前稳定基准：`main`，`722fc51`；BE-3 PR #8 已验收并合并，控制文档 PR #9 已合并。
- 当前阶段：PM-006，BE-4 采集契约冻结与准入控制。
- 准入：BE-4 仅在包含 `docs/07-BE4-ACQUISITION-BASELINE.md` 与 `docs/15-BE-4-ADMISSION.md` 的控制 PR 合并后生效；在此之前 Backend 不得正式开工。
- 当前控制分支/PR：待创建 `chore/pm-be4-admission`；Backend 目标分支为 `feat/be-4`。

开始任何后续任务前仅读取：本文件、`docs/02-DELIVERY-BOARD.md`、对应 Phase 的准入与基线文件；涉及接口/数据模型时追加 `docs/03-BACKEND-CONTRACT-BASELINE.md` 与相应 ADR。

验收命令（仅在获准的最终待审 commit 上执行）：`py -m uv sync --locked`、`py -m uv run ruff check .`、`py -m uv run ruff format --check .`、`py -m uv run mypy app`、`py -m uv run pytest -q`、`py -m uv run alembic check`、`docker compose -f infra/compose.yaml config --quiet`；按阶段风险补充真实服务探活。

下一步：提交并合并 PM-006 控制 PR；随后创建全新的 Backend BE-4 任务，从最新 `origin/main` 建立 `feat/be-4`，完成后直接向总控汇报。BE-5、Frontend、Integration、Release 均未准入。
