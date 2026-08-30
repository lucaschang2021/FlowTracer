# FlowTracer ACQ-1 WP-1 Contract Addendum

状态：控制提交合并到 `main` 后生效

版本：`acq-source-v1`

适用阶段：WP-1 / ACQ-1A + H0

目的：补齐 `docs/23-ACQ1-ACQUISITION-CONTRACT.md` 中实现数据库 CHECK、严格 Pydantic/OpenAPI Schema 与安全策略合并所需的精确值域。本文与 ADR-027 优先解释 WP-1；未在本文列出的字段和值一律不属于 v1。

## 1. 冻结枚举

### SourceFamily

```text
policy | academic | finance | corporate | technology
community | event | opportunity | generic_web
```

数据库：`varchar(32)`，named CHECK `ck_sources_source_family`。Legacy 默认 `generic_web`。

### AcquisitionMode / DiscoveryMode

```text
acquisition_mode: auto | native | dynamic | advanced
discovery_mode: single_page | same_path | same_domain | approved_domains
```

数据库 CHECK：`ck_sources_acquisition_mode`、`ck_sources_discovery_mode`。WP-1 只执行 `auto/native` 的 Native 安全接入点；`dynamic/advanced` 仅保存兼容值，不准启动 Browser。`same_path/same_domain/approved_domains` 仅保存声明，不准在 WP-1 执行 Discovery。

### ContentProfile / Priority

```text
content_profile: generic | article | document | feed | listing | event | opportunity
priority: low | normal | high
```

### SourceHealthStatus

```text
healthy | degraded | unhealthy | circuit_open
```

数据库：`varchar(20)`，named CHECK `ck_source_acquisition_states_health_status`，默认 `healthy`。

- 成功终态将 `consecutive_failures` 归零并恢复 `healthy`，但当前仍存在未到期 circuit 时保持 `circuit_open`。
- 1..4 次连续临时失败为 `degraded`；达到 5 次为 `unhealthy`。
- `circuit_open_until > now()` 时为 `circuit_open`；到期等待 probe 时回到 `degraded`。Circuit 的自动开/半开执行保留至 WP-4，WP-1 只保证字段、纯状态函数和并发写入正确。
- Source pause/delete 不改写 health；资源生命周期与采集健康是不同状态。

### AcquisitionAttemptStatus

```text
succeeded | failed | blocked | cancelled
```

数据库：`varchar(20)`，named CHECK `ck_acquisition_attempts_status`。Attempt 是完成后写入的不可变终态证据，不使用 `queued/running`。`blocked` 表示 Backend 已被选择但在建立目标连接前被 Network/Site/Resource policy 拒绝；细分原因使用 `error_code`。从未选择 Backend 的运行不创建 Attempt。

### BackendName

```text
rss | native_http | scrapling_http | dynamic_browser | advanced_browser
```

数据库 CHECK：`ck_acquisition_attempts_backend`，以及 nullable `last_backend` 的 `ck_source_acquisition_states_last_backend`。WP-1 只产生 `rss/native_http`。

## 2. Profile v1 完整 JSON Schema

顶层必须是 JSON object，序列化后不超过 16 KiB，所有对象 `extra=forbid`，所有数字为严格整数或有限 Decimal，禁止 bool 冒充整数、NaN/Infinity、控制字符、任意 Header/Cookie/Authorization/Token/password/proxy/browser 参数。

```text
content_profile: ContentProfile = generic
priority: Priority = normal
allow_browser: strict bool = false
change_detection: ChangeDetectionProfile
resource_budget: ResourceBudgetProfile
site_policy: SitePolicyProfile
approved_domains: list[hostname] = []
family_options: FamilyOptionsV1 = {}
```

缺失字段由应用物化以下完整默认值；新写入保存规范化完整对象。Expand 期间数据库可暂以 `{}` 兼容 legacy writer，backfill 将 legacy 行写为完整默认 Profile；兼容读取把 `{}` 视为默认 Profile。不得把任意部分对象原样返回。

### ChangeDetectionProfile

```text
enabled: strict bool = true
materiality_threshold: finite Decimal(5,4), 0.0000..1.0000 = 0.1500
semantic_enabled: strict bool = false
```

WP-1 只保存和校验，不执行 Change/Semantic Pipeline。

### ResourceBudgetProfile

```text
max_requests: strict int 1..1000 = 10
max_pages: strict int 1..100 = 1
max_depth: strict int 0..3 = 0
max_duration_seconds: strict int 5..900 = 120
max_concurrency: strict int 1..8 = 1
max_browser_pages: strict int 0..10 = 0
max_retries_per_target: strict int 0..2 = 2
max_total_bytes: strict int 1024..52428800 = 5242880
```

