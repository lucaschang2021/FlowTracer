# FlowTracer

**面向个人的桌面 AI 情报系统：从持续采集、可追踪分析到长期 Memory，帮助用户从信息流中发现并沉淀高价值内容。**

[当前闸门](docs/CURRENT-GATE.md) · [交付看板](docs/02-DELIVERY-BOARD.md) · [Backend 开发](backend/DEVELOPMENT.md) · [English](#english)

> **Alpha 状态：** FlowTracer v0.1 正在开发，尚未发布。BE-1 至 BE-8、ACQ-1 Preflight、Contract Freeze、WP-1 与 WP-2 均已验收并合并。WP-2 实现 PR #39 已进入 `main`；WP-3 Browser 的精确兼容性与隔离证据尚未冻结，因此 WP-3 至 WP-8、PLUGIN-1、Frontend、Integration 和 Release 均未准入。

## 中文

### 产品定位

FlowTracer 让用户通过核心领域对象 **Radar** 定义关注目标，并绑定 RSS 或单页 URL 信息源。后端持续采集内容，保留原始证据，完成清洗、去重、AI 分类、摘要、评分和成本审计，再逐步将高价值情报沉淀为可检索的个人 Memory。

Radar 是 FlowTracer 的核心领域对象，不是项目名称。项目正式名称始终为 **FlowTracer**。

### Alpha v0.1 进度

| 阶段 | 状态 | 已合并或当前范围 |
| --- | --- | --- |
| BE-1 | 已完成 | FastAPI/Celery 骨架、健康检查、迁移与本地基础设施 |
| BE-2 | 已完成 | 数据模型、认证与用户接口 |
| BE-3 | 已完成 | Radar/Source 管理、绑定与 URL 规范化 |
| BE-4 | 已完成 | RSS/URL 受控采集、调度、运行记录与 RawItem |
| BE-5 | 已完成 | 内容清洗、Document 去重、AI 分析、评分、成本审计与 Intelligence API |
| BE-6 | 已完成 | 确定性切块、Embedding、pgvector HNSW 检索、Bookmark 与 Memory Search |
| BE-7 | 已完成 | Notification、WebSocket 在线事件、CollectionRun retry 与恢复补偿，含 Analysis retry 回归 |
| BE-8 | 已完成 | 离线 Alpha 闭环、稳定化、OpenAPI 快照冻结、运行文档与前端交接材料 |
| ACQ-1 Preflight / Contract Freeze | 已完成 | 工程盘点、采集与安全契约、分工作包交付计划已合并；契约冻结不代表后续能力已实现 |
| ACQ-1 WP-1 Admission / Addendum | 已完成 | PR #31 / #32 已合并，Source Profile 与 Policy 精确契约已冻结 |
| ACQ-1 WP-1 | 已完成 | PR #33 已验收合并：Source Profile、采集状态/Attempt、lease/heartbeat/stale recovery 与安全策略内核 |
| ACQ-1 WP-2 | 已完成 | PR #39 已验收合并：统一静态 Adapter、无网络 Scrapling parser、quality v1、通用 family extractor 与解析证据 |
| ACQ-1 WP-3..WP-8 | 未准入 | WP-3 Browser 的 package/revision/image digest、egress 与资源隔离精确证据待冻结；Router、Discovery、Change Intelligence、Opportunity 与最终收尾继续未准入 |
| PLUGIN-1 | 待办、未准入 | 用户指定在 ACQ-1 完成验收后、Frontend 前处理；尚未实现，未形成正式准入或架构基线 |
| Frontend / Integration / Release | 未准入 | 桌面客户端、集成验收与 Alpha 发布尚未开始 |

已实现能力仅以合并到 GitHub `main` 的事实为准；阶段门禁见[当前闸门](docs/CURRENT-GATE.md)和[交付看板](docs/02-DELIVERY-BOARD.md)。开放中的 PR、准入许可和计划能力不视为已实现；PLUGIN-1 仅记录用户指定的待办顺序，不构成准入。

### 核心数据闭环

```text
用户注册/登录                         ✅ BE-2 已完成
  → 创建 Radar 与配置 RSS/URL Source  ✅ BE-3 已完成
  → 受控后台采集与原始证据保存         ✅ BE-4 已完成
  → 清洗、去重、AI 摘要/分类/评分      ✅ BE-5 已完成
  → 文档切块、向量化与 Memory Search   ✅ BE-6 已完成
  → Notification、WebSocket 与运行重试 ✅ BE-7 已完成
  → Tauri 桌面信息流与知识库           ⏳ Frontend 未准入
```

### 当前已实现

- 版本化 FastAPI REST API、统一错误响应、请求追踪、健康检查和 Celery 后台任务基础设施。
- PostgreSQL + pgvector 数据层、SQLAlchemy 2.x Async、Alembic 迁移和 Redis 任务基础设施。
- 用户注册、登录、Token 生命周期和用户资料接口。
- Radar/Source CRUD、所有权隔离、软删除、启停、绑定及确定性 URL 规范化。
- RSS 与单页 URL 的受控采集、调度、幂等、去重、运行状态和 RawItem 查询。
- 确定性清洗、全局 Document 去重、版本化 AI 分析、四维评分、成本审计、恢复任务和 Intelligence 查询接口。
- 确定性切块、Embedding、pgvector HNSW 检索、Bookmark 与 Memory Search。

- Notification 阈值/优先级判定、分页与已读接口、用户隔离的 WebSocket 在线事件，以及 CollectionRun retry、Analysis retry 和遗漏任务补偿。
- BE-8 离线闭环验收、OpenAPI 快照冻结、运行文档与前端交接材料；交接材料完成不等于 Frontend 已准入。
- ACQ-1 WP-1 的严格 `acq-source-v1` Source Profile、legacy config 秘密拒绝/脱敏、采集状态与 Attempt、CollectionRun 租约/心跳/过期恢复/旧 Worker 写入防护，以及 Network/Site/Resource 策略内核。

### 当前开发状态与验收证据

本次同步基于 `main@70a3b0462e9a9303ddb3f5be56c84ed5d2fead40`。WP-2 实现 PR #39 已通过 Stage Gate 并合并；[WP-2 验收记录](docs/36-ACQ1-WP2-ACCEPTANCE.md)对应实现提交 `90c4645c95a96608a35565ca90b022dfb2f1f1a7`：286 tests、87.61% coverage，P0/P1/P2 = 0/0/0。

WP-2 已实现统一 RSS/Native 静态 Adapter 边界、只消费本地响应的 Scrapling parser、`extraction-quality-v1`、通用 family extractor 与内部解析证据。它没有启用 Browser/fetcher，也没有引入 Router、Discovery、Change、Opportunity、Schema/migration 或公开 API 变化。

下一阶段是 WP-3 / ACQ-1B Dynamic + H-browser。现有契约已冻结独立 Browser 镜像、专用 worker/queue、强制受控 egress 和 fail-closed 安全方向，但精确 package/browser revision/system dependency/image digest、egress 实现与资源限值尚无可复现实证；因此 **WP-3 仍未准入**，详见 [WP-3 Readiness Blocker](docs/37-ACQ1-WP3-READINESS-BLOCKER.md)。

WP-3 的计划目标是隔离的 Dynamic/Advanced Browser adapter、专用 worker/queue、强制受控 egress 与 Browser pool/resource isolation。这些仍不是 `main` 已实现能力；在精确证据和后续 Admission 控制 PR 合并前，不得安装或启用 Browser，也不得进入 Router 或 Discovery。

### 技术栈

| 层 | 技术 |
| --- | --- |
| Backend | Python 3.13、FastAPI、Pydantic、Celery |
| 数据与迁移 | PostgreSQL、pgvector、SQLAlchemy 2.x Async、Alembic |
| 任务与缓存 | Redis、Celery Worker/Beat |
| 采集 | RSS/Atom、受控 HTTP(S) fetcher、安全 HTML 解析 |
| Intelligence | Provider 抽象、离线 Fake Provider、OpenAI-compatible Adapter |
| API | 已实现 REST `/api/v1` 与 WebSocket `/api/v1/ws`；在线事件为 best-effort，断线后通过 REST 恢复事实 |
| Desktop 目标 | Tauri 2、React、TypeScript；Frontend 尚未准入 |
| 验证 | Pytest、Ruff、Mypy、Alembic、Docker Compose |

### 项目结构

```text
FlowTracer/
├── backend/       FastAPI 服务、Celery 任务、迁移与后端测试
├── frontend/      Tauri + React 桌面客户端目录（正式开发未准入）
├── docs/          架构、契约、阶段基线、准入与交付控制
├── infra/         PostgreSQL、Redis、API 与 Worker 的 Compose 配置
├── tests/         跨组件与集成测试目录
├── .codex/        项目级 Codex 配置
└── README.md      项目入口与已合并进度摘要
```

### 快速开始

当前可验证入口是已合并的 Backend 服务；桌面客户端尚未进入正式开发。

要求：Git、Docker Desktop（Linux containers）和 Docker Compose。

```bash
git clone https://github.com/lucaschang2021/FlowTracer.git
cd FlowTracer
docker compose -f infra/compose.yaml build api
docker compose -f infra/compose.yaml up -d --wait postgres redis
docker compose -f infra/compose.yaml run --rm api alembic upgrade head
docker compose -f infra/compose.yaml up -d api worker
```

API 启动后可检查存活状态：

```bash
curl http://127.0.0.1:8000/api/v1/health/live
```

停止本地服务：

```bash
docker compose -f infra/compose.yaml down
```

使用 `uv` 在宿主机开发、执行迁移或运行质量检查时，请遵循 [Backend 开发指南](backend/DEVELOPMENT.md)。示例配置只用于本地开发，切勿复用默认凭据。

### 关键文档

- [当前阶段闸门](docs/CURRENT-GATE.md)
- [Alpha v0.1 交付看板](docs/02-DELIVERY-BOARD.md)
- [项目总控基线](docs/00-PROJECT-CONTROL.md)
- [架构决策记录](docs/01-ARCHITECTURE-DECISIONS.md)
- [后端契约基线](docs/03-BACKEND-CONTRACT-BASELINE.md)
- [Backend 正式任务包](docs/10-BACKEND-WORK-PACKAGE.md)
- [Backend 开发指南](backend/DEVELOPMENT.md)
- [Backend 前端交接包](backend/FRONTEND-HANDOFF.md)
- [ACQ-1 总体基线](docs/22-ACQ1-MASTER-BASELINE.md)
- [ACQ-1 采集契约](docs/23-ACQ1-ACQUISITION-CONTRACT.md)
- [ACQ-1 验收基线](docs/25-ACQ1-ACCEPTANCE.md)
- [ACQ-1 工作包与边界](docs/29-ACQ1-WORK-PACKAGES.md)
- [WP-1 Profile / Policy Addendum](docs/32-ACQ1-WP1-CONTRACT-ADDENDUM.md)
- [WP-1 验收记录](docs/33-ACQ1-WP1-ACCEPTANCE.md)
- [WP-2 静态解析阶段准入](docs/34-ACQ1-WP2-ADMISSION.md)
- [WP-2 提取质量契约 Addendum](docs/35-ACQ1-WP2-CONTRACT-ADDENDUM.md)
- [WP-2 Stage Gate 验收](docs/36-ACQ1-WP2-ACCEPTANCE.md)
- [WP-3 准入阻塞与证据要求](docs/37-ACQ1-WP3-READINESS-BLOCKER.md)

### 路线图与门禁

FlowTracer 当前交付顺序（含未准入的待办阶段）：

```text
架构冻结 → BE-1..BE-8 → ACQ-1 WP-1..WP-8
  → PLUGIN-1（待办、未准入）→ Frontend → Integration → Alpha Release
```

BE-1..BE-8、WP-1 与 WP-2 已完成并合并。WP-3 Browser 的精确兼容性、不可变镜像、受控 egress 与资源隔离证据尚未冻结，所以 WP-3 仍未准入；WP-4..WP-8、Router、Discovery、Change Intelligence、Opportunity、PLUGIN-1、Frontend、Integration 与 Release 也继续未准入。

PLUGIN-1 仅为用户指定的后续待办：排在 ACQ-1 全部完成验收之后、Frontend 之前，尚未准入或实现。本文不为其补写架构、接口或仓库文档链接。

### 安全与范围边界

- 密钥只来自环境变量或密钥管理，不得提交真实 `.env`、Token、API Key、用户数据或抓取正文样本。
- 采集链路限制协议、端口、重定向、DNS/IP、响应类型、大小和超时；测试不得访问公网。
- API、任务和查询必须实施用户所有权隔离；不得泄漏正文、查询、向量、凭据或跨用户数据。
- Alpha 使用 PostgreSQL + pgvector 作为唯一 Memory 事实源；不引入 Qdrant、Milvus、Neo4j、知识图谱、多模型 Router 或 Agent。
- FlowTracer v0.1 仍是开发中的 Alpha；目前没有可下载的正式桌面版本或 GitHub Release。

---

## English

**A personal desktop AI intelligence system for continuous acquisition, traceable analysis, and long-term Memory—designed to surface and preserve high-value information.**

> **Alpha status:** FlowTracer v0.1 is in development and has not been released. BE-1 through BE-8, ACQ-1 Preflight, Contract Freeze, WP-1, and WP-2 have been accepted and merged. WP-2 implementation PR #39 is on `main`; WP-3 Browser still lacks frozen, reproducible compatibility and isolation evidence, so WP-3 through WP-8, PLUGIN-1, Frontend, Integration, and Release are not admitted.

### Product Positioning

FlowTracer lets users define intelligence goals through its core domain object, **Radar**, and attach RSS or single-page URL sources. Its backend continuously acquires content, preserves raw evidence, cleans and deduplicates it, performs AI classification, summarization, scoring, and cost auditing, and progressively retains valuable intelligence in searchable personal Memory.

Radar is FlowTracer's core domain object, not the project name. The official product name is always **FlowTracer**.

### Alpha v0.1 Progress

| Phase | Status | Merged or current scope |
| --- | --- | --- |
| BE-1 | Completed | FastAPI/Celery foundation, health checks, migrations, and local infrastructure |
| BE-2 | Completed | Data models, authentication, and user APIs |
| BE-3 | Completed | Radar/Source management, bindings, and URL normalization |
| BE-4 | Completed | Controlled RSS/URL acquisition, scheduling, runs, and RawItem persistence |
| BE-5 | Completed | Cleaning, Document deduplication, AI analysis, scoring, cost auditing, and Intelligence APIs |
| BE-6 | Completed | Deterministic chunking, embeddings, pgvector HNSW retrieval, Bookmark, and Memory Search |
| BE-7 | Completed | Notification, WebSocket online events, CollectionRun retry, and recovery dispatchers, including Analysis retry regression coverage |
| BE-8 | Completed | Offline Alpha closure, stabilization, OpenAPI snapshot freeze, operations documentation, and Frontend handoff materials |
| ACQ-1 Preflight / Contract Freeze | Completed | Engineering inventory, acquisition and safety contracts, and work-package plan merged; frozen contracts do not imply later capabilities are implemented |
| ACQ-1 WP-1 Admission / Addendum | Completed | PRs #31 / #32 merged; exact Source Profile and Policy contracts frozen |
| ACQ-1 WP-1 | Completed | PR #33 accepted and merged: Source Profile, acquisition state/Attempt, lease/heartbeat/stale recovery, and safety-policy core |
| ACQ-1 WP-2 | Completed | PR #39 accepted and merged: unified static adapters, a network-free Scrapling parser, quality v1, common family extractors, and parsing evidence |
| ACQ-1 WP-3..WP-8 | Not admitted | WP-3 Browser package/revision/image digest, egress, and resource-isolation evidence remain unfrozen; Router, Discovery, Change Intelligence, Opportunity, and final stabilization are also not admitted |
| PLUGIN-1 | Backlog, not admitted | User-requested stage after full ACQ-1 acceptance and before Frontend; not implemented, with no formal admission or architecture baseline |
| Frontend / Integration / Release | Not admitted | Desktop development, integration acceptance, and the Alpha release have not started |

Implemented capabilities are determined only by facts merged into GitHub `main`; phase gates are recorded in the [current gate](docs/CURRENT-GATE.md) and [delivery board](docs/02-DELIVERY-BOARD.md). Open pull requests, admission approvals, and planned capabilities are not treated as implemented. PLUGIN-1 records only a user-requested backlog order, not admission.

### Core Data Loop

```text
User registration/sign-in                    ✅ BE-2 completed
  → Create Radar and configure RSS/URL Source ✅ BE-3 completed
  → Controlled acquisition and raw evidence   ✅ BE-4 completed
  → Cleaning, deduplication, AI summary/score  ✅ BE-5 completed
  → Chunking, embeddings, and Memory Search    ✅ BE-6 completed
  → Notification, WebSocket, and run retry      ✅ BE-7 completed
  → Tauri desktop feed and knowledge base      ⏳ Frontend not admitted
```

### Implemented Today

- Versioned FastAPI REST APIs, unified errors, request tracing, health checks, and Celery task infrastructure.
- PostgreSQL + pgvector persistence, SQLAlchemy 2.x Async, Alembic migrations, and Redis task infrastructure.
- User registration, sign-in, token lifecycle, and profile APIs.
- Radar/Source CRUD, ownership isolation, soft deletion, activation controls, bindings, and deterministic URL normalization.
- Controlled RSS and single-page URL acquisition, scheduling, idempotency, deduplication, run state, and RawItem queries.
- Deterministic cleaning, global Document deduplication, versioned AI analysis, four-dimensional scoring, cost auditing, recovery tasks, and Intelligence query APIs.
- Deterministic chunking, embeddings, pgvector HNSW retrieval, Bookmark, and Memory Search.

- Notification threshold/priority evaluation, pagination and read-state APIs, user-isolated WebSocket online events, CollectionRun retry, Analysis retry, and missed-task recovery.
- BE-8 offline closure acceptance, OpenAPI snapshot freeze, operations documentation, and Frontend handoff materials; completing handoff materials does not admit Frontend.
- ACQ-1 WP-1 strict `acq-source-v1` Source Profiles, legacy config secret rejection/redaction, acquisition state and Attempts, CollectionRun leases/heartbeats/stale recovery/old-worker fencing, and the Network/Site/Resource policy core.

### Current Development and Acceptance Evidence

This update is based on `main@70a3b0462e9a9303ddb3f5be56c84ed5d2fead40`. WP-2 implementation PR #39 passed its Stage Gate and was merged. The [WP-2 acceptance record](docs/36-ACQ1-WP2-ACCEPTANCE.md) covers implementation commit `90c4645c95a96608a35565ca90b022dfb2f1f1a7`: 286 tests, 87.61% coverage, and P0/P1/P2 = 0/0/0.

WP-2 implements the unified RSS/Native static-adapter boundary, a Scrapling parser that consumes only local responses, `extraction-quality-v1`, common family extractors, and internal parsing evidence. It does not enable a Browser/fetcher or introduce Router, Discovery, Change, Opportunity, schema/migration, or public API changes.

The next stage is WP-3 / ACQ-1B Dynamic + H-browser. Existing contracts freeze the independent Browser image, dedicated worker/queue, mandatory controlled egress, and fail-closed security direction, but reproducible evidence for the exact package/browser revision/system dependencies/image digest, egress implementation, and resource limits does not yet exist. **WP-3 therefore remains not admitted**; see the [WP-3 Readiness Blocker](docs/37-ACQ1-WP3-READINESS-BLOCKER.md).

WP-3 is planned to add isolated Dynamic/Advanced Browser adapters, a dedicated worker/queue, mandatory controlled egress, and Browser pool/resource isolation. These are not implemented on `main`; Browser installation or enablement, Router, and Discovery remain prohibited until exact evidence is frozen and a later Admission control PR is merged.

### Technology Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.13, FastAPI, Pydantic, Celery |
| Data and migrations | PostgreSQL, pgvector, SQLAlchemy 2.x Async, Alembic |
| Tasks and cache | Redis, Celery Worker/Beat |
| Acquisition | RSS/Atom, controlled HTTP(S) fetcher, secure HTML parsing |
| Intelligence | Provider abstraction, offline Fake Provider, OpenAI-compatible adapter |
| API | Implemented REST `/api/v1` and WebSocket `/api/v1/ws`; online events are best effort, with REST fact recovery after disconnection |
| Desktop target | Tauri 2, React, TypeScript; Frontend is not admitted |
| Validation | Pytest, Ruff, Mypy, Alembic, Docker Compose |

### Project Structure

```text
FlowTracer/
├── backend/       FastAPI service, Celery tasks, migrations, and backend tests
├── frontend/      Tauri + React desktop directory (formal development not admitted)
├── docs/          Architecture, contracts, phase baselines, admissions, and delivery control
├── infra/         Compose configuration for PostgreSQL, Redis, API, and Worker
├── tests/         Cross-component and integration test directory
├── .codex/        Project-level Codex configuration
└── README.md      Project entry point and merged-progress summary
```

### Quick Start

The currently verifiable entry point is the merged Backend service; formal desktop development has not started.

Requirements: Git, Docker Desktop with Linux containers, and Docker Compose.

```bash
git clone https://github.com/lucaschang2021/FlowTracer.git
cd FlowTracer
docker compose -f infra/compose.yaml build api
docker compose -f infra/compose.yaml up -d --wait postgres redis
docker compose -f infra/compose.yaml run --rm api alembic upgrade head
docker compose -f infra/compose.yaml up -d api worker
```

After the API starts, check liveness:

```bash
curl http://127.0.0.1:8000/api/v1/health/live
```

Stop the local services with:

```bash
docker compose -f infra/compose.yaml down
```

For host development with `uv`, migrations, and quality checks, follow the [Backend development guide](backend/DEVELOPMENT.md). Example configuration is for local development only; never reuse default credentials.

### Authoritative Documents

- [Current phase gate](docs/CURRENT-GATE.md)
- [Alpha v0.1 delivery board](docs/02-DELIVERY-BOARD.md)
- [Project control baseline](docs/00-PROJECT-CONTROL.md)
- [Architecture decision records](docs/01-ARCHITECTURE-DECISIONS.md)
- [Backend contract baseline](docs/03-BACKEND-CONTRACT-BASELINE.md)
- [Backend formal work package](docs/10-BACKEND-WORK-PACKAGE.md)
- [Backend development guide](backend/DEVELOPMENT.md)
- [Backend Frontend handoff package](backend/FRONTEND-HANDOFF.md)
- [ACQ-1 master baseline](docs/22-ACQ1-MASTER-BASELINE.md)
- [ACQ-1 acquisition contract](docs/23-ACQ1-ACQUISITION-CONTRACT.md)
- [ACQ-1 acceptance baseline](docs/25-ACQ1-ACCEPTANCE.md)
- [ACQ-1 work packages and boundaries](docs/29-ACQ1-WORK-PACKAGES.md)
- [WP-1 Profile / Policy Addendum](docs/32-ACQ1-WP1-CONTRACT-ADDENDUM.md)
- [WP-1 acceptance record](docs/33-ACQ1-WP1-ACCEPTANCE.md)
- [WP-2 static parsing admission](docs/34-ACQ1-WP2-ADMISSION.md)
- [WP-2 extraction-quality contract Addendum](docs/35-ACQ1-WP2-CONTRACT-ADDENDUM.md)
- [WP-2 Stage Gate acceptance](docs/36-ACQ1-WP2-ACCEPTANCE.md)
- [WP-3 admission blocker and evidence requirements](docs/37-ACQ1-WP3-READINESS-BLOCKER.md)

### Roadmap and Gates

FlowTracer's current delivery order (including unadmitted backlog stages):

```text
Architecture freeze → BE-1..BE-8 → ACQ-1 WP-1..WP-8
  → PLUGIN-1 (backlog, not admitted) → Frontend → Integration → Alpha Release
```

BE-1..BE-8, WP-1, and WP-2 are complete and merged. WP-3 Browser still lacks frozen evidence for exact compatibility, immutable images, controlled egress, and resource isolation, so WP-3 remains not admitted; WP-4..WP-8, Router, Discovery, Change Intelligence, Opportunity, PLUGIN-1, Frontend, Integration, and Release also remain not admitted.

PLUGIN-1 is only a user-requested backlog stage after full ACQ-1 acceptance and before Frontend. It is neither admitted nor implemented. This README does not define its architecture, interfaces, or repository document links.

### Security and Scope Boundaries

- Secrets must come from environment variables or secret management. Never commit real `.env` files, tokens, API keys, user data, or acquired content samples.
- Acquisition restricts protocols, ports, redirects, DNS/IP targets, response types, sizes, and timeouts; tests must not access the public internet.
- APIs, tasks, and queries must enforce user ownership. Content, queries, vectors, credentials, and cross-user data must not leak.
- Alpha uses PostgreSQL + pgvector as its only Memory source of truth; Qdrant, Milvus, Neo4j, knowledge graphs, multi-model routers, and agents are out of scope.
- FlowTracer v0.1 remains an in-development Alpha. There is no downloadable production desktop build or GitHub Release yet.
