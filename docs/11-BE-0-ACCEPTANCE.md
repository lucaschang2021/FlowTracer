# FlowTracer Alpha v0.1 BE-0 阶段验收报告

## 1. 验收结论

- Phase：BE-0 工程盘点与实施计划
- 验收结果：**通过**
- Stage Gate：**BE-1 暂不准入**
- 验收日期：2026-08-23

BE-0 已按任务包要求完成只读盘点、工具链核验、目录规划、依赖建议、预计变更范围和风险识别；未安装依赖、未编写业务代码、未创建数据库迁移，符合阶段停点要求。

BE-0 通过只代表工程盘点合格，不自动授予 BE-1 开工许可。

## 2. 独立复核结果

- 工作区为 `D:\FlowTracer`，Git 已初始化在 `main`，尚无提交和远程。
- 当前项目文件均未跟踪，必须继续按用户已有资产保护。
- 目录骨架与报告一致；后端仅有占位文件和 README，无业务实现。
- PowerShell 7.6.4、Python 3.13.7、pip 26.2.1、Git 2.55.0.windows.3、ripgrep 15.2.0 可用。
- uv、Poetry、Docker、Docker Compose、PostgreSQL 客户端和 Redis 不可用或不在 PATH。
- 本机 5432、6379 端口未监听，pgvector 无法验证。
- Git 所有权检查会触发 `dubious ownership`；复核仅使用单次 `git -c safe.directory=D:/FlowTracer`，未修改全局配置。
- Backend 报告所称“交付看板仍标记 M0 进行中”与复核时工作区不一致；当前看板已标记 M0 初步冻结完成、BE-0 已准入。

## 3. BE-1 准入前置条件

以下条件全部满足后，由总控另行签发 BE-1 许可：

1. 总控冻结 Python 基准版本、依赖管理与锁文件方案。
2. 总控冻结 PostgreSQL/pgvector、Redis 和 Docker Compose 的版本与端口矩阵。
3. 可用的 Docker / Docker Compose 环境已准备并可由 Backend 验证。
4. BE-1 所需的健康检查响应、readiness 判定、配置和日志最低契约已补齐。
5. Git 所有权问题具有不修改用户全局配置的可执行处理约定。

## 4. 契约缺口分期

### BE-1 前必须冻结

- Python、依赖管理和锁文件方案。
- Docker 镜像、端口、服务名和健康检查矩阵。
- `/api/v1/health/live`、`/api/v1/health/ready` 响应及 readiness 判定。
- 配置加载、统一错误响应和结构化日志最低字段。

### BE-2 前必须冻结

- Access/Refresh Token 生命周期、JWT 算法与轮换规则。
- 数据库字段类型、可空性、索引、外键删除策略和数据保留规则。
- Auth/User 精确请求响应 Schema、状态码和错误码。

### 对应后续阶段前冻结

- BE-3：Radar/Source 筛选、排序、精确 Schema 和错误码。
- BE-4：采集部分失败、重试终态和死信处理。
- BE-5：AI Provider、模型、Prompt 和严格输出 JSON Schema。
- BE-6：Embedding Provider、切块参数、Top-K 和相似度指标。
- BE-7：WebSocket Token 传递、事件 `data` Schema 和事件顺序规则。

## 5. 变更与测试

- 业务代码：无变更。
- 数据库迁移：无。
- 项目测试：未运行；当前无业务代码和测试套件。
- 本报告及总控状态同步不构成 BE-1 开工许可。
