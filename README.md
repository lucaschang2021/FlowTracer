# FlowTracer

**面向个人的桌面 AI 情报系统：从持续采集、可追踪分析到长期 Memory，帮助用户从信息流中发现并沉淀高价值内容。**

[当前闸门](docs/CURRENT-GATE.md) · [交付看板](docs/02-DELIVERY-BOARD.md) · [Backend 开发](backend/DEVELOPMENT.md) · [English](#english)

> **Alpha 状态：** FlowTracer v0.1 正在开发，尚未发布。BE-1 至 BE-5 已验收并合并；BE-6 Vector Memory 与知识库接口已准入、正在开发。BE-7、Frontend、Integration 和 Release 尚未准入。

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
| BE-6 | 开发中 | 已准入；目标为确定性切块、Embedding、pgvector 检索、Bookmark 与 Memory Search |
| BE-7、BE-8 | 未准入 | 通知、WebSocket、恢复与后端稳定化尚未开始 |
| Frontend / Integration / Release | 未准入 | 桌面客户端、集成验收与 Alpha 发布尚未开始 |

阶段状态仅以已合并到 GitHub `main` 的事实、[当前闸门](docs/CURRENT-GATE.md)和[交付看板](docs/02-DELIVERY-BOARD.md)为准。开放中的 PR 或计划能力不视为已实现。

### 核心数据闭环

```text
用户注册/登录                         ✅ BE-2 已完成
  → 创建 Radar 与配置 RSS/URL Source  ✅ BE-3 已完成
  → 受控后台采集与原始证据保存         ✅ BE-4 已完成
  → 清洗、去重、AI 摘要/分类/评分      ✅ BE-5 已完成
  → 文档切块、向量化与 Memory Search   🚧 BE-6 开发中
  → 高价值事件与桌面通知               ⏳ BE-7 未准入
  → Tauri 桌面信息流与知识库           ⏳ Frontend 未准入
```

### 当前已实现

- 版本化 FastAPI REST API、统一错误响应、请求追踪、健康检查和 Celery 后台任务基础设施。
- PostgreSQL + pgvector 数据层、SQLAlchemy 2.x Async、Alembic 迁移和 Redis 任务基础设施。
- 用户注册、登录、Token 生命周期和用户资料接口。
- Radar/Source CRUD、所有权隔离、软删除、启停、绑定及确定性 URL 规范化。
- RSS 与单页 URL 的受控采集、调度、幂等、去重、运行状态和 RawItem 查询。
- 确定性清洗、全局 Document 去重、版本化 AI 分析、四维评分、成本审计、恢复任务和 Intelligence 查询接口。

BE-6 的 Embedding、HNSW、Bookmark 和 Memory Search 目前属于已准入开发范围，不属于 `main` 上已完成能力。

### 技术栈

| 层 | 技术 |
| --- | --- |
| Backend | Python 3.13、FastAPI、Pydantic、Celery |
| 数据与迁移 | PostgreSQL、pgvector、SQLAlchemy 2.x Async、Alembic |
| 任务与缓存 | Redis、Celery Worker/Beat |
| 采集 | RSS、受控 HTTP(S) fetcher、Scrapling 页面提取 |
| Intelligence | Provider 抽象、离线 Fake Provider、OpenAI-compatible Adapter |
| API | REST `/api/v1`；WebSocket 属于未准入的 BE-7 |
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
docker compose -f infra/compose.yaml up --build
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
- [BE-6 Vector Memory 契约基线](docs/09-BE6-MEMORY-BASELINE.md)
- [BE-6 阶段准入许可](docs/17-BE-6-ADMISSION.md)

### 路线图与门禁

FlowTracer 固定按以下阶段推进：

```text
架构冻结 → Backend BE-1..BE-8 → Frontend → Integration → Alpha Release
```

当前只允许实施 BE-6。BE-6 完成后必须提交阶段报告、测试与迁移证据并停点，等待总控验收；未经新的阶段准入，不得进入 BE-7、Frontend、Integration 或 Release。

### 安全与范围边界

- 密钥只来自环境变量或密钥管理，不得提交真实 `.env`、Token、API Key、用户数据或抓取正文样本。
- 采集链路限制协议、端口、重定向、DNS/IP、响应类型、大小和超时；测试不得访问公网。
- API、任务和查询必须实施用户所有权隔离；不得泄漏正文、查询、向量、凭据或跨用户数据。
- Alpha 使用 PostgreSQL + pgvector 作为唯一 Memory 事实源；不引入 Qdrant、Milvus、Neo4j、知识图谱、多模型 Router 或 Agent。
- FlowTracer v0.1 仍是开发中的 Alpha；目前没有可下载的正式桌面版本或 GitHub Release。

---

## English

**A personal desktop AI intelligence system for continuous acquisition, traceable analysis, and long-term Memory—designed to surface and preserve high-value information.**

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
| BE-6 | In development | Admitted; targets deterministic chunking, embeddings, pgvector retrieval, Bookmark, and Memory Search |
| BE-7 and BE-8 | Not admitted | Notifications, WebSocket, recovery, and backend stabilization have not started |
| Frontend / Integration / Release | Not admitted | Desktop development, integration acceptance, and the Alpha release have not started |

Phase status is determined only by facts merged into GitHub `main`, the [current gate](docs/CURRENT-GATE.md), and the [delivery board](docs/02-DELIVERY-BOARD.md). Open pull requests and planned capabilities are not treated as implemented.

### Core Data Loop

```text
User registration/sign-in                    ✅ BE-2 completed
  → Create Radar and configure RSS/URL Source ✅ BE-3 completed
  → Controlled acquisition and raw evidence   ✅ BE-4 completed
  → Cleaning, deduplication, AI summary/score  ✅ BE-5 completed
  → Chunking, embeddings, and Memory Search    🚧 BE-6 in development
  → High-value events and desktop notification ⏳ BE-7 not admitted
  → Tauri desktop feed and knowledge base      ⏳ Frontend not admitted
```

### Implemented Today

- Versioned FastAPI REST APIs, unified errors, request tracing, health checks, and Celery task infrastructure.
- PostgreSQL + pgvector persistence, SQLAlchemy 2.x Async, Alembic migrations, and Redis task infrastructure.
- User registration, sign-in, token lifecycle, and profile APIs.
- Radar/Source CRUD, ownership isolation, soft deletion, activation controls, bindings, and deterministic URL normalization.
- Controlled RSS and single-page URL acquisition, scheduling, idempotency, deduplication, run state, and RawItem queries.
- Deterministic cleaning, global Document deduplication, versioned AI analysis, four-dimensional scoring, cost auditing, recovery tasks, and Intelligence query APIs.

BE-6 embeddings, HNSW, Bookmark, and Memory Search are admitted development scope, not completed capabilities on `main`.

### Technology Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.13, FastAPI, Pydantic, Celery |
| Data and migrations | PostgreSQL, pgvector, SQLAlchemy 2.x Async, Alembic |
| Tasks and cache | Redis, Celery Worker/Beat |
| Acquisition | RSS, controlled HTTP(S) fetcher, Scrapling page extraction |
| Intelligence | Provider abstraction, offline Fake Provider, OpenAI-compatible adapter |
| API | REST `/api/v1`; WebSocket belongs to the not-yet-admitted BE-7 phase |
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
docker compose -f infra/compose.yaml up --build
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
- [BE-6 Vector Memory contract baseline](docs/09-BE6-MEMORY-BASELINE.md)
- [BE-6 phase admission](docs/17-BE-6-ADMISSION.md)

### Roadmap and Gates

FlowTracer follows a fixed delivery sequence:

```text
Architecture freeze → Backend BE-1..BE-8 → Frontend → Integration → Alpha Release
```

Only BE-6 is currently admitted. When BE-6 is complete, the Backend role must submit its phase report, tests, and migration evidence, then stop for controller acceptance. BE-7, Frontend, Integration, and Release cannot begin without a new phase admission.

### Security and Scope Boundaries

- Secrets must come from environment variables or secret management. Never commit real `.env` files, tokens, API keys, user data, or acquired content samples.
- Acquisition restricts protocols, ports, redirects, DNS/IP targets, response types, sizes, and timeouts; tests must not access the public internet.
- APIs, tasks, and queries must enforce user ownership. Content, queries, vectors, credentials, and cross-user data must not leak.
- Alpha uses PostgreSQL + pgvector as its only Memory source of truth; Qdrant, Milvus, Neo4j, knowledge graphs, multi-model routers, and agents are out of scope.
- FlowTracer v0.1 remains an in-development Alpha. There is no downloadable production desktop build or GitHub Release yet.
