# FlowTracer ACQ-1 交付包说明书

> **独立验收更新（2026-10-07）**：独立审核确认的未完成清单已按 [`docs/71`](71-ACQ1-CLOSURE-PLAN.md) 完成 Phase 0-5；审核方在精确代码提交 `01155294f151cb1c453ddbaf8af6ed34ef3228c1` 上复核通过，见 [`docs/78`](78-ACQ1-INDEPENDENT-ACCEPTANCE.md)。**READY_FOR_FRONTEND（后端交接就绪）**；不代表 Frontend 已准入或实现。下方 500/92.29% 数字为原交付方候选的历史证据，独立结果为 504/89.49%。

状态：**INDEPENDENTLY ACCEPTED BACKEND DELIVERY（交付说明，documentation only）**。本文件不新增能力、不改变任何冻结契约与安全边界。
交付代码基线：本地 `main@48c2e2260f303ef0b18470a4d31fb6cb8f73070d`（本说明书随文档提交追加；收口溯源见 `docs/71` §9；本地 Git 仓库，**无远端**）。
日期：2026-10-05（初稿）/ 2026-10-06（收口实现）/ 2026-10-07（候选文档收口）。
验收模式：交付侧候选为 owner-confirmed；审核方须在精确候选提交上独立复核。500 passed / 92.29% 是交付方可复现报告，不构成独立批准。

## 三十秒摘要

- **交付物（Phase 0-5 本地候选）**：FlowTracer Alpha v0.1 后端 —— BE-1..BE-8 基线 + ACQ-1 WP-1/WP-2、WP-4 生产路径、WP-5 I2 受控抓取、WP-6 I2 写路径与读取 API、WP-7 生命周期/重评、WP-8 整链验收与交接。
- **不包含**：Dynamic/Advanced Browser（未准入，disabled；R3 BLOCKED）、`semantic-change-v1`、平台授权工作流、多币种 FX、外部执行适配器、前端/集成/发布；PLUGIN-1 为 POST-v0.1 / deferred。
- **质量证据（交付方本地候选）**：500 项测试全过 / 覆盖率 92.29%（阈值 87.61%）；全部静态门禁与迁移门禁通过；**Docker 全栈已实测可从零启动**（§4.2）。审核方仍须在精确候选提交上独立复核。
- **启动方式**：六条 `docker compose` 命令（§6.2），完成后 `health/ready` 返回 database/redis 双 ok。
- **硬性禁区（禁止虚报）**：Dynamic/Advanced Browser 不可用；`semantic-change-v1`、平台授权工作流、多币种 FX 与外部执行适配器未启用；无自动投标/报价/付款；Frontend/Integration/Release 未准入。PLUGIN-1 为 POST-v0.1 / deferred，不在 Alpha v0.1 关键路径。能力清单见 `docs/68`，收口证据见 `docs/71`–`docs/77`。
- **证据入口**：`docs/68`（能力清单）、`docs/69`（阶段报告）、`docs/71`（收口计划）、本文件 §4（门禁矩阵）、`docs/02`（看板）。

---

## 1. 交付概述

| 项 | 内容 |
| --- | --- |
| 交付对象 | 面向个人的桌面 AI 情报系统的后端：持续采集 → 清洗/去重 → AI 分析/评分 → 记忆检索 → 通知；以及 ACQ-1 采集增强（路由、发现、版本证据、机会雷达） |
| 交付形态 | 完整 Git 仓库（含全部提交历史与分支）；**无 GitHub 远端**，接收方需自建远端或通过 `git bundle` 接收（§9） |
| 运行形态 | Docker Compose 四服务：`api` / `worker`（内嵌 Beat，勿扩多副本）/ `postgres`（pgvector）/ `redis` |
| 技术栈 | Python 3.13、FastAPI、Pydantic、Celery、PostgreSQL 16 + pgvector、Redis 7、SQLAlchemy 2 Async、Alembic、Pytest |
| 迁移头 | `20261006_0009`（`0001`..`0009`；收口候选零漂移） |
| 依赖锁定 | `pyproject.toml` + `uv.lock`；容器内 `uv sync --locked` 已验证（§4.2） |

