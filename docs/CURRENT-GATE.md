# FlowTracer 当前阶段闸门

更新时间：2026-09-01。

- 当前稳定基准：`main@7ae213b9849a843eb0a276610e4ad19656bb3fe8`；WP-2 契约 Addendum/ADR-028 控制 PR #37 已合并，WP-2 准入控制 PR #35 与 WP-1 实现 PR #33 均已合并。
- 已完成：ACQ-1 Preflight、Contract Freeze 与 WP-1（ACQ-1A + H0）已通过总控验收；WP-1 结论见 `docs/33-ACQ1-WP1-ACCEPTANCE.md`。
- 当前阶段：ACQ-1 WP-2（ACQ-1B + D-static）已准入，契约已冻结，Backend 正在开发；WP-2 目标能力尚未合并到 `main`，不得描述为已实现。
- 准入：PR #35 与 PR #37 合并已使 `docs/34-ACQ1-WP2-ADMISSION.md`、`docs/35-ACQ1-WP2-CONTRACT-ADDENDUM.md` 及 ADR-028 生效；Backend 目标分支为 `feat/acq-1b-static`，仅按冻结契约实现 WP-2。
- 未准入：WP-3..WP-8；Browser、Router、Discovery、Change、Opportunity；PLUGIN-1；Frontend、Integration 与 Release。

WP-2 开工只读取：本文件、`docs/34-ACQ1-WP2-ADMISSION.md`、`docs/35-ACQ1-WP2-CONTRACT-ADDENDUM.md`、`docs/33-ACQ1-WP1-ACCEPTANCE.md` 及其中列出的直接输入和本阶段相关 Backend 文件。

WP-2 必须交付：

- 统一静态 Acquisition Adapter，保持 RSS/Native 事实等价；
- 只消费本地响应的 Scrapling static parser adapter，不具备 fetch/browser 能力；
- quality v1、family extractor、解析证据与 Attempt 记录；
- Python 3.13/Debian Bookworm 可复现依赖锁、离线测试及 WP-1/BE-4 回归。

WP-2 禁止 Scrapling fetcher、Playwright/Browser、Router、Discovery、Change Intelligence、Opportunity、Schema/migration 与公开 API 变化。任何冻结契约偏离必须 STOP 并提交 ADR 请求。

下一步：Backend 在 `feat/acq-1b-static` 按已生效的 Addendum/ADR-028 完成 WP-2，实现完成后报告并等待书面验收；WP-3..WP-8、PLUGIN-1 与 Frontend 继续未准入。
