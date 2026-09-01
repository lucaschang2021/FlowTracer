# FlowTracer ACQ-1 WP-2 Quality / Extraction Addendum

状态：Proposed；本补充控制提交合并后生效。合并前 Backend 保持契约澄清停点。

基准：WP-2 准入 PR #35 / `main@fcfab2492e4ee88202672787d425c084d0b4afc9`。

优先级：本文与 ADR-028 优先解释 `23-ACQ1-ACQUISITION-CONTRACT.md` §5/§6 和 `25-ACQ1-ACCEPTANCE.md` §7/§8 的 WP-2 语义；不提前决定 WP-4 Router，也不改变 Profile、Schema 或公开 API。

## 1. 范围与版本

- 质量公式：`extraction-quality-v1`。
- 提取规则：`static-extractor-v1`；证据：`extraction-evidence-v1`。
- WP-2 是静态提取与质量观测阶段，不是质量过滤、Router 或 RawItem writer 切换阶段。
- 全部九类 family 使用 §3 的封闭规则；`content_profile` 保留声明值但不改变本文阈值、公式或写入策略。`family_options` 继续严格为 `{}`。
- 后端可决定内部模块/类名、Protocol 的内部字段组织、测试文件拆分，以及满足冻结输入输出的 parser API 调用方法；不得改变本文计数、规则优先级、上限、版本和值域。改变这些语义必须另提 ADR/版本裁定。

## 2. Quality v1 精确计算

### 2.1 字符与结构计数

质量计算只观察本地字节，绝不联网或执行脚本。它使用的规范化文本不回写 legacy RawItem：HTML entity 解码一次，NFC，CRLF/CR 转 LF，以 CPython 3.13 `str.isspace()` 定义把连续空白折叠为一个 ASCII 空格，最后 trim。`L(s)` 是其中 Unicode category 以 `L` 或 `N` 开头的 code point 数；不是 UTF-8 字节数、英文词数或显示字形数。emoji、标点、空白不计入 L，CJK 字母/数字按 code point 计数。

HTML 以现有 `_decode_html` 规则解码。解析前后都不得主动加载资源。下列节点及子树不计入可见文本：`head/script/style/noscript/template`、带 `hidden` 属性或 `aria-hidden` 值 trim/casefold 后等于 `true` 的节点。位于这些节点之外的 tail text 仍计入。可见范围取首个 body，无 body 时取文档根。

导航噪声子树：`nav/header/footer/aside`，以及 `role` 属性 trim/casefold 后精确为 `navigation/banner/contentinfo` 的节点。嵌套子树中的字符只计一次；不按任意 class/id、自然语言关键词或广告猜测剔除。

正文根按顺序选首个非隐藏、非噪声且正文 L>0 的 `article` → `main` → `[role=main]` → 可见范围；同类按文档顺序。正文文本为正文根内去掉上述不可见/导航子树后的文本节点序列，以单个空格连接并规范化。没有合格正文时为空串。

定义：`M=L(正文文本)`；`V=L(整个可见范围文本，保留导航噪声)`；`N=L(可见范围中导航噪声文本)`。V、N 基于相同文本节点遍历，保证 `0 <= N <= V`；正文根只选择一次，不跨重叠根累计。

`S` 为正文原始文档中潜在脚本元素数：script 不在 template 内，type 缺失/空，或 trim/lowercase 为 `module/text/javascript/application/javascript/text/ecmascript/application/ecmascript`，且具有非空 src 或非空文本。JSON-LD/data script 不计入 S。只计数，不下载或执行。

RSS/Atom 每个已被 legacy parser 接受的 entry 单独评分：使用该 entry 已选的 content/description HTML 片段套用上述文本规则（纯文本视为可见根）；不把整个 feed 的导航/脚本/标题混入各 entry。

### 2.2 八分项

所有分项落在 [0,1]，M=0 时八项及总分一律为 0：

| 分项 | 精确值（M>0 时） |
| --- | --- |
| meaningful_text | `min(M / 400, 1)` |
| text_density | `min(2 * M / max(V, 1), 1)`；正文占可见文本一半即饱和 |
| title | 按 §3 找到非空有效真实标题为 1；缺失/URL 或系统生成回退为 0 |
| publish_date | 真实来源日期可规范化为带 offset 的 UTC instant 为 1，否则 0 |
| author | 按 §3 找到非空有效真实作者为 1，否则 0 |
| canonical | 有明确来源链接、且通过 §3 纯语法校验为 1；仅使用 final/feed URL 回退为 0 |
| navigation_noise_inverse | `1 - N / max(V, 1)` |
| js_shell_inverse | `0` 当 `M < 80 且 S > 0`，否则 `1` |

