# ACQ-1 WP-5 Controlled Discovery 契约冻结（含实现注记）

状态：**FROZEN（ADR-035 Accepted）+ IMPLEMENTED（discovery-v1，I1 范围）**。冻结规则以本文件为准；§15 实现注记记录落到代码时的精确裁定。
日期：2026-10-05。依据：`docs/29` WP-5、`docs/23` 采集契约、`GOVERNANCE-V2 §3`（Capability DAG）、ADR-022/023/026、ADR-034/035；锚定代码：`app/models/entities.py`（`DiscoveryMode`、`Source`）、`app/services/discovery_policy.py`、`app/services/discovery_links.py`、`app/services/discovery_frontier.py`、`app/services/acquisition_route.py`、`app/services/acquisition_policy.py`、`app/schemas/resources.py`。

## 0. 增量拆分（冻结）

- **I1（本增量，已实现）**：Discovery **规划与 Frontier 状态**——四种 scope 边界、link scoring、站点路径策略、硬上限、并发/跨 run 去重、checkpoint 持久化与恢复。**不向发现的 URL 发出任何请求**（无 crawl 执行）。
- **I2（已准入并实现，2026-10-06，收口 Phase 2 / ADR-039；注记见 §17）**：**crawl 执行**——对 frontier 中的 URL 发起真实抓取、逐跳计费、robots.txt 获取与遵守、子资源与 redirect 计费、取消/恢复的抓取语义。I2 自身准入与 robots 契约由 ADR-039 补齐（§5 的 robots 义务在 I2 生效）。

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

## 12. 冻结裁定（2026-10-05）

1. `min_score`=20；`max_frontier_size`=500（硬上限 `FRONTIER_HARD_CAP`，profile 值取 min）；`max_discovered_urls = max_pages × 5`；
2. discovery 参数落在既有 `ResourceBudgetProfile`（`max_depth`/`max_pages`）与固定常量，不新增 profile 字段；
3. **不落独立 frontier 表**：复用 `SourceAcquisitionState.checkpoint` JSONB（无 migration）；
4. `nofollow` 链接：I1 记录但结果中不单列；I2 决定抓取语义；
5. 不新增公开 API：discovery 证据落在 `CollectionRun.budget_summary["discovery"]` 与 `SourceAcquisitionState.checkpoint`（内部证据）。

## 15. 实现注记（2026-10-05，discovery-v1 / I1 实值）

1. **模块**：`discovery_policy.py`（scope/scoring/路径门，纯函数）、`discovery_links.py`（有界 HTML 链接抽取，stdlib）、`discovery_frontier.py`（规划+checkpoint 合并，纯函数）；执行接线在 `acquisition_route.py`（`_plan_discovery`）与 `acquisition_run_repository.py`（`finish_success(discovery_checkpoint=…)` → `_update_source_state(checkpoint_update=…)`），读取经 `acquisition_attempts._discovery_checkpoint`。
2. **触发条件**：仅 `SourceType.URL` 且 `discovery_mode != single_page` 且该 stage **质量达标**（`met`）时规划；RSS 与非达标页不产生 discovery 证据，checkpoint 不被触碰。
3. **scoring 实值（对 §4 的精确化）**：深度惩罚为 `-20 × max(0, depth-1)`（种子页直链为第 1 层，不惩罚；更深层才衰减）；同路径目录前缀 `+30`；同主机 `+15`；跨主机但在批准交集内 `+10`；命中 `allow_paths` `+10`；锚文本 ≥4 字符 `+10`；追踪参数 `-10`；clamp `[0,100]`。`deny_paths` 在打分前直接拒绝（计入 `rejected_scope`）。
4. **scope 硬前置（fail-closed）**：仅 `http/https`、端口 80/443、拒绝 userinfo/`@`；无法解析即拒绝。规范化为 `url_normalization.normalize_source_url` 后比较。
5. **上限**：`max_depth` 取 `min(profile.max_depth, 3)`；`max_frontier_size` 取 `min(配置, 500)`；`max_discovered_urls` 为累计 accepted 上限（跨 run）。任一超限即停止入队（`truncated` 标记）；**无 unrestricted crawl 路径**。
6. **去重与顺序**：URL 的 SHA-256 为身份键；`seen` 上限 `MAX_SEEN_HASHES=2000`（确定性截断）；单页链接 ≤200；入队顺序按 `(-score, depth, url)` 稳定排序。
7. **checkpoint 文档**：`{version:1, seen:[hash…], frontier:[{url,parent_url,depth,score}…], counters:{runs,accepted_total}}`；成功终结时**整文档替换**写入（与 run 成功同事务）；损坏内容按空状态容忍处理。
8. **取消与恢复**：无 crawl（I1），"取消"即未写入；已写入的 checkpoint 即事实；重复 run 幂等（`duplicates` 计数、`accepted=0`）。
9. **robots**：I1 不抓取，故不触发 robots 义务；`deny_if_unavailable` 的抓取前门禁随 I2 落地（§0）。
10. **运行摘要**：`CollectionRun.budget_summary["discovery"] = {policy_version, scope, links_found, rejected_scope, rejected_score, duplicates, accepted, frontier_size, depth_cap, truncated}`。

