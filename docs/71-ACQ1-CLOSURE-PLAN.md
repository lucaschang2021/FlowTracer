# ACQ-1 收口计划（独立审核确认版）

状态：**ACTIVE CLOSURE PLAN（计划冻结，2026-10-06）**。本文件不声明任何已完成能力；它是**独立审核确认的未完成清单**的执行映射与验收口径。

判定基线（本文件生效后的统一口径）：

- 当前交付状态 = **I1 / 阶段性交付**（可接收、可运行、证据完整），**不是 ACQ-1 整体收口**。
- **READY_FOR_FRONTEND 未达成**（判定条件见 §6）。
- 不在本计划内（已明确延期）：Dynamic/Advanced Browser（WP-3 及 R3/R4/R5）、PLUGIN-1、Frontend（前端侧负责）。
- 范围纪律：**多币种 FX 与外部平台执行适配器不因收口而扩张**（机会域仅保持"非 USD 拒绝"语义）。

**优先级（固定）**：修 P1 → WP-4 收口 → 完整 WP-5 → 完整 WP-6 → WP-7 收口 → WP-8 整链验收与交接。
本计划各阶段与审核清单**逐条对应**（编号顺序一致）。

## 0. 核实结论（2026-10-06，代码级）

审核清单各项经代码核实成立，落点如下（供实现直接定位）：

1. **逐跳计费缺失**：重定向在 `services/safe_fetcher.py`（`MAX_REDIRECTS` 循环，约 L328）内完成，但账本仅记 `retry_count + 1`（`services/acquisition_route.py` L291-292、L309）；超限检查只在**阶段开始前**（L281 `ledger.exceeds`），无法做到"超限前停止请求"。
2. **有效预算未贯穿执行**：`safe_fetcher.py` 以固定常量（`MAX_WIRE_BYTES`/`READ_TIMEOUT` 等）在读取中强制（L139-231，字节上限在流内生效），但**按源的有效预算**（`max_total_bytes`/`max_duration_seconds`/`max_requests`）未传入读取/执行路径，仅在阶段返回后记账。
3. **版本回退判定**：`services/change_tracking.py` 的 `_resolve_current`/`_latest_snapshot` 以 `max(version)` 为"最新"，回退时复用旧快照行；后续比对对象是**最大版本**而非**最近一次观测状态** → A→B→A→A 会重复报变（第 4 次 A 仍报 content_changed），A→B→A→B 语义不明确。
4. **限速与并行只算不做**：`requests_per_minute`/`max_parallel_requests` 仅在 `acquisition_policy.py` L178-179 计算合并值，未被任何执行路径消费；crawl delay 每次 run 仅 sleep 一次（`acquisition_route.py` L186、L230-247），不在请求之间执行。
5. **机会筛选未限定集合本身**：`services/opportunity_queries.py` 的筛选作用在"最近一条评分"的连接结果上，未定义"合格机会集合"本身（radar 作用域/存在性语义不明确）。
6. **回填无游标**：`change_tracking.backfill_source_evidence` 先 `limit(batch_size)` 再逐条跳过已存在记录 → 第二次调用重复处理同一头部，**超过 batch_size 的记录永不处理**。

## Phase 0 — P1/P2 缺陷修复（必须先做）—— **已完成（2026-10-06）**

> **状态：COMPLETE。** 六项缺陷已全部修复并附测试证据，见 `docs/72-ACQ1-CLOSURE-P0-REPORT.md`：逐跳计费（`FetchSession`/`redirects` 计数、超限前停止）、时间与字节预算硬执行（贯穿读取/退避）、版本回退指针（迁移 `20261006_0007`，A→B→A→A / A→B→A→B / removed-重现全覆盖）、真实限速与串行（`SiteGate` 执行 crawl delay/RPM/并行并落盘证据）、机会筛选集合语义（EXISTS + radar 来源域）、回填游标推进（超批处理）。门禁：新增测试 18/18、全量候选结果见 §9 溯源与 `docs/72`。

### 0.1 预算逐跳计费（P1）

- **工作**：`SafeFetcher` 统计真实 hop 数（每次重定向=1 次实际请求），与 retry 分开上报；`FetchResponse`/`AcquisitionResult.budget_used` 增加 `redirects` 字段；账本按 `retries + redirects + 1` 计费；**在每个 hop 与每次重试之前**检查剩余预算（请求数/字节/时长），超限立即停止且不发出下一个请求，错误码 `acquisition_budget_exhausted`。
- **文件**：`services/safe_fetcher.py`、`services/acquisition_types.py`、`services/native_acquisition.py`、`services/acquisition_route.py`、`adapters/acquisition/*`（透传）、`tests/`。
- **验收/证据**：重定向链 0/1/N 的计费精确；边界 N-1/N/N+1 精确；超限时有"下一个请求未发出"的传输层调用计数证据。

### 0.2 时间与字节预算硬执行（P1）

