# FlowTracer Alpha v0.1 BE-1 阶段准入许可

## 1. 准入结论

- Phase：BE-1 基础骨架与本地基础设施
- Stage Gate：**通过，准入**
- 签发日期：2026-08-24
- 生效条件：本准入文档通过 Pull Request 合并到 `main`

BE-0 已通过验收，BE-1 工程基线已经冻结，Docker Desktop / WSL 2 环境已经完成复核。总控批准 Backend 在本准入 PR 合并后正式开始 BE-1。

## 2. 环境复核证据

- WSL：2.7.12.0；Docker Desktop 使用 WSL 2。
- Docker CLI：29.7.2。
- Docker Compose：v5.4.0。
- Docker Server：29.7.2，Linux/amd64。
- `docker run --rm hello-world`：通过。
- 验证镜像 digest：`sha256:5dd0d3e6e255913fc30f90b9f2b1d359cc2cbdb48090cc4b65f1676e203243cc`。

## 3. Backend 开工指令

- 从已包含本许可的最新 `main` 创建新分支 `feat/be-1-foundation`。
- 严格遵循 `docs/04-BE1-ENGINEERING-BASELINE.md` 和 `docs/10-BACKEND-WORK-PACKAGE.md`。
- 只实施 BE-1：工程骨架、配置、日志、数据库/Celery 连接、Compose、健康检查、空迁移和测试框架。
- 完成后必须 commit、push、创建 Pull Request，并提交 BE-1 阶段报告。
- 总控检查变更、commit、测试、迁移、契约和跨模块影响后，才决定是否授权合并。

## 4. 禁止事项

- 不得实现 Auth/User、Radar、Source 或其他 BE-2+ 业务功能。
- 不得进入 Frontend、Integration 或 Release 开发。
- 不得直接 push 到 `main`，不得绕过 Pull Request。
- 不得修改其他角色的 worktree。
- 不得引入未批准的数据库、消息系统、微服务或 Alpha 范围外能力。

## 5. BE-1 停点

BE-1 完成后必须停止，并按任务包固定格式提交：

- 变更文件与 commit SHA；
- 数据库迁移及升级、降级、再次升级结果；
- 测试、静态检查和格式检查结果；
- Docker Compose 启动与健康检查结果；
- 接口或契约变化；
- 风险、遗留和下一阶段建议。

本许可不包含 BE-2 准入。BE-1 PR 合并也不自动授予 BE-2、Frontend 或 Integration 开工权。

## 6. GitHub 控制说明

当前私有仓库套餐无法启用 GitHub Branch Protection API。项目继续以人工门禁执行：任何 PR 未经总控明确 Review 和合并授权，GitHub 管理角色不得合并。
