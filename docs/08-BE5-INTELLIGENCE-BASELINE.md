# FlowTracer Alpha v0.1 BE-5 Intelligence 契约基线

## 1. 阶段目标与边界

BE-5 将 BE-4 产生的 `RawItem` 确定性清洗为 `Document`，并针对处理时仍为 active、未删除且与 Source 绑定的 Radar 生成版本化 `Analysis`。阶段交付包括 Provider 隔离、严格结构化输出、四维评分、成本审计、失败恢复和 Intelligence 查询。

BE-5 的终点是 `Document.status = embedding`，表示内容已可交给 BE-6。不得生成向量或 `DocumentChunk`，不得创建 Notification、发送 WebSocket 事件、实现 Bookmark/Memory Search、站点深爬、多模型 Router、Agent 或知识图谱。暂停或删除的 Radar 不创建新 Analysis；已有历史产物不因资源暂停而删除。

## 2. 清洗、Document 与全局去重

- 仅处理 `status=fetched` 的 RawItem；任务以 `raw_item_id` 为业务幂等键，重复投递必须安全退出。
- 清洗是纯函数：Unicode NFC、CRLF/CR 转 LF、移除除 LF/TAB 外的 C0/C1 控制字符、行内连续空白折叠为单空格、连续空行最多保留一个、首尾 trim。不得覆盖 `raw_text`。
- 清洗后为空或超过既有 5 MiB 内容预算，RawItem 进入 `failed`，错误分别为 `empty_content` 或 `cleaned_content_too_large`；错误信息最长 500 且不包含正文。
- `Document.content_hash` 是清洗后 UTF-8 正文的 SHA-256。创建 Document 时先锁定 RawItem，再按该强哈希查找；不存在则创建，存在则复用。
- 新建 Document 的 `raw_item_id` 指向首个证据 RawItem；后续相同内容的 RawItem 标记 `duplicate`，不创建第二个 Document。首次成功建立 Document 的 RawItem 标记 `cleaned`。
- `canonical_url` 继承 RawItem；标题使用清洗后的 RawItem title，空标题回退为 canonical URL；作者仅从 `metadata.author` 读取、清洗并截断到 300 字符；语言无法可靠确定时为 null，不得调用外部检测服务。
- `word_count` 使用固定 Unicode 规则：每个 CJK Unified Ideograph 计 1；其他语言按连续字母/数字序列计 1；标点与纯空白不计。英文、中文和混合文本必须有表格测试。
- 同一 Source 的新 RawItem 完成持久化后才允许投递清洗任务。Broker 失败不得回滚采集结果；每 60 秒运行的补偿 dispatcher 使用 `FOR UPDATE SKIP LOCKED` 扫描 `fetched` RawItem 并重新投递。

## 3. Pipeline、并发与状态机

- 固定 `pipeline_version = alpha-v1`、`prompt_version = intelligence-v1`。版本变化必须由总控修订本基线；不得覆盖旧 Analysis。
- 清洗事务必须短小，不得在数据库事务或行锁内等待远程 AI。Document 新建后依次记录 `pending -> cleaning -> deduplicating -> analyzing`；清洗/去重完成后提交，再创建或认领 Analysis。
- 对处理时 active、未删除且经 `radar_sources` 绑定到该 Source 的每个 Radar，创建唯一 `(document_id, radar_id, pipeline_version)` Analysis，初始 `pending`。并发冲突以数据库唯一约束兜底，禁止通过捕获任意 IntegrityError 掩盖其他错误。
- Analysis Worker 使用条件更新或行锁完成 `pending -> running` 认领；`running`、`completed`、`failed` 的重复投递均不得再次调用 Provider。
- pending dispatcher 每 60 秒补偿提交后未投递的 Analysis。任务 soft time limit 120 秒、hard time limit 150 秒；`running` 超过 10 分钟视为失联，仅由恢复任务在加锁后重置为 `pending`。恢复和正常 Worker 的并发必须有真实 PostgreSQL 测试。
- 一个 Document 的所有目标 Analysis 进入终态后：至少一个 completed 或目标集合为空时进入 `embedding`；全部 failed 时进入 `failed`。任一 Analysis 仍 pending/running 时保持 `analyzing`。BE-5 不进入 `ready`。
- 失败 Analysis 允许所有者通过 retry Endpoint 重置为 `pending`；同版本仍复用原记录。成功 Analysis 不可重试，也不得生成第二条同版本记录。

