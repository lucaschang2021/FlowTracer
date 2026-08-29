# FlowTracer ACQ-1 Opportunity Radar Contract

状态：Frozen Candidate

Profile：`freelance-v1`

Score：`opportunity-score-v1`

Payload：`opportunity-action-v1`

## 1. 产品边界

Opportunity Radar 监控有明确时间窗口、值得用户采取行动的公开机会。ACQ-1 首个 Profile 是 Freelance / Mercenary；未来可扩展 internship、grant、hackathon、competition、event、beta 和 collaboration，但必须新增版本化 Profile。

ACQ-1 只允许：发现、采集、结构化、筛选、评分、通知和生成只读 Action Payload。

禁止：自动 Proposal、报价、工期/合同承诺、代表用户沟通、资金处理、接受合同、最终交付或调用外部执行 Agent。

## 2. 数据模型

### Radar

PostgreSQL `radar_type` 增加 `opportunity`。现有 Radar API 保持兼容；生成型客户端必须重新冻结 enum。

### OpportunityItem

```text
id, user_id, source_id, artifact_id, snapshot_id
profile_version
title, platform, description
budget_min, budget_max, currency
skills[]
deadline, published_at
estimated_effort_hours
delivery_type
client_metadata
source_url
status
created_at, updated_at
```

状态：`active | expired | removed | rejected`。

约束：

- `snapshot_id` 唯一，事实来自 Snapshot；
- money 使用 `numeric(18,2)`，currency 为大写 ISO 4217；
- skills 最大 50 项，每项 80 字符；description 使用清洗后的有界文本；
- client_metadata 仅 allowlist（例如公开评分、历史公开统计），不得含联系方式、Cookie、Token 或推断的敏感属性；
- 缺失字段保持 NULL，不由 Parser 猜测。

### OpportunityScore

```text
id, opportunity_id, radar_id
score_version
hard_filter_passed, disqualifiers[]
fit, expected_value, completion_probability
effort_efficiency, time_to_delivery
competition, ambiguity, risk
overall_score, recommendation, reason
scored_at
```

每个维度是严格整数 0..100；`competition`、`ambiguity`、`risk` 越高越差。`(opportunity_id, radar_id, score_version)` 唯一。

### Action Payload

Action Payload 是不可执行的版本化投影：

```text
payload_version
opportunity_id
source
title
description
budget {min,max,currency}
skills
deadline
score {overall,dimensions,recommendation,reason}
risk
source_url
recommended_action
context
generated_at
```

Payload 必须带 `requires_human_approval=true`，不含凭据、Proposal 文本自动提交指令、合同接受标记或付款动作。可存 immutable JSON + SHA-256 以便审计；任何外部执行系统必须另行准入。

## 3. Schema Freeze

### opportunities

```text
id uuid PK
user_id uuid FK users(id) ON DELETE CASCADE
source_id uuid FK sources(id) ON DELETE RESTRICT
artifact_id uuid FK source_artifacts(id) ON DELETE RESTRICT
snapshot_id uuid FK acquisition_snapshots(id) ON DELETE RESTRICT UNIQUE
profile_version varchar(40) NOT NULL
title text NOT NULL
platform varchar(120) NULL
description text NOT NULL
budget_min / budget_max numeric(18,2) NULL CHECK >=0
currency char(3) NULL
skills jsonb NOT NULL DEFAULT '[]'
deadline / published_at timestamptz NULL
estimated_effort_hours numeric(8,2) NULL CHECK >=0
delivery_type varchar(24) NULL
client_metadata jsonb NOT NULL DEFAULT '{}'
source_url text NOT NULL
status varchar(20) NOT NULL DEFAULT 'active'
created_at / updated_at timestamptz NOT NULL
```

named CHECK：budget_min ≤ budget_max；currency 必须为三个大写 ASCII 字母；skills 为 JSON array；client_metadata 为 object；status 使用 varchar + named CHECK。索引：`(user_id,status,created_at DESC,id)`、`(source_id,published_at DESC)`、`(deadline)`。

### opportunity_scores

