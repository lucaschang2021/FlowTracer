# FlowTracer Alpha v0.1 BE-1 工程基线

## 1. 文档地位

- 状态：Accepted for BE-1 admission preparation
- 生效日期：2026-08-23
- 适用范围：BE-1 基础骨架与本地基础设施
- 变更控制：影响本文件公开契约、运行拓扑或依赖主版本的变化必须由总控批准并记录 ADR。

本文件补齐 BE-1 开工前所需的工程规格，不授予 BE-1 开工许可。Backend 仍须等待交付看板明确标记“已准入”。

## 2. Python 与依赖管理

### 2.1 Python 基准

- 运行时：CPython 3.13，项目声明 `requires-python = ">=3.13,<3.14"`。
- 仓库使用 `.python-version` 固定 `3.13` minor line；`uv.lock` 固定实际解析版本。
- API 和 Worker 的参考运行环境为 Linux 容器；Celery Worker 不以原生 Windows 作为验收环境。
- Backend 可在 Windows 主机运行 lint 和单元测试，但 Compose 内的 Linux 环境是最终本地验收基准。
- 后端基础镜像使用 `python:3.13-slim-bookworm`，BE-1 报告必须记录实际拉取镜像的 digest。

选择 Python 3.13 的依据：当前工作区已有 3.13.7；Celery 5.5、Scrapling 和 asyncpg 的官方元数据均声明支持 Python 3.13。Celery 不正式支持 Windows，因此 Worker 固定在 Linux 容器内运行。

### 2.2 依赖与锁文件

- 依赖管理工具：uv。
- 项目元数据：`backend/pyproject.toml`。
- 唯一正式锁文件：`backend/uv.lock`，必须进入版本控制，不得手工编辑。
- 开发和 CI 使用 `uv sync --locked`；锁文件不一致时必须失败，不得静默更新。
- 不并行维护 Poetry lock、手写冻结版 `requirements.txt` 或 pipenv 锁文件。
- 如需导出部署清单，由 `uv.lock` 生成，不作为依赖事实源。

### 2.3 依赖分期

BE-1 可引入：

- API/config：FastAPI、Uvicorn、Pydantic 2、pydantic-settings。
- Database：SQLAlchemy 2.x async、asyncpg、Alembic、pgvector Python adapter。
- Tasks：Celery 5.x Redis extra、redis-py。
- Logging：一个结构化日志实现，由 Backend 在不改变日志字段契约的前提下选择。
- Test/quality：Pytest、pytest-asyncio、pytest-cov、HTTPX、Ruff、Mypy 及必要类型 stubs。

后续阶段再引入：

- BE-2：Argon2、JWT 和 email validation。
- BE-4：feedparser、Scrapling、HTML 清洗库及采集测试辅助库。
- BE-5：经批准的 AI Provider SDK；业务层必须先依赖 Provider 接口。
- BE-6：Embedding Provider SDK（若与 AI Provider 不同）。

直接依赖使用兼容的主版本约束，精确版本由 `uv.lock` 固定。不得在 BE-1 为未来阶段提前安装浏览器、AI SDK 或未使用的依赖。

## 3. 本地基础设施矩阵

| 组件 | BE-1 基线 | 服务名 | Host 端口 | 健康检查 |
| --- | --- | --- | --- | --- |
| API | 同一 Backend 镜像 | `api` | `8000` | HTTP `/api/v1/health/live` |
| Worker | 同一 Backend 镜像 | `worker` | 不发布 | Celery ping 或等价探活 |
| PostgreSQL + pgvector | `pgvector/pgvector:0.8.6-pg16-bookworm` | `postgres` | `5432` | `pg_isready` |
| Redis | `redis:7.4.11-alpine3.21` | `redis` | `6379` | `redis-cli ping` |

- Compose 文件：`infra/compose.yaml`。
- API 与 Worker 使用同一个 `backend/Dockerfile` 构建，命令不同，不复制两套镜像定义。
- PostgreSQL 使用命名卷持久化；Redis 在 Alpha 本地环境也使用命名卷。
- `api` 和 `worker` 必须通过 `depends_on.condition: service_healthy` 等待 PostgreSQL 与 Redis 健康。
- Compose 不使用 `latest`、浮动 major tag 或宿主机安装的 PostgreSQL/Redis 作为验收基准。
- Compose 项目名固定为 `flowtracer`；容器名不硬编码，以避免多工作区冲突。
- 仅用于本地开发；不得包含生产凭据或生产部署假设。

## 4. 配置矩阵

