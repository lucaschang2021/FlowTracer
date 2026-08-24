# FlowTracer Alpha v0.1 BE-3 Radar 与 Source 契约基线

- 状态：Accepted for BE-3 admission
- 适用范围：BE-3 Radar、Source 与绑定关系管理
- 变更控制：公开字段、状态码、URL 规范化、所有权或删除语义变化时，必须先由总控修订本基线或新增 ADR。

## 1. 阶段边界

BE-3 只实现 Radar、Source 与 RadarSource 的管理闭环。不得启动采集任务、访问来源 URL、解析 RSS、实现 CollectionRun/RawItem、AI、Embedding、Notification 或 WebSocket。

## 2. 通用 API 规则

- 所有路径位于 `/api/v1`，均要求有效 Bearer Access Token。
- 所有查询必须同时限定当前 `user_id` 与 `deleted_at IS NULL`；跨用户对象与不存在对象统一返回 `404 resource_not_found`，不得泄露存在性。
- 分页：`page` 默认 1、最小 1；`page_size` 默认 20、范围 1..100；响应 `{items, page, page_size, total}`。
- 列表稳定排序：默认 `created_at desc, id desc`；BE-3 不开放任意 `sort_by`。
- 时间使用带时区 UTC ISO 8601；请求/响应字段使用 `snake_case`。
- 请求模型必须拒绝未知字段；空 PATCH 返回 `422 invalid_request`。
- 写操作必须在单事务内完成；唯一约束冲突不得以先查后写作为唯一保护。
- 所有错误遵循 `{error: {code, message, details, request_id}}`。

## 3. Radar 契约

### 3.1 请求与响应

`RadarCreate`

- `name`: string，trim 后 1..120。
- `description`: string null，非 null 时 trim；空字符串规范为 null。
- `goal`: string，trim 后 1..4000。
- `radar_type`: 冻结枚举。
- `categories`: string list，默认 `[]`，每项 trim 后 1..80，最多 20 项，大小写不敏感去重并保持首次顺序。
- `keywords`: string list，默认 `[]`，每项 trim 后 1..120，最多 50 项，大小写不敏感去重并保持首次顺序。
- `notification_threshold`: integer 0..100，默认 75。

`RadarUpdate` 允许上述全部字段的可选子集，但不允许直接修改 `status`、`user_id`、时间戳或删除状态；至少提供一个字段。

`RadarResponse`

`{id, name, description, goal, radar_type, categories, keywords, status, notification_threshold, created_at, updated_at}`。不得返回 `user_id` 或 `deleted_at`。

### 3.2 Endpoint

- `POST /radars`：成功 `201`；同一用户活动 Radar 名称冲突返回 `409 radar_name_conflict`。
- `GET /radars`：成功 `200` 分页；可选过滤 `status`、`radar_type`；同字段多值不在 BE-3 范围。
- `GET /radars/{radar_id}`：成功 `200`。
- `PATCH /radars/{radar_id}`：成功 `200`；名称冲突返回 `409 radar_name_conflict`。
- `DELETE /radars/{radar_id}`：成功 `204`；设置 `deleted_at` 与 `status=archived`，物理删除该 Radar 的 RadarSource 绑定，但不删除任何 Source。
- `POST /radars/{radar_id}/pause`：`active -> paused`，成功 `200`；已 paused 幂等返回 `200`；archived 返回 `409 invalid_radar_state`。
- `POST /radars/{radar_id}/resume`：`paused -> active`，成功 `200`；已 active 幂等返回 `200`；archived 返回 `409 invalid_radar_state`。

## 4. Source 契约

### 4.1 请求与响应

`SourceCreate`

- `name`: string，trim 后 1..160。
- `source_type`: `rss | url`；请求 `api` 返回 `422 unsupported_source_type`。
- `url`: string，原始输入 trim 后 1..2048，必须是绝对 HTTP/HTTPS URL，禁止 userinfo，必须含有效主机。
- `poll_interval_minutes`: integer，最小 15、最大 10080，默认 60。
- `config`: object，默认 `{}`；BE-3 只持久化 JSON，不解释采集参数；序列化后最大 16 KiB。

`SourceUpdate` 允许 `name`、`url`、`poll_interval_minutes`、`config`；不允许修改 `source_type`、`status`、`user_id`、调度时间或删除状态；至少提供一个字段。

`SourceResponse`

`{id, name, source_type, url, normalized_url, poll_interval_minutes, status, last_fetched_at, next_fetch_at, config, created_at, updated_at}`。不得返回 `user_id` 或 `deleted_at`。

