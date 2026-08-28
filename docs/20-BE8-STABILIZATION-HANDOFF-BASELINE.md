# FlowTracer BE-8 稳定化与前端交接基线

状态：Frozen for admission
基准：`main@d30fcfd02d4d62e7b16282a004a74a19c8f7685f`

## 1. 目标

BE-8 是 Alpha 后端最后一个 Phase。它验证并固化 BE-1 至 BE-7 已交付能力，输出稳定契约与前端交接材料；不增加新业务范围。

## 2. 范围

- 完整离线闭环：注册、Radar、Source、采集、清洗、Analysis、Embedding、Intelligence、Bookmark/Memory、Notification。
- WebSocket 在线事件与断线后 REST 恢复。
- 全量回归、并发/幂等/权限/SSRF/秘密扫描。
- OpenAPI JSON 导出、契约校验与前端接口说明。
- 空库迁移循环、Compose 四服务、Celery/Beat、live/ready、同镜像非 root。
- 启动、环境变量、迁移、测试、故障恢复、已知限制与轻量性能基线。

## 3. 冻结边界

不得新增或修改数据库 Schema/迁移、公开 REST Endpoint、WebSocket 事件类型、评分规则、Provider、Pipeline 状态和依赖。不得开发前端、生产部署、Release、深爬、模型 Router、团队权限或 v0.2+ 能力。发现必要变化必须停点并提交 ADR。

## 4. 离线闭环

测试必须使用 Fake Analysis/Embedding Provider、本地 RSS/HTML Fixture、隔离 PostgreSQL/Redis，不访问公网。闭环必须验证事实状态、幂等重放、通知资格、WebSocket best-effort 信号以及通过 REST 恢复最终事实。

## 5. OpenAPI 与交接包

交接包必须包含：
- 可重复生成并校验的 OpenAPI JSON。
- Endpoint、请求/响应、分页、枚举、错误码与示例 Payload。
- Access/Refresh Token 生命周期与鉴权规则。
- WebSocket Header 鉴权、Envelope、事件类型、4401/1013 与 REST 恢复。
- 环境变量矩阵、Quick Start、迁移、测试、Worker/Beat 和故障排查。
- Alpha 已知限制与非目标。

## 6. 质量门禁

- locked sync、Ruff、format、Mypy、完整 Pytest，覆盖率 >=85%。
- 空库 upgrade head、downgrade base、再次 upgrade head、Alembic check。
- Compose config、API/Worker 同镜像 UID 10001、Celery pong、Beat 自动调度、live/ready。
- 无公网测试；日志/响应/交接样例无密码、Token、Key、连接串、正文、Prompt 或向量泄漏。
- P0/P1 为零；P2 有处置或书面接受；启动与闭环可重复。

## 7. 完成条件

Backend 提交精确 commit、迁移/零漂移、测试、运行态、安全、OpenAPI、交接包、性能与风险报告并停点。总控独立验收通过并合并后，BE-8 才完成；Frontend 仍需独立准入。
