# FlowTracer 当前阶段闸门

更新时间：2026-08-31。

- 当前稳定基准：`main@fcfab2492e4ee88202672787d425c084d0b4afc9`；ACQ-1 WP-1 验收/WP-2 准入控制 PR #35 已合并，WP-1 实现 PR #33 已独立 Review 并合并。
- 已完成：ACQ-1 Preflight、Contract Freeze 与 WP-1（ACQ-1A + H0）已通过总控验收；WP-1 结论见 `docs/33-ACQ1-WP1-ACCEPTANCE.md`。
- 当前阶段：ACQ-1 WP-2（ACQ-1B + D-static）已准入，契约澄清中；实现未开始。Backend 已完成开工审计，因 quality v1 分项公式、writer 终态及 family/evidence 精确契约缺口停点。
- 准入：PR #35 合并已满足 `docs/34-ACQ1-WP2-ADMISSION.md` 的条件准入；Backend 目标分支为 `feat/acq-1b-static`，仅按该准入文件实现 WP-2。
- 未准入：WP-3..WP-8；Browser、Router、Discovery、Change、Opportunity；Frontend、Integration 与 Release。

WP-2 开工只读取：本文件、`docs/34-ACQ1-WP2-ADMISSION.md`、`docs/33-ACQ1-WP1-ACCEPTANCE.md` 及其中列出的直接输入和本阶段相关 Backend 文件。

WP-2 必须交付：

- 统一静态 Acquisition Adapter，保持 RSS/Native 事实等价；
- 只消费本地响应的 Scrapling static parser adapter，不具备 fetch/browser 能力；
- quality v1、family extractor、解析证据与 Attempt 记录；
- Python 3.13/Debian Bookworm 可复现依赖锁、离线测试及 WP-1/BE-4 回归。

WP-2 禁止 Scrapling fetcher、Playwright/Browser、Router、Discovery、Change Intelligence、Opportunity、Schema/migration 与公开 API 变化。任何冻结契约偏离必须 STOP 并提交 ADR 请求。

下一步：总控补充 WP-2 Addendum/ADR 并完成书面裁定后，另行通知 Backend 续跑；澄清前保持停点，不实施代码或依赖变更。WP-2 完成后仍须报告并等待书面验收；WP-3..WP-8 与 Frontend 继续未准入。
