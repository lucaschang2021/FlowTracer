# ACQ-1 WP-5 Controlled Discovery 契约冻结（草案）

状态：**DRAFT — NOT FROZEN / NOT ADMITTED**。本文件补齐 `docs/29` WP-5 的开工前置：把 Controlled Discovery 的精确规则写成可冻结合同。所有 `PROPOSED` 值须经 ADR 冻结后才成为合同；`FROZEN` 项引用既有已冻结事实，不得改。
日期：2026-10-05。依据：`docs/29` WP-5、`docs/23` 采集契约、`GOVERNANCE-V2 §3`（Capability DAG）、ADR-022/023/026；锚定代码：`app/models/entities.py`（`DiscoveryMode`、`Source`）、`app/services/acquisition_policy.py`、`app/services/acquisition_router.py`、`app/services/acquisition_route.py`、`app/schemas/resources.py`。

## 1. 范围与非目标

- **范围**：`feat/acq-1e-discovery` 的静态发现——Frontier/checkpoint、四种 scope、link scoring、robots/domain policy 执行、硬预算、取消与恢复。
- **非目标（FROZEN）**：不实现 Browser/Change/Opportunity；不放宽 WP-1 NetworkPolicy/SitePolicy/预算；不改变下游 Intelligence/Memory；Browser-dependent discovery **暂停**（`browser_dynamic=disabled`）。
- **依赖**：已验收 Static/Native Router（WP-4）+ SitePolicy/预算（WP-1）。本草案不授权实现。

## 2. 四种 scope（FROZEN 枚举 + PROPOSED 精确语义）

枚举（FROZEN，`DiscoveryMode`）：`single_page`、`same_path`、`same_domain`、`approved_domains`。默认 `single_page`。

| scope | 允许发现（PROPOSED） | 明确拒绝 |
| --- | --- | --- |
| `single_page` | 无发现；仅种子 URL（行为等同 WP-4 现状） | 任何新 URL |
| `same_path` | 与种子**同 scheme+host+端口**，且路径以种子路径的**目录前缀**开头 | 跳出该目录前缀、换 host/端口 |
| `same_domain` | 与种子**同 host**（大小写折叠 + IDNA + 去尾点后精确相等） | 子域、父域、兄弟域 |
| `approved_domains` | `same_domain` ∪ `profile.approved_domains ∩ operator.approved_domains`（既有保守交集） | 未同时获 source 与 operator 批准的域 |

**共同硬边界（PROPOSED，全部 fail-closed）**：
- scheme 仅 `http`/`https`；端口仅 `80`/`443`（沿用 `NetworkPolicy`）；
- 拒绝 userinfo、`@`、非全局 IP、metadata 主机、`.internal`（沿用既有 `validate`）；
- 拒绝与种子不同 origin 的重定向目标（逐跳重校验）；
- scope 判定基于**规范化后**的 URL（既有 `url_normalization`），而非原始字符串。

## 3. Frontier 与 checkpoint（PROPOSED）

- **Frontier**：待抓取 URL 的有界队列，元素含 `url`（规范化）、`parent_url`、`depth`、`score`、`discovered_at`。
- **去重**：以规范化 URL 的 SHA-256 为身份键；已见集合跨 run 持久化于 checkpoint，**并发去重**必须在行锁/唯一约束下保证（同 URL 只入队一次）。
- **checkpoint**：`SourceAcquisitionState.checkpoint`（既有 JSONB）保存 `{seen_hashes_version, frontier[], cursor, counters}`；每次 run 结束原子写入；崩溃后从 checkpoint 恢复，不重复、不丢失已发现事实。
- **depth 上限（PROPOSED）**：`min(profile.resource_budget.max_depth, operator.max_depth)`（种子 depth=0）。
- **顺序（PROPOSED）**：按 `(-score, depth, url)` 稳定排序；同分同深度按 URL 字典序，保证确定性可复现。
- **并发（PROPOSED）**：单 run 内串行 frontier 消费（Alpha 不引入并行爬取）；跨 run 互斥由 run 租约保证。

## 4. Link scoring（PROPOSED）

- **打分输入**：仅来自已抓取页面的事实（链接锚文本、rel、URL 路径特征、来源深度），**不使用外部模型**。
- **分值（PROPOSED，0–100 整数）**：
  - `-20 × depth`（越深越降）；
  - `+30` 同路径目录前缀；`+15` 同域；`+10` 在 `approve_paths` 内；
  - `-40` 命中 `deny_paths`（并直接拒绝，不入队）；
  - `+10` 锚文本非空且长度 ≥ 4；`-10` 命中 `?`/`#`/`utm_*` 追踪参数（仅降分，不拒绝）；
  - 末尾分数 clamp 到 `[0, 100]`。
- **阈值（PROPOSED）**：低于 `min_score`（默认 20）不入队。
- **确定性**：同输入必得同分；打分函数为纯函数，无 I/O。

## 5. robots / domain policy（PROPOSED）

