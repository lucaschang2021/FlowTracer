# FlowTracer Architecture Governance & Modularization Pass v1

状态：AG-0 架构合同已冻结；只定义治理、基线和后续任务包，不代表实现准入或架构债务已解决。

机器可执行的唯一规则源是 [`ARCHITECTURE.toml`](../ARCHITECTURE.toml)。本文解释规则、记录审计证据，并把后续工作拆成可独立验收和回滚的最小提交。

## 1. 范围与兼容边界

本流程从 `origin/main@f4b58c1ec0d20d075b98d5a9ca3d146d0b4deb56` 建立，未来实现分支固定为 `feat/architecture-governance`。目标是让依赖方向、状态所有权、外部 I/O 和 Provider 替换边界可以自动检查；不是重写，不拆微服务，不按 Clean Architecture 目录图大搬文件。

以下内容必须零漂移：

- 已冻结的 REST/WebSocket 与 [OpenAPI snapshot](../backend/openapi/flowtracer-alpha-v0.1.json)；
- 数据库 Schema、Alembic 链和当前 head `20260830_0004`；
- ACQ-1 的 Native First、安全 fetch、提取质量、legacy writer、健康状态和事件语义，详见 [ACQ-1 主基线](22-ACQ1-MASTER-BASELINE.md) 与 [Acquisition Contract](23-ACQ1-ACQUISITION-CONTRACT.md)；
- 现有测试、最后已验收的 `286 passed / 87.61%` 证明和 [当前闸门](CURRENT-GATE.md) 中的产品阶段边界。

本任务输入声明 ACQ WP-3 Preflight PR #41 仍为 OPEN；AG-0 没有联网刷新该外部状态，也没有修改、合并或启动该 PR。架构分支不修改 `README.md`、`docs/CURRENT-GATE.md`、`docs/02-DELIVERY-BOARD.md` 或既有 ADR；控制状态同步必须等控制 PR 处理完成后另行提交。

## 2. 目标依赖方向

```text
API / inbound adapter  --->  Application service  --->  Domain policy + ports
           |                         |                         ^
           |                         |                         |
           +-- no DB/task/provider --+             Infrastructure adapters

Tasks and bootstrap are composition roots: they may wire ports to adapters.
Models/persistence own database mechanics, not domain decisions.
```

核心约束：

- API/Adapter 只负责传输转换和调用用例，不直接选择 concrete provider、投递 Celery、执行 Redis 或掌握 DB 查询细节。
- Application 负责用例编排；新增代码只依赖纯 Domain/Ports。现有服务的直接 ORM 依赖作为基线债务治理，不要求本轮一次 repository 化全部 ORM。
- Domain/Ports 不得依赖 SQLAlchemy、FastAPI、Starlette、Redis、Celery、httpx、asyncpg、pgvector、socket/ssl 或任何 provider network 实现。
- Infrastructure 实现 Domain Port；禁止 `provider -> service`，也禁止用 Provider 反向承载产品决策。
- Task 只是 Celery 到用例的适配器；Bootstrap/Lifecycle 是 FastAPI、Settings、DB、Redis、Provider 与 Worker 的组装点。
- `service -> api` 永久禁止。新增循环依赖、模块级可变运行态和 import-time external I/O 均为闸门失败。

## 3. Responsibility Map 与架构基线

分类：A=编排，B=确定性领域决策，C=持久化，D=基础设施/外部 I/O，E=传输映射。分类按实际行为，不按文件大小推断。

| 文件 | A 编排 | B 确定性规则 | C 持久化 | D 基础设施 | E 传输 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| [`acquisition.py`](../backend/app/services/acquisition.py) | manual/retry/schedule/dispatch/lease/execute workflow | idempotency、状态/健康转换、去重、attempt/quality 决策 | SQLAlchemy 查询、锁、事务、RawItem/Run/State 写入 | 直接构造 `NativeAcquisitionBackend`，调用 fetcher、event publisher、raw dispatcher | `AppError`、列表分页与 API-facing error | 五类责任混合；`execute_run` 256 行且同时做 fetch→parse→quality→DB→event，存在抽最小 ports/DI 的充分证据 |
| [`intelligence.py`](../backend/app/services/intelligence.py) | claim/retry/recover/dispatch/run analysis | 四维 Decimal 评分、Recommendation、通知资格、成本、输出验证 | Analysis/Document/AIUsage 查询、锁、状态写入 | Analysis Provider、sleep/retry、event publisher | ownership 查询、response dict、`AppError` | 五类责任混合；纯政策已经可识别，应最先无语义变化抽离 |
| [`memory.py`](../backend/app/services/memory.py) | embedding 与 search workflow | cost、向量结果量化、相似度/稳定排序与访问过滤规则 | advisory lock、Chunk 原子替换、Bookmark CRUD、pgvector SQL | Embedding Provider 与重试/审计 | resource error 与 response dict | 五类责任混合；ranking/filtering 有抽纯边界证据，但当前文件没有 retention policy，禁止凭空新增 |
| [`entities.py`](../backend/app/models/entities.py) | 无 | 业务枚举与约束名称 | 16 个声明式实体、索引、FK、CHECK 与类型映射 | pgvector/SQLAlchemy mapping | 无 | 797 行主要来自声明密度；本轮只设增长阈值，不机械拆表或移动模型 |