## 16. 复验

- 纯策略/规划测试 + DB 集成测试共 18 项（`tests/test_acquisition_discovery.py`）；WP-4/WP-1/WP-2 回归与全量套件见 `docs/62-ACQ1-WP5-DISCOVERY-STAGE-REPORT.md`。
- 架构门（跟踪后）`introduced=0`；ruff/format/mypy 全绿。

## 17. 实现注记（2026-10-06，crawl execution / I2 实值；ADR-039）

1. **模块**：`discovery_pages.py`（状态、逐页步骤：验证器/抓取/评估/子规划/CAS 提交、`budget_gap` 纯函数）、`discovery_crawl.py`（循环、robots 接线、上下文工厂 `crawl_context_for`/`plan_seed_page`、run 证据）、`discovery_robots.py`（robots 获取/解析/判定）；生产 transport 为 `native_acquisition.SafeCrawlTransport`（经 `SafeFetcher`），worker 在 `execute_route_run(discovery_transport=…)` 注入。无 transport 时保持 I1 规划语义不变。
2. **触发**：`SourceType.URL` 且 `discovery_mode != single_page` 且 stage 质量达标（与 I1 相同门槛）；RSS/非达标不进入 crawl。
3. **逐跳复核**：目标与每个 redirect hop 均执行 `NetworkPolicy.validate` + `EffectiveSitePolicy.validate_target` + `scope_allows`（范围违例为 `site_policy_denied`，fail-closed，越界 hop 不传输）；robots 目标仅做 origin/approved-host 网络校验（无路径门）。
4. **robots 细节**：每 origin 缓存于本 run；仅接受 `text/plain`（否则按 unavailable）；`Crawl-delay` 以秒计并作为该 host 后续请求的间距下限（与 `max(crawl_delay, 60000/rpm)` 取 max 后经 SiteGate 执行）；robots 请求计入 requests（不计 pages），max_requests=2（允许一次 http→https 跳转）、max_retries=0。
5. **预算边界**：`budget_gap` 判定为“下一请求是否仍可负担”（`used+1 > max` 即阻塞；bytes 为 `used >= max` 阻塞），在 robots 消耗后、页面请求前**再次**检查；停止原因写入 `stopped_reason` ∈ {frontier_empty, targets_deferred, page_budget, request_budget, byte_budget, time_budget, robots_unavailable, checkpoint_conflict, claim_lost}。
6. **checkpoint v2**：`{version:2, seen, frontier[{url,parent_url,depth,score,attempts}], crawl{run_id,claimed_at,expires_at}, counters{runs,accepted_total,crawled,failed,abandoned}}`；v1 文档按等价形态读取（无 lease/attempts 视为缺省）；`checkpoint_view` 对损坏内容保持空态容忍。
7. **CAS 与并发**：`commit_crawl_step` 在单事务内完成 claim 校验（run RUNNING + token）→ `state.version == expected` → 页面 attempt + 版本证据 → checkpoint 替换 + version+1；无关写者的版本前进由 `cas_crawl_step` 在租约仍属本 run 时重试（最多 3 次），其他 crawl 接管（租约 run_id 不同且未过期）立即停止；双 run 并发时后到者以 `checkpoint_conflict` 跳过 crawl（不传输、不写 checkpoint）。
8. **崩溃恢复**：成功页在提交事务内进 `seen` 并移除 frontier；失败页原位 attempts+1；崩溃/claim 丢失时未提交页留在 frontier；同 run 重新 claim 后接管自身租约并继续；stale worker 的迟到写因 claim token 不匹配被拒（`commit_crawl_step` 返回 None）。attempt ordinal 用 `requested-if-free-else-max+1` 保证 `(run_id, ordinal)` 跨重入唯一。
9. **证据落点**：attempt 行（ordinal=stage+1+n、`decision_version=discovery-crawl-v1`、requested_url=页面 URL、requests/pages/bytes 账）＋版本证据（artifact/snapshot/change event，键=页面 canonical URL）；run 级 `budget_summary.discovery.crawl` 含 pages_fetched/failed、robots_skipped、requests_used、bytes_received、frontier_remaining、complete、stopped_reason、robots 每 origin 状态。
10. **明确的边界**：a) crawl run 暂停 miss-streak removed 判定（consume-once 非全量重复观测；feed/single-page 路径不变）；b) 本增量不改 RawItem/下游写入（WP-6 接线）；c) 逐目标 Circuit 升级延后（run 级 Circuit 语义不变）；d) robots 缓存仅实例/run 级；e) 注入 stub transport 的测试不覆盖 `_decode_body` 逐字节硬截断（该证据在 Phase 0 的真实读取路径测试中）。
