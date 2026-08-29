# FlowTracer ACQ-1 Acquisition Contract

状态：Frozen；WP-1 精确值域与 Profile v1 Schema 由 `docs/32-ACQ1-WP1-CONTRACT-ADDENDUM.md` 补充

版本：`acquisition-v1`

## 1. Universal Source Contract

### Source 稳定字段

在保留现有字段基础上新增：

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `source_family` | varchar(32) + CHECK | 九类 Source Family；legacy 默认 `generic_web` |
| `acquisition_mode` | varchar(16) + CHECK | `auto | native | dynamic | advanced`；默认 `auto` |
| `discovery_mode` | varchar(24) + CHECK | `single_page | same_path | same_domain | approved_domains` |
| `profile_version` | varchar(40) | 固定版本标识，初始 `acq-source-v1` |
| `acquisition_profile` | JSONB | 严格 Schema、最大 16 KiB、非秘密配置 |

现有 `config` 在兼容窗口内继续返回；ACQ-1 Profile 写入新字段。Profile 必须 `extra=forbid`，禁止 NaN/Infinity、控制字符、任意 Header、Cookie、Authorization、Token、密码、代理凭据或 Browser 启动参数。

ACQ-1 不支持 per-source 登录凭据。Operator 级 proxy/provider secret 只能来自 Secret 配置或部署 Secret，不进入 Source 表、公开 API、日志或事件。

### Profile v1

```text
content_profile
change_detection
priority
resource_budget
site_policy
approved_domains
family_options
```

Profile 只保存声明式业务配置，不保存计数、健康、熔断、租约、checkpoint 或历史决策。

ACQ-1 新增、预期继续演进的枚举在数据库中统一使用 `varchar + named CHECK`，在 Pydantic/OpenAPI 中使用严格 enum；不新增 PostgreSQL enum。唯一例外是既有 `radar_type`，其 `opportunity` 值必须按现有 PostgreSQL enum 迁移。该策略保证新 Profile/Backend/Health 值可用可逆迁移演进。

Profile v1 固定默认值：

```text
content_profile: generic
priority: normal                 # low | normal | high
allow_browser: false
change_detection:
  enabled: true
  materiality_threshold: 0.1500
  semantic_enabled: false
resource_budget:
  max_requests: 10
  max_pages: 1
  max_depth: 0
  max_duration_seconds: 120
  max_concurrency: 1
  max_browser_pages: 0
  max_retries_per_target: 2
  max_total_bytes: 5242880
approved_domains: []
family_options: {}
```

所有数值使用严格整数/Decimal 边界；legacy backfill 使用以上默认，确保不会因迁移自动启用 Browser 或 Discovery。

### SourceAcquisitionState

一 Source 一行：

```text
source_id PK/FK
health_status
success_count / failure_count / consecutive_failures
latency_ewma_ms / quality_ewma
last_backend / last_error_code
circuit_open_until
last_success_at / last_failure_at
checkpoint JSONB
version
updated_at
```

运行更新使用行锁或版本 CAS。`checkpoint` 最大 32 KiB，不含正文、URL 列表全集或秘密。

## 2. Backend Boundary

业务层只依赖：

```text
AcquisitionBackend.acquire(request, context) -> AcquisitionResult
```

### AcquisitionRequest

```text
source_id
run_id
target_url
source_family
mode
content_profile
site_policy
network_policy
remaining_budget
correlation_id
```

### AcquisitionResult

```text
requested_url
final_url
status_code
content_type
title
text
normalized_content
safe_metadata
links
fetched_at
backend
duration_ms
retry_count
pages
bytes_received
quality
evidence
```

正文/HTML 仅在受控内部对象中传递，不进入日志、公开 CollectionRun 或 Router trace。`safe_metadata` 使用 allowlist；`links` 已规范化、去 fragment、去重并受数量/长度限制。

### Backend 名称

```text
rss | native_http | scrapling_http | dynamic_browser | advanced_browser
```

`advanced_browser` 仅表示同一安全边界内的更完整标准浏览器能力，不表示反访问控制或隐匿绕过。

## 3. AcquisitionAttempt

每个实际 Backend 调用形成一条不可变 attempt：

