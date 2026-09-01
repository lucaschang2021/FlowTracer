# FlowTracer ACQ-1 Acceptance Baseline

状态：Frozen Candidate

ACQ-1 只有全部阶段完成、P0/P1 清零且本文件所有门禁通过后才可 ACCEPT。

## 1. 通用质量门禁

最终候选 commit 仅执行一次：

```text
uv sync --locked
ruff check
ruff format --check
mypy
pytest + coverage
alembic check
empty-db upgrade / downgrade / re-upgrade
docker compose config
OpenAPI export --check
secret scan
git diff --check
```

Coverage 不得低于 BE-8 冻结基线 87.27%。所有测试不得访问公网；正式 Browser 运行验证使用 internal network、本地 fixture 与受控 proxy。

## 2. Contract 与 Migration

- 旧 BE-8 数据原样可读，现有 RSS/URL Source 无需用户手工修复。
- legacy Source 默认映射 `generic_web/auto/single_page/acq-source-v1`。
- RawItem backfill 生成准确 Artifact/Snapshot 关联；迁移可重入且无重复。
- writer 双写、切换和 legacy 约束收缩均有并发测试。
- 空库和含 BE-8 fixture 数据的 upgrade 通过。
- downgrade 在无多版本 ACQ-1 数据时通过；存在不可逆数据时必须 fail-fast 并只列安全原因，不静默丢数据。
- PostgreSQL enum `opportunity` 的 upgrade/downgrade 重建策略有真实数据库验证。
- Alembic metadata 零漂移。

## 3. Native / RSS Regression

- BE-4 RSS、Atom、单页 HTML、redirect、timeout、Content-Type、精确大小边界与压缩炸弹全部通过。
- 手动 Idempotency-Key、scheduler、queued dispatcher、retry child 与三层 legacy 去重无回归。
- Native 合格时 Router 不创建 Browser attempt。

## 4. Scrapling Static

- Scrapling 只位于 Adapter 内，不泄漏 API 到业务层。
- 静态 byte fixture 正常解析；不允许 parser 自行联网。
- package、extras、transitive dependencies 和 license 形成锁定清单。
- 与 Native 对同一 fixture 输出等价的 AcquisitionResult 语义。

## 5. Dynamic Browser

- 本地 JS fixture 渲染成功；popup、download、WebSocket、iframe、XHR/fetch 均受策略控制。
- Browser 只能通过受控 egress proxy；容器内直连 Internet、host network、系统 DNS 和 Docker socket 均失败。
- API/普通 worker 与 Browser worker 镜像、queue 和资源边界隔离。
- 非 root、read-only rootfs、tmpfs、cap_drop、no-new-privileges、seccomp、PID/CPU/memory 限制通过。
- Browser revision、镜像 digest 和系统依赖可重复构建；版本不匹配 fail-fast。

## 6. SSRF 与访问控制

所有 Backend 覆盖：

- IPv4/IPv6 loopback、RFC1918、link-local、multicast、reserved、unspecified、metadata；
- 混合公网/私网 DNS、DNS rebinding、逐跳 redirect、端口和 userinfo；
- Browser navigation、redirect、iframe、script、XHR/fetch、WebSocket、download 与 popup；
- scope escape、approved-domain escape、redirect 到私网；
- Header/Cookie/Authorization/Source config 不透传。

401/403、登录、CAPTCHA、付费墙、robots deny 和明确平台限制必须 Stop/Report，不启动 Advanced 绕过。

任何 Backend 存在网络旁路即 P0，阶段 REJECT。

## 7. Router 与 Quality

WP-2 按 `docs/35-ACQ1-WP2-CONTRACT-ADDENDUM.md` 验收精确公式与观测模式：低分/观测失败不得丢弃已被 legacy parser 接受的 RawItem；八项权重不变，writer/去重/终态不变。以下 Browser/fallback/family 路由要求仅在 WP-4 等相应能力准入后验收，不是 WP-2 的实现许可。

- Native quality ≥0.60 时不启动 Browser。
- quality <0.45 且预算允许时按 Profile 升级。
- `[0.4500,0.6000)` 按 WP-4 准入前另行冻结的 family/profile 决策稳定执行。
- access control、policy deny、circuit open 或预算耗尽安全终止。
- fallback 顺序、attempt ordinal、decision version 与安全 trace 可重放。
- quality 公式精确覆盖 0、阈值边界、ROUND_HALF_UP、缺失字段和噪声。

## 8. Adaptive Extraction

WP-2 的九类 family 均仅提取五种通用字段；精确来源优先级、rule_id、confidence、links/metadata/DOM 上限以 `docs/35-ACQ1-WP2-CONTRACT-ADDENDUM.md` 为准。领域特有字段和持久 selector 学习不得提前实现。