每请求解码后 5 MiB 的既有 SafeFetcher 上限继续有效；`max_total_bytes` 是跨 redirect/retry/fallback/page 的额外累计上限。Effective budget 对每个数值取 Source、Operator 和阶段硬上限中的最小值，Profile 不得扩大部署上限。

### SitePolicyProfile

```text
robots_mode: respect | deny_if_unavailable = respect
crawl_delay_ms: strict int 0..60000 = 1000
requests_per_minute: strict int 1..60 = 30
max_parallel_requests: strict int 1..8 = 1
allowed_content_types: list[str] = [
  text/html,
  application/rss+xml,
  application/atom+xml,
  application/xml,
  text/xml
]
allow_paths: list[path-prefix] = []
deny_paths: list[path-prefix] = []
```

- `allowed_content_types`：1..16 个，trim/lowercase/deduplicate；每项 1..160 ASCII 字符，只允许规范 MIME type，不允许参数或 wildcard。Effective 值为 Source 与 Operator allowlist 的交集。
- `allow_paths` / `deny_paths`：各最多 64 项，每项 1..512 字符；必须以 `/` 开头，是 NFC、无控制字符、无 scheme/host/userinfo/query/fragment 的规范 path prefix，不支持 glob/regex。空 `allow_paths` 表示不额外缩小已批准 scope；deny 始终优先，Effective deny 为并集。
- `approved_domains`：最多 32 个精确 hostname；IDNA ASCII、小写、去末尾点、每项最多 253 字符；禁止 IP literal、端口、scheme、path、userinfo 与 wildcard。父域不隐式批准子域。
- Source 只能把 `robots_mode` 从 `respect` 收紧为 `deny_if_unavailable`，增加 crawl delay，降低 rate/parallel，缩小 content/path/domain allowlist 或增加 deny path；不能放宽 Operator policy。
- ACQ-1 v1 的 WebSocket 与 download 固定拒绝，不提供公开开关。未来需要时必须新增 Profile 版本和 Browser 安全验收。

### FamilyOptionsV1

`family_options` 对全部九类 SourceFamily 均必须是严格空对象 `{}`。它不是自由 JSON 扩展点。Family-specific extractor 规则在 WP-2 使用版本化内部规则；若必须暴露 per-source 配置，总控需发布 `acq-source-v2`、Schema、迁移、OpenAPI 与回滚计划。

## 3. Network / Site / Budget 边界

- `NetworkPolicy` 是内部 Operator 固定策略，只来自代码常量与部署配置，不进入 `acquisition_profile`、Source create/update/response、日志或事件。
- Profile 不能覆盖协议、80/443 端口、userinfo、IP/host deny、DNS 全答案验证、redirect 逐跳校验、verified-IP/Host/SNI 绑定、metadata deny、响应大小/解压或访问控制停止信号。
- `SitePolicyProfile` 是公开、非秘密、Source 级声明；服务层把它与 Operator policy 合成为只会更严格的 EffectiveSitePolicy。
- `ResourceBudgetProfile` 是公开 Source 上限；EffectiveResourceBudget 始终受 Operator 和当前阶段硬上限夹制。
- 公开 API 返回规范化 Profile，不返回 Effective NetworkPolicy、Operator denylist、代理、DNS 结果或内部预算余量。

## 4. 数据库与 API 冻结

- `profile_version` 仅允许 `acq-source-v1`，named CHECK `ck_sources_profile_version`。
- `acquisition_profile` 必须满足 `jsonb_typeof(acquisition_profile) = 'object'`，named CHECK `ck_sources_acquisition_profile_object`；完整字段约束由严格应用 Schema 和集成测试保证。
- Profile 校验失败沿用 422 `invalid_request`；合法 JSON 但违反 Profile 契约可在 service 边界使用 422 `source_profile_invalid`，不得回显秘密、完整 Profile 或数据库异常。
- Source create/update/response 的新字段均为兼容扩展；请求省略时使用 legacy 默认，响应始终返回规范化完整 Profile 与 `profile_version`。
- `config` 在兼容窗口继续按既有字段返回，但不得被复制进 Profile；双方均禁止秘密。WP-1 不删除 `config`。

## 5. WP-1 实现裁定

Backend 获准按本文继续现有 `feat/acq-1a-h0`。任何需要新增枚举值、公开字段、family option、Browser 开关或放宽策略的情况再次 STOP。WP-2 及以后仍未准入。