| 环境变量 | 示例/默认 | 必需 | 说明 |
| --- | --- | --- | --- |
| `FLOWTRACER_ENV` | `development` | 是 | `development | test`；Alpha 不定义生产部署 |
| `FLOWTRACER_LOG_LEVEL` | `INFO` | 是 | 标准日志级别 |
| `FLOWTRACER_APP_VERSION` | `0.1.0` | 是 | 健康检查返回版本 |
| `FLOWTRACER_API_HOST` | `0.0.0.0` | 是 | 容器监听地址 |
| `FLOWTRACER_API_PORT` | `8000` | 是 | API 端口 |
| `DATABASE_URL` | `postgresql+asyncpg://...@postgres:5432/flowtracer` | 是 | API/Worker 异步连接 |
| `REDIS_URL` | `redis://redis:6379/0` | 是 | 通用 Redis 连接 |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | 是 | Celery Broker |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/1` | 是 | Celery Result Backend |
| `POSTGRES_DB` | `flowtracer` | Compose | 本地数据库名 |
| `POSTGRES_USER` | `flowtracer` | Compose | 本地数据库用户 |
| `POSTGRES_PASSWORD` | 仅示例值 | Compose | 真实值不得提交 |

- `.env.example` 只保存无敏感示例；真实 `.env` 已由 `.gitignore` 排除。
- 配置启动失败必须给出变量名和安全化原因，不得打印变量值。
- 测试配置不得连接开发数据库；测试数据库名必须显式包含 `_test`。

## 5. 健康检查契约

### 5.1 Liveness

`GET /api/v1/health/live`

- 无鉴权。
- 不访问数据库、Redis 或外部网络。
- 正常时返回 HTTP 200：

```json
{
  "status": "ok",
  "service": "flowtracer-api",
  "version": "0.1.0"
}
```

### 5.2 Readiness

`GET /api/v1/health/ready`

- 无鉴权。
- 并行检查 PostgreSQL `SELECT 1` 和 Redis `PING`。
- 单项超时不超过 2 秒，总响应不超过 5 秒。
- 全部正常时返回 HTTP 200：

```json
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "redis": "ok"
  }
}
```

- 任一依赖异常时返回 HTTP 503，并遵循统一错误格式：

```json
{
  "error": {
    "code": "service_not_ready",
    "message": "Service dependencies are not ready",
    "details": {
      "checks": {
        "database": "ok",
        "redis": "unavailable"
      }
    },
    "request_id": "uuid"
  }
}
```

- `details` 只允许 `ok | unavailable | timeout`，不得泄露连接串、主机异常堆栈或凭据。

## 6. 错误、请求追踪与日志

- API 的每个请求接受或生成 `X-Request-ID`；响应回传同名 Header。
- 内部 `request_id` 必须是 UUID；非法外部值应被替换，不直接信任。
- 统一错误响应继续使用 `{error: {code, message, details, request_id}}`。
- 结构化日志最低字段：`timestamp`、`level`、`service`、`environment`、`event`、`message`、`request_id`、`correlation_id`。
- HTTP 访问日志另含：`method`、`path`、`status_code`、`duration_ms`。
- Celery 日志另含：`task_name`、`task_id`、`correlation_id`、`attempt`。
- 时间使用 UTC ISO 8601；日志输出到 stdout/stderr，不在容器内写持久日志文件。
- 禁止记录密码、Token、API Key、完整连接串、完整正文、请求 Authorization Header。

## 7. BE-1 测试与质量门槛

BE-1 至少提供以下可重复命令，并在报告中给出实际结果：

```text
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
```

必须覆盖：

- Liveness 正常响应。
- Readiness 的全健康、数据库失败、Redis 失败和超时。
- `request_id` 生成、传递和非法输入替换。
- 统一错误格式和敏感信息不泄露。
- 配置缺失时 fail-fast。
- Celery 探活任务可由 Worker 执行。
- 空数据库迁移升级、降级、再次升级成功。
- Compose 从空环境启动后 PostgreSQL、Redis、API、Worker 均健康。

## 8. BE-1 外部前置条件

在正式准入前必须由总控复核：

```text
docker version
docker compose version
docker run --rm hello-world
```

Windows 基准使用 Docker Desktop 的 Linux containers + WSL 2 backend。当前机器尚未提供可用的 WSL 2/Docker 环境，因此 BE-1 仍未准入。

Git 所有权异常不通过修改全局 `safe.directory` 解决。自动化读取如确有需要，仅可使用单次 `git -c safe.directory=D:/FlowTracer ...`；长期修复由用户在宿主账户下处理目录所有权。

## 9. 参考依据

- uv 项目与锁文件：https://docs.astral.sh/uv/concepts/projects/sync/
- uv Python 管理：https://docs.astral.sh/uv/concepts/python-versions/
- Celery Python/平台支持：https://pypi.org/project/celery/
- Scrapling Python 要求：https://pypi.org/project/scrapling/
- asyncpg 支持矩阵：https://pypi.org/project/asyncpg/
- pgvector Docker 标签：https://github.com/pgvector/pgvector
- Redis 官方镜像标签：https://hub.docker.com/_/redis
- Compose 健康依赖顺序：https://docs.docker.com/compose/how-tos/startup-order/
- Docker Desktop Windows 要求：https://docs.docker.com/desktop/setup/install/windows-install/
