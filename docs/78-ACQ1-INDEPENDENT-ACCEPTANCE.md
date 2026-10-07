# ACQ-1 独立收口验收记录

日期：2026-10-07。结论：**READY_FOR_FRONTEND（后端交接就绪）**；这不是 Frontend、Integration 或 Release 的开发准入，也不是远端发布或 GitHub 合并记录。

## 精确输入与证据边界

- 交付候选来源：本地 `main@48c2e2260f303ef0b18470a4d31fb6cb8f73070d`，Phase 0–5 的历史证据见 [收口计划](71-ACQ1-CLOSURE-PLAN.md)及 `docs/72`–`docs/77`。
- 独立复核代码提交：`01155294f151cb1c453ddbaf8af6ed34ef3228c1`，本地分支 `fix/acq1-delivery-closure`。其上一提交 `4af0df2e233c7a915f4bcea56ae6b9cdda6c05ad` 只修订交付文档与验收器；`0115529` 仅修复 `change_tracking.py` 的类型返回，无业务语义变更。
- 本记录及状态同步为后续纯文档提交。完整测试、迁移和运行证据绑定上述精确代码提交；不声称文档提交另行执行全量门禁。
- 仓库包无可用于本次发布的远端；未 push、创建 PR、merge 或启动 Frontend。

## 独立门禁

| 项目 | 结果 |
| --- | --- |
| 完整 Pytest（Linux LF checkout、隔离 PostgreSQL/Redis、无公网出口） | **504 passed**，0 failed，250 warnings；覆盖率 **89.49%**，高于 87.61% 门槛 |
| Ruff check / format | 通过；294 files already formatted |
| Mypy `app` | 通过；109 source files |
| Architecture Gate | `introduced=0`、`p0_total=0`、`resolved=28`、`status=passed`；129 项历史 baseline 不代表新违例 |
| 冻结 OpenAPI `--check` / secret scan / Compose config / `git diff --check` | 全部通过 |
| 空库迁移循环 | `upgrade head → downgrade base → upgrade head → alembic check` 全通过；head=`20261006_0009`，无新 upgrade operation |

首次独立测试在 Windows 只读绑定副本上报告 501 passed / 3 failed：两项因该临时 runner 缺少 Git，一项因 Windows `core.autocrlf` 将冻结 OpenAPI 的工作树字节转成 CRLF。验收方未把夹具故障归为产品缺陷；改用同一精确提交的隔离 Linux LF checkout、离线提供 Git 后，只执行一次最终完整 Pytest，取得上表结果。此前 Mypy 的两项 `no-any-return` 是真实静态问题，已由 `0115529` 修复后复验通过。

## 运行与交接

- 独立构建候选镜像成功。隔离库**先迁移**，再启动 API/Worker；API、Worker、PostgreSQL、Redis 正常。API/Worker 使用同一镜像、非 root UID 10001；Worker 未挂载额外卷。
- `health/live=ok`；`health/ready=ready` 且 database/redis 均为 ok；Celery `inspect ping` 返回 pong。
- 内嵌 Beat 的 schedule 文件归 UID 10001；观察到 `dispatch_notifications` 与 `dispatch_queued_runs` **自动**投递并执行，不以手动 `celery call` 代替。
- [前端交接包](../backend/FRONTEND-HANDOFF.md) 与 [启动手册](../backend/ALPHA-OPERATIONS.md) 提供冻结 OpenAPI、事件、错误、分页、运行与本地演示入口。前端代码尚未实现。

## 裁定与限制

- [收口计划](71-ACQ1-CLOSURE-PLAN.md) §6 条件 1–8 均有交付侧和独立复核证据；本次独立 Review：**P0=0、P1=0**。ACQ-1 WP-1/WP-2/WP-4–WP-8 的 **Static/Native Alpha v0.1 后端范围可交接前端**。
- Dynamic/Advanced Browser（WP-3）仍 **disabled/deferred**；R3 真实执行 BLOCKED，R4/R5 未准入；不得将历史证据标记 PASS。PLUGIN-1 为 POST-v0.1/deferred，不阻塞前端。
- 已知 P2：Alembic 检查提示 `acquisition_snapshots` 与 `source_artifacts` 的外键环在未来 Alembic 版本可能影响自动排序；本次空库升级、降级、重升与零漂移均通过。该提示不是本次新增迁移/Schema 变更。
- 运行验证不等于生产容量/SLA；Frontend、Integration、Release 均未实现或准入。此处 **READY_FOR_FRONTEND** 只表示后端跑道就绪；下一阶段仍须独立授权。