## 2. 交付内容清单

| 类别 | 位置 | 说明 |
| --- | --- | --- |
| 后端代码 | `backend/app/` | 分层：api / services / domains / models / providers / adapters / tasks / core |
| 数据库迁移 | `backend/alembic/versions/` | `0001`..`0009`（0007 = 观测指针；0008 = RawItem 快照身份；0009 = 评分评估版本） |
| OpenAPI 冻结快照 | `backend/openapi/flowtracer-alpha-v0.1.json` | blob `faff18501e…`（收口 Phase 3 重新冻结，含 Change 读取端点），`--check` 零漂移 |
| 测试 | `backend/tests/` | 500 项；含 `test_alpha_e2e.py`（BE-8 闭环）、`test_acq1_final_e2e.py` 与 `test_acq1_closure_p0.py`..`p5.py`（收口验收矩阵） |
| 验证脚本 | `backend/scripts/` | `closure_acceptance.py`（收口独立验收复现器）、`verify_fresh_startup.py`、`secret_scan.py`、`benchmark_offline.py`、`export_openapi.py` |
| 基础设施 | `infra/compose.yaml` | 四服务编排 + 健康检查 + 命名卷 |
| 运行/交接文档 | `backend/ALPHA-OPERATIONS.md`、`FRONTEND-HANDOFF.md`、`PERFORMANCE-BASELINE.md`、`DEVELOPMENT.md` | 启动、恢复、环境矩阵、前端契约、性能参考 |
| 治理/契约文档 | `docs/00`..`docs/77` | 入口：`docs/68` 能力清单、`docs/69` 最终报告、`docs/02` 交付看板、`docs/CURRENT-GATE.md` 当前闸门、收口计划 `docs/71` 与报告 `docs/72`..`docs/77`、本文件 |
| 架构门 | `ARCHITECTURE.toml` + `backend/architecture_gate/` | `introduced=0 / P0=0` |

附：各工作包契约与阶段报告 —— WP-1 `docs/32/33`、WP-2 `docs/35/36`、WP-4 `docs/57/58/60`、WP-5 `docs/61/62`、WP-6 `docs/63/64`、WP-7 `docs/65/66`、WP-8 `docs/67/68/69`；契约总纲 `docs/23`（采集）、`docs/24`（机会）、`docs/25`（验收）。

## 3. 交付基线提交记录（本地 Git）

| 里程碑 | 合并提交 | 门槛证据（合并时）|
| --- | --- | --- |
| WP-4 Router v1 | `91ef8d9` | 373 passed / 91.92% |
| WP-5 Discovery I1 | `1c410b1` | 391 passed / 91.78% |
| WP-6 版本证据 I1 | `8f4f52a` | 403 passed / 92.17% |
| WP-7 机会雷达 I1 | `bba30aa` | 435 passed / 92.16% |
| WP-8 Final 收尾 | `afd7b72` | 438 passed / 92.16% + fresh startup + secret scan |
| 记录提交（交付基线）| `2da5665` | 其后仅追加本说明书 |
| 收口 Phase 0（P1/P2 六项修复）| `6e05480` | 456 passed / 92.13%；迁移 `0007`（`9cbdc97`→`6e05480`→`d0dbb56`）|
| 收口 Phase 1（WP-4 生产路径收口）| `0fca397` | 466 passed / 92.17%；ADR-038（`ad0c8ae`→`0fca397`→`be5e255`）|
| 收口 Phase 2（WP-5 I2 抓取执行）| `ddb0723` | 480 passed / 92.20%；ADR-039（`56eebd7`→`ddb0723`→`2c3640f`）|
| 收口 Phase 3（WP-6 I2 写路径 + 读取 API）| `f5ba2c6` | 487 passed / 92.25%；ADR-040；迁移 `0008`（`8dc1fb1`→`f5ba2c6`→`fec3e90`）|
| 收口 Phase 4（WP-7 生命周期与重评）| `e3eb0d0` | 494 passed / 92.29%；ADR-041；迁移 `0009`（`2eb60e4`→`e3eb0d0`→`45bcc76`）|
| 收口 Phase 5（WP-8 整链验收与交接）| 见 `docs/77` | 500 passed / 92.2%；`scripts/closure_acceptance.py` |