```text
id uuid PK
opportunity_id uuid FK opportunities(id) ON DELETE CASCADE
radar_id uuid FK radars(id) ON DELETE RESTRICT
score_version varchar(40) NOT NULL
hard_filter_passed boolean NOT NULL
disqualifiers jsonb NOT NULL DEFAULT '[]'
fit smallint NULL CHECK 0..100
expected_value smallint NULL CHECK 0..100
completion_probability smallint NULL CHECK 0..100
effort_efficiency smallint NULL CHECK 0..100
time_to_delivery smallint NULL CHECK 0..100
competition smallint NULL CHECK 0..100
ambiguity smallint NULL CHECK 0..100
risk smallint NULL CHECK 0..100
overall_score numeric(5,2) NULL CHECK 0..100
recommendation varchar(20) NOT NULL
reason varchar(1000) NOT NULL
scored_at / created_at timestamptz NOT NULL
UNIQUE(opportunity_id, radar_id, score_version)
```

Hard Filter 未通过时 8 个维度和 overall 必须 NULL，recommendation=`dismiss`；通过时全部维度和 overall 必须非空。

### opportunity_action_payloads

```text
id uuid PK
opportunity_score_id uuid FK opportunity_scores(id) ON DELETE CASCADE
payload_version varchar(40) NOT NULL
payload jsonb NOT NULL
payload_hash char(64) NOT NULL
generated_at timestamptz NOT NULL
UNIQUE(opportunity_score_id, payload_version)
UNIQUE(payload_hash)
```

payload 必须为 object、最大 32 KiB，并通过冻结 Schema；记录不可更新，只能由新 payload_version 产生新行。

### notifications 兼容扩展

按第 6 节固定 XOR 约束和两个部分唯一索引扩展；`opportunity_score_id` 使用 `ON DELETE RESTRICT`。现有 Analysis Notification 不改变 ID、状态、read_at 或事件语义。

## 4. Freelance v1 Hard Filter

默认 Profile 配置，不写死在 Acquisition Engine：

```text
currency_allowlist: [USD]
budget_min: 10.00
budget_max: 80.00
max_estimated_effort_hours: 8
max_delivery_days: 2
delivery_type_allowlist: [one_off]
max_required_meetings: 1
maintenance_required: false
```

必须存在：title、description、source_url、currency，以及 budget_min/budget_max 至少一个。缺少必需字段时 `hard_filter_passed=false`，disqualifier=`insufficient_data`。

固定拒绝项：

- 登录凭据、资金转移、支付账户或身份冒用；
- 非法访问、漏洞利用、恶意软件、垃圾信息或访问控制绕过；
- 自动承诺合同/价格/工期；
- 长期维护、持续值守或高频会议超出 Profile；
- budget 与 Profile 无交集；
- 不支持的 currency 或无法确定币种；
- 明确高法律、财务、安全或隐私风险。

非 USD 不进行在线汇率查询。未来支持多币种时必须由版本化 Profile 提供固定 `fx_table` 与 `fx_version`；没有匹配汇率即拒绝评分。

## 5. Opportunity Score v1

仅对 Hard Filter 通过的 Opportunity 计算：

```text
overall =
  fit                    * 0.25
  + expected_value       * 0.20
  + completion_probability * 0.20
  + effort_efficiency    * 0.15
  + time_to_delivery     * 0.10
  + (100 - competition)  * 0.04
  + (100 - ambiguity)    * 0.03
  + (100 - risk)         * 0.03
```

服务端使用 Decimal，`ROUND_HALF_UP` 到两位并 clamp 0.00..100.00。模型或规则只提供维度与证据，不能提供最终分。

### Evaluation Provider

- Prompt/Schema 版本固定为 `opportunity-eval-v1`；业务层依赖独立 `OpportunityEvaluationProvider` Protocol。
- Alpha 只实现确定性 Fake 与现有 operator 配置的单一 OpenAI-compatible Provider，不引入模型 Router。
- Hard Filter 在远程调用前执行；未通过不产生 AI 调用或成本。
- Provider 只接收 bounded Opportunity 事实、Radar goal/skills 和 Profile 规则，不接收 Source config、用户 profile、Cookie、Token 或内部 Browser trace。
- 严格输出仅包含 8 个整数维度和 bounded reason/evidence；未知字段、bool/float、NaN/Infinity、Markdown/附加文本均拒绝。
- 最多 3 次真实调用、2/4 秒临时错误退避、一次 repair 且共享总预算；远程调用不得发生在数据库事务或锁内。
- 每次调用写 AIUsageRecord，`analysis_id=NULL`、task_type=`opportunity_evaluation`，记录 provider/model/token/cost/duration/success/error；Prompt 和原始输出不落日志。

