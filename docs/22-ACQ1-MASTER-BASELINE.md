# FlowTracer ACQ-1 Master Baseline

状态：Frozen Candidate（待总控 Review 与控制 PR 合并）

基准：`main@76e86c375cb769bc3716614d8d3f1cb470e4955f`

## 1. 目标

ACQ-1 在 Backend Alpha Core BE-1 至 BE-8 之后建立统一、自适应、受控且可审计的采集层：

```text
Source Discovery
→ Acquisition Router
→ RSS / Native / Scrapling / Browser Adapter
→ Adaptive Extraction
→ Artifact / Snapshot / Change Evidence
→ qualifying RawItem
→ 既有 Document / Analysis / Embedding / Notification Pipeline
```

ACQ-1 是 Frontend 的硬依赖。ACQ-1 完成并冻结前，Frontend、Integration 与 Release 不准入。

## 2. 正式范围

- ACQ-1A：Universal Source Contract。
- ACQ-1B：Multi-Mode Acquisition Engine。
- ACQ-1C：Intelligent Acquisition Router。
- ACQ-1D：Adaptive Extraction Engine。
- ACQ-1E：Controlled Discovery Spider。
- ACQ-1F：Change Intelligence Engine。
- ACQ-1G：Opportunity Discovery Engine。
- ACQ-1H：Reliability、Safety 与 Observability。

Source Family 固定为：

```text
policy | academic | finance | corporate | technology
community | event | opportunity | generic_web
```

它们是 Profile，不是九套 Pipeline。

## 3. 非目标

ACQ-1 不实现：

- Frontend、Rasputin/Claude Agent 或其他执行 Agent；
- 自动投标、报价、工期/合同承诺、沟通、付款或最终交付；
- CAPTCHA、登录墙、付费墙、Cloudflare 或其他访问控制绕过；
- 用户凭据采集、登录态采集、代理池、无限爬取或分布式爬虫集群；
- Kafka、微服务、知识图谱、多模型 Router、团队/企业权限；
- Browser Everywhere 或站点级无限深爬。

## 4. 固定原则

1. Native First，Browser When Necessary。
2. 数据库与 REST 是事实源；在线事件仅是 best-effort 信号。
3. 所有 Backend 输出统一 `AcquisitionResult`，RawItem writer 不感知具体实现。
4. 所有网络 Backend 共享同一 `NetworkPolicy` 与 `SitePolicy`，安全边界不得因 fallback 降级。
5. 版本证据先于 AI 总结；AI 不能替代旧/新 Snapshot。
6. 资源预算为硬上限，跨 retry、redirect、fallback、discovery 和 Browser 子资源累计。
7. Opportunity 仅生成事实、评分和 Action Payload，所有外部行动保留人类确认。
8. 所有阶段完全离线验证核心行为，不依赖真实目标站点。

## 5. 模块依赖

```text
Contract Freeze
  ↓
ACQ-1A + H0（Source / State / NetworkPolicy / Budget）
  ↓
ACQ-1B + D-static（RSS / Native / Scrapling parser / Quality）
  ↓
ACQ-1B-dynamic + H-browser（隔离 Browser）
  ↓
ACQ-1C（Router）
  ↓
ACQ-1E（Controlled Discovery）
  ↓
ACQ-1F（Version Evidence / Change）
  ↓
ACQ-1G（Opportunity）
  ↓
ACQ-1H Final（恢复 / 安全 / 性能 / 全回归）
```

不得跳过 H0 直接引入 Browser，不得跳过版本证据直接实现 Change Intelligence。

## 6. Acquisition 状态

CollectionRun 保留：

```text
queued → running → succeeded | partial | failed
```

ACQ-1 增加运行租约语义：

- `claimed_at`、`heartbeat_at`、`lease_expires_at`、`worker_id`；
- Worker 定期续租；超过租约且未完成的 run 由 recovery dispatcher 加锁恢复；
- 重试使用既有 child run，不改写原 run；
- 旧 Worker 只能以 claim token 条件写入，不能覆盖恢复后的新 Worker。

Source Health 固定为：

```text
healthy | degraded | failing | blocked | unsupported
```

一次失败不得永久禁用 Source。`blocked` 只表示访问控制或 SitePolicy 阻止，`unsupported` 表示能力不支持；两者不得自动升级为绕过模式。

## 7. Change 状态

Change Type 固定为：

```text
created | unchanged | content_changed | metadata_changed
structure_changed | removed
```

每次观测形成 `ChangeEvent`。Snapshot 只在新的内容/metadata/structure 指纹组合出现时创建；`unchanged` 可引用既有 Snapshot。只有 `created` 或达到 materiality 门槛的 `content_changed` 默认生成 RawItem。

## 8. 迁移策略

所有 ACQ-1 Schema 采用：

```text
expand → backfill → dual-read/write → switch → contract
```

- 不直接删除 BE-8 索引、列或枚举。
- 首阶段只新增可空列、表、索引和兼容 API 字段。
- 旧 RawItem 回填为一个 Artifact 与初始 Snapshot。
- writer 切换后，新 RawItem 以 `snapshot_id` 唯一；旧 `(source_id, external_id)` 唯一约束仅保留给 `snapshot_id IS NULL` 的 legacy 行。
- contract 步骤只能在回填、双写、回归和回滚窗口验收后执行。
- 含多版本数据时不得执行会丢失 Snapshot/Change 的 downgrade；运行回滚优先回退应用、保留扩展 Schema。

## 9. 兼容性

- 现有 RSS、单页 URL、CollectionRun、RawItem、Document、Analysis、Memory、Notification 接口保持兼容。
- `source_type=rss|url` 继续有效；`api` 不在 ACQ-1 开放创建。
- Source 新字段均有 legacy 默认值：`generic_web / auto / single_page / acq-source-v1`。
- 新增 `radar_type=opportunity` 属于显式 enum 变更，必须迁移、OpenAPI 和客户端兼容测试。
- WebSocket 现有三类事件不修改；ACQ-1 新事实先通过 REST 暴露。新增在线事件必须另行 ADR。

## 10. 阶段停点

每个实施阶段必须：开发 → 单次最终全量门禁 → commit/push/PR → Backend 向总控报告 → STOP。总控独立 Review 后才签发下一阶段。任何 P0/P1、契约漂移或不可重复启动均阻断下游。
