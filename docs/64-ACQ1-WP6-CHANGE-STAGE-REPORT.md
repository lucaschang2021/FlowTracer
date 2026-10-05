# ACQ-1 WP-6 Change Intelligence 阶段验收报告（I1：shadow-write 版本证据）

状态：**ACCEPTED（委托方确认，无独立第三方角色）**。I2（writer 切换/读取 API/语义变化）未准入。
日期：2026-10-05。格式：`docs/29-ACQ1-WORK-PACKAGES.md` 阶段报告格式。
依据：ADR-036、`docs/63-ACQ1-WP6-CHANGE-CONTRACT.md`（含 §15 实现注记）。

> **验收口径**：与 WP-4/WP-5 相同——本环境无第二角色、无可用远端，无法执行独立第三方复审；经委托方确认以"开发自测证据 + 委托方确认"验收，**不声称独立复审已完成**。复审对象为本地 `main` 合并提交。

## Phase / Status

- Phase：ACQ-1F Change Intelligence **I1**（shadow-write 版本证据）；静态范围，Browser disabled。
- Status：实现 + 自测完成；I2（RawItem writer 切换、读取 API、`semantic-change-v1`、notification 资格化）未准入。

## Implemented

- **`app/models/evidence.py`**：`SourceArtifact` / `AcquisitionSnapshot` / `ChangeEvent`（按 `docs/23` §13 schema，含 named uniques 与组合 CHECKs）；在 `app/models/__init__.py` 注册（alembic autogenerate 元数据一致）。
- **迁移 `20261005_0005`**：expand 三表；**不触碰 raw_items**；downgrade 带安全守卫（有证据行即拒绝）。
- **`version_evidence.py`（纯函数）**：噪声规范化（NFC/换行/零宽/tracking query/动态时间戳行）、三类指纹、结构摘要（语义块标签 + 附件 identity，不含文本）、分类（content>structure>metadata）、materiality 权重（0.6/0.3/0.1）、bounded field diff。
- **`change_tracking.py`**：artifact upsert（`ON CONFLICT DO NOTHING` + `FOR UPDATE`）、快照追加（version 计数**不同内容状态**，回退复用）、事件写入（每 run 每 artifact 一条，`UNIQUE` 保障）、两次缺失 removed 判定、legacy backfill（幂等、确定性顺序）。
- **接线**：`SqlAlchemyAcquisitionRunRepository.finish_success` 内与 run 成功同事务调用；legacy 与 Router 两条管线全覆盖；`RawItem` 行为零变化。

## Changed Files

新增：`backend/app/models/evidence.py`、`backend/app/services/version_evidence.py`、`backend/app/services/change_tracking.py`、`backend/alembic/versions/20261005_0005_version_evidence.py`、`backend/tests/test_acquisition_change.py`、`docs/63`、`docs/64`。
修改：`backend/app/models/__init__.py`、`backend/app/services/acquisition_run_repository.py`、`docs/01`（ADR-036）、`docs/02`。
未触碰：`entities.py`、公开 API/Schema、RawItem 写路径、WP-1..WP-5 语义、下游 Intelligence/Memory。

## Schema / Migration

- 新增三表（`source_artifacts`、`acquisition_snapshots`、`change_events`）；`raw_items` 无列变化（`snapshot_id` 属 I2）。
- `alembic check` 零漂移；upgrade→downgrade(空)→re-upgrade 循环通过；**守卫拒降级**（存在证据行时 `RuntimeError`）有测试证据。

## Public API / OpenAPI

无变化；契约冻结测试在全量套件内通过。

## Pipeline / State Changes

- 成功 run 在**同事务**内追加版本证据（artifact/snapshot/change event）；失败 run 不写证据。
- removed 判定按两次成功观测缺失推进 `miss_streak`；重现即清除。

## NetworkPolicy / SitePolicy

不变；本增量无网络路径（仅消费已抓取结果）。

## Security / SSRF

无新增网络面；指纹与结构摘要不含凭据、完整 DOM 或正文副本以外的字段；事件/changed 字段有界（≤16 字段、≤200 字符）。

## Concurrency / Idempotency / Recovery

- artifact 行锁串行化版本分配；并发 run 版本单调（测试断言 [1,2] 且各 run 一条事件）。
- 重复投递/重复 run 幂等；backfill 幂等（二次调用返回 0）。
- 无 ORM relationship → 显式 `flush()` 保证 artifact→snapshot→event 外键顺序。

## Offline Tests / Full Tests / Coverage

- 新增 `test_acquisition_change.py`：**12/12**（纯提取 5、版本序列与分类 2、并发 1、removed 1、backfill/RawItem 兼容 2、迁移循环与守卫 1）。
- 定向回归（change/acquisition/lease/router/discovery）：**56/56**。
- **全量（单次门禁）：403 passed / 0 failed，覆盖率 92.17%**（CI 门槛 87.61%）。
  - 该次全量同时更新并验证了冻结模型契约测试 `tests/test_models.py`（纳入三张证据表的表/唯一/CHECK/外键契约；`raw_items` 契约保持不变），属本增量的受控扩展。

## Commit / Branch / PR

- 分支：`feat/acq-1f-change`（`6919a97` 实现 → `798e495` 冻结与报告）；合并提交：`main@8f4f52a`（`--no-ff`，树与验证头 `798e495` 逐字节一致）。
- 远端：**未推送**（无可用远端写权限），无 PR。复审对象为本地 `main@8f4f52a` 的 exact head。

## Docker / Compose / Browser Runtime

未启动 Browser；未修改默认 Compose；测试用 Postgres/Redis 容器仅用于测试。

## Performance

无显著回归：每成功 run 增加常量级指纹计算与最多 N 条证据插入（N=该 run 的 candidates 数）；结构解析为单次有界 HTMLParser。

## Known Limitations

- I1 为 shadow-write：RawItem 生成条件未切换，`raw_items.snapshot_id` 尚不存在（测试断言，防影子实现）。
- 权威 404/410 的 removed 确认路径需要状态码贯通，I1 未实现（随 I2 评估）。
- DOM 级噪声区移除（导航/广告块）I1 采用保守文本规则；语义变化未实现。

## P0 / P1 / P2

- 本阶段：**0 / 0 / 0**（架构门跟踪后 `introduced=0`）。
- 架构门参考：`existing=130 / introduced=0 / resolved=27 / P0=0 / P1=114 / P2=16`。

## Recommendation

`ACCEPTED（委托方确认）`。实现、自测、迁移循环与门禁通过；独立第三方复审因环境限制未执行，已如实记录。

## Next Phase Admission Recommendation

WP-6-I2（writer 切换 + 读取 API + 语义变化）或 WP-7（Opportunity）均须各自独立准入；WP-7 的真实依赖为"已验收静态 Discovery/Change 与 Opportunity 评分/人工 Action 合同"，不得跳过版本证据。WP-3/R3 状态不受本报告影响（仍 BLOCKED）。