### 4.2 URL 规范化

规范化只用于身份与去重，不发起网络请求，也不替代 BE-4 SSRF 校验：

1. trim 输入；scheme 与 host 转小写；Unicode host 转 IDNA ASCII；移除 host 尾部点。
2. 仅允许 `http`、`https`；拒绝 userinfo、缺失 host 和无效端口；接受输入 fragment 但在规范化结果中移除。
3. 移除默认端口 `http:80`、`https:443`，保留其他显式端口。
4. 空 path 规范为 `/`；解析 dot segments；保留 path 大小写与尾随斜杠语义。
5. percent-encoding 使用大写十六进制；仅解码 RFC 3986 unreserved 字符。
6. Query 保留重复键，按解码前的 `(key, value)` 稳定排序；移除 fragment；空 query 不保留 `?`。
7. 生成的 `normalized_url` 最大 2048 字符。

### 4.3 Endpoint

- `POST /sources`：成功 `201`；同一用户活动 `normalized_url` 冲突返回 `409 source_url_conflict`。
- `GET /sources`：成功 `200` 分页；可选过滤 `status`、`source_type`。
- `GET /sources/{source_id}`：成功 `200`。
- `PATCH /sources/{source_id}`：成功 `200`；URL 变化时原子重算 `normalized_url`；冲突返回 `409 source_url_conflict`。
- `DELETE /sources/{source_id}`：成功 `204`；设置 `deleted_at` 与 `status=archived`，物理删除全部 RadarSource 绑定，不删除 Radar。
- Source 暂停/恢复通过 `PATCH /sources/{source_id}` 不开放；为避免绕过状态机，BE-3 新增：
  - `POST /sources/{source_id}/pause`：`active -> paused`，已 paused 幂等；archived 返回 `409 invalid_source_state`。
  - `POST /sources/{source_id}/resume`：`paused -> active`，已 active 幂等；archived 返回 `409 invalid_source_state`。

## 5. Radar 与 Source 绑定

- `POST /radars/{radar_id}/sources/{source_id}`：双方必须属于当前用户且未软删除；创建绑定成功 `204`，已存在幂等 `204`。
- `DELETE /radars/{radar_id}/sources/{source_id}`：双方必须属于当前用户且未软删除；解绑成功或绑定不存在均返回 `204`。
- 任一对象不存在或不属于当前用户统一返回 `404 resource_not_found`。
- 不允许 archived Radar 或 Source 新增绑定，返回 `409 invalid_resource_state`；paused 对象允许绑定。
- `GET /radars/{radar_id}/sources`：返回该 Radar 已绑定、未软删除的 Source 分页列表，规则与 Source 列表一致。

## 6. 事务、并发与删除要求

- Radar 名称与 Source normalized URL 冲突必须捕获明确的数据库唯一约束名，只将对应冲突映射为 409；其他 IntegrityError 不得伪装成业务冲突。
- 并发创建相同 Radar/Source 时至多一个 `201`，其余返回对应 `409`。
- 绑定依赖联合主键解决并发重复；幂等成功不得产生 500。
- 所有更新必须推进 `updated_at`；软删除后普通读取、列表、更新、状态变更和绑定均不可见。
- 删除 Radar 不得删除 Source；删除 Source 不得删除 Radar；只清理关联绑定。

## 7. OpenAPI 与错误码

新增错误码：`resource_not_found`、`radar_name_conflict`、`source_url_conflict`、`unsupported_source_type`、`invalid_radar_state`、`invalid_source_state`、`invalid_resource_state`。

OpenAPI 必须包含 Radar/Source create、update、response、分页模型，Bearer security，以及每个 Endpoint 的 401/404/409/422 统一错误响应。

## 8. BE-3 验收门槛

- BE-2 全部测试零回归，整体覆盖率不低于 85%。
- 测试覆盖字段边界、未知字段、空 PATCH、枚举、列表去重、分页边界与稳定排序。
- 测试覆盖 URL 规范化表格案例、非法协议、userinfo、fragment 移除、无效端口、超长输入和重复 normalized URL。
- 使用两个用户证明所有 GET/PATCH/DELETE/状态/绑定接口无跨用户访问或存在性泄露。
- 测试软删除、Radar/Source 删除不误删、绑定幂等、并发唯一冲突和状态转换。
- OpenAPI 与本基线一致；日志与错误不得包含 Access Token、完整配置或数据库异常细节。
- `uv sync --locked`、Ruff、格式、Mypy、Pytest、Alembic check、Compose config 全部通过。
