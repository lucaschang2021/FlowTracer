# FlowTracer Alpha v0.1 BE-4 采集契约基线

## 1. 阶段目标与边界

BE-4 建立 RSS 与单页 URL 的受控采集链路：API 创建运行记录，Celery 调度和执行，结果保存为 `RawItem`。本阶段不创建 `Document`，不做正文清洗、AI、Embedding、通知、WebSocket、手动运行重试接口或站点级爬取；这些仍属于后续 Phase。

支持 `SourceType.rss` 与 `SourceType.url`；`api` 继续返回 `unsupported_source_type`。只有当前用户拥有、未删除且 `active` 的 Source 可创建或调度运行。暂停 Source 返回 `409 source_not_active`；不存在、已删除或跨用户访问统一返回 `404 resource_not_found`。

## 2. REST 契约

全部 Endpoint 位于 `/api/v1`，要求 Bearer Token、严格 Schema、统一错误 Envelope，并显式限定 Source 所有者。

### 2.1 手动采集

`POST /sources/{source_id}/collect`

- 可选 Header `Idempotency-Key`：trim 后 1..128 个可打印 ASCII 字符，不允许空白控制字符。
- 首次创建返回 `202`、`Location: /api/v1/collection-runs/{run_id}`，响应 `{run_id, status}`，初始状态为 `queued`。
- 相同用户、Source 和 Key 重放返回同一运行与 `202`；不同 Source 可复用同一 Key。未提供 Key 时每次创建新运行。
- 运行记录必须先提交，再投递 Celery。Broker 投递失败返回 `503 collection_queue_unavailable`，运行保持 `queued` 并记录安全化 `queue_unavailable`；周期性 dispatcher 必须补偿投递失败或提交后进程中断遗留的 queued 运行，成功投递后清除该临时错误。

### 2.2 运行查询

- `GET /sources/{source_id}/runs?page=1&page_size=20&status=&trigger_type=`
- `GET /collection-runs/{run_id}`
- `GET /collection-runs/{run_id}/items?page=1&page_size=20&status=`

分页上限 100，统一按 `created_at DESC, id DESC` 稳定排序。跨用户与不存在统一 404。

`CollectionRunResponse`：`{id, source_id, trigger_type, status, started_at, finished_at, fetched_count, created_count, duplicate_count, failed_count, error_code, error_message, created_at, updated_at}`。

`RawItemResponse`：`{id, source_id, collection_run_id, external_id, canonical_url, title, published_at, fetched_at, content_type, content_hash, metadata, status, error_code, error_message, created_at, updated_at}`。公开响应不返回 `raw_text`。

## 3. 调度与并发

- Celery Beat 每 60 秒触发 scheduler。可调度条件：Source `active`、未删除，且 `next_fetch_at IS NULL OR next_fetch_at <= now()`。
- scheduler 使用 `FOR UPDATE SKIP LOCKED` 分批认领；调度幂等键为 `schedule:<UTC minute bucket>`，依赖既有 `(source_id, idempotency_key)` 唯一索引防止重复运行。
- 创建 scheduled run 时将 `next_fetch_at` 更新为当前 UTC 时间加 `poll_interval_minutes`；成功或部分成功完成时更新 `last_fetched_at`。
- worker 以条件更新/行锁将 `queued -> running`；已处于终态或已被其他 worker 认领时直接幂等退出。
- 终态：全成功为 `succeeded`；至少一项成功且至少一项失败为 `partial`；没有可保存项且发生采集/解析错误为 `failed`。所有计数不得为负且必须与本次处理结果一致。

## 4. 网络安全契约

所有网络访问统一经过安全 fetcher；Scrapling 只解析已经由安全 fetcher 获取的字节，不得自行访问 URL。