title/date/author/canonical 是二值，不乘 evidence confidence。Evidence 置信度不表示真实性概率。

总分为 `0.30*m + 0.15*d + 0.10*t + 0.10*p + 0.05*a + 0.10*c + 0.10*n + 0.10*j`。整数及权重作为精确有理数计算，不经过 binary float；只对最终加权值以 `ROUND_HALF_UP` 量化至 Decimal `0.0001`，不先舍入各分项。可用精确分数/整数除法实现；序列化诊断值使用四位 Decimal 字符串。

使用量化后的分数分桶：`low: [0.0000,0.4500)`；`marginal: [0.4500,0.6000)`；`acceptable: [0.6000,1.0000]`。因此 0.5999 仍为 marginal；不以两位显示值判定。

Golden examples：八项全 0 → 0.0000；全 1 → 1.0000；M=400,V=400,N=0,S=0、四个元数据分项均 0 → 0.6500；M=80,V=80,N=0,S=0、四个元数据分项均 0 → 0.4100。分项纯函数输入必须拒绝 bool/非有限值/越界比率。

## 3. Family extractor 与字段来源

### 3.1 支持映射

`policy/academic/finance/corporate/technology/community/event/opportunity/generic_web` 全部支持 **common-static-v1**，只提取 `title/text/author/published_at/canonical_url` 这五种通用事实。family 来自已验证 Source 声明，禁止依据域名/正文猜测 family。

本阶段不提取或推断 DOI、机构、组织、地点、金额、currency、deadline、Event 时间或 Opportunity 职位等领域字段；声明 family 为 event/opportunity 不代表已提供对应领域业务能力。以后增加 family 专用规则必须新版本和 ADR，不接受任意 selector/Profile 扩展。

### 3.2 HTML 来源优先级

每行依序选择首个合法非空值；同一规则内按文档顺序，值不合法则继续下一候选。自定义属性名/token 比较采用 ASCII lowercase；文本保留大小写。只识别以下来源，不执行 JSON-LD 或外部引用。

| 字段 | 来源优先级 / 封闭 rule_id |
| --- | --- |
| title | `meta[property=og:title]@content` (`html.og_title`) → 正文根首个 h1 (`html.h1`) → 首个 head/title (`html.title`) |
| published_at | `meta[property=article:published_time]@content` (`html.published_meta`) → 正文根首个 time@datetime (`html.time`) |
| author | `meta[name=author]@content` (`html.author_meta`) → 正文根首个 `[rel~=author]` 文本 (`html.author_rel`) |
| canonical_url | head 内首个 `link[rel~=canonical]@href` (`html.canonical`) → final_url 回退 (`fallback.final_url`) |
| text | §2 正文根，rule_id 为 `html.article/html.main/html.role_main/html.body/html.root` 之一 |

字段 trim/NFC/空白规范化后，title 最多 500、author 最多 300 code points；超限候选视为无效，不截断造出新事实。C0/C1 控制字符（除规范化所需 CR/LF/TAB）或非法 Unicode surrogate 使候选无效。日期只认 ISO-8601 带明确 offset（含 Z）；naive、date-only、时区缩写、无效日期保持缺失，不猜时区、不用 fetched_at 冒充发布日期。日期转 UTC，不依赖当前时间裁剪。

canonical 相对路径只对 response.final_url 做 urljoin，忽略 `<base>`；采用已验收 URL 规范化，且 HTTP(S) 80/443、无 userinfo、无控制字符、无已知禁止 hostname/IP literal，最长 2048 UTF-8 bytes。不调用 DNS。此项仅表示观察到了声明，不证明真实性、目标可达性或允许后续抓取；未来访问仍须完整 SafeFetcher 校验。质量观测链接不改变 writer 已有 canonical/dedupe 规则。

RSS/Atom 保留现有字段选择次序；对应 rule_id 为 `feed.title/feed.content/feed.author/feed.published/feed.link`，无真实链接时为 `fallback.feed_url`。作者/标题边界同上；日期允许现有 parser 支持的 ISO-8601/RFC822，但只有原始值含明确数字 offset 或 Z/UT/GMT、能解析出 aware datetime 才获 quality credit。Legacy parser 对 naive 日期的既有结果不修改。

