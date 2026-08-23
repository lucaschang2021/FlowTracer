# FlowTracer

## 中文

### 产品介绍

FlowTracer 是一套桌面 AI 情报系统。用户通过核心领域对象 Radar 定义关注目标与信息来源，系统持续采集、清洗、分析、评分并保存内容，帮助用户从信息流中识别高价值情报，并沉淀到个人知识库。

Radar 是 FlowTracer 的核心领域对象，不是项目名称。

### Alpha v0.1 与当前阶段

- 当前发布目标：**Alpha v0.1**
- 当前阶段：**Backend Phase BE-1 — 基础骨架与本地基础设施**
- 阶段准入：仅 BE-1 已获批准；BE-2 及后续后端阶段、Frontend、Integration、Release 均未准入。
- BE-0、BE-1 工程基线和本地环境复核已经通过；Backend 必须在独立开发分支严格执行 BE-1，并在完成后停点提交报告和 PR。

固定交付顺序：架构冻结 → 后端开发 → 前端开发 → 前后端集成测试 → GitHub 上传与 Alpha 发布。

### 核心数据闭环

```text
用户注册/登录
  → 创建 Radar
  → 配置 RSS 或自定义 URL
  → 后台采集
  → 清洗和去重
  → AI 分类、摘要、评分
  → 保存文档和向量
  → 桌面信息流
  → 高价值内容通知
  → 收藏并沉淀到个人知识库
```

### 项目目录结构

```text
FlowTracer/
├── backend/       FastAPI 服务与 Celery 后台任务
├── frontend/      Tauri + React 桌面客户端
├── docs/          架构、契约、任务包与交付管理文档
├── infra/         Docker Compose 等本地基础设施配置
├── tests/         跨组件测试与端到端测试
└── .vscode/       共享的 VS Code 配置
```

### 开发状态与正式文档

架构、领域模型、状态机、REST API 范围、WebSocket 事件、评分规则和 Backend 任务包已完成初步冻结，BE-0 与本地环境复核已经通过。Backend 当前只获准执行 BE-1 基础骨架与本地基础设施。

- [项目总控基线](docs/00-PROJECT-CONTROL.md)
- [架构决策记录](docs/01-ARCHITECTURE-DECISIONS.md)
- [交付看板](docs/02-DELIVERY-BOARD.md)
- [后端契约基线](docs/03-BACKEND-CONTRACT-BASELINE.md)
- [BE-1 工程基线](docs/04-BE1-ENGINEERING-BASELINE.md)
- [Backend 正式任务包](docs/10-BACKEND-WORK-PACKAGE.md)
- [BE-0 验收报告](docs/11-BE-0-ACCEPTANCE.md)
- [BE-1 准入许可](docs/12-BE-1-ADMISSION.md)

### Alpha 技术栈

- Desktop：Tauri 2 + React + TypeScript
- Backend：FastAPI + Python
- ORM / Migration：SQLAlchemy 2.x Async + Alembic
- Database：PostgreSQL + pgvector
- Background Tasks：Celery + Redis
- Acquisition：RSS + Scrapling + 单页自定义 URL
- Communication：REST `/api/v1` + WebSocket
- Testing：Pytest + 前端单元测试 + E2E
- Local Infrastructure：Docker Compose

---

## English

### Product Overview

FlowTracer is a desktop AI intelligence system. Through Radar, its core domain object, users define intelligence goals and sources. The system continuously collects, cleans, analyzes, scores, and preserves content so users can identify high-value intelligence in a desktop feed and retain it in a personal knowledge base.

Radar is FlowTracer's core domain object, not the project name.

### Alpha v0.1 and Current Stage

- Current release target: **Alpha v0.1**
- Current stage: **Backend Phase BE-1 — Foundation and Local Infrastructure**
- Stage admission: only BE-1 is approved; BE-2 and later backend phases, Frontend, Integration, and Release are not admitted.
- BE-0, the BE-1 engineering baseline, and the local environment review have passed. Backend must implement BE-1 on an independent development branch and stop for a report and PR when complete.

The fixed delivery sequence is: architecture freeze → backend development → frontend development → frontend/backend integration testing → GitHub upload and Alpha release.

### Core Data Loop

```text
User registration/sign-in
  → Create a Radar
  → Configure RSS or a custom URL
  → Background acquisition
  → Cleaning and deduplication
  → AI classification, summarization, and scoring
  → Store documents and vectors
  → Desktop intelligence feed
  → High-value content notifications
  → Bookmark and retain in the personal knowledge base
```

### Repository Layout

```text
FlowTracer/
├── backend/       FastAPI service and Celery background tasks
├── frontend/      Tauri + React desktop client
├── docs/          Architecture, contracts, work packages, and delivery control
├── infra/         Local infrastructure such as Docker Compose
├── tests/         Cross-component and end-to-end tests
└── .vscode/       Shared VS Code configuration
```

### Development Status and Authoritative Documents

The architecture, domain model, state machine, REST API scope, WebSocket events, scoring rules, and Backend work package have completed their initial freeze. BE-0 and the local environment review have passed. Backend is currently admitted only for the BE-1 foundation and local infrastructure phase.

- [Project control baseline](docs/00-PROJECT-CONTROL.md)
- [Architecture decision records](docs/01-ARCHITECTURE-DECISIONS.md)
- [Delivery board](docs/02-DELIVERY-BOARD.md)
- [Backend contract baseline](docs/03-BACKEND-CONTRACT-BASELINE.md)
- [BE-1 engineering baseline](docs/04-BE1-ENGINEERING-BASELINE.md)
- [Backend formal work package](docs/10-BACKEND-WORK-PACKAGE.md)
- [BE-0 acceptance report](docs/11-BE-0-ACCEPTANCE.md)
- [BE-1 admission](docs/12-BE-1-ADMISSION.md)

### Alpha Technology Stack

- Desktop: Tauri 2 + React + TypeScript
- Backend: FastAPI + Python
- ORM / Migration: SQLAlchemy 2.x Async + Alembic
- Database: PostgreSQL + pgvector
- Background Tasks: Celery + Redis
- Acquisition: RSS + Scrapling + single-page custom URLs
- Communication: REST `/api/v1` + WebSocket
- Testing: Pytest + frontend unit tests + E2E
- Local Infrastructure: Docker Compose
