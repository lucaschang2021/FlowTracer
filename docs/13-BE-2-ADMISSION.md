# FlowTracer Alpha v0.1 BE-2 阶段准入许可

- Phase：BE-2 数据模型、迁移、认证与用户
- 状态：批准（本文件所在 PR 合并后生效）
- 前置验收：BE-1 PR #4 已通过总控验收并合并至 `main`

## 1. 正式范围

- 落地 `docs/05-BE2-DATA-AUTH-BASELINE.md` 冻结的全部 Alpha 关系模型、约束、索引、删除策略和 Alembic 迁移。
- 实现注册、登录、Refresh 轮换、Logout、Access Token 鉴权、`GET/PATCH /users/me`。
- 补齐 Argon2id、JWT/Refresh 配置、OpenAPI、安全与数据库集成测试。
- 只建立后续阶段实体模型，不实现 BE-3+ 的 CRUD、采集、AI、向量检索、通知或 WebSocket 业务。

## 2. Git 与交付

- Backend 工作分支：`feat/be-2`；必须从最新 `origin/main` 创建或 fast-forward 对齐。
- 完成后 commit、push、创建 PR；Backend 不得自行 merge。
- 阶段报告必须包含 commit SHA、PR、迁移链、测试结果、OpenAPI/契约变化和风险。
- 完成后立即停止，并直接向总控任务汇报；未经总控书面批准不得进入 BE-3。

## 3. 阶段禁令

- 不修改冻结的公开契约、评分或 Pipeline；发现冲突先停点汇报。
- 不引入新数据库、微服务、OAuth、RBAC 或 Alpha 范围外能力。
- 不提交真实 Secret、Token、用户数据或正文样本。
- 不批准 Frontend、Integration 或 Release 开工。