更早基线（BE-1..BE-8、WP-1、WP-2、R1..R2C 证据）在同一仓库历史与 `docs/` 归档中；R3 离线增量位于分支 `feat/acq1-r3-fail-closed-offline`（**未合并**，见 §5.2）。

## 4. 验收证据

### 4.1 自动化门禁（收口最终候选，2026-10-06 全量执行；此前的 `123ae18` 结果为 I1 基线，保留于 git 历史）

| 门禁 | 结果 |
| --- | --- |
| 全量测试 + 覆盖率 | **500 passed / 92.2%**（阈值 87.61%）|
| `ruff check` / `ruff format --check` | 通过（293 files）|
| `mypy app`（strict）| 通过（109 source files）|
| 架构门（baseline-no-regression）| `introduced=0 / P0=0`（existing 129 / resolved 28）|
| `alembic check` | No new upgrade operations detected（零漂移）|
| OpenAPI 冻结校验 | `export_openapi.py --check` 通过 |
| 秘密扫描 | `SECRET SCAN CLEAN`（含植入自检）|
| 空库迁移循环 | upgrade head → check → downgrade base → re-upgrade 通过（真实 PostgreSQL 16）|
| `docker compose config` | 通过 |
| `git diff --check` | clean |

### 4.2 Docker 全栈实测（2026-10-05，按 `ALPHA-OPERATIONS.md` Quick Start 原样执行）

| 步骤 | 结果 |
| --- | --- |
| `docker compose build api`（容器内 `uv sync --locked --no-dev`）| ✅ 镜像 `flowtracer-backend:be6` 构建成功（lock 解析 75 包，安装 61 包）|
| 启动 `postgres` + `redis` | ✅ 两服务 healthy |
| 空库 `alembic upgrade head` | ✅ `0001`→`0006` 六个迁移全部通过 |
| 启动 `api` + `worker` | ✅ 两服务 healthy；`celery inspect ping` → pong（1 node online）|
| `GET /api/v1/health/live` | ✅ `{"status":"ok","service":"flowtracer-api","version":"0.1.0"}` |
| `GET /api/v1/health/ready` | ✅ `{"status":"ready","checks":{"database":"ok","redis":"ok"}}` |
| 端到端冒烟（真实容器栈）| ✅ 注册 201 → 登录 200 → 创建 Radar 201 → 列表 `total=1` |
| 清理 | ✅ 验证用容器/网络/卷精确删除，无残留 |

### 4.3 三项验证脚本（均可复跑）

| 脚本 | 实测结果 | 约束 |
| --- | --- | --- |
| `scripts/verify_fresh_startup.py` | `FRESH STARTUP VERIFIED`（建库→迁移循环→启动→OpenAPI 比对→删库）| 仅接受 `*_test` 库名 |
| `scripts/secret_scan.py` | `SECRET SCAN CLEAN` | 扫描全部 git 跟踪文件；植入自检证明会报警 |
| `scripts/benchmark_offline.py` | 组件级 + 运行级（p50 81.9ms / p95 126.6ms / 峰值 ≈124KB / fallback 0-10）| 单机 fixture 参考，非 SLA；Browser 标注 NOT MEASURED |

### 4.4 第二轮复核与证据去向（2026-10-05 晚，同机）