```text
id, run_id, source_id, ordinal
backend, started_at, finished_at, status
requested_url, final_url_host
status_code, content_type
duration_ms, retry_count, pages, bytes_received
quality_score, fallback_reason
budget_used JSONB
error_code, safe_error
decision_version
```

唯一约束：`(run_id, ordinal)`。不存 raw HTML、正文、完整 DNS 答案、Cookie、Header、Token、selector 或 Browser trace。

## 4. Router

Router 版本：`acquisition-router-v1`。

顺序：

1. RSS Source 先使用 RSS Backend。
2. `native` 只允许 Native；失败后安全终止。
3. `auto` 先 Native，质量不足且预算允许时升级 Dynamic；Advanced 必须由 Profile 明确允许。
4. `dynamic` 直接进入隔离 Dynamic Browser，但仍执行 probe、SitePolicy 与预算校验。
5. `advanced` 仅允许已批准 Profile；访问控制信号立即停止，不继续升级。

决策输入：family、历史 Backend/成功率、响应状态/类型、正文长度、文本密度、标题/日期、JS shell、导航噪声、质量、延迟、连续失败、优先级和剩余预算。

Router 输出只记录安全摘要：selected backend、reason code、quality bucket、budget bucket、fallback count、decision version。不得记录正文、selector 或秘密。

### 固定停止信号

```text
access_control_detected
robots_disallowed
site_policy_denied
network_policy_denied
budget_exhausted
unsupported_content
captcha_detected
login_required
payment_required
```

以上均不可通过 Advanced 自动绕过。

## 5. Content Quality

质量版本：`extraction-quality-v1`，0.00–1.00，Decimal `ROUND_HALF_UP` 四位。

```text
0.30 meaningful_text
0.15 text_density
0.10 title
0.10 publish_date
0.05 author
0.10 canonical
0.10 navigation_noise_inverse
0.10 js_shell_inverse
```

缺失字段得 0；不可确定的数据保持缺失。接受阈值默认 `0.60`，Router 升级阈值默认 `<0.45`；0.45–0.59 可按 family/profile 明确决定接受或升级。Profile 只能在冻结范围内调整阈值，不能关闭安全校验。

## 6. Adaptive Extraction

- Parser 先使用稳定语义标记、结构、正文算法，再使用版本化 Profile selector。
- 自适应恢复只能在本地候选 selector/结构规则中选择，不允许向目标站点写入或执行模型生成脚本。
- 输出字段附带 `evidence_path`、`extractor_version` 与置信度；Parser 不制造作者、日期、金额、deadline 或组织。
- selector/profile 更新不自动触发公网重抓；必须由正常调度或人工运行验证。

## 7. Controlled Discovery

Scope：

```text
single_page | same_path | same_domain | approved_domains
```

每次 run 硬限制：

```text
max_depth: 0..3（默认 0）
max_pages: 1..100（默认 1）
max_duration_seconds: 5..900
max_concurrency: 1..8
max_browser_pages: 0..10
max_redirects_per_request: 5
max_retries_per_target: 2
```

预算跨 redirect、retry、fallback 和 Browser 子资源累计；任何单项耗尽即停止扩展 frontier。

`DiscoveryFrontierEntry` 保存 run、URL identity、parent、depth、priority、状态和安全 reason；`(run_id, normalized_url)` 唯一。优先级由 URL pattern、anchor text、family、content type、历史价值与重复度确定；不允许抓取所有链接。

## 8. SitePolicy

优先级：全局 deny → operator deny → robots → domain policy → Source allow。Allowlist 不能覆盖网络 deny 或访问控制。

```text
robots_mode: respect | deny_if_unavailable
crawl_delay_ms
requests_per_minute
max_parallel_requests
allowed_content_types
allow_paths / deny_paths
approved_domains
```

ACQ-1 默认尊重 robots；无法取得或解析 robots 时，Discovery 停止，single-page 手动 Source 仍须符合明确 SitePolicy。政策/学术/政府 Source 使用低侵扰默认值。

## 9. NetworkPolicy 与 Browser 隔离

### 不可绕过边界

