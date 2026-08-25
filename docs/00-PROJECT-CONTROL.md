# FlowTracer Alpha v0.1 项目总控基线

## 1. 文档地位

- 输入基线：用户提供的《FlowTracer 技术设计文档 Alpha v0.1》。
- 当前阶段：Backend Phase BE-1 基础骨架与本地基础设施，已准入。
- 当前结论：Alpha 架构、BE-1 工程基线和本地运行环境已通过门禁；Backend 只可执行 BE-1。
- 项目正式名称：FlowTracer。
- Radar 是 FlowTracer 的核心领域对象，不再作为项目名称使用。

## 2. Alpha 交付目标

交付一个可运行的桌面 AI 情报雷达原型，完成以下闭环：

```text
用户注册/登录
  -> 创建 Radar
  -> 配置 RSS 或自定义 URL 来源
  -> 后台采集内容
  -> 清洗与去重
  -> AI 摘要、分类和评分
  -> 保存正文、摘要与向量
  -> 在桌面信息流展示
  -> 对高价值内容发送桌面通知
  -> 用户收藏并进入个人知识库
```

## 3. Alpha 范围

### 必须交付

- FastAPI 后端及版本化 REST API。
- 邮箱与密码身份认证、用户资料。
- Radar CRUD、启停和领域配置。
- RSS、自定义 URL 两类来源；API Source 仅保留扩展接口。
- 后台定时采集、失败重试、内容清洗和哈希去重。
- AI 摘要、分类、四维评分及推荐理由。
- PostgreSQL 文档存储与 pgvector 向量检索。
- Tauri + React 桌面端。
- Dashboard、Radar 管理、情报流、基础知识库、设置页面。
- WebSocket 在线事件与 Tauri 原生桌面通知。
- 单元、API、数据闭环和桌面端关键路径测试。
- Docker Compose 本地运行环境、README 和 Alpha Release。

### 明确不进入 Alpha

- Neo4j 和知识图谱。
- Milvus、Qdrant 等独立向量数据库。
- 多模型智能 Router、本地模型调度和自动质量优化。
- 团队、组织、企业权限体系。
- Market/Business/Policy 等领域专用分析器。
- 大规模通用爬虫、浏览器自动化反爬对抗。
- 移动端、网页端和 AgentOS 集成。
- Obsidian 双向同步、知识图谱自动维护、跨 Agent 长期上下文编译等高级 Knowledge Layer 能力。

## 4. 工程原则

- 流程固定为：架构冻结 -> 后端 -> 前端 -> 集成测试 -> GitHub 发布。
- 前端正式开发以前，必须冻结 OpenAPI 契约和事件格式。
- 采集和 AI 推理必须在后台任务中执行，不阻塞 API 请求。
- 所有后台处理必须幂等、可重试、可追踪。
- 原始内容、标准化内容、AI 产物分层保存，禁止覆盖原始证据。
- 密钥只能来自环境变量或密钥管理，不得进入代码库或数据库明文日志。
- Alpha 优先验证端到端价值，不提前实现后续版本能力。
- 所有开发必须经过任务规划、开发分支、commit、push、Pull Request、Review 和 Merge。
- 禁止直接向 `main` push；未经总控明确 Review 和授权，GitHub 管理角色不得合并。

## 5. 里程碑与阶段闸门

| 里程碑 | 产出 | 通过条件 |
| --- | --- | --- |
| M0 架构冻结 | 数据模型、状态机、API、事件、部署拓扑、ADR | 无阻塞级待决策项；后端任务可无歧义执行 |
| M1 后端骨架 | FastAPI、配置、数据库、迁移、认证、测试框架 | 健康检查与认证测试通过；迁移可重复执行 |
| M2 后端闭环 | Radar、Source、采集、AI、Memory、通知事件 | 测试数据完成一次端到端处理；失败可定位和重试 |
| M3 前端完成 | Tauri 桌面端和 Alpha 页面 | 使用已冻结 API 完成核心用户路径 |
| M4 集成候选 | 联调、E2E、性能与安全检查 | P0/P1 缺陷清零；验收场景全部通过 |
| M5 Alpha 发布 | GitHub 仓库、文档、标签、Release | 新环境按 README 可启动；发布产物可下载运行 |

## 6. 职责边界

### 总控

- 维护范围、架构决策、依赖关系和验收标准。
- 为每个工程阶段签发任务包。
- 审查阶段产出，不在总控阶段编写业务代码。
- 阻止未通过阶段闸门的下游工作正式开工。

### Backend

- 只实现已冻结的数据模型、API 和后台任务契约。
- 提交迁移、测试、OpenAPI 产物与运行说明。

### Frontend

- 以冻结的 OpenAPI 和事件模型为唯一接口依据。
- 不复制后端业务判断，不直接操作后端数据库。

### Integration

- 负责联调、契约测试、E2E、异常路径、性能基线和缺陷回归。

### Release

- 负责仓库整理、CI、版本号、变更记录、构建产物和发布检查。

## 7. 当前状态