同日另有一轮同机复核：全量 pytest 已复跑并留存日志 `ft_verify_pytest.log`（末行 `438 passed`、`Total coverage: 92.16%`，与 §4.1 一致，且为独立于 §4.1 的另一次运行）；`ft-smoke.py`（httpx 版 注册→登录→Radar 冒烟）与 `ft-inspect-schema.py`（OpenAPI 结构探查，用于编写冒烟脚本）亦留存；首版 PowerShell 冒烟 `ft-smoke.ps1` 已弃用。以上文件均位于交付机系统临时目录（**仓库外，不随 Git bundle 交付**）。compose 验证栈（含 `flowtracer_postgres_data`、`flowtracer_redis_data`）已 `down -v` 精确删除，无容器/网络/卷残留；测试容器 `ft-pg-test` / `ft-redis-test` 验证前停止、验证后恢复。除上述文件外其余门禁仅屏幕输出，结果已记录于 §4.1，并可按 §6 的命令复现；接收方无需上述临时文件。

## 5. 能力范围

### 5.1 已验收可用（委托方确认；证据指针逐项）

- **采集与解析**：RSS/Atom、单页 HTML、Scrapling 静态解析、`extraction-quality-v1`、通用 family extractor（`docs/33/36`）。
- **路由**：Router v1 —— 静态候选、有序降级、质量门、Circuit、AutoThrottle、累计预算账本、闭合决策 trace（`docs/60`，ADR-034）。
- **发现**：Controlled Discovery I1 —— 四种 scope 规划、确定性评分、硬上限、checkpoint 恢复；**不向发现的 URL 发起请求**（`docs/62`，ADR-035）。
- **版本证据**：Artifact/Snapshot/ChangeEvent 影子写入、三指纹、materiality、两次缺失判 removed、legacy backfill；**RawItem 写路径不变**（`docs/64`，ADR-036）。
- **机会雷达**：Freelance v1 Hard Filter、`opportunity-score-v1`、评估 Provider（Fake/OpenAI 兼容）、只读 Action Payload（`requires_human_approval=true`）、通知 XOR、REST 三端点（`docs/66`，ADR-037）。
- **智能链路**：清洗、全局去重、AI 分析/评分、成本审计、Embedding、pgvector 检索、收藏与记忆搜索（`docs/08/09/18`）。
- **通知与事件**：通知 REST（含 `kind=intelligence|opportunity`）、WS 三冻结事件、CollectionRun/Analysis 重试与补偿任务（`docs/18/21`）。

### 5.2 禁用 / 未准入（**不得虚报为已实现**）

| 项 | 状态 |
| --- | --- |
| Dynamic / Advanced Browser | **disabled**（`BROWSER_DYNAMIC_ENABLED=False`；`allow_browser=True` → `acquisition_browser_not_admitted`）；R3 真实执行 **BLOCKED**，需另签 lease |
| R3 离线增量（A1 设计/A2 DenialLatch/F1-F6 取证/就绪报告）| 位于分支 `feat/acq1-r3-fail-closed-offline`（`docs/54/55/56/59` 在该分支），**未合并** |
| R4 回收/资源、R5 双 worker 隔离 | 未准入 |
| `semantic-change-v1`、WP-7 平台授权工作流、多币种 FX、外部执行适配器 | 未实现 / 明确延期；WP-5 I2、WP-6 I2 与 WP-7 生命周期/重评已在 Phase 2-4 本地候选完成 |
| 机会通知的 WS 事件扩张 | 禁止（ADR-026：ACQ-1 不扩张 WS）|
| 自动投标/报价/工期/合同/沟通/付款/外部 Agent | **永久禁止**（ACQ-1 边界）|
| Frontend（FE-001）、Integration（INT-001）、Release（REL-001） | 未准入；`frontend/` 仅为占位目录 |
| PLUGIN-1 | POST-v0.1 / deferred；不阻塞 Frontend，不得视为已实现 |

## 6. 接收与验收指引

### 6.1 环境要求

- Git；Docker Desktop（Linux containers），支持 `compose up --wait`。
- 可选：宿主机跑质量门禁需 Python 3.13 + `uv`（或等价 `python -m` 调用）。
- 应用为 **fail-fast**：不隐式加载 `.env`；宿主机运行/迁移需显式提供环境变量（样例见 `backend/.env.example`；测试套件经 `conftest.py` 自动注入）。