缺失/无效字段使用 `rule_id=missing`，值保持 null；正文为空使用空串。未知 family 由既有 Source enum 校验拒绝，不映射任意默认值。

## 4. Evidence、metadata 与 links

### 4.1 Evidence（仅内部对象）

封闭对象，所有层 `extra=forbid`；序列化按 UTF-8、`ensure_ascii=False/allow_nan=False`、紧凑分隔符计算最大 16 KiB：

```text
schema_version: "extraction-evidence-v1"
extractor_version: "static-extractor-v1"
quality_version: "extraction-quality-v1"
source_family: SourceFamily
fields: {title, text, author, published_at, canonical_url}
  每字段: {present: strict bool, evidence_path: rule_id, confidence: Decimal}
metrics: {meaningful_chars: int>=0, visible_chars: int>=0,
          navigation_chars: int>=0, executable_script_count: int>=0}
quality_score: Decimal(四位) | null
quality_bucket: low | marginal | acceptable | unscored
diagnostic_codes: list[内部固定 code]（最多 4 项、去重排序）
```

`evidence_path` 只能为 §3 的 rule_id，不存 CSS/XPath 原文、DOM id/class、来源值、URL 或正文片段；rule_id 不允许执行为 selector。直接 meta/feed/link 取 `1.0000`，结构文本 h1/title/author_rel/time/text 取 `0.7500`；final/feed URL 回退即使 present=true 也为 `0.0000`，missing 为 present=false/confidence=0。M=0 时 text present=false、rule_id=missing。

内部 diagnostic code 封闭为 `extraction_quality_low/extraction_quality_marginal/extraction_observation_failed/extraction_resource_limit`。它们不是公开 ErrorEnvelope 或 CollectionRun.error_code，固定含义分别是低分、中间分、观测失败、观测资源上限；不附带原始异常或输入。

`safe_metadata` 最多 8 KiB，唯一允许键为 `source_family/content_profile/extractor_version/quality_version`，值为已验证枚举或上述固定版本字符串；无正文、作者、自由标签、token、Header 或任意来源 JSON。它不覆盖 legacy RawCandidate.metadata（包括既有 author），不合并到公开 RawItem.metadata。

WP-2 evidence/safe_metadata/links 只存在于受控 AcquisitionResult 内，不新增表/列，不写入 RawItem.metadata、Source config/profile/checkpoint、Attempt budget_used、日志、事件或公开 API。Aggregate quality 只填已有数据库质量列，不新增公开响应字段，不顺带暴露 evidence。

### 4.2 Links

结果为规范化 URL 字符串数组，最多 128 项，单 URL 最多 2048 UTF-8 bytes，整个 compact JSON 数组最多 64 KiB。只观察正文原始可见范围中前 4096 个 `a[href]` 节点（按文档顺序；不获取内容），相对路径基于 final_url，忽略 base，去 query/fragment 后使用现有 URL 规范化并稳定去重。只保留符合 §3 canonical 纯语法/host/IP 限制的链接。超长/无效值丢弃，不截断；数组将超过 count/byte 上限时停止收集。

无 DNS、HEAD、GET、附件下载、Discovery 入队；路径/主机也可能敏感，因此 links 仅内部临时使用，不日志或公开。RSS links 只来自该 entry 的真实 link，同样规范化，不把共享 Feed fallback 当发现链接。

### 4.3 静态解析资源

沿用每响应解码后 5 MiB；静态观测另加最多 50,000 个元素、最大嵌套 128 层和 2 MiB 累计原始属性值 UTF-8 bytes。达到上限前允许，超出任一项停止观测；必须在构造不受限 Scrapling DOM 前使用有界预检，不开启 huge-tree、XML entity 或网络解析。

资源受限或 parser 观测失败按 §5 降级为 unscored，不阻塞已成功的 legacy writer；不得 catch 并吞掉进程退出、取消、lease fencing 或既有安全拒绝。实现者负责对畸形 HTML 的有界预检/解析证明与进程资源测量，不可通过放宽上限通过测试。

## 5. WP-2 Writer / Attempt / Run 裁定

### 5.1 实际接入与兼容

正常 URL 采集的顺序是一次 Native 安全获取 → 既有 parse_html 的 legacy candidates → 对同一响应调用 Scrapling static parser 做通用提取/质量观测 → writer 消费未改写的 legacy candidates。RSS 使用既有 parse_feed 身份规则，对每个 accepted entry 的本地片段观测。不得二次获取或把 static parser 作为可联网 Backend。