## 4. AI Provider 与配置

业务层只依赖 `AnalysisProvider` Protocol，不导入厂商 SDK 类型。Provider 请求至少包含 Document 标题、受限正文以及 Radar 的 name、goal、categories、keywords；不得包含密码、Token、用户 profile、Source config、完整 RawItem metadata 或内部连接信息。

支持两个适配器：

- `fake`：离线、确定性，仅用于测试与显式本地开发，不访问网络，usage/cost 可预测。
- `openai_compatible`：单一远程 LLM，使用 Operator 配置的 HTTPS Base URL 和模型；不做模型 Router、自动回退或多模型竞价。测试环境可显式使用 loopback Fixture，正式配置禁止 HTTP、userinfo 和重定向。

新增 fail-fast 配置：`AI_PROVIDER`、`AI_MODEL`、`AI_BASE_URL`、`AI_API_KEY`、`AI_INPUT_COST_PER_MILLION`、`AI_OUTPUT_COST_PER_MILLION`。选择 `openai_compatible` 时全部必填，费率为非负 Decimal；Key 使用 Secret 类型并纳入日志脱敏。选择 `fake` 时不得要求真实 Key。不得把 acquisition safe fetcher 用作 AI 客户端。

远程调用 connect timeout 5 秒、read timeout 60 秒、总预算 90 秒；响应体最大 256 KiB，不跟随重定向。发送给模型的正文最多 24,000 个 Unicode 字符，Document 仍保存完整清洗正文。测试不得访问公网；真实 Provider 测试必须显式 opt-in，缺少 Key 时跳过且不属于常规门禁。

`openai_compatible` wire contract 固定为 `POST {AI_BASE_URL}/chat/completions`，Header 仅含 `Authorization: Bearer <AI_API_KEY>`、JSON Content-Type 和固定 User-Agent。请求使用 `model=AI_MODEL`、`temperature=0`、system/user messages 以及 `response_format.type=json_schema` 的 strict Schema；响应只接受 `choices[0].message.content` 中的 JSON 字符串。该内容路径缺失或类型错误时按 `ai_invalid_output` 处理；`usage.prompt_tokens`、`usage.completion_tokens`、`usage.total_tokens` 若存在必须是非负整数，缺失时按 0 记录。不得记录原始响应。

## 5. Prompt 与严格输出 Schema

模型输出必须是单一 JSON Object，UTF-8 解码，禁止 Markdown fence、前后附加文本、NaN/Infinity 和未知字段：

```json
{
  "summary": "1..2000 characters",
  "category": "1..120 characters",
  "relevance": 0,
  "importance": 0,
  "novelty": 0,
  "impact": 0,
  "reason": "1..1000 characters"
}
```

四个分数必须是 JSON integer 且范围 0..100，bool 不视为 integer。若 Radar.categories 非空，category 必须等于其中一项或 `other`；为空时允许任意非空安全分类。summary、category、reason 均 trim 并禁止控制字符。`radar_score` 与 `recommendation` 不接受模型输入，必须由服务端计算。

每次 Analysis 最多 3 次 Provider 调用（首次加最多 2 次重试）。超时、429、5xx 和临时网络错误可在总预算内按 2/4 秒退避；认证、权限、无效配置和其他确定性 4xx 不重试。结构化输出失败允许一次带原始校验错误摘要的 repair 调用，且仍计入 3 次总调用上限；repair 后仍无效则失败。Prompt、模型输入、模型原始输出和正文禁止写日志。

## 6. 评分、推荐与阈值

- 四维分均为 0..100 整数。
- 使用 Decimal 计算：`relevance * 0.40 + importance * 0.25 + novelty * 0.20 + impact * 0.15`，最终按 ROUND_HALF_UP 保留两位小数后写入 `numeric(5,2)`。
- Recommendation：`score >= 85` 为 `must_read`；`>= 70` 为 `read`；`>= 50` 为 `monitor`；其余为 `archive`。
- `score >= radar.notification_threshold` 的判定必须实现为独立纯函数并覆盖 0、49.99、50、69.99、70、84.99、85、100 及阈值相等边界。BE-5 只验证资格，不创建 Notification；BE-7 复用该函数。