- 只允许 HTTP(S) 80/443；禁止 userinfo、localhost、私网、link-local、multicast、reserved、unspecified、metadata host/IP 和危险端口。
- DNS 每次解析验证全部 A/AAAA；redirect 每跳重验；Native 保留已验证 IP 与 Host/SNI 绑定。
- Browser 运行于独立非 root 镜像与专用 Celery queue。其网络命名空间只能连接受控 egress proxy、Redis 与必要内部服务，不可直连 Internet、host network 或 Docker socket。
- Egress proxy 负责 DNS 与目标 IP/端口校验；Browser 进程不得访问系统 DNS。应用层拦截每个 navigation、redirect、iframe、script、XHR/fetch、WebSocket、下载与 popup，并执行 scope/SitePolicy/预算。
- 下载默认拒绝；WebSocket 默认拒绝，只有 Profile 与 SitePolicy 同时允许时才经 proxy 建连。
- 任一子资源无法证明经过策略时，Dynamic/Advanced 阶段验收失败。

### Browser 资源

- 独立镜像 digest、Python package、Browser revision 与系统依赖必须锁定。
- queue 专用；prefetch=1；默认 concurrency=1，最大 2。
- 单页、单 run、单 worker 均有 wall clock、CPU、memory、PID、临时磁盘和 popup 上限。
- read-only rootfs、tmpfs、no-new-privileges、seccomp、cap_drop、无特权模式。
- Browser crash/OOM 只失败当前 attempt，不得拖死普通 API/worker。

## 10. Version Evidence

### SourceArtifact

来源内稳定身份：`(source_id, artifact_key)` 唯一；保存 canonical URL、first/last seen、removed_at 与安全 metadata。

### AcquisitionSnapshot

保存 artifact、run、版本序号、正文证据、metadata、结构摘要、三个 SHA-256 指纹、提取版本、质量与 fetched_at。`(artifact_id, version)` 唯一，指纹组合在 artifact 内唯一。

### ChangeEvent

保存 artifact、run、previous/current snapshot、change type、materiality、bounded field diff、evidence refs 与 detector version。`(run_id, artifact_id)` 唯一。

指纹：

- content：NFC、换行/空白规范化、正文噪声区移除后的 SHA-256；
- metadata：字段 allowlist、UTC 时间、稳定 key 排序后的 SHA-256；
- structure：语义块标签/层级/附件 identity 的稳定序列 SHA-256，不保存完整 DOM。

导航、广告、动态时间戳、随机 ID 和 tracking query 默认属于噪声。`removed` 需要至少两个成功观测周期缺失，或权威 404/410 且 SitePolicy 允许确认；访问失败不等于 removed。

RawItem 仅由 qualifying Snapshot 创建，并以 `snapshot_id` 唯一。`metadata_changed`、`structure_changed` 默认只保留 ChangeEvent；可由 Profile 明确升级为 RawItem。`unchanged` 不生成 RawItem。

Semantic Change 使用独立 `semantic-change-v1` Prompt/Schema，只在 Source priority=high、确定性 materiality ≥0.3000、old/new Snapshot 均存在且 Source AI 预算允许时触发。它复用已配置的单一 Analysis Provider 与 AIUsageRecord，不引入模型 Router；调用发生在事务外，失败不回滚 Snapshot/ChangeEvent。输出只允许 bounded `summary`、`changed_fields[]` 与 `importance 0..100`，必须引用 snapshot IDs，不能改写确定性 change type。

## 11. Reliability

- Retry：只重试临时网络/5xx/429，指数退避 2/4 秒并受总预算限制；确定性错误不重试。
- Circuit：按 Source+Backend 维护；连续 5 次临时失败打开 15 分钟，半开只允许一个 probe；成功关闭。
- Lease：running run 默认 10 分钟租约，每 60 秒 heartbeat；超过租约由 dispatcher `FOR UPDATE SKIP LOCKED` 恢复 queued，最多 3 次 claim。
- AutoThrottle：基于 domain latency、429/503 与 SitePolicy 调整，永不突破配置上限。
- Pool：Native session 与 Browser context 有界，跨用户不共享 Cookie/storage；ACQ-1 不启用登录态。

## 12. Observability

