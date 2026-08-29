# FlowTracer ACQ-1 Preflight 验收

状态：ACCEPT（仅接受 Preflight 结论）

核验基准：`main@5a81248c15ea6ce8a7543b7926df7d061f5022dd`

正式实现准入：NO

Frontend 准入：NO

## 已核验事实

- ACQ-1 Preflight 在独立 worktree 上以只读方式完成，最终 HEAD 与 `origin/main` 一致，工作树干净。
- 未修改文件、安装依赖、启动 Docker/Browser、运行全量测试、创建开发分支或访问真实目标站点。
- 现有链路为 SafeFetcher → RSS/HTML parser → RawCandidate → RawItem；调度、幂等和补偿基于 PostgreSQL 锁/唯一约束、Celery Beat 与 Redis。
- 当前 CPython 基线为 3.13，锁文件未包含 Scrapling、Playwright 或其他 Browser runtime；Compose 没有 Browser 隔离队列或资源边界。

## 总控结论

Preflight 的盘点、风险识别和分期建议完整，准予进入 ACQ-1 Contract Freeze；不准予直接开始 ACQ-1A～H 编码。

## 必须先关闭的阻塞

### P0 安全边界

- Browser/Scrapling fetcher 不得绕过 SafeFetcher 的 SSRF、DNS rebinding、redirect、协议/端口和响应预算控制。
- 禁止 stealth 被解释为 CAPTCHA、登录墙、付费墙或访问控制绕过。

### P1 契约与可靠性

- 当前 `(source_id, external_id)` 唯一约束与三层去重会把同一条目的内容更新判为重复，无法承载可追溯 Change Intelligence。
- Source `config` 无类型且由公开 API 返回，不能保存秘密或高频运行状态。
- running CollectionRun 缺少 lease/heartbeat/stale recovery。
- Browser 与普通 Worker 尚未隔离，存在资源耗尽与攻击面扩大风险。
- Opportunity Radar、Opportunity Score、Action Payload 和人类确认边界尚未形成冻结契约。
- Browser 二进制、系统依赖和 Scrapling extras 尚未进入可重复锁定构建体系。

## 已接受的架构方向

- Source Profile 使用少量稳定列、版本化 JSON Profile 与独立运行状态，秘密不进入公开 config。
- 新增 SourceArtifact / AcquisitionSnapshot / ChangeEvent 版本证据层；RawItem 继续作为既有 Intelligence Pipeline 的兼容入口。
- Browser 使用独立镜像、专用队列、低并发和受控出口；安全策略不可因 fallback 降级。
- Opportunity 使用独立版本化评分与 Action Payload，不复用通用 Radar Score 语义，不执行投标、合同或资金动作。
- Schema 采用 expand/backfill/switch/contract，不能直接破坏 BE-8 数据和唯一约束。
- ACQ-1 必须拆分独立阶段逐一验收，不使用单一大型实现分支。

## 下一步

完成 Contract Freeze 文档、ADR、迁移/API 兼容方案和分期任务包；经独立 Review 与 PR 合并后，从 ACQ-1A + H0 开始逐阶段准入。