- 仅允许 `http`/`https`，Alpha 仅允许目标端口 80/443；禁止 userinfo。
- 每次请求及每次重定向前解析全部 A/AAAA；任一结果不是全局可路由地址即拒绝。必须覆盖 loopback、private、link-local、multicast、reserved、unspecified、IPv6 site-local、云元数据地址及元数据主机名。
- 验证后的 IP 必须绑定到实际连接，同时保留原 Host/SNI，防止 DNS rebinding；禁止代理继承环境变量。
- 最多 5 次重定向；Location 必须重新执行协议、端口、DNS 和地址校验。
- connect timeout 5 秒、read timeout 15 秒、总预算 30 秒；解压后的响应体最大 5 MiB，流式读取并在超限时立即中止。
- RSS 仅接受 `application/rss+xml`、`application/atom+xml`、`application/xml`、`text/xml`；URL 仅接受 `text/html`、`application/xhtml+xml`。忽略 Content-Type 参数并大小写不敏感比较。
- 固定、可识别的 FlowTracer Alpha User-Agent；不得携带用户 Cookie、Authorization 或 Source config 中的秘密。

确定性错误不重试：非法 URL、SSRF、端口、Content-Type、响应过大、无效 Feed/HTML。瞬时 DNS、连接、超时、HTTP 408/429/5xx 最多重试 3 次，退避 2/4/8 秒；HTTP 4xx（408/429 除外）不重试。

## 5. RSS、HTML 与 RawItem

- RSS/Atom 每个 entry 生成候选 RawItem。`external_id` 优先使用非空 guid/id，否则使用规范化绝对链接；二者均缺失时使用内容 SHA-256 派生的稳定 ID。
- 单页 URL 每次成功获取生成一个候选 RawItem，`external_id` 使用 Source 的 `normalized_url`。
- 相对链接以最终响应 URL 解析；Canonical URL 仅允许绝对 HTTP(S)，移除 fragment，并复用 BE-3 确定性规范化规则。
- `raw_text` 保存采集到的 entry 内容或页面可读文本；统一 Unicode NFC、换行符为 LF、首尾 trim 后计算 SHA-256。空内容记为项目失败，不创建 RawItem。
- HTML 移除 script/style/noscript/template、事件属性和可执行内容；BE-4 只做安全提取，不做 BE-5 的语义清洗。
- `metadata` 只保存 JSON 安全的非秘密字段，最大 16 KiB；不得保存完整响应头、Cookie、Token 或未经限制的 HTML。

去重顺序为 `source_id + external_id`、`source_id + canonical_url`、`source_id + content_hash`。并发写入必须以每 Source 的事务锁或等效数据库机制串行化；已存在则不新增 RawItem，增加 `duplicate_count`。不得创建 Document。

## 6. 错误与观测

允许的稳定错误码：`ssrf_blocked`、`dns_resolution_failed`、`unsupported_port`、`unsupported_content_type`、`response_too_large`、`request_timeout`、`http_error`、`invalid_feed`、`extraction_failed`、`empty_content`、`queue_unavailable`、`internal_collection_error`。

`error_message` 最长 500，只包含安全化摘要；日志不得输出完整 URL query、正文、Source config、DNS 答案全集、Token、连接串或 traceback 给客户端。日志必须带 `request_id`、`correlation_id`、`run_id`、`source_id` 和 Celery task id；指标至少记录运行终态、耗时、计数、重试次数和错误码。

## 7. 测试与验收

- 测试不得访问公网；网络层使用注入式 resolver/transport、本地 Fixture 或 Mock。
- 覆盖每类保留地址、混合公网/私网 DNS、DNS rebinding、逐跳重定向、端口、超时、大小、压缩后大小、Content-Type 和秘密脱敏。
- 覆盖 RSS/Atom、相对链接、缺失 ID、畸形 Feed、HTML 安全提取、空内容、字符编码与 5 MiB 边界。
- 覆盖手动 Key 重放、并发相同 Key、scheduler 多实例、worker 重复投递、状态机、计数、所有权、分页和三层去重。
- 真实 PostgreSQL/Redis/Celery 集成验证；API 与 Worker 同镜像且非 root。迁移（若有）必须完成空库 upgrade、downgrade、再次 upgrade 与 Alembic 零漂移。
- `uv sync --locked`、Ruff、格式、Mypy、Pytest（总覆盖率不低于 85%）、Compose config、live/ready 和 Celery 探活全部通过。

Backend 完成后提交阶段报告并停点。不得自行合并或进入 BE-5。