## 7. Usage、错误与观测

- 每次实际 Provider 调用各写一条 `AIUsageRecord`，`task_type=analysis`；成功和失败均记录 user、Analysis、provider、model、耗时、成功状态和安全错误码。Token 缺失时记 0，不得伪造。Usage 必须在独立短事务中持久化，Analysis 失败不得回滚已经发生的调用审计。
- `total_tokens` 必须等于 provider 明确返回值；若只返回 input/output，则本地求和。估算成本为 `(input_tokens * input_rate + output_tokens * output_rate) / 1_000_000`，Decimal ROUND_HALF_UP 到 6 位；Fake Provider 默认费率和成本为 0。
- 稳定错误码：`cleaning_failed`、`cleaned_content_too_large`、`ai_timeout`、`ai_rate_limited`、`ai_provider_unavailable`、`ai_auth_failed`、`ai_invalid_output`、`ai_response_too_large`、`analysis_queue_unavailable`、`internal_analysis_error`。
- 客户端错误和持久化 `error_message` 最长 500；不得包含 API Key、Authorization、Base URL query、Prompt、正文、模型原始输出、连接串或 traceback。
- 日志必须包含 correlation_id、raw_item_id、document_id、analysis_id、radar_id、provider、model、attempt、duration_ms 和终态；不得包含秘密或内容。

## 8. REST 契约

全部 Endpoint 位于 `/api/v1`，要求 Bearer Token、统一错误 Envelope、严格 Schema 和所有权隔离。

- `GET /intelligence?page=1&page_size=20&radar_id=&status=&recommendation=&category=&min_score=`：按 `created_at DESC, id DESC` 稳定分页；只返回当前用户 Radar 的 Analysis。`min_score` 为 0..100 Decimal。
- `GET /intelligence/{analysis_id}`：跨用户、已删除 Radar 与不存在统一 `404 resource_not_found`。
- `POST /analyses/{analysis_id}/retry`：failed 重置为 pending 并返回 `202` 与 `{analysis_id,status}`；pending/running 重放返回同一对象与 `202`；completed 返回 `409 analysis_not_retryable`。提交后再投递，Broker 失败仍保留 pending 并返回 `503 analysis_queue_unavailable`，由 dispatcher 补偿。

列表项返回 Analysis 标识、Document/Radar 标识、标题、canonical URL、summary、category、四维分、radar_score、recommendation、reason、status、error_code/error_message、pipeline/prompt/provider/model 与时间戳，不返回 Document content。详情在上述字段之外返回完整清洗 `content`、author、language、word_count；不得返回 raw_text、Prompt、原始模型输出、Token 或成本明细。

## 9. 测试与验收

- Fake Provider 固定输入必须确定性生成 Document、Analysis 和 Usage；全流程不得访问公网。
- 覆盖清洗表格、空内容、5 MiB 边界、英文/中文/混合 word_count、全局内容去重、不同 Source/Radar、暂停/删除 Radar 和跨用户隔离。
- 覆盖并发 RawItem、重复 Celery 投递、并发 Analysis 创建、dispatcher 补偿、失联 running 恢复、手动 retry 和同版本唯一性；使用真实 PostgreSQL/Redis/Celery 证明。
- 覆盖严格 JSON、未知字段、bool/浮点分数、NaN/Infinity、超长字符串、超大响应、timeout、429、4xx、5xx、repair 与 3 次总预算。
- 覆盖评分 Decimal 精度、ROUND_HALF_UP、Recommendation 全边界、通知阈值纯函数及成本 6 位舍入。
- API/OpenAPI 覆盖认证、分页、筛选、稳定排序、所有权、404/409/422/503 和响应不泄密。
- 无新迁移为预期；若实现发现现有 Schema 无法满足契约，必须停点提交 ADR，不得擅自迁移。
- `uv sync --locked`、Ruff、格式、Mypy、Pytest（总覆盖率不低于 85%）、Alembic 零漂移、Compose config、live/ready、无 Beat Worker、Celery pong 和真实 Fake Provider 任务均通过；API/Worker 同镜像且非 root。

Backend 完成后提交阶段报告并停点。不得自行合并或进入 BE-6。