安全字段：source/run/family/backend/fallback/duration/retry/pages/quality/change/result/error/budget/decision version。禁止正文、HTML、Cookie、Token、Authorization、密码、完整 URL query、DNS 全集和用户敏感 Profile。

最低指标：acquisition success、extraction success、fallback、browser usage、latency、source failure、change detection、opportunity discovery、budget exhaustion、circuit open、stale recovery。

## 13. Schema Freeze

### sources 扩展

```text
source_family varchar(32) NOT NULL DEFAULT 'generic_web'
acquisition_mode varchar(16) NOT NULL DEFAULT 'auto'
discovery_mode varchar(24) NOT NULL DEFAULT 'single_page'
profile_version varchar(40) NOT NULL DEFAULT 'acq-source-v1'
acquisition_profile jsonb NOT NULL DEFAULT '{}'
```

四个字符串字段使用 named CHECK；Profile 由应用严格校验并由数据库限制 `jsonb_typeof(...)='object'`。既有 `config` 不删除。

### source_acquisition_states

```text
source_id uuid PK FK sources(id) ON DELETE CASCADE
health_status varchar(20) NOT NULL DEFAULT 'healthy'
success_count bigint NOT NULL DEFAULT 0 CHECK >=0
failure_count bigint NOT NULL DEFAULT 0 CHECK >=0
consecutive_failures integer NOT NULL DEFAULT 0 CHECK >=0
latency_ewma_ms integer NULL CHECK >=0
quality_ewma numeric(5,4) NULL CHECK 0..1
last_backend varchar(32) NULL
last_error_code varchar(80) NULL
circuit_open_until timestamptz NULL
last_success_at / last_failure_at timestamptz NULL
checkpoint jsonb NOT NULL DEFAULT '{}'
version integer NOT NULL DEFAULT 1 CHECK >=1
created_at / updated_at timestamptz NOT NULL
```

### collection_runs 扩展

```text
claimed_at timestamptz NULL
heartbeat_at timestamptz NULL
lease_expires_at timestamptz NULL
worker_id varchar(160) NULL
claim_token uuid NULL
claim_count integer NOT NULL DEFAULT 0 CHECK >=0
backend varchar(32) NULL
fallback_count integer NOT NULL DEFAULT 0 CHECK >=0
pages_count integer NOT NULL DEFAULT 0 CHECK >=0
duration_ms integer NULL CHECK >=0
quality_score numeric(5,4) NULL CHECK 0..1
budget_summary jsonb NOT NULL DEFAULT '{}'
```

索引：`(status, lease_expires_at)`；running 时 claim token、lease 与 worker 必须非空的 named CHECK，非 running 允许保留审计字段。

### acquisition_attempts

```text
id uuid PK
run_id uuid FK collection_runs(id) ON DELETE CASCADE
source_id uuid FK sources(id) ON DELETE RESTRICT
ordinal smallint NOT NULL CHECK >=1
backend varchar(32) NOT NULL
status varchar(20) NOT NULL
requested_url text NOT NULL
final_url text NULL
status_code smallint NULL CHECK 100..599
content_type varchar(160) NULL
started_at / finished_at timestamptz NOT NULL
duration_ms integer NOT NULL CHECK >=0
retry_count smallint NOT NULL DEFAULT 0 CHECK >=0
pages integer NOT NULL DEFAULT 0 CHECK >=0
bytes_received bigint NOT NULL DEFAULT 0 CHECK >=0
quality_score numeric(5,4) NULL CHECK 0..1
fallback_reason varchar(80) NULL
budget_used jsonb NOT NULL DEFAULT '{}'
error_code varchar(80) NULL
safe_error varchar(500) NULL
decision_version varchar(40) NOT NULL
UNIQUE(run_id, ordinal)
```

索引：`(source_id, started_at DESC)`、`(run_id, started_at)`。

### discovery_frontier_entries

```text
id uuid PK
run_id uuid FK collection_runs(id) ON DELETE CASCADE
source_id uuid FK sources(id) ON DELETE RESTRICT
parent_id uuid FK discovery_frontier_entries(id) ON DELETE SET NULL
normalized_url text NOT NULL
depth smallint NOT NULL CHECK 0..3
priority numeric(7,4) NOT NULL
status varchar(20) NOT NULL
decision_reason varchar(80) NULL
discovered_at / updated_at timestamptz NOT NULL
UNIQUE(run_id, normalized_url)
```