### 3.1 现有债务（existing）

- `EX-001 / P1`：[`api/v1/routes/memory.py`](../backend/app/api/v1/routes/memory.py) 在 transport 层构造 concrete embedding provider。
- `EX-002 / P2`：`backend/app/api` 多处直接导入 `AsyncSession`、SQLAlchemy 查询和 ORM entity。治理目标禁止新增；本轮不强迫全量 repository 化。
- `EX-003 / P1`：三个核心 service 直接导入 concrete analysis/embedding/acquisition backend、fetcher 或 event infrastructure；这是本 Pass 必须解决的 Provider seam。
- `EX-004 / P1`：`acquisition.execute_run` 内部构造 `NativeAcquisitionBackend(fetcher)`，把 backend selection、fetch、parse、quality、持久化、事件和下游 dispatch 绑定在一个函数。
- `EX-005 / P2`：[`main.py`](../backend/app/main.py) import 时执行 `create_app()`；[`celery_app.py`](../backend/app/tasks/celery_app.py) import 时加载 Settings、配置日志并构造 Celery app/schedule。审计未发现 import 时连接 DB/Redis、发 HTTP、publish 或 dispatch；它们属于已知 bootstrap surface，必须以 import-safety 测试守住。
- `EX-006 / P2`：`acquisition.py` 925 行、`intelligence.py` 668 行、`memory.py` 621 行，且三者确有 A-E 责任混合；`entities.py` 797 行但没有同等行为混合证据。
- `EX-007 / P1`：基线提交没有 tracked CI workflow，因此当前不存在可验证的 pipeline concurrency/cancel-in-progress 配置。AG-1 已获合同授权：若确认没有等价 workflow，则以独立 gate-tooling/CI commit 新建最小 backend workflow，包含 lint/types/tests/architecture 和 concurrency/`cancel-in-progress`，不得混入业务重构。
- `EX-008 / P1`：[`static_scrapling.py`](../backend/app/adapters/acquisition/static_scrapling.py) 有 6 个导入语句指向 `app.services`，覆盖 parser、policy、types、quality 与 URL normalization；这是 `adapter -> service` 的既有命中。
- `EX-009 / P2`：`backend/app/services` 对 `app.core`、ORM models 与 SQLAlchemy persistence 的直接依赖面比三个目标文件更广。它是分组历史债务，本 Pass 不要求一次清空，但不得新增或扩大。

### 3.2 本轮新增与解决

- `introduced = 0`：AG-0 没有新增依赖、运行态、外部 I/O 或业务实现。
- `resolved = 0`：AG-0 只冻结合同，不能把文档记录算作债务修复。
- 上述人工 finding 是责任级摘要，不是逐 import 豁免清单。AG-1 必须从 `baseline_commit=f4b58c1...` 全量扫描 `backend/app`，把稳定 fingerprint 写入受版本控制的 `backend/architecture-baseline.json`；只有 baseline commit 中存在的 fingerprint 才是 existing，任何缺失于 snapshot 的命中都是 introduced。
- 后续每个提交都必须输出 `existing / introduced / resolved` 三组差异；introduced P0/P1/P2 必须为零，existing 只能不变或减少且保留 disposition，resolved 不得回归。

## 4. Lifecycle、Settings 与 import safety

[`create_app`](../backend/app/main.py) 当前把 `Settings`、logging、FastAPI middleware/router 和 lifecycle 绑定在 bootstrap。无注入 `readiness_service` 时，lifespan 内创建 engine、session factory、Redis client、event publisher 与 readiness probes，并在退出时关闭 Redis/engine；注入 readiness service 的测试/健康模式不会创建这些运行依赖。此注入路径与 liveness 不访问外部依赖的既有健康语义必须保留。

`application.state` 当前持有 Settings、session factory、Redis client、event publisher 与 readiness service。这些是 process runtime dependency，不是业务事实；其唯一 owner 是 Bootstrap/Lifecycle。API 可以通过明确依赖取得用例入口，但不得新增任意 state key 或把业务状态放进 `app.state`。

