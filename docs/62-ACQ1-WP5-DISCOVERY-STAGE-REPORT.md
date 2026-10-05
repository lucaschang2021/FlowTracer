# ACQ-1 WP-5 Controlled Discovery 阶段验收报告（I1）

状态：**ACCEPTED（委托方确认，无独立第三方角色）**。I2（crawl 执行）未准入。
日期：2026-10-05。格式：`docs/29-ACQ1-WORK-PACKAGES.md` 阶段报告格式。
依据：ADR-035、`docs/61-ACQ1-WP5-DISCOVERY-CONTRACT.md`（含 §15 实现注记）。

> **验收口径**：与 WP-4 相同——本环境无第二角色、无可用远端，无法执行独立第三方复审；经委托方确认以"开发自测证据 + 委托方确认"验收，**不声称独立复审已完成**。复审对象为本地 `main` 合并提交。

## Phase / Status

- Phase：ACQ-1E Controlled Discovery **I1（规划与 Frontier 状态）**；静态范围，Browser disabled。
- Status：实现 + 自测完成；I2（对发现的 URL 执行抓取、robots 义务、逐跳计费）**未准入**。

## Implemented

- **`discovery_policy.py`（纯函数）**：四 scope 精确边界（single_page 仅种子 / same_path 目录前缀 / same_domain 精确主机 / approved_domains 取 source∩operator 交集）；fail-closed 硬前置（仅 http/https、端口 80/443、拒绝 userinfo）；确定性 0–100 scoring（深度衰减、同路径/同主机/批准主机加分、锚文本加分、追踪参数降分）；站点 `allow_paths`/`deny_paths` 门；目录前缀与追踪参数判定。
- **`discovery_links.py`（纯函数）**：有界 HTML `<a>` 抽取（忽略 script/style/noscript/template，rel/nofollow 标记，转义与编码容错，单页 ≤200 链接）。
- **`discovery_frontier.py`（纯函数）**：规划管线（scope → 路径门 → scoring → 阈值 → 去重 → 排序 → 三硬上限）与 checkpoint 合并；`{version, seen[≤2000], frontier, counters}` 文档；损坏 checkpoint 容忍为空状态；跨 run 幂等。
- **执行接线**：`acquisition_route._plan_discovery`（仅 URL 源、`discovery_mode != single_page`、质量达标时触发）；`finish_success(discovery_checkpoint=…)` → `_update_source_state(checkpoint_update=…)` 与 run 成功同事务写入；读取经 `acquisition_attempts._discovery_checkpoint`；ports 增加 `discovery_checkpoint`。
- **无迁移、无公开 API 变化**：复用 `Source.discovery_mode` 与 `SourceAcquisitionState.checkpoint`。

## Changed Files

新增：`backend/app/services/discovery_policy.py`、`discovery_links.py`、`discovery_frontier.py`、`backend/tests/test_acquisition_discovery.py`、`docs/61-ACQ1-WP5-DISCOVERY-CONTRACT.md`、`docs/62`（本文）。
修改：`backend/app/services/acquisition_route.py`、`acquisition_run_repository.py`、`acquisition_attempts.py`、`acquisition.py`（checkpoint 写入）、`acquisition_router.py`（`route_summary(discovery=…)`）、`app/domains/acquisition_ports.py`、`docs/01`（ADR-035）、`docs/02`。
未触碰：公开 API/Schema、迁移、WP-1/WP-2/WP-4 语义、下游 Intelligence/Memory。

## Schema / Migration

无。Alembic upgrade 幂等复核通过。

## Public API / OpenAPI

无变化；契约冻结测试在全量套件内通过。

## Pipeline / State Changes

- `SourceAcquisitionState.checkpoint` 在 discovery 活跃且成功时被整文档替换（version=1 文档）；非活跃源保持 `{}`。
- `CollectionRun.budget_summary["discovery"]` 记录封闭摘要（10 键）。

## NetworkPolicy / SitePolicy

不变；discovery 只**消费**既有 `EffectiveSitePolicy`（路径门、批准域交集）与 Network 形态前置；I1 不发起任何网络请求。

## Security / SSRF

- 不解析/不访问发现的 URL（无 SSRF 面）；越 scope、deny 路径、超上限、非法形态一律 fail-closed 拒绝。
- 无 unrestricted crawl：`max_depth`、`max_frontier_size`、`max_discovered_urls` 三硬上限 + 单页链接上限 + seen 上限。

## Concurrency / Idempotency / Recovery

- checkpoint 与 run 成功同事务提交；重复投递/重复 run 幂等（`accepted=0`，`duplicates` 计数）。
- 恢复语义：checkpoint 即事实；损坏输入按空状态容忍，不放大。

## Offline Tests / Full Tests / Coverage

- 新增 `test_acquisition_discovery.py`：**18/18**（scope 边界 6、scoring 2、规划/上限/去重/幂等 6、链接抽取 1、DB 集成 3）。
- 定向回归（router/lease/app-port/tasks/acquisition）：36/36。
- **全量（单次门禁）：391 passed（389 + 2 项 PATH 复跑）/ 0 failed，覆盖率 91.78%**（CI 门槛 87.61%）。
  - 说明：首轮运行中 `test_architecture_gate.py` 的 2 项因本次 shell 会话 PATH 未含 `git` 而失败（子进程调用 `git`）；带 `F:\Git\cmd` 复跑 13/13 通过。用户级 PATH 已持久化，新终端可直接复现全绿。

## Docker / Compose / Browser Runtime

未启动 Browser；未修改默认 Compose；测试用 Postgres/Redis 容器仅用于测试，结束清理。

## Known Limitations

- I1 只规划不抓取；frontier 中的 URL 尚无执行路径（I2 未准入）。
- 深度惩罚与加分权重为本增量冻结值（docs/61 §15.3）；I2 可在其准入中复评，但不得放宽上限。
- `nofollow` 仅记录；抓取语义留待 I2。

## P0 / P1 / P2

- 本阶段：**0 / 0 / 0**（架构门跟踪后 `introduced=0`）。
- 架构门参考：`existing=130 / introduced=0 / resolved=27 / P0=0 / P1=114 / P2=16`。

## Recommendation

`ACCEPTED（委托方确认）`。实现、自测与门禁通过；独立第三方复审因环境限制未执行，已如实记录。

## Next Phase Admission Recommendation

WP-5-I2（crawl 执行）或 WP-6（Change Intelligence）均须各自独立准入；WP-6 的真实依赖为"已验收静态 discovery 输入与版本证据合同"，不得跳过版本证据。WP-3/R3 状态不受本报告影响（仍 BLOCKED）。
