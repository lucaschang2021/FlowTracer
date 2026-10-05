# ACQ-1 能力清单（已验收 vs 禁用）

状态：**FINAL（WP-8 收尾产物）**。日期：2026-10-05。依据：`docs/25` §16、`docs/29` WP-8、`docs/67`。
验收模式：**委托方确认（owner-confirmed，无独立第三方角色）**；未验收能力一律如实标注 disabled，不得虚报。

## 1. 已验收能力（Backend，owner-confirmed）

| 能力 | 状态 | 证据指针 |
| --- | --- | --- |
| BE-1..BE-8 Alpha 基线（工程/数据与认证/Radar-Source/采集/智能/记忆/通知与 WS/稳定化与交接） | 完成（历史独立验收） | `docs/04`–`docs/21`；全量测试套件（见 `docs/69`） |
| WP-1：Source 契约、NetworkPolicy/SitePolicy/预算、健康状态、lease/heartbeat/stale recovery | 完成 | `docs/31`–`docs/33`、迁移 `20260830_0004` |
| WP-2：静态 adapter（Scrapling parser）、quality v1、family extractor | 完成 | `docs/34`–`docs/36` |
| WP-4：Router v1（静态候选、fallback、quality gate、circuit、AutoThrottle、预算账本、闭合 trace） | 完成 | ADR-034、`docs/57/58/60`、`tests/test_acquisition_router.py` |
| WP-5 I1：Controlled Discovery 规划与 Frontier（四 scope、link scoring、硬上限、checkpoint 恢复；**不发起请求**） | 完成（I1） | ADR-035、`docs/61/62`、`tests/test_acquisition_discovery.py` |
| WP-6 I1：版本证据 shadow-write（Artifact/Snapshot/ChangeEvent、三指纹、materiality、removed 两次缺失、backfill） | 完成（I1；RawItem 写路径不变） | ADR-036、`docs/63/64`、`tests/test_acquisition_change.py` |
| WP-7 I1：Opportunity Radar（`radar_type=opportunity`、三表、Freelance v1 Hard Filter、score v1、Provider、Action Payload、Notification XOR、REST） | 完成（I1） | ADR-037、`docs/65/66`、`tests/test_opportunity.py` |
| WP-8：价值闭环离线 E2E、可重复启动验证、性能基线、秘密扫描、能力清单、交接文档 | 完成 | `docs/67/69`、`tests/test_acq1_final_e2e.py`、`scripts/verify_fresh_startup.py`、`scripts/secret_scan.py`、`scripts/benchmark_offline.py` |

三条闭环均由 `tests/test_acq1_final_e2e.py` 在离线 fixture 上端到端验证：
采集（Router 决策）→ 版本证据 → Discovery checkpoint → RawItem → Document → Analysis → Embedding → 通知；
机会采集 → Snapshot → OpportunityItem → Hard Filter → Score → Action Payload → 通知 → REST。

## 2. 禁用能力（未准入，fail-closed）

| 能力 | 状态与门 | 证据/说明 |
| --- | --- | --- |
| Dynamic/Advanced Browser（含 Browser worker/queue/pool、真实 egress 运行） | **disabled**；`BROWSER_DYNAMIC_ENABLED=False`；`select_candidates(allow_browser=True)` → `acquisition_browser_not_admitted`；`mode=dynamic/advanced` → `acquisition_mode_unsupported` | `docs/29` WP-3、ADR-029/030、`docs/CURRENT-GATE.md`；R1/R1C/R1D/R1E/R2C 供应链与受控出口证据保留但 ≠ 准入 |
| R3 Application interception matrix（真实执行） | **BLOCKED**；真实执行需 B 阶段 lease | 离线增量（A1 设计 + A2 DenialLatch/deny-terminate + F1-F6 取证 + 就绪报告）位于**分支 `feat/acq1-r3-fail-closed-offline`**（docs/54/55/56/59 在该分支，未合并）；main 仅含基线离线 harness |
| R4 回收/资源、R5 双 worker 隔离 | 未准入 | `docs/29`、`GOVERNANCE-V2` §6 |
| WP-5 I2：crawl 执行（向发现的 URL 发起请求、robots 获取、逐跳计费） | 未实现 | 最终 E2E 断言：一次 run 仅 1 个 attempt，frontier 仅规划；`docs/61` §0 |
| WP-6 I2：RawItem writer 切换、读取 API、`semantic-change-v1` | 未实现 | 最终 E2E 断言 `raw_items` 无 `snapshot_id` 列；`docs/63` §0 |
| WP-7 I2：平台逐站点访问授权工作流、版本变化驱动重评/生命周期、多币种 FX | 未实现 | `docs/65` §0；I1 仅首见快照建 item |
| Opportunity Notification 的 WS 事件扩张 | 禁止（ADR-026：ACQ-1 不扩张 WS） | 通知通过 REST 轮询；WS 仍为三个冻结事件 |
| 任何自动执行：自动投标/报价/工期/合同承诺/沟通/资金/外部 Agent | **永久禁止**（ACQ-1 边界） | ADR-025；Action Payload `requires_human_approval=true` 恒真 |
| PLUGIN-1 / FE-001 前端 / INT-001 集成 / REL-001 发布 | 未准入 | `docs/02-DELIVERY-BOARD.md` |

## 3. 不可伪造声明

- 本清单中每一项"完成"均有仓库内可执行证据（测试、脚本输出、文档）；WP-3 相关能力在获得真实执行证据并独立复审前，**不得**在任何报告、看板或发行说明中标记为通过。
- 性能数据仅为本机隔离 fixture 的复现参考（`PERFORMANCE-BASELINE.md`），Browser 相关指标统一标注 NOT MEASURED。
- 秘密扫描为模式级扫描（`scripts/secret_scan.py`，含植入自检），不构成全量熵扫描或第三方审计。
