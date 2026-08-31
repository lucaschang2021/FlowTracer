# FlowTracer ACQ-1 WP-1 验收

状态：ACCEPT

核验基准：`main@9f019072bb71a43e1e2253f2f55d217865d2e239`

实现 PR：#33（已独立 Review 并合并）

实现提交：`0e95a5698ae5b8964fb387aaa9c1bb77e3a439ec`

下一工作包准入：仅允许 WP-2 控制提交合并后启动

Frontend 准入：NO

## 验收范围

- Source 强类型稳定字段、严格 `acq-source-v1` Profile、legacy `config` 兼容与秘密拒绝/脱敏。
- `source_acquisition_states`、`acquisition_attempts` 与冻结约束、索引和运行状态。
- CollectionRun lease、heartbeat、stale recovery、claim 上限及旧 Worker fencing。
- NetworkPolicy、SitePolicy、ResourceBudget 安全内核，以及仅限 Native/RSS 的统一 Acquisition 接入点。
- expand/backfill migration `20260830_0004`、Source API/OpenAPI 兼容及 BE-4/BE-7/BE-8 回归。

## 独立 Stage Gate 证据

- 精确候选共 17 个 Backend 文件，无 Frontend、Integration、Release 或 WP-2 越界。
- Ruff、format、Mypy、OpenAPI snapshot check、Compose config 与 `git diff --check` 全部通过。
- 完整测试：264 passed；覆盖率 87.76%，高于 85% 门禁。
- 空库 upgrade、downgrade、legacy backfill、re-upgrade 与 `alembic check` 零漂移通过；冻结 named CHECK 全部存在。
- API/Worker 使用同一官方候选镜像，UID/GID 10001 非 root；live、ready 与 Celery pong 通过。
- 隔离 `_test` 数据库证明过期 lease 恢复、重新认领、旧 claim 审计保留和 NetworkPolicy 连接前阻断；未访问真实目标站点。
- P0/P1/P2：0/0/0；唯一第三方 Starlette/httpx deprecation warning 不影响 Alpha 行为。

## 总控结论

WP-1 达到功能、迁移、测试、契约、安全、恢复和可重复运行门禁，正式验收通过。允许签发 WP-2（ACQ-1B + D-static）的独立准入控制提交，但不得据此一次性准入 WP-3..WP-8。

## 保留约束

- WP-1 中保存的 `dynamic`、`advanced`、Discovery 等枚举仅用于兼容声明，不代表运行能力已开放。
- Browser、Scrapling fetcher、Router、Discovery、Change Intelligence、Opportunity 和 Frontend 仍未准入。
- 任何 Schema、API、Pipeline、评分或 NetworkPolicy 偏离必须立即 STOP，并提交 ADR/契约变更请求。