- 合理 DOM 变化能够恢复或明确失败。
- Policy、Academic、Corporate、Event、Opportunity fixture 覆盖允许缺失字段。
- Parser 不制造作者、日期、预算、currency、deadline 或组织。
- 超大 DOM、恶意 selector、prompt-injection 文本、编码和控制字符安全处理。
- selector/profile 版本和 evidence path 可追溯。

## 9. Controlled Discovery

- single_page/same_path/same_domain/approved_domains 精确生效。
- depth/pages/duration/concurrency/browser-pages/retry/redirect 为硬上限，跨 fallback 累计。
- frontier `(run_id, normalized_url)` 幂等；并发 worker 不重复抓取。
- robots、crawl delay、domain rate、allow/deny path 与取消/checkpoint 生效。
- 不存在 unrestricted crawl 入口。

## 10. Change Intelligence

本地版本序列覆盖：

```text
created
unchanged
content_changed
metadata_changed
structure_changed
removed
```

- 导航、广告、随机 ID、tracking query 与动态时间戳不触发 material content change。
- 数字、日期、适用对象、监管要求、附件增删形成 bounded diff。
- removed 不能由一次失败推断。
- 相同 artifact 并发写入不重复 Snapshot/Change/RawItem。
- qualifying change 只创建一个 RawItem；unchanged 不进入下游。
- AI semantic change 必须引用 old/new snapshot，预算不足时保留确定性 diff，不阻塞事实写入。

## 11. Opportunity

本地 job fixtures 完整执行：

```text
Discovery → Extraction → OpportunityItem
→ Hard Filter → OpportunityScore → Action Payload → Notification
```

- budget 10/80 精确边界、9.99/80.01、缺失、currency 不支持与固定 FX 版本覆盖。
- 8 小时、2 天、one-off、会议与 maintenance 边界覆盖。
- 8 个维度 0/100、缺失值、bool/float/NaN/Infinity、ROUND_HALF_UP 和 Recommendation 边界覆盖。
- Notification 同时验证分数、risk、ambiguity、deadline、Radar 所有权与幂等。
- Action Payload 固定 `requires_human_approval=true`，没有执行能力。
- 跨用户请求、已删除 Radar/Source 与不存在统一 404。

## 12. Reliability 与资源耗尽

- worker kill、lease 超时与旧 Worker 条件写入；stale run 至多恢复一次。
- Broker/Redis 中断保留数据库事实并由 dispatcher 补偿。
- Browser crash、OOM、无限 JS、popup storm、下载、慢页面、重定向环、超大 DOM、压缩炸弹和过量链接不会拖死普通 worker。
- Circuit open/half-open/close、AutoThrottle、per-domain/global concurrency 与 pool leak 覆盖。
- 同 Source、artifact、snapshot、change、opportunity、score 的并发/重放幂等。

## 13. Observability 与安全

- 指标能计算 acquisition/extraction success、fallback、browser usage、latency、failure、change、opportunity、budget、circuit 和 recovery。
- 日志和公开响应扫描不得出现正文、HTML、Cookie、Token、Authorization、密码、Proxy secret、完整 DNS 答案、向量、Prompt 或数据库连接串。
- 错误只包含固定 code、安全 message、bounded details 与 request_id/correlation_id。
- Source config/profile、Router trace、Snapshot 与 Opportunity client metadata 使用 allowlist。

## 14. OpenAPI 与交接

- OpenAPI 快照与实现一致，新路径、枚举、错误和 security 完整。
- Source 新字段对 legacy 客户端可选且有默认值。
- Opportunity enum 变更明确记录为生成型客户端需更新的兼容变化。
- 分页、排序、UTC offset、money Decimal 字符串/数值格式必须冻结。
- Frontend handoff 更新 Endpoint inventory、事件、恢复策略、已知限制和 Quick Start。

## 15. Performance Baseline

至少记录：Native、Scrapling static、Dynamic Browser、Extraction 的 p50/p95/max；单 run 峰值内存；Browser concurrency；fallback frequency；每 Source 预算消耗。数据只代表本机隔离 fixture，不作为 SLA、生产容量或无依据优化结论。

## 16. 最终判定

ACQ-1 ACCEPT 必须同时满足：

- A–H 全部独立阶段已验收合并；
- P0=0、P1=0，P2 有明确接受或延期记录；
- BE-1..BE-8 无 P0/P1 回归；
- Acquisition 与 Opportunity Contract 已导出、冻结并完成 Frontend handoff；
- 可从空环境按文档重复启动；
- Backend 完成报告后 STOP。

只有上述条件满足，总控才可另行签发 Frontend Admission。
