# FlowTracer 当前阶段闸门

更新时间：2026-08-30。

- 当前稳定基准：`main@b9eb485e815bbd7926f500600e73da3132b429a2`；ACQ-1 WP-1 Contract Addendum PR #32 已 Review 并合并。
- 已完成：ACQ-1 Preflight 与 Contract Freeze 已通过总控审查；结论见 `docs/27-ACQ1-PREFLIGHT-ACCEPTANCE.md` 与 `docs/30-ACQ1-CONTRACT-FREEZE-ACCEPTANCE.md`。
- 当前阶段：ACQ-1 WP-1（ACQ-1A + H0）实现候选审查中。Backend 候选为 `feat/acq-1a-h0@0e95a5698ae5b8964fb387aaa9c1bb77e3a439ec`，尚未 push 或创建 PR。
- 准入：现有 Backend 可按 `docs/31-ACQ1-WP1-ADMISSION.md` 与 `docs/32-ACQ1-WP1-CONTRACT-ADDENDUM.md` 完成 WP-1 实现、补充运行态证据并向总控报告。
- 未准入：WP-2..WP-8；Scrapling/Browser、Router、Discovery、Change、Opportunity；Frontend、Integration 与 Release。

WP-1 续跑只读取：本文件、`docs/31-ACQ1-WP1-ADMISSION.md`、`docs/32-ACQ1-WP1-CONTRACT-ADDENDUM.md`、`docs/23-ACQ1-ACQUISITION-CONTRACT.md`、`docs/25-ACQ1-ACCEPTANCE.md`、`docs/29-ACQ1-WORK-PACKAGES.md` 的通用规则与 WP-1、ADR-022/023/027，以及本阶段直接涉及的 Backend 代码、迁移与测试。

WP-1 必须交付：

- Source 强类型稳定字段、严格公开 Profile、秘密边界与 legacy config 兼容；
- SourceAcquisitionState、AcquisitionAttempt 与 CollectionRun lease/heartbeat/stale recovery；
- NetworkPolicy、SitePolicy、ResourceBudget 纯逻辑安全内核和 Native 接入点；
- expand migration、legacy backfill、Source API/OpenAPI 兼容、离线测试及 BE-4/BE-7/BE-8 回归。

WP-1 禁止提前处理 RawItem 版本切换、Browser/Scrapling、Router、Discovery、Change Intelligence 或 Opportunity；这些能力分别保留至后续工作包。任何冻结契约偏离必须 STOP 并提交 ADR 请求。

下一步：Backend 在不重复既有全量门禁的前提下，完成官方 Compose 镜像与隔离运行态补充验收并报告。总控复核候选提交、迁移、测试、安全和运行证据后，方可另行授权 push 与创建 PR。WP-2 与 Frontend 继续未准入。
