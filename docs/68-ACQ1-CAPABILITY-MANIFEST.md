# ACQ-1 能力清单（已验收 vs 禁用）

状态：**READY_FOR_FRONTEND（Static/Native 后端交接就绪）**。日期：2026-10-07。依据：`docs/25` §16、`docs/29` WP-8、`docs/67`、`docs/71`–`docs/78`。
验收模式：本地候选由交付侧形成；审核方已在精确代码提交 `01155294f151cb1c453ddbaf8af6ed34ef3228c1` 独立复核并确认 P0/P1=0，见 [独立验收记录](78-ACQ1-INDEPENDENT-ACCEPTANCE.md)。未验收能力一律如实标注 disabled，不得虚报。

## 1. 已验收能力（Backend，owner-confirmed）

| 能力 | 状态 | 证据指针 |
| --- | --- | --- |
| BE-1..BE-8 Alpha 基线（工程/数据与认证/Radar-Source/采集/智能/记忆/通知与 WS/稳定化与交接） | 完成（历史独立验收） | `docs/04`–`docs/21`；全量测试套件（见 `docs/69`） |
| WP-1：Source 契约、NetworkPolicy/SitePolicy/预算、健康状态、lease/heartbeat/stale recovery | 完成 | `docs/31`–`docs/33`、迁移 `20260830_0004` |
| WP-2：静态 adapter（Scrapling parser）、quality v1、family extractor | 完成 | `docs/34`–`docs/36` |
| WP-4：Router v1 + 生产路径收口（受控静态重试、共享预算、Circuit 半开并发保护、节流恢复） | 本地候选完成 | ADR-034/038、`docs/57/58/60/73`、`tests/test_acq1_closure_p1.py` |
| WP-5：Controlled Discovery I1 + I2 受控抓取（frontier 消费、robots、逐跳复核、有界遍历、取消/恢复、并发去重） | 本地候选完成 | ADR-035/039、`docs/61/62/74`、`tests/test_acq1_closure_p2.py` |
| WP-6：版本证据 I1 + I2 写路径（快照身份 RawItem、Change/Artifact 读取 API、回填与序列验证） | 本地候选完成；`semantic-change-v1` 仍未启用 | ADR-036/040、`docs/63/64/75`、`tests/test_acq1_closure_p3.py` |
| WP-7：Opportunity Radar I1 + 生命周期与版本化重评（created/content_changed/removed/expired） | 本地候选完成；平台授权工作流与 FX 不扩张 | ADR-037/041、`docs/65/66/76`、`tests/test_acq1_closure_p4.py` |
| WP-8：价值闭环与收口整链离线 E2E、失败/恢复/并发/预算路径、可复现验收器、前端契约冻结与交接 | 完成；独立验收通过 | `docs/67/69/70/77/78`、`tests/test_acq1_final_e2e.py`、`tests/test_acq1_closure_p5.py`、`scripts/closure_acceptance.py` |

I1 历史闭环由 `tests/test_acq1_final_e2e.py` 保留；当前收口实现另由 `tests/test_acq1_closure_p5.py` 验证完整链路：
配置 Radar/Source → Router → seed 抓取 → Discovery 消费 frontier → 版本证据/Change → RawItem → Opportunity 生命周期/评分 → REST/通知；
失败、取消、恢复、所有权、并发、幂等与预算耗尽路径由 Phase 0-5 测试矩阵覆盖；独立全量复核结果见 `docs/78`。

## 2. 禁用能力（未准入，fail-closed）

| 能力 | 状态与门 | 证据/说明 |
| --- | --- | --- |
| Dynamic/Advanced Browser（含 Browser worker/queue/pool、真实 egress 运行） | **disabled**；`BROWSER_DYNAMIC_ENABLED=False`；`select_candidates(allow_browser=True)` → `acquisition_browser_not_admitted`；`mode=dynamic/advanced` → `acquisition_mode_unsupported` | `docs/29` WP-3、ADR-029/030、`docs/CURRENT-GATE.md`；R1/R1C/R1D/R1E/R2C 供应链与受控出口证据保留但 ≠ 准入 |
| R3 Application interception matrix（真实执行） | **BLOCKED**；真实执行需 B 阶段 lease | 离线增量（A1 设计 + A2 DenialLatch/deny-terminate + F1-F6 取证 + 就绪报告）位于**分支 `feat/acq1-r3-fail-closed-offline`**（docs/54/55/56/59 在该分支，未合并）；main 仅含基线离线 harness |
| R4 回收/资源、R5 双 worker 隔离 | 未准入 | `docs/29`、`GOVERNANCE-V2` §6 |
| `semantic-change-v1` | 未启用（明确延期） | `docs/63` §17、`docs/75` |
| WP-7 平台逐站点访问授权工作流、多币种 FX、外部执行适配器 | 未实现 / 不在本次收口范围 | `docs/65` §12、`docs/76` |
| Opportunity Notification 的 WS 事件扩张 | 禁止（ADR-026：ACQ-1 不扩张 WS） | 通知通过 REST 轮询；WS 仍为三个冻结事件 |
| 任何自动执行：自动投标/报价/工期/合同承诺/沟通/资金/外部 Agent | **永久禁止**（ACQ-1 边界） | ADR-025；Action Payload `requires_human_approval=true` 恒真 |
| FE-001 前端 / INT-001 集成 / REL-001 发布 | 未准入 | `docs/02-DELIVERY-BOARD.md` |
| PLUGIN-1 | **POST-v0.1 / deferred**；不在 Alpha v0.1 关键路径，不阻塞 Frontend | `docs/02-DELIVERY-BOARD.md` |

## 3. 不可伪造声明

- 本清单中每一项"完成"均有仓库内可执行证据（测试、脚本输出、文档）；WP-3 相关能力在获得真实执行证据并独立复审前，**不得**在任何报告、看板或发行说明中标记为通过。
- 性能数据仅为本机隔离 fixture 的复现参考（`PERFORMANCE-BASELINE.md`），Browser 相关指标统一标注 NOT MEASURED。
- 秘密扫描为模式级扫描（`scripts/secret_scan.py`，含植入自检），不构成全量熵扫描或第三方审计。