索引：`(run_id, status, priority DESC, id)`。

### source_artifacts

```text
id uuid PK
source_id uuid FK sources(id) ON DELETE RESTRICT
artifact_key varchar(512) NOT NULL
canonical_url text NOT NULL
first_seen_at / last_seen_at timestamptz NOT NULL
removed_at timestamptz NULL
safe_metadata jsonb NOT NULL DEFAULT '{}'
created_at / updated_at timestamptz NOT NULL
UNIQUE(source_id, artifact_key)
```

### acquisition_snapshots

```text
id uuid PK
artifact_id uuid FK source_artifacts(id) ON DELETE RESTRICT
collection_run_id uuid FK collection_runs(id) ON DELETE RESTRICT
version integer NOT NULL CHECK >=1
fetched_at timestamptz NOT NULL
title text NULL
author varchar(300) NULL
published_at timestamptz NULL
content_type varchar(160) NULL
normalized_content text NOT NULL
safe_metadata jsonb NOT NULL DEFAULT '{}'
structure_summary jsonb NOT NULL DEFAULT '{}'
content_hash / metadata_hash / structure_hash char(64) NOT NULL
extractor_version varchar(40) NOT NULL
quality_score numeric(5,4) NOT NULL CHECK 0..1
evidence jsonb NOT NULL DEFAULT '{}'
created_at timestamptz NOT NULL
UNIQUE(artifact_id, version)
UNIQUE(artifact_id, content_hash, metadata_hash, structure_hash)
```

正文沿用解码后 5 MiB 上限；metadata、structure 与 evidence 各自最大 32 KiB，由应用严格限制。

### change_events

```text
id uuid PK
artifact_id uuid FK source_artifacts(id) ON DELETE RESTRICT
collection_run_id uuid FK collection_runs(id) ON DELETE RESTRICT
previous_snapshot_id uuid FK acquisition_snapshots(id) ON DELETE RESTRICT NULL
current_snapshot_id uuid FK acquisition_snapshots(id) ON DELETE RESTRICT NULL
change_type varchar(24) NOT NULL
materiality numeric(5,4) NOT NULL CHECK 0..1
field_diff jsonb NOT NULL DEFAULT '{}'
detector_version varchar(40) NOT NULL
occurred_at timestamptz NOT NULL
created_at timestamptz NOT NULL
UNIQUE(collection_run_id, artifact_id)
```

named CHECK：created 必须 previous NULL/current 非 NULL；removed 必须 previous 非 NULL/current NULL；其余必须 previous/current 非 NULL；unchanged 允许二者相同。

### raw_items 切换

新增 nullable `snapshot_id uuid FK acquisition_snapshots(id) ON DELETE RESTRICT` 与 `UNIQUE(snapshot_id) WHERE snapshot_id IS NOT NULL`。回填完成并切换 writer 后，将 `uq_raw_items_source_external` 重建为 `snapshot_id IS NULL AND external_id IS NOT NULL` 的 legacy 部分唯一索引。`source_id`、`collection_run_id` 和 Snapshot 所属关系必须一致，由 service 校验与集成测试保证。

## 14. API 草案

兼容扩展：

- Source create/update/response 增加可选 family、mode、discovery、profile/version；legacy 默认不变。
- `GET /api/v1/sources/{id}/health`
- `GET /api/v1/collection-runs/{id}/attempts`
- `GET /api/v1/sources/{id}/changes`
- `GET /api/v1/sources/{id}/artifacts/{artifact_id}/changes`

分页沿用 `{items,page,page_size,total}`；所有权与不存在统一 404；错误沿用 ErrorEnvelope。候选新错误码：

```text
acquisition_mode_unsupported
network_policy_denied
site_policy_denied
access_control_detected
acquisition_budget_exhausted
browser_unavailable
source_circuit_open
source_profile_invalid
run_lease_exhausted
```

公开响应不返回 raw HTML、完整 Snapshot 正文、内部 selector、Router 完整 trace、Proxy/Browser 调试数据或任何秘密。
