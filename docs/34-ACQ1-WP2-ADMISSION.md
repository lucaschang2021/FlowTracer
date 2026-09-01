# FlowTracer ACQ-1 WP-2 准入

状态：本控制提交合并到 `main` 后生效

补充条件：WP-2 已由 PR #35 合并准入；后端开工澄清停点必须等 `docs/35-ACQ1-WP2-CONTRACT-ADDENDUM.md` 与 ADR-028 合并后才可续跑，不重建既有干净分支。

前置基准：`main@9f019072bb71a43e1e2253f2f55d217865d2e239`

执行角色：现有 Backend 角色

目标分支：`feat/acq-1b-static`

Phase：WP-2 / ACQ-1B + D-static

## 开工输入

Backend 只读取：

- `docs/CURRENT-GATE.md`
- 本文件
- `docs/33-ACQ1-WP1-ACCEPTANCE.md`
- `docs/22-ACQ1-MASTER-BASELINE.md`
- `docs/23-ACQ1-ACQUISITION-CONTRACT.md`
- `docs/25-ACQ1-ACCEPTANCE.md`
- `docs/29-ACQ1-WORK-PACKAGES.md` 的通用规则与 WP-2
- `docs/32-ACQ1-WP1-CONTRACT-ADDENDUM.md`
- `docs/35-ACQ1-WP2-CONTRACT-ADDENDUM.md`
- ADR-022、ADR-023、ADR-027、ADR-028
- 本阶段直接涉及的 Backend 代码、依赖、Dockerfile 与测试

## 授权范围

- 完成统一 `AcquisitionBackend` / `AcquisitionRequest` / `AcquisitionResult` 的静态 Adapter 边界，使 RawItem writer 不感知 RSS、Native 或 static parser 的具体实现。
- 保持并接入现有 RSS 与 Native adapter；新增 Scrapling **静态解析器 adapter**，只处理已由安全 fetcher 获取的本地响应字节/文本。
- 按 WP-2 Addendum 实现 quality v1、通用 family extractor、内部解析证据与既有 Attempt/Run 质量列；所有决策保持确定性、可解释和离线可测。质量仅观测，不改变 legacy writer/去重/终态，不引入 family 专用领域事实。
- 精确锁定 Python 3.13 兼容的静态解析依赖及许可证证据；更新 `pyproject.toml`、`uv.lock`、Backend 文档与必要的 Dockerfile 静态依赖。
- 允许文件限于 `backend/app/services/acquisition*`、`backend/app/adapters/acquisition/`、`backend/app/services/extraction*`、直接相关 schemas/tasks、对应 Backend tests、依赖清单/锁文件、Backend 文档；Dockerfile 仅允许静态依赖构建所需的最小变更。

## 安全边界

- Scrapling 只能作为无网络 static parser；不得调用其 fetcher、browser、stealth、proxy、session、download 或任何网络接口。
- 所有 HTTP(S) 获取继续且只能经过 WP-1 已验收的 SafeFetcher/NetworkPolicy；parser 不得接收凭据、Cookie、Authorization、Source secret 或连接配置。
- 测试只使用本地 RSS/HTML fixtures 与注入字节，不访问真实目标站点或公网。
- 解析失败、质量不足和不支持的 family 必须产生安全、限长、无正文/堆栈泄漏的结果；不得自动升级到 Browser。

## 明确禁止

- 不安装 Playwright、Chromium 或 Scrapling Browser/fetcher extras；不新增 Browser 镜像、worker、queue、egress proxy 或动态渲染。
- 不实现 Router fallback、Circuit/AutoThrottle 执行、Discovery、Change Intelligence、Opportunity 或外部动作。
- 不修改公开 REST/WebSocket 契约、数据库 Schema/migration、RawItem 版本语义、Intelligence/Memory/Notification 业务语义。
- 不进入 Frontend、Integration 或 Release；不扩大普通 API/Worker 权限。

## 必须验收

- RSS/Native 全量回归；相同 fixture 经现有与统一 Adapter 的事实结果等价。
- static parser 对 HTML 结构、正文/标题/作者/时间/canonical/metadata 的确定性提取及失败边界有表格测试。
- quality v1 的全部冻结阈值、边界值、缺失字段、噪声页面和 family extractor 均有离线证据。
- AcquisitionAttempt backend/status/质量/安全错误记录正确；重复投递、并发和既有 lease recovery 不漂移。
- 证明 parser 调用期间无网络请求；SafeFetcher SSRF、redirect、大小、压缩与秘密边界回归通过。
- `uv.lock` 精确可复现，依赖许可证与 Python 3.13/Debian Bookworm 兼容；最终镜像仍为非 root，API/Worker 同镜像。
- 最终 commit 只执行一次 Ruff、format、Mypy、完整 Pytest/覆盖率、OpenAPI check、Compose config 与必要运行态门禁；无 Schema 时 `alembic check` 必须零漂移。

## 交付与停点

Backend 完成后按 `docs/29-ACQ1-WORK-PACKAGES.md` 的阶段报告格式直接向总控汇报，并立即 STOP。未经书面验收不得 push/PR/merge，也不得进入 WP-3；WP-3..WP-8 与 Frontend 继续未准入。