### 6.2 路径 A：Docker 全栈启动（推荐，接收方第一步）

在仓库根目录依次执行（与 `ALPHA-OPERATIONS.md` Quick Start 一致）：

```powershell
docker compose -f infra/compose.yaml config
docker compose -f infra/compose.yaml build api
docker compose -f infra/compose.yaml up -d --wait postgres redis
docker compose -f infra/compose.yaml run --rm api alembic upgrade head
docker compose -f infra/compose.yaml up -d --wait api worker
curl.exe http://localhost:8000/api/v1/health/live
curl.exe http://localhost:8000/api/v1/health/ready
docker compose -f infra/compose.yaml exec worker celery -A app.tasks.celery_app:celery_app inspect ping
```

预期输出（实测样本）：`live` 返回 `{"status":"ok",...}`；`ready` 返回 `{"status":"ready","checks":{"database":"ok","redis":"ok"}}`；ping 返回 `pong`。
停止（保留数据卷）：`docker compose -f infra/compose.yaml down`；仅在明确要删除开发数据时加 `--volumes`。

### 6.3 路径 B：宿主机质量门禁复跑

```powershell
cd backend
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest --cov-fail-under=87.61
uv run python scripts/export_openapi.py --check
uv run alembic check
```

预期：全部通过；覆盖率 ≥ 87.61%；`alembic check` 输出 `No new upgrade operations detected`；OpenAPI `--check` 退出码 0。
（无 `uv` 时以 `python -m pytest` 等等价命令执行；测试需要 `TEST_DATABASE_URL` 指向 `*_test` 库，见 `backend/tests/conftest.py`。）

### 6.4 路径 C：三项验证脚本

```powershell
cd backend
python scripts/verify_fresh_startup.py   # 预期末行: FRESH STARTUP VERIFIED
python scripts/secret_scan.py            # 预期末行: SECRET SCAN CLEAN
python scripts/benchmark_offline.py      # 预期末行: BENCHMARK COMPLETE（JSON 报告）
```

前两者需要数据库可达（`*_test` 保护）；基准脚本需要可用的隔离 PostgreSQL。

### 6.5 验收判定建议（勾选清单）

- [ ] 六条启动命令全部成功，`ready` 双 ok；worker ping 有 pong。
- [ ] 冒烟：注册 → 登录 → 创建 Radar → 列表返回 1 条。
- [ ] 在精确候选提交上运行 `backend/scripts/closure_acceptance.py`，全部门禁通过；测试不少于 500 项、覆盖率 ≥ 87.61%。
- [ ] `alembic check` 零漂移；OpenAPI `--check` 通过。
- [ ] `verify_fresh_startup.py` 与 `secret_scan.py` 输出预期末行。
- [ ] 对照 `docs/68` 确认交付内容中**没有** Browser、延期能力或前端被虚报；WP-5/WP-6/WP-7 的已完成 I2 边界与阶段证据一致。
- [ ] 记录本次验收使用的提交哈希（`git rev-parse HEAD`）与执行日期。

## 7. 已知限制（交付边界，如实声明）