- **robots（FROZEN 语义来源）**：沿用 `EffectiveSitePolicy.robots_mode`：`respect`（遵守 robots，禁止项跳过）或 `deny_if_unavailable`（robots 不可得即整体拒绝）。
- **crawl delay（PROPOSED）**：每个发现目标请求前遵守 `EffectiveSitePolicy.crawl_delay_ms`；`requests_per_minute` 与 `max_parallel_requests` 沿用保守交集。
- **站点限制**：发现目标须通过 `EffectiveSitePolicy.validate_target`（origin/allow_paths/deny_paths）与 `NetworkPolicy.validate`；任一失败即跳过该目标（fail-closed，不降级为 Browser）。
- **Domain 批准**：仅在 `approved_domains` scope 下放行 `profile ∩ operator` 交集域；其余 scope 不得借此越域。
- **禁止**：`no_follow`/`nofollow` 链接**按 RESPECT 语义跳过**（PROPOSED 默认）；不绕过登录态、付费墙、CAPTCHA 或访问控制。

## 6. 硬预算（PROPOSED，逐跳口径）

- **账户**：run 级累计 `requests`、`pages`、`bytes_received`（沿用 WP-4 账本语义，跨 stage/fallback/redirect **逐跳**计入）。
- **发现专属上限（PROPOSED）**：`max_discovered_urls`（新，默认 `profile.resource_budget.max_pages × 5`，上限 operator 侧定义）、`max_depth`、`max_frontier_size`（默认 500）。
- **执行**：每次入队前校验 `max_frontier_size` 与 `max_discovered_urls`；每次请求前校验 requests/pages/bytes；超限即 `acquisition_budget_exhausted` 终态，已发现但未抓取的事实保留在 checkpoint，**不丢弃**。
- **子资源计费**：Browser 子资源计费 **N/A**（Browser disabled）；HTML 内联资源不计入 requests（仅文档页计入）。
- **无 unrestricted crawl 不变量**：任何路径都不得出现"无上限扩散"；`max_depth`、`max_discovered_urls`、`max_frontier_size` 三者同时为硬上限。

## 7. 取消与恢复（PROPOSED）

- **取消**：收到取消信号即停止 frontier 消费；已完成事实保留；run 记 `cancelled`（沿用 `AcquisitionAttemptStatus.CANCELLED` 语义）；checkpoint 原子落盘。
- **恢复**：新 run 从 checkpoint 恢复 frontier 与 seen 集合；已抓取 URL 不重复抓取；已发现未抓取 URL 继续按 score 顺序处理。
- **幂等**：同一 seed + 同一 scope 在相同外部状态下产生相同的发现序列（确定性由 §3 顺序 + §4 打分保证）。
- **失败**：单目标失败不终止整个 run；失败计数与 code 记录在对应 attempt；连续失败沿用 WP-4 Circuit 语义。

## 8. 数据与迁移（PROPOSED）

- **复用**：`Source.discovery_mode`（既有列，已存在默认 `single_page`）；`SourceAcquisitionState.checkpoint`（既有 JSONB）。
- **新增（PROPOSED）**：若需独立 Frontier/已见集合持久化，新增 expand 表 `extraction_frontier`（或等价）——`source_id` FK、`url_hash` unique per source、`url`、`parent_url`、`depth`、`score`、`state`、`created_at`。**必须**附 upgrade/downgrade/re-upgrade 循环证据；不得修改既有表语义。
- **回滚**：禁用 discovery（`discovery_mode=single_page`），保留种子 URL；已发现事实不删除。

## 9. 验收矩阵（对齐 docs/29 WP-5）

| 项 | 通过条件 |
| --- | --- |
| scope escape | 四种 scope 的边界（同路径前缀、子域/父域、未批准域）逐一拒绝，无越界 |
| 预算精确边界 | requests/pages/bytes 的 0/上限/超限三种情形精确；`max_depth`/`max_discovered_urls`/`max_frontier_size` 硬上限 |
| frontier 并发去重 | 并发投递下同 URL 只入队/抓取一次（唯一约束/行锁） |
| robots/crawl delay | `respect` 跳过禁止项；`deny_if_unavailable` 不可得即拒绝；delay 生效 |
| redirect 计费 | 逐跳计入 requests；跨 origin 重定向拒绝 |
| 无 unrestricted crawl | 无任何无界扩散路径 |
| 取消/恢复 | 取消保留事实并可恢复；幂等；失败不终止全 run |
| 回归 | WP-4/WP-1/WP-2/BE-4 全回归；OpenAPI/Schema 零漂移（或按冻结字段扩展）；P0/P1=0 |

## 10. 回滚与安全不变量

- 回滚：feature flag 固定 `single_page`；保留 attempt 历史与已发现事实；安全策略不可回滚。
- 安全不变量（FROZEN，不得放宽）：NetworkPolicy、SSRF、访问控制、预算、无凭据/登录态、无 CAPTCHA/付费墙绕过。

## 11. 流程

本草案经 ADR 冻结为合同后，方可签发独立 WP-5 Admission（精确 baseline/branch/允许文件/回滚），再由 Backend 实现并 Stage-Gate 验收。本草案本身**不授权任何实现、迁移或 API 变化**。

## 12. 待冻结项（OPEN）

1. §3/§4/§6 的 `min_score`、`max_frontier_size`、`max_discovered_urls` 默认值与 operator 上限；
2. §6 发现专属上限是落在 `ResourceBudgetProfile` 还是 operator 侧；
3. §8 是否落独立 frontier 表，或复用 `checkpoint` JSONB（影响 migration）；
4. §4 `nofollow` 的默认（RESPECT 跳过 vs 记录）；
5. 是否在 v1 暴露 discovery 统计 API，或仅落内部证据。