这不是只交付未接入的工具：正常成功采集必须在 AcquisitionResult 中携带观测结果，且提交 aggregate quality 至现有质量列；static parser 提取值/evidence 仅作为内部候选证据，不替换本阶段的原始正文和身份。

`backend/last_backend` 按真正采集路径仍为 `rss/native_http`，单次成功采集一个 Attempt；Scrapling 本地解析不多计 request/page/Attempt，不产生 `scrapling_http` 调度分支。`decision_version` 仍沿用已验收 `acquisition-native-v1`（WP-2 没有新 Router 决策），extractor/quality 版本放内部观测对象。

### 5.2 状态表

以下对九类 family、全部合法 content_profile 和 `auto/native` 一致：

| 情况 | RawItem / quality | Attempt | CollectionRun / health |
| --- | --- | --- | --- |
| legacy parse 成功，quality >=0.6000 | 全部 candidates 经既有三层去重；观测 acceptable | succeeded，error=null | 无 entry 失败为 succeeded，否则 partial；health 沿用 WP-1 成功语义 |
| legacy parse 成功，0.4500<=quality<0.6000 | 同上；marginal，内部 diagnostic | 同上 | 同上，不因质量变为 failed/degraded |
| legacy parse 成功，quality<0.4500（含 0） | 同上；low，内部 diagnostic | 同上 | 同上，不重试、不 fallback |
| legacy parse 成功，但观测解析失败/超观测资源上限 | 同上；null/unscored，内部 diagnostic | 同上 | 同上，原有数据闭环不得丢失 |
| legacy parse 本身失败/无可读内容 | 不写 RawItem；quality=null | 沿用原 failed/error（如 invalid_feed/empty_content/extraction_failed） | 原 failed/health 更新；不被观测降级掩盖 |
| 既有网络/策略/预算/访问控制拒绝 | 不写 RawItem；quality=null | 沿用 WP-1 blocked/failed/no-attempt 规则 | 沿用原状态，不受质量豁免 |

duplicate 仍计入 duplicate_count，质量低不计 failed_count；不改变 external_id/canonical/raw_text/content_hash/metadata/日期、RawItem 版本语义或下游投递条件。尤其无 link RSS 不因共享 Feed URL 去重。

成功候选一一评分；RSS 不按整份 feed 混合字段。只要任何 accepted candidate 为 unscored，run/attempt quality_score=null；否则为全部 accepted candidate 四位分数的算术平均，最后 ROUND_HALF_UP 四位（包括 writer 判 duplicate 的 candidate，不包括 parse 已拒绝的 entry）。无 accepted candidate 时 null。

run 与 attempt 的 aggregate 必须相同；`quality_ewma` 仅在非 null aggregate 时更新：初次=aggregate，否则 `ROUND_HALF_UP(0.8*old+0.2*aggregate,4)`；null 保留旧值。不以 quality 修改 health/circuit。质量写入须使用已有 claim-token fencing 并随终态同事务提交；失败/旧 worker 不得覆盖新状态。

## 6. 验收与后续约束

- 测试精确覆盖 M=0/79/80/399/400/401、CJK/emoji/组合字符、空白、噪声嵌套、JSON-LD 不计 script、标题/日期/作者/链接真实值与 fallback。
- 覆盖八分项 golden vectors、四位 HALF_UP 临界、0.4499/0.4500/0.5999/0.6000 和无浮点中间舍入。
- 九类 family fixtures 同时覆盖通用能力与领域字段不制造；增加 meta→h1 的确定性 fallback 证据。
- 所有质量桶/unscored 下验证 legacy writer 字段/ID/hash/去重一致；RSS 无 link 与 mixed-entry、partial、duplicate、并发 lease fencing 回归。
- evidence/metadata/links 的精确上限、未知字段、秘密字段、query 去除、无网络 parser、DOM 预检必须验证。
- 覆盖聚合质量/ EWMA / old-worker 防覆盖；完整回归覆盖率不得低于 87.27%。
- WP-4 准入前另行冻结质量驱动的 family/profile 路由表；本文没有授权 Browser 升级或新增 Profile 阈值字段。
- 本补充不修改数据库、公开 REST/WebSocket/OpenAPI、评分 Intelligence 或迁移；后端完成后报告并 STOP，不进入 WP-3。
