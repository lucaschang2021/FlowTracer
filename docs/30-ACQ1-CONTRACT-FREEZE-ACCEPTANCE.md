# FlowTracer ACQ-1 Contract Freeze 验收

状态：ACCEPT

核验基准：`main@f7e7d113faa70c0daa6be33c6e6ce5721e919e97`

控制 PR：#30（已 Review 并合并）

正式实现准入：仅允许后续按独立工作包逐阶段签发

Frontend 准入：NO

## 已冻结

- ADR-022..026：Source Contract、Acquisition/Version Evidence、Browser NetworkPolicy、Controlled Discovery、Opportunity 与人类确认边界。
- `23-ACQ1-ACQUISITION-CONTRACT.md`：强类型 Source Profile、运行状态、统一 Acquisition Contract、版本证据、租约恢复、迁移/API 兼容方案。
- `24-ACQ1-OPPORTUNITY-RADAR.md`：Opportunity/Freelance Profile、Hard Filter、确定性 score v1、Notification 兼容关联与 Action Payload。
- `25-ACQ1-ACCEPTANCE.md`：离线安全、并发、迁移、回归、运行态和阶段关闭门禁。
- `29-ACQ1-WORK-PACKAGES.md`：WP-1 至 WP-8 的依赖、授权范围、验收与回滚点。

## 总控结论

Contract Freeze 范围完整，Preflight 中识别的 P0/P1 已获得明确设计处置；允许签发 WP-1（ACQ-1A + H0），但不允许以本验收一次性准入整个 ACQ-1。

## 约束

- 实现发现 Schema、API、Pipeline、评分或 Browser NetworkPolicy 需要偏离冻结契约时必须立即 STOP，并提交 ADR/契约变更请求。
- Browser、Scrapling、Router、Discovery、Change Intelligence、Opportunity 和 Frontend 均不属于 WP-1。
- WP-1 完成后 Backend 必须提交阶段报告并停止，未经总控验收不得进入 WP-2。