- 已完成：产品愿景、Alpha 范围、核心架构与后端契约初步冻结、Backend 任务包、BE-0 验收、BE-1 工程基线、本地环境复核和 BE-1 准入。
- 进行中：Backend Phase BE-1 基础骨架与本地基础设施。
- 尚未准入：BE-2 及后续 Backend Phase、Frontend、Integration、Release。
- 当前代码状态：`main` 跟踪 `origin/main`；尚无后端业务实现。

## 8. Memory 演进边界（接任总控必须遵守）

### 8.1 Alpha Memory 定义

FlowTracer 的 Memory 是核心产品能力，不是后续附加功能。Alpha 继续严格实现已经冻结的内部 Memory：

```text
Document / Analysis
      ↓
DocumentChunk + Embedding
      ↓
PostgreSQL + pgvector
      ↓
Bookmark + /memory/search
      ↓
基础知识库 UI
```

Alpha 阶段 PostgreSQL + pgvector 是唯一事实数据源（Source of Truth）。不得因为 Obsidian、Notion、Logseq 或其他外部知识工具的出现而替换、绕过或削弱现有内部 Memory 数据模型与检索契约。

### 8.2 Memory 分层模型

接任总控将 FlowTracer Memory 视为三层演进，而不是单一“知识库页面”：

```text
L1 Raw / Evidence Memory
- RawItem
- Document
- Analysis
- DocumentChunk
- Embedding

L2 Semantic / User Memory
- Bookmark
- User Notes
- Semantic Search
- Related Content
- Personal Knowledge Base

L3 Knowledge Memory（Future）
- Topic
- Entity
- Value Thread
- Research Idea
- Backlinks
- Knowledge Projection
- Agent Context
```

Alpha v0.1 仅交付 L1 + L2 所需能力；L3 仅允许设计和记录，不得越过阶段门禁提前实现。

### 8.3 Obsidian 的正式定位

Obsidian 不作为 FlowTracer 的运行时依赖，也不替代内部数据库和 Memory Engine。

正式定位为：**FlowTracer Knowledge Projection / Export Target**。

目标关系：

```text
Internet
  ↓
FlowTracer Acquisition
  ↓
Intelligence Engine
  ↓
Memory Engine
  ├─ Internal Memory → PostgreSQL + pgvector
  └─ Knowledge Projection → Markdown / Obsidian（Future）
```

原则：

- PostgreSQL + pgvector 始终保存机器可检索、可验证、可隔离的核心事实与向量数据。
- Obsidian 负责面向人的长期知识表达与整理，不保存 FlowTracer 业务状态的唯一副本。
- 第一阶段优先实现通用 `Markdown Export`，而不是直接绑定 Obsidian API 或插件。
- Obsidian-compatible 能力建立在 Markdown 之上，包括 YAML frontmatter、`[[wikilinks]]`、tags、Daily Notes、Topics、Entities、Value Threads 等。
- 任何未来 Obsidian 集成都必须通过独立 Adapter / Exporter 边界接入，不得将 Obsidian 特有逻辑渗透到 Intelligence、Ingestion、Database 等核心领域模块。

### 8.4 后续推荐演进顺序

在 Alpha v0.1 完成并通过发布门禁之后，接任总控可按以下顺序评估：

1. `KnowledgeExporter` 抽象接口。
2. 通用 `MarkdownExporter`。
3. Obsidian-compatible Markdown：双链、frontmatter、tags、Daily Notes。
4. Topics / Entities / Value Threads 等结构化知识投影。
5. Obsidian 单向导出与增量更新。
6. 在明确需求、冲突策略和安全边界后，再评估 Obsidian → FlowTracer 双向读取。
7. 最后再评估将个人知识作为 GPT/Codex 等 Agent 的 Context Source，实现长期 Agent Context。

不得将第 5–7 项提前纳入 Alpha。

### 8.5 与外部 Claude/Codex + Obsidian 项目的关系

可研究现有 Claude/Codex + Obsidian 开源项目的知识组织方式，包括 source note、实体页、双链、笔记更新策略和 Agent 检索方式，但原则上只吸收经过验证的设计思想，不直接将第三方项目作为 FlowTracer 核心 Memory 的替代品。

FlowTracer 的差异化边界保持为：

```text
外部知识工具：用户提供内容 → AI 整理和记忆
FlowTracer：主动发现内容 → AI 判断价值 → 形成情报 → 进入长期 Memory
```

因此，未来 Obsidian 集成应增强 FlowTracer 的长期知识沉淀能力，而不能改变 FlowTracer 作为“主动发现与理解信息”的核心定位。

## 9. 接任总控的变更禁令

除非重新走正式 ADR、影响分析与阶段准入流程，否则接任总控不得：

- 为接入 Obsidian 重构 Alpha 数据闭环。
- 用 Obsidian/Markdown 替代 PostgreSQL + pgvector。
- 提前实现知识图谱、Neo4j 或复杂实体关系系统。
- 在 Alpha 阶段增加 GPT/Codex/AgentOS 运行时耦合。
- 因新发现的第三方开源项目改变已冻结的 Backend Phase 交付顺序。
- 将 Knowledge Projection 与核心业务数据库做不可逆双向耦合。

任何未来 Memory / Obsidian 提案必须首先回答：是否保持 Alpha Source of Truth、是否通过 Adapter 边界、是否影响当前阶段、是否有真实用户验证。