1. **验收模式**：当前材料是交付侧 owner-confirmed 候选；READY_FOR_FRONTEND 必须由审核方在精确候选提交上执行独立复核并确认 P0/P1=0。`closure_acceptance.py --no-tests` 仅生成 static-only 证据，不构成完整验收；完整判定必须实际执行全量测试与全部静态门禁。
2. **Browser**：不可用（§5.2 全部条目）；性能基线中 Browser 相关一律 NOT MEASURED（无估算值）。
3. **发现抓取是受控、有界路径**：I2 仅消费冻结 scope/frontier，并执行 robots、逐跳 SitePolicy/SSRF 复核、跨页预算、取消/恢复与并发去重；不存在 unrestricted crawl 入口。
4. **版本写路径已切换**：合格快照可生成带 `snapshot_id` 的 RawItem，并提供 Change/Artifact 读取 API；`semantic-change-v1` 仍未启用。
5. **机会雷达**：已支持版本变化驱动重评与 removed/expired/重现生命周期；仍为单币种 USD（无 FX），且不含平台授权或外部执行工作流。
6. **性能数据**：单机、隔离 fixture、确定性 stub 的复现参考，非 SLA/容量结论（`PERFORMANCE-BASELINE.md`）。
7. **仓库形态**：无远端；全部历史在本地 Git。构建产物镜像 `flowtracer-backend:be6` 为本地验证产物，非交付必需。
8. **宿主机 `uv sync`**：本机曾无 uv 环境；该缺口已由 §4.2 容器内 `uv sync --locked` 实测覆盖。

## 8. 文档一致性处置记录（已闭环，2026-10-05）

原列出的两处交付前待处置事项已修正（纯文档变更，可经 Git 历史完整还原）：

1. **根 `README.md`（中/英）**：状态声明、进度表、开发状态段落、路线图段落与关键文档索引已对齐 `docs/68/69` 事实；WP-3 行改为「未准入（fail-closed）」并新增 WP-4..WP-8 完成行（含 438 tests / 92.16% 指针）。
2. **`docs/00-PROJECT-CONTROL.md` 头部**：改为 2026-10-05 当前状态并注明 FT-GOV-V2.1 段落为历史记录。

处置提交：`8cf39b3`；no-ff 合并：`e98fb52`（本 traceability 提交记录以上哈希）。此后对外展示以 `README.md` + 本文件 + `docs/68/69` + `docs/02-DELIVERY-BOARD.md` + `docs/CURRENT-GATE.md` 为准。

3. **2026-10-06 独立审核（收口确认）**：审核方确认 ACQ-1 收口未完成并给出未完成清单；清单的执行映射见 `docs/71-ACQ1-CLOSURE-PLAN.md`。

4. **2026-10-06 收口执行（历史交付侧记录）**：未完成清单已按优先级逐阶段执行完毕，证据见 `docs/72`–`docs/77`。当时的“待独立验收”口径已由 2026-10-07 的 `docs/78` 独立结果取代：**READY_FOR_FRONTEND（后端交接就绪）**。本地包未推送/合并远端；Frontend 仍须独立准入。

## 9. 移交操作指引

推荐以 Git 打包移交（保留全部历史与分支，且自动排除未跟踪工作区文件）：

```powershell
# 交付方（本仓库根目录）
git bundle create flowtracer-acq1-delivery.bundle --all

# 接收方
git clone flowtracer-acq1-delivery.bundle FlowTracer
cd FlowTracer
git checkout main
```

说明：
- bundle 含**全部分支**（包括未合并的 R3 离线增量分支与历史 feat/chore 分支），便于审计；不包含未跟踪文件（如工作区元数据）。
- 仓库仅含占位凭据（秘密扫描 CLEAN）。**共享/部署前必须更换** `JWT_SECRET`、数据库口令等（经环境变量或 `.env` 提供，勿使用示例值）。
- 也可整目录拷贝，但需自行排除未跟踪文件；bundle 方式更可靠。

## 10. 建议的后续路径（由委托方书面决定）

1. 安排独立复核：在精确候选提交上运行 `backend/scripts/closure_acceptance.py`（或等价命令），对照 `docs/71` §6 的 8 项判定条件逐条核验；通过后即可判定 READY_FOR_FRONTEND。
2. 若需要浏览器能力：签发 R3 B 阶段真实执行 lease（草案在未合并分支 `docs/56`），通过后合并 R3 离线增量。
3. Frontend（FE-001）准入准备：以 `backend/FRONTEND-HANDOFF.md` + OpenAPI 快照为契约输入。
4. 集成（INT-001）与 Alpha 发布（REL-001）：按 `docs/02` 看板顺序推进。