`bootstrap_lifecycle` 当前还承载少量 shared core compatibility imports：API/service 会使用 `app.core.errors`、context、middleware、security 或 logging。这不是允许 API 广泛新增 bootstrap dependency。AG-1 必须把 baseline commit 的现存 core import 形成精确 fingerprint allowlist，并禁止增长；若以后引入 shared primitive 分类，也只能是无大搬迁、无行为变化的独立治理决定。

[`Settings`](../backend/app/core/config.py) 是 fail-fast、case-sensitive、无 `.env` 自动读取的配置边界；`get_settings()` 使用单项缓存。Provider 的构造函数只解析配置和保存 client/url/key；真实 HTTP 在 `analyze/embed` 被调用后发生。Celery module import 只允许 Settings/logging/app/schedule construction；DB engine、Redis client、Provider 调用和 task dispatch 必须发生在 task invocation 后。

import-safety gate 必须在受控 fake 环境变量下导入 `app.main`、`app.tasks.celery_app`、Provider 与三个目标 service，并 monkeypatch/阻断 socket、HTTP、DB connect/query、Redis ping/publish/subscribe、Celery dispatch 和 filesystem writes。允许对象构造，不允许一次实际 external call。

## 5. 最小实施任务包

每个任务包在新的 Codex 任务中执行，使用同一 `feat/architecture-governance` 分支但各自独立提交、验证和停点。未经总控书面许可不得进入下一包。

### AG-1 — Executable gate foundation

- 为 `ARCHITECTURE.toml` 增加 schema/语义验证、layer assignment、AST import rule、模块级 mutable runtime state、疑似 import-time external call、complexity/responsibility growth 与 baseline delta 检查。
- 从固定 baseline commit 全量生成并提交 machine baseline snapshot；逐命中以稳定 fingerprint 分类 existing/introduced/resolved，人工 finding 仅作责任摘要。
- 增加 contract、dependency、import-safety、provider-substitution 测试。
- 在受治理的 backend pipeline 增加 `architecture` step，并复用其 concurrency group 与 `cancel-in-progress`。若确认没有等价 workflow，AG-1 直接新建只含 lint/types/tests/architecture 的最小 backend CI，显式设置 concurrency 与 `cancel-in-progress: true`；只有发现已有外部/隐藏 CI 或仓库政策冲突时才 STOP。
- 不改业务行为；commit 边界：gate tooling + tests + CI only。

### AG-2 — Pure intelligence policy

- 把 `calculate_score`、`recommendation_for`、`qualifies_for_notification`、`calculate_cost` 和 output validation/policy 抽到纯 Domain 模块。
- Domain 输入不得接受 `Settings`、ORM entity 或 Provider response；价格、阈值和 allowed categories 通过不可变值传入。
- 保持 40/25/20/15 权重、HALF_UP 两位、85/70/50 Recommendation、通知 `>= threshold`、成本百万 token/HALF_UP 六位，以及 strict output/`other` fallback 的既有语义。
- commit 边界：pure module + characterization/unit tests + thin service delegation。

### AG-3 — Acquisition ports and minimal DI

- 定义 `AcquisitionBackend`、fetcher、event publisher 和必要 persistence boundary 的最小 Ports；backend/fetcher/event/persistence 均可 fake。
- `execute_run` 不再内部决定 concrete backend 构造；composition root 负责注入。
- 保持 Native First、SafeFetcher 安全意图、单 Attempt、legacy RawItem writer、去重、lease/heartbeat、health/quality EWMA、事件先提交后发布和 queue failure 语义。
- 只围绕 `execute_run` seam 建最小 persistence boundary；不一次 repository 化 manual/list/scheduler/所有 ORM 查询。
- commit 边界：ports + adapter wiring + fake-dependency tests；无 migration/API drift。

### AG-4 — Composition and import safety

- 把 API 中 concrete provider construction 移到允许的 composition root；统一 FastAPI lifespan 与 Celery task 的 Provider/DB/Event wiring。
- 保持 `create_app(Settings(), readiness_service=...)` 测试/健康模式、资源关闭和现有 `app.state` keys 兼容，除非先提供兼容 shim 与证明。
- Provider fake/production adapter 必须在不改 domain/application/public contract 的情况下替换。
- commit 边界：bootstrap/task wiring + import/substitution tests only。

### AG-5 — Conditional memory policy

- 仅当 characterization tests 能把相似度 clamp、六位量化、稳定排序、ownership/bookmark filter 表达为纯输入输出规则时，抽最小 ranking/filtering policy。
- SQL 中的 user authorization 与 pgvector distance 仍由 persistence adapter 执行；不得为“纯化”把全量结果拉入 Python。
- 当前未发现 retention policy；没有新增产品合同前不得抽象或实现 retention。
- 若证据不足，本任务包以“无需变更”的审计提交或无代码停点结束。