### 缺失值

- 正向维度缺失按 0；
- competition/ambiguity/risk 缺失按 100；
- 任一维度缺失在 `reason` 中明确记录；
- 必需事实缺失由 Hard Filter 拒绝，不进入通知；
- bool、float、NaN、Infinity 或超范围维度均拒绝整个评分结果。

### 维度语义

- Fit：与 Radar goal/skills 的匹配度。
- Expected Value：预算相对工作量和交付价值。
- Completion Probability：在限制内按时完成的概率。
- Effort Efficiency：单位时间预期价值；越高越好。
- Time-to-Delivery：短周期得分更高。
- Competition：公开竞争压力；越高越差。
- Ambiguity：需求、验收和沟通不确定性；越高越差。
- Risk：法律、财务、安全、隐私、平台与声誉风险；越高越差。

## 6. Recommendation 与通知

```text
85.00..100.00  act_now
70.00..84.99   review
50.00..69.99   watch
0.00..49.99    dismiss
```

Notification 资格必须同时满足：

- Hard Filter 通过；
- `overall_score >= max(85, radar.notification_threshold)`；
- `risk <= 30`；
- `ambiguity <= 40`；
- Opportunity 为 active 且 deadline 未过；
- Radar active、未删除且属于当前用户。

Opportunity Notification 继续使用既有 Notification 事实源，并按以下兼容迁移冻结：

- `notifications.analysis_id` 改为 nullable；
- 新增 nullable `opportunity_score_id` FK；
- named CHECK 强制 `analysis_id` 与 `opportunity_score_id` 恰好一个非空；
- 既有 `(user_id, analysis_id)` 唯一约束改为 `analysis_id IS NOT NULL` 的部分唯一索引；
- 新增 `(user_id, opportunity_score_id)`、`opportunity_score_id IS NOT NULL` 的部分唯一索引；
- 公开 Notification 增加 `kind=intelligence|opportunity` 与可空 `opportunity_id`，legacy 字段保持兼容。

不能把 Opportunity Score 写入现有 Analysis radar_score。迁移采用 expand/backfill/check/switch；所有旧 Notification 自动满足 intelligence 分支。

## 7. 来源与合规

- 仅采集公开、允许自动访问且符合 SitePolicy 的页面。
- 平台来源必须逐站点批准；Upwork、Freelancer 等名称仅代表未来候选 Profile，不构成自动访问授权。
- 登录、CAPTCHA、付费墙、访问限制或平台禁止自动化时 Stop/Report/Human Action。
- Fiverr 等服务发布平台不强行映射为 Job Feed。

## 8. API 草案

- `GET /api/v1/opportunities`
- `GET /api/v1/opportunities/{opportunity_id}`
- `GET /api/v1/opportunities/{opportunity_id}/action-payload`

列表支持 radar、status、recommendation、min_score、currency、deadline 和稳定分页；详情不返回 raw HTML、Prompt、向量、内部 Router trace 或秘密。

候选错误码：

```text
opportunity_not_found
opportunity_profile_invalid
opportunity_insufficient_data
opportunity_currency_unsupported
opportunity_score_invalid
action_payload_unavailable
human_approval_required
```

所有权与不存在统一 404；Schema `extra=forbid`；公开 OpenAPI 必须冻结 0..100、money、currency、enum 与 ErrorEnvelope。

## 9. 证据与可追溯性

OpportunityItem 引用 SourceArtifact/Snapshot，OpportunityScore 引用明确 score/profile version。Action Payload 中每个事实可追溯到 Snapshot 字段；AI reason 不能替代证据。Snapshot 删除策略必须满足用户删除与数据保留 ADR，ACQ-1 不创建永久外部档案。
