# FlowTracer ACQ-1 Contract Freeze 准入

状态：已生效

前置基准：`main@5a81248c15ea6ce8a7543b7926df7d061f5022dd`

生效基准：`main@76e86c375cb769bc3716614d8d3f1cb470e4955f`

控制 PR：#29（已 Review 并合并）

目标：由总控在主工作区执行架构与契约文档冻结

## 授权范围

- 建立 `22-ACQ1-MASTER-BASELINE.md`、`23-ACQ1-ACQUISITION-CONTRACT.md`、`24-ACQ1-OPPORTUNITY-RADAR.md`、`25-ACQ1-ACCEPTANCE.md`。
- 新增或修订 ADR，冻结 Source Profile、AcquisitionBackend/Result、版本证据、Browser NetworkPolicy、Discovery、Opportunity 与评分。
- 设计 Schema、迁移链、公开 API/OpenAPI、错误码、枚举、Pipeline 兼容与回滚方案。
- 将 ACQ-1 拆为独立实施阶段，形成每阶段任务包、依赖、验收和停点规则。
- 更新 CURRENT-GATE、交付看板和相关文档链接草案。

## 明确禁止

- 不修改 Backend/Frontend/infra 业务实现、模型、迁移、依赖锁文件、Compose 或 OpenAPI 快照。
- 不安装依赖、启动 Docker/Browser、访问真实目标站点或运行全量测试。
- 不创建 ACQ-1 实现分支，不 push/PR/merge，不进入 Frontend。
- 不以文档冻结代替后续每个实现阶段的独立 Stage Gate。

## 冻结要求

- 所有新增 Schema/API/enum 必须说明兼容性、迁移顺序、downgrade 和 BE-8 回归影响。
- Browser 网络请求必须共享统一 NetworkPolicy；子资源、iframe、XHR、WebSocket 和下载均在策略内。
- Opportunity Score 公式、版本、缺失值、货币/预算和通知映射必须确定性定义。
- Action Payload 只用于人类审阅和未来外部执行系统，不包含自动投标或承诺能力。
- 测试策略必须完全离线，并覆盖 SSRF、资源耗尽、并发、重放、迁移和 BE-1..BE-8 回归。

## 停点

Contract Freeze 文档完成后必须提交变更范围、决策、未决问题和建议的首个实现阶段，然后停止。总控 Review 和控制 PR 合并前，ACQ-1 正式实现仍未准入。