### AG-6 — Final compatibility gate

- 只在最终待合并提交复跑一次全量 backend gate；不重复未变 commit 的全量测试。
- 比较 OpenAPI blob、Alembic head/schema、ACQ contract、测试计数与 coverage；coverage 不得低于 87.61%。
- 最终强制解决 `EX-001`（API concrete embedding construction）、`EX-003`（service concrete provider/backend imports）、`EX-004`（`execute_run` 内部 backend construction）和 `EX-007`（CI architecture gate）。其他 existing finding 可在不扩大且有 disposition 的条件下保留。
- 输出最终 `existing / introduced / resolved`、P0/P1/P2、回滚证明和可重复命令。状态文档同步仍走独立控制 PR。

## 6. Architecture Gate 与测试冻结

Architecture Gate 至少包含：TOML parse/schema、从固定 commit 生成的 machine baseline snapshot、跨层 import、`service -> api`、Domain 禁止基础设施、模块级 mutable runtime state、疑似 import-time external call、文件/责任增长 warning、Provider substitutability 与 baseline-no-regression。Snapshot 缺失时 fail closed；人工 finding 未列出的现存 import 只要 fingerprint 存在于 snapshot，仍正确归类为 existing。

复杂度阈值采用物理 UTF-8 行数，只用于触发审查：module 600 行 warning、新 module 900 行 failure；function 80 行 warning、新 function 200 行 failure；单 module 超过 3 类责任 warning。已超阈值的 baseline module/function 允许重构减少但净增长额度为 0。阈值不能替代责任证据，也不能作为机械拆 `entities.py` 的理由。

测试必须保留全部现有 suite，并新增：

- pure intelligence policy characterization；
- acquisition fake backend/fetcher/event/persistence；
- import safety；
- contract validation 与 dependency gate；
- provider substitution；
- OpenAPI snapshot、Alembic/schema、ACQ contract no-regression。

AG-0 不运行 Backend tests 或 Docker。`286 passed / 87.61%` 是当前 gate 记录的最后验收证明，不是本任务新生成的测试结果。工作树中用户已有的 `backend/tests/test_error_paths.py` 删除保持未恢复、未暂存、未提交；后续实现的“保留现有测试”以 committed baseline 为准，同时继续保护该用户改动。

## 7. Stage Gate、提交与回滚

| 严重度 | 定义 | 通过条件 |
| --- | --- | --- |
| P0 | API/Schema/ACQ/安全/健康/状态所有权漂移，Domain 引入基础设施，import-time external I/O | introduced=0；existing 不增且有 disposition |
| P1 | 新增或扩大依赖债务、Provider 不可替换、可变运行态、确定性语义丢失、coverage 下降 | introduced=0；existing 不增且有 disposition |
| P2 | 复杂度/责任增长 warning、文档不一致、未归属清理风险 | introduced=0；existing 不增且有 disposition |

AG-1 至 AG-5 的 per-commit gate：introduced P0/P1/P2=0，existing 不增且有 disposition，resolved 不回归。AG-6 final acceptance 额外要求清除 `EX-001/EX-003/EX-004/EX-007`；不要求一次清空 API→ORM、adapter→services、shared core 或其余 baseline。每包仍须 coverage 不下降、无 migration、OpenAPI/DB/ACQ zero drift、现有测试不删减。禁止把跨包变化压成不可独立回滚的大提交。

回滚以提交为边界逆序 revert：先 wiring，再 acquisition，再 intelligence，再 gate foundation。由于本流程禁止 migration，运行回滚不需要 Schema downgrade；若任何任务发现必须改 API、Schema、migration 或 ACQ 产品语义，应停止并提交独立 ADR/兼容计划，而不是继续实现。

## 8. AG-0 检查与已知风险

AG-0 只要求并计划执行：TOML parse、Markdown local link validation、`git diff --check` 与范围检查；不运行 Backend tests/Docker。

已知风险：

- 当前 origin/main 的 `CURRENT-GATE` 文本仍以 WP-2 merge commit 作为“当前稳定基准”，而 PR #40 merge commit 是当前 Git head；PR #41 的控制分支已包含相应状态更新。AG-0 不复制或修改该同步内容，避免与 PR #41 冲突。
- baseline 没有 tracked CI workflow；合同已直接授权 AG-1 在确认无等价 workflow 时创建最小 backend CI，只有外部/隐藏 CI 或仓库政策冲突才形成停点风险。
- API 直连 ORM 的存量面较大；本 pass 只封住新增并处理与 Provider/关键用例直接相关的 seam，避免范围爆炸。
- 用户测试文件删除不是 AG-0 产物，不能在 commit、范围检查或验收计数中混入。
