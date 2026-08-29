# FlowTracer 当前阶段闸门

更新时间：2026-08-29。

- 当前稳定基准：`main@76e86c375cb769bc3716614d8d3f1cb470e4955f`；ACQ-1 Contract Freeze 准入 PR #29 已合并。
- 已完成：ACQ-1 Preflight 已通过总控审查，结论记录于 `docs/27-ACQ1-PREFLIGHT-ACCEPTANCE.md`。
- 当前阶段：ACQ-1 Contract Freeze 完成候选，等待总控复核与控制 PR 合并。
- 准入：仅允许 Review 本分支的架构文档、ADR、Schema/Migration 设计、公开 API/OpenAPI 草案、Browser NetworkPolicy、Opportunity 评分和分期任务包。
- 未准入：ACQ-1 业务代码、依赖安装或升级、数据库迁移、公开 API 实现、Scrapling/Browser 运行、Frontend、Integration 与 Release。

Contract Freeze Review 只读取：本文件、`docs/02-DELIVERY-BOARD.md`、`docs/22-ACQ1-MASTER-BASELINE.md`、`docs/23-ACQ1-ACQUISITION-CONTRACT.md`、`docs/24-ACQ1-OPPORTUNITY-RADAR.md`、`docs/25-ACQ1-ACCEPTANCE.md`、ADR-022..026、`docs/29-ACQ1-WORK-PACKAGES.md` 与本次 diff。

必须冻结：

- Universal Source Contract：强类型 Source Profile、公开/秘密配置边界、运行状态与健康状态；
- Acquisition Contract：统一 AcquisitionBackend/Request/Result/Attempt、Router trace、预算与错误分类；
- Version Evidence：SourceArtifact、AcquisitionSnapshot、ChangeEvent 与 RawItem 下游兼容；
- Browser NetworkPolicy：受控出口、DNS/redirect/子资源校验、队列/镜像隔离和资源上限；
- Controlled Discovery：scope、frontier、checkpoint、Site Policy 与全局/域名预算；
- Opportunity Contract：Radar Family、Opportunity/Freelance Profile、评分版本、Action Payload 和人类确认边界；
- Migration/OpenAPI：expand/backfill/switch/contract 方案、兼容字段、枚举演进与前端冻结影响；
- ACQ-1A 至 ACQ-1H 的独立实施阶段、每阶段验收与回滚点。

Preflight 已确认的阻塞不得在实现中隐式解决：现有 RawItem 唯一/去重语义无法保存版本；Source config 无类型且公开返回；running CollectionRun 无 stale recovery；Browser 可能绕过 SafeFetcher；Opportunity/评分未冻结；Browser 二进制和 Scrapling extras 未进入锁定构建体系。

下一步：总控完成文档一致性复核并提交控制 PR。该 PR 合并后仍需单独签发 WP-1（ACQ-1A+H0）准入，再直接向现有 Backend 下达任务；不得一次性准入整个 ACQ-1，Frontend 继续未准入。
