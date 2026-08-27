# FlowTracer Alpha v0.1 BE-6 Vector Memory 契约基线

## 1. 阶段目标与边界

BE-6 将 `status=embedding` 的 Document 确定性切块，通过独立 Embedding Provider 生成 1536 维向量并写入 PostgreSQL + pgvector；随后将 Document 置为 `ready`，开放 Bookmark 与 Memory Search。BE-5 的 `GET /intelligence` 和详情继续作为 Alpha Feed，不新增重复 Feed Endpoint。

本阶段不得创建 Notification、发送 WebSocket 事件、实现 CollectionRun retry、站点深爬、知识图谱、外部知识库同步、多模型 Router 或 Agent。BE-7、Frontend、Integration、Release 仍未准入。

## 2. 切块、幂等与 Document 状态

- 只处理 `Document.status=embedding`；任务业务键为 `document_id + embedding_model`，重复投递必须安全。
- 切块输入只使用已清洗的 `Document.content`。默认按 Unicode code point 形成 1200 字符窗口、200 字符重叠；配置范围为 size 256..4000、overlap 0..size-1。不得按 UTF-8 字节中途截断，空块不得持久化。
- `chunk_index` 从 0 连续递增；相同 Document、顺序和模型必须得到相同内容。模型或切块配置变化不得混用旧结果：同一模型的既有完整集合可复用；不完整或内容不一致的集合必须在 Document 级锁内整体替换。
- 远程调用前后使用短事务；不得在数据库事务或行锁内等待 Provider。可使用 PostgreSQL session advisory lock 串行化同一 Document 的 Worker，但必须在 `finally` 释放，连接异常时由 PostgreSQL自动释放。
- Provider 成功且全部 Chunk 原子写入后，Document 进入 `ready` 并清除错误；失败进入 `failed`，保存安全错误码/信息。崩溃导致的 `embedding` 遗留由每 60 秒 dispatcher 重投。
- 并发、重复投递和 Worker 崩溃不得留下部分 Chunk；数据库唯一约束作为最终幂等防线。BE-6 不新增人工 embedding retry Endpoint。

## 3. Embedding Provider 与安全边界

业务层只依赖 `EmbeddingProvider` Protocol，不导入厂商 SDK类型。支持：

- `fake`：离线、确定性生成经 L2 归一化的 1536 维向量；固定输入结果稳定，用于常规测试。
- `openai_compatible`：`POST {EMBEDDING_BASE_URL}/embeddings`，单一 Operator 配置模型，不做 Router、自动回退或公网常规测试。

新增 fail-fast 配置：`EMBEDDING_PROVIDER`、`EMBEDDING_MODEL`、`EMBEDDING_BASE_URL`、`EMBEDDING_API_KEY`、`EMBEDDING_INPUT_COST_PER_MILLION`、`EMBEDDING_CHUNK_SIZE`、`EMBEDDING_CHUNK_OVERLAP`。维度固定为 1536，不提供可变配置。远程模式只允许安全 HTTPS URL；test 环境可用显式 loopback Fixture；禁止 userinfo、query、fragment 和重定向。

- 每批最多 16 个 Chunk；connect timeout 5 秒、read timeout 60 秒、总预算 90 秒；最多 3 次真实调用，临时网络错误、429、5xx 按 2/4 秒退避，确定性错误不重试。
- 请求只含 Chunk 文本、模型和固定 dimensions；不得发送用户 profile、Radar、Source config、Token 或连接信息。正文、查询和向量不得写日志。
- 显式请求 `Accept-Encoding: identity`；非 identity 编码在读取前拒绝；响应使用 raw streaming，解码前硬上限 2 MiB，并验证 Content-Length。
- 响应 `data` 数量和 index 必须与输入一一对应；每个向量恰为 1536 个有限 JSON number，拒绝 bool、NaN、Infinity、零范数和绝对值大于 1,000,000 的分量。入库前以 float32 表示并 L2 归一化。
- 每次真实调用写 `AIUsageRecord(analysis_id=null)`：索引调用使用 `task_type=embedding`，用户归属为 Document 首个证据 RawItem 的 Source owner；查询调用使用 `task_type=memory_search`，用户归属为请求者。成功、失败、Token、耗时、Provider/Model、六位 Decimal 成本均审计；秘密与内容不入库。

稳定错误码：`embedding_timeout`、`embedding_rate_limited`、`embedding_provider_unavailable`、`embedding_auth_failed`、`embedding_invalid_output`、`embedding_response_too_large`、`embedding_queue_unavailable`、`embedding_failed`。

## 4. pgvector 与检索规则

