# FlowTracer 当前阶段闸门

更新时间：2026-08-30。

- 当前稳定基准：`main@9f019072bb71a43e1e2253f2f55d217865d2e239`；ACQ-1 WP-1 PR #33 已独立 Review 并合并。
- 已完成：ACQ-1 Preflight、Contract Freeze 与 WP-1（ACQ-1A + H0）已通过总控验收；WP-1 结论见 `docs/33-ACQ1-WP1-ACCEPTANCE.md`。
- 当前阶段：ACQ-1 WP-2（ACQ-1B + D-static）准入控制候选，尚未生效。
- 准入：本控制提交合并到 `main` 后，允许现有 Backend 从最新 main 创建 `feat/acq-1b-static`，按 `docs/34-ACQ1-WP2-ADMISSION.md` 实现 WP-2。
- 未准入：本控制提交合并前的 WP-2 实现；WP-3..WP-8；Browser、Router、Discovery、Change、Opportunity；Frontend、Integration 与 Release。

WP-2 开工只读取：本文件、`docs/34-ACQ1-WP2-ADMISSION.md`、`docs/33-ACQ1-WP1-ACCEPTANCE.md` 及其中列出的直接输入和本阶段相关 Backend 文件。

WP-2 必须交付：

- 统一静态 Acquisition Adapter，保持 RSS/Native 事实等价；
- 只消费本地响应的 Scrapling static parser adapter，不具备 fetch/browser 能力；
- quality v1、family extractor、解析证据与 Attempt 记录；
- Python 3.13/Debian Bookworm 可复现依赖锁、离线测试及 WP-1/BE-4 回归。

WP-2 禁止 Scrapling fetcher、Playwright/Browser、Router、Discovery、Change Intelligence、Opportunity、Schema/migration 与公开 API 变化。任何冻结契约偏离必须 STOP 并提交 ADR 请求。

下一步：Review 并合并 WP-1 验收/WP-2 准入控制 PR；合并前 Backend 不得开工。控制 PR 合并后，总控向现有 Backend 下达 WP-2 任务。WP-3 与 Frontend 继续未准入。