- **工作**：把**有效预算剩余量**贯穿执行——读取按 `remaining_bytes` 截断（超限立即失败，不是读满固定上限后才发现）；run 级 deadline 贯穿 connect/read/等待（剩余时长作为每次 timeout 上限）；重定向与重试同样受剩余时长与字节约束。
- **文件**：`services/safe_fetcher.py`、`services/acquisition_route.py`（deadline 计算与参数下传）、`services/native_acquisition.py`、`tests/`（慢流/大流/预算边界）。
- **验收/证据**：超字节时在预算处提前失败；超时在预算处提前终止；固定上限路径回归不破。

### 0.3 版本回退判断（P1）

- **工作**：引入**当前观测状态指针**（如 `source_artifacts.current_snapshot_id`；迁移 `0007` + 回填=当前最大版本）；分类一律与"最近一次观测状态"比较；明确四条语义：A→B→A（content_changed 复用快照）、A→B→A→A（第 4 次=unchanged，不再报变）、A→B→A→B（content_changed，复用 B）、removed 后重现。
- **文件**：`models/evidence.py`、`alembic/versions/0007`、`services/change_tracking.py`、`tests/`。
- **验收/证据**：审核给出的两条序列 + removed 重现 + 连续重复观测全覆盖；迁移循环与 downgrade guard。

### 0.4 实际限速与并行控制（P1）

- **工作**：在执行点消费三个配置值——`crawl_delay_ms`（**请求与请求之间** sleep）、`requests_per_minute`（域级滑动窗口，跨 run 生效）、`max_parallel_requests`（域级并发闸；当前单 worker 执行模型下强制 ≤1，用并发测试证明互斥）。**只计算不执行不得记为已实现。**
- **实现归属**：Phase 0 先完成 route 级"每请求 crawl delay 执行 + 并发互斥证明"；完整域级 RPM/并行随 Phase 2 抓取执行器落地（抓取是唯一多请求场景）。
- **文件**：`services/acquisition_route.py`、`services/acquisition_policy.py`、新增 `services/site_throttle.py`（或 Redis 状态实现）、`tests/`（时间证据用可注入时钟/并发证据）。
- **验收/证据**：延迟在请求之间真实发生（可注入计时证据）；并发互斥有测试；RPM 窗口边界测试。

### 0.5 机会雷达筛选（P2）

- **工作**：冻结并实现"**合格机会集合**"语义——筛选条件先限定机会集合（radar 作用域下"最近评分"为该 radar 的最近评分；跨 radar 视图语义显式定义），总数与列表一致；改为 EXISTS/显式子查询而非仅连接过滤。
- **文件**：`services/opportunity_queries.py`、`schemas/`（语义文档）、`tests/`（无评分/错 radar/双 radar 场景）。
- **验收/证据**：各筛选组合下 total 与 items 一致；边界场景矩阵。

### 0.6 历史回填推进（P2）

- **工作**：`backfill_source_evidence` 改为"SQL 侧排除已回填（`WHERE NOT EXISTS`）+ 循环推进直到空批或达上限"；重复调用幂等；任意规模可全量处理。
- **文件**：`services/change_tracking.py`、`tests/`。
- **验收/证据**：450 条记录两批全覆盖；重复调用为 no-op。

## Phase 1 — WP-4 路由器收口 —— **已完成（2026-10-06）**

> **状态：COMPLETE。** 契约变更 ADR-038（注册受控静态重试阶段，经 SafeFetcher）、生产路径降级/共享预算/Circuit 半开并发保护/节流恢复全部收口并有证据，见 `docs/73-ACQ1-CLOSURE-P1-REPORT.md`。

- **1.1 生产路径有效选择与受控降级证明**：以**真实 `NativeAcquisitionBackend` + `SafeFetcher`**（仅传输层替换为离线确定性 transport；选择器/路由/账本/解析全部真实）跑出降级链；"测试替换选择器"不作为证据。
- **1.2 降级/重试/重定向共享同一预算**：基于 Phase 0.1，在单 run 混合场景断言累计精确（含 fallback 与重定向）。
- **1.3 Circuit 独立验证**：半开探测（并发下同一时刻仅一个探针）、成功闭合、失败重开且退避升级；throttle 恢复（成功后延迟衰减）行为测试。
- **1.4 Browser 不可达**：保持不可达且不作为 fallback（断言不变）。

## Phase 2 — WP-5 受控发现：完整抓取执行 —— **已完成（2026-10-06）**

> **状态：COMPLETE。** I2 crawl 执行经 ADR-039 准入：frontier 消费（真实 SafeFetcher 路径、每页 attempt+版本证据）、robots/crawl delay 执行、逐跳 scope/SitePolicy/SSRF 复核、四账跨页累计且超限前停止、claim 丢失即停 + CAS 检查点恢复 + 崩溃不重抓不丢目标、双 run 并发去重，全部有证据；见 `docs/74-ACQ1-CLOSURE-P2-REPORT.md`。

