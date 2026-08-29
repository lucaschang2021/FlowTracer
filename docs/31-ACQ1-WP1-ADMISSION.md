# FlowTracer ACQ-1 WP-1 准入

状态：控制提交合并到 `main` 后生效

前置基准：`main@f7e7d113faa70c0daa6be33c6e6ce5721e919e97`

执行角色：现有 Backend 角色

目标分支：`feat/acq-1a-h0`

Phase：WP-1 / ACQ-1A + H0

## 开工输入

Backend 只读取：

- `docs/CURRENT-GATE.md`
- 本文件
- `docs/23-ACQ1-ACQUISITION-CONTRACT.md`
- `docs/25-ACQ1-ACCEPTANCE.md`
- `docs/29-ACQ1-WORK-PACKAGES.md` 的通用规则与 WP-1
- ADR-022、ADR-023
- 本阶段直接涉及的 Backend 代码、迁移与测试

## 授权范围

- Source 稳定强类型字段、严格且版本化的公开 Profile Schema，以及 legacy `config` 兼容读取/写入边界。
- `source_acquisition_states`、`acquisition_attempts` 与冻结索引、约束、所有权关系。
- CollectionRun lease、heartbeat、stale recovery 和并发安全状态转换。
- NetworkPolicy、SitePolicy、ResourceBudget 的纯逻辑安全内核及 Native acquisition 接口接入点。
- expand migration、legacy backfill/default、兼容 Source API/OpenAPI、配置、Backend 文档与测试。

允许文件限于 `backend/app/{models,schemas,services,api/v1/routes,tasks,core}` 中与 Source/Acquisition 直接相关的文件、`backend/alembic/versions/`、对应 Backend tests、`backend/.env.example` 与 Backend 运行文档。

## 明确禁止

- 不安装或引入 Scrapling、Playwright、Browser runtime；不启动 Browser，不访问真实目标站点。
- 不实现 Browser worker/queue、Router fallback、Discovery、Change Intelligence、Opportunity 或外部动作。
- 不改变 Intelligence、Memory、Notification 的业务语义，不进入 Frontend/Integration/Release。
- 不提前删除 legacy 列或唯一约束；本阶段仅执行冻结的 expand/backfill/兼容步骤。
- 不自行扩大 Schema/API/Pipeline/评分/NetworkPolicy；需要偏离时立即 STOP。

## 必须验收

- legacy Source backfill/default 可重复且不泄漏秘密；公开 Profile 严格校验，未知字段与秘密字段被拒绝。
- 所有权与软删除边界保持；Source API/OpenAPI 对既有调用方兼容。
- lease 认领、heartbeat、并发 worker、过期恢复、旧 worker 防覆盖与重复投递均有真实 PostgreSQL 证据。
- Network/Site/Resource policy 覆盖协议、端口、地址、redirect、预算和安全错误分类；核心测试离线。
- migration 完成空库 upgrade、downgrade/re-upgrade、legacy 数据 backfill 与 `alembic check` 零漂移。
- BE-4 acquisition、BE-7 recovery 和 BE-8 契约/闭环相关回归通过；最终 commit 满足 Ruff、format、Mypy、Pytest 与覆盖率门禁。
- Compose/API/Worker 可重复启动；不得引入 Browser 或新的共享基础设施。

## 交付与停点

Backend 完成后提交规定格式的阶段报告、精确 commit、迁移、OpenAPI、测试、安全、运行态、风险与 PR 信息，然后立即 STOP。Backend 不自行 merge，不进入 WP-2；WP-2 仍未准入。