- 新迁移只为 `document_chunks.embedding` 创建 HNSW cosine 索引：`vector_cosine_ops`，`m=16`、`ef_construction=64`；不得修改 1536 维列、既有实体语义或引入第二向量数据库。
- 检索使用 cosine distance `<=>`；响应 `similarity = max(0, 1 - distance)`，ROUND_HALF_UP 保留 6 位。排序固定为 similarity DESC、Analysis.created_at DESC、Analysis.id DESC。
- 默认 `top_k=10`，允许 1..50。查询字符串 trim 后 1..4000 字符；查询向量同样通过 Provider 生成，但不持久化为 Chunk。
- 每条结果以 Analysis 为单位，返回 `analysis_id`、`document_id`、`radar_id`、标题、canonical URL、summary、category、radar_score、recommendation、matched chunk excerpt、similarity 和时间；同一 Document 在不同 Radar 的 Analysis 可分别出现。不得返回完整正文、原始 RawItem、完整向量或内部距离。
- 可过滤 `radar_id`、`date_from`、`date_to` 与 `bookmarked_only`。日期字段固定为 `COALESCE(raw_items.published_at, documents.created_at)`，区间含端点；`date_from > date_to` 返回 422。

## 5. 所有权与 Bookmark 语义

- 普通可访问内容必须存在当前用户拥有、未软删除 Radar 下的 `completed` Analysis；所有权过滤必须在数据库查询中完成，禁止先取向量结果再在 Python 过滤。
- Bookmark 是用户对 Document 的持久个人知识库授权。创建时必须能通过上述 Radar 规则访问 Document；创建后即使 Radar 暂停、解绑或软删除，Bookmark 仍保留，且该用户仍可在 Bookmark 列表和 Memory Search 访问该 Document。删除 Bookmark 后不再具有该额外授权。
- `bookmarked_only=true` 只检索当前用户 Bookmark；默认检索“当前 Radar 可访问内容 ∪ 当前用户 Bookmark”。传入 `radar_id` 时必须验证 Radar 所有权并仅返回该 Radar 的 completed Analysis，Bookmark 不绕过该过滤。
- 跨用户、无权限和不存在统一返回 `404 resource_not_found`；响应和日志不得暴露其他用户的 Document、Chunk、Bookmark 或相似度信息。

## 6. REST 契约

全部 Endpoint 位于 `/api/v1`，要求 Bearer Token、严格 Schema、统一 Error Envelope 和 OpenAPI 声明。

- `POST /bookmarks`：Body `{document_id, note?}`；note 为 null 或 trim 后 0..4000 字符。首次创建返回 201；重复或并发重复返回 409 `bookmark_exists`。
- `GET /bookmarks?page=1&page_size=20`：page >=1、page_size 1..100；按 `created_at DESC, id DESC`，返回 Bookmark、Document 摘要字段及用户可用的最新 completed Analysis 摘要，不返回正文。
- `PATCH /bookmarks/{bookmark_id}`：严格 Body `{note}`，允许 null 清空；返回更新对象。
- `DELETE /bookmarks/{bookmark_id}`：204；他人或不存在对象统一 404，不泄露存在性。
- `POST /memory/search`：Body `{query, top_k=10, radar_id?, date_from?, date_to?, bookmarked_only=false}`；返回 `{items, query, top_k}`。Provider 暂不可用返回 503；非法参数或 Provider 确定性输出错误返回安全 422/502，不回显查询或向量。

`GET /intelligence` 与详情增加只读 `bookmarked: boolean`，不改变既有字段、分页或 Feed 排序。

## 7. 测试、迁移与验收

- 表格覆盖精确窗口、重叠、Unicode/CJK、短文、空内容、边界配置、连续索引与重复切块；真实 PostgreSQL 覆盖并发、重复投递、原子替换和状态机。
- Fake Provider 覆盖确定性、维度、归一化、批次顺序；远程适配器覆盖 raw 上限、压缩响应、timeout/429/4xx/5xx、非法 index/count、NaN/Infinity/零向量和秘密脱敏，测试不得访问公网。
- 迁移必须在空库及 BE-5 基准库执行 upgrade、downgrade、再次 upgrade；`alembic check` 零漂移，并核对 HNSW index 定义。downgrade 只移除本阶段索引。
- 检索覆盖 Top-K 1/10/50/51、稳定排序、Radar/日期/Bookmark 过滤、相同 Document 多 Radar、无结果、相似度边界以及 SQL 级跨用户隔离。
- Bookmark 覆盖创建/并发冲突、列表、note 更新/清空、删除、Radar 暂停/解绑/软删除后的持久授权和删除 Bookmark 后权限撤销。
- 最终候选执行 uv locked sync、Ruff、format、Mypy、Pytest（总覆盖率不低于 85%）、迁移循环、Alembic 零漂移、Compose config、live/ready、无 Beat Worker、Celery pong 与真实 Fake embedding task；API/Worker 同镜像且非 root。

Backend 完成后必须 commit、push、创建 PR，直接向总控提交报告并停点。不得自行合并或进入 BE-7。