- **2.1 消费 frontier**：实际抓取发现的页面（真实 `SafeFetcher` 路径；每页产生 attempt 记录）。
- **2.2 robots/domain policy**：获取并执行 robots 与站点策略、crawl delay（依赖 Phase 0.4 执行器）。
- **2.3 逐跳复核**：每个发现目标与每次重定向执行 scope/SitePolicy/SSRF 检查。
- **2.4 有界遍历**：深度、页数、请求数、时间、字节上限**跨页累计**且超限前停止。
- **2.5 取消/恢复**：取消（claim 丢失即停）、检查点恢复（CAS）、崩溃恢复（stale worker 重入不重复消费、不丢失待处理目标）。
- **2.6 并发去重证明**：双 worker 并发场景不重复抓取。

## Phase 3 — WP-6 变更情报：完整写路径

- **3.1 合格变化产生新下游输入**：改造去重规则（同源新版本产生新 RawItem），含迁移/回填/兼容验证。
- **3.2 接入下游链路**：变化 → 清洗 → 分析 → 情报 → 适用通知（新版本 Document/Analysis 与通知资格）。
- **3.3 读取接口**：前端可用的 Change/Artifact 历史读取 API + schema + OpenAPI 冻结。
- **3.4 序列验证**：removed、重新出现、内容回退、连续重复观测（与 Phase 0.3 共测）。
- **3.5 写路径切换**：迁移、回填、兼容性验证与 downgrade guard。

## Phase 4 — WP-7 机遇收口

- **4.1 真实输入**：Discovery/Change 的真实输出接入 Opportunity（不再只处理首见页面）。
- **4.2 生命周期与重评**：内容变化、移除、过期的状态与评分生命周期一致（评分版本化；唯一约束按需修订）。
- **4.3 契约收口**：Opportunity REST、通知/适用事件与人工确认边界（OpenAPI 冻结）。
- **4.4 禁止项保持**：自动投标、报价、沟通、合同承诺与资金操作**永久禁止**；FX 与外部执行适配器不扩张。

## Phase 5 — WP-8 整链验收与交接

- **5.1 真实整链 E2E**：配置 Radar/Source → Acquisition → Router → Discovery → Change → Opportunity → 持久化 → REST/适用事件。
- **5.2 路径覆盖**：失败、取消、恢复、所有权、并发、幂等、预算耗尽。
- **5.3 独立验收证据**：在**精确候选提交**上形成独立测试、迁移与运行验收证据——交付方提供可复现步骤/脚本与候选哈希，验收由审核方执行；**"438 passed"仅为交付方报告，不能作为独立证据**。
- **5.4 前端契约冻结**：完整 OpenAPI、状态、错误、分页、筛选与适用事件契约。
- **5.5 交接补齐**：新增接口示例、演示数据方法、真实能力限制。
- **5.6 文档口径**：WP-5/WP-6 的局部 I1 不得写成整个 ACQ 收口（本次已修正，见 §8）。

## 6. READY_FOR_FRONTEND 判定条件（冻结）

仅当以下全部满足才可判定 READY_FOR_FRONTEND：

1. Phase 0 全部 P1/P2 修复完成并通过门禁；
2. WP-4 收口（1.1-1.4）有生产路径证据；
3. WP-5 完整（2.1-2.6）与 WP-6 完整（3.1-3.5）完成；
4. WP-7 收口（4.1-4.4）完成；
5. WP-8 整链验收（5.1-5.2）通过；
6. **审核方在精确候选提交上独立复核**（5.3）P0/P1=0；
7. 前端契约冻结（5.4）且交接补齐（5.5）；
8. 看板/文档口径与事实一致（5.6）。

## 7. 治理与纪律

- 每个 Phase 照既有模式执行：独立分支 → 定向测试 → 全量门禁（ruff/format/mypy/pytest+coverage/架构门/alembic/openapi/secret scan）→ 阶段报告 → no-ff 合并 → 溯源提交。
- 涉及迁移的 Phase 附 ADR 与 downgrade guard；安全边界（SSRF/预算/dispatch）只允许收紧。
- 本计划不含时间承诺；阶段顺序固定为文首优先级。

## 8. 文档口径修正记录（本次同步完成）

- `README.md`（中/英）、`docs/00-PROJECT-CONTROL.md`、`docs/02-DELIVERY-BOARD.md`、`docs/CURRENT-GATE.md`、`docs/70-ACQ1-DELIVERY-PACKAGE.md` 已统一改为：**WP-4..WP-8 = I1/实现完成 + 收口未完成（本计划）**；新增 **READY_FOR_FRONTEND 未达成**声明；WP-5/WP-6 的局部 I1 不再表述为整体收口。
- 修正提交与合并哈希见紧随本分支的 traceability 提交（§9）。

## 9. 溯源

- 计划文件提交：**`d51968b`**；no-ff 合并到 `main`：**`451d848`**。
- Phase 0 实现提交：**`9cbdc97`**；no-ff 合并：**`6e05480`**（以 git 历史为准）。
- Phase 1 实现提交：**`ad0c8ae`**；no-ff 合并：**`0fca397`**（以 git 历史为准）。
- Phase 2 实现提交：**`56eebd7`**；no-ff 合并：**`ddb0723`**（以 git 历史为准）。
