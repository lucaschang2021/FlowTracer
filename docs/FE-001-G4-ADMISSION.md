# FE-001 G4 · Windows 发行候选准入

Control Epoch: GOV-2.1

来源：用户 FE-001-HANDOFF-v1.0 与持续完成软件的授权；G3 验收代码 `7789fac068915d1846cfcc4d266a1da95b715f5b`，见 [G3 记录](FE-001-G3-ADMISSION.md)。本控制变更合并后，总控核实精确 post-merge main，向新 G4 任务签发下述首项操作；合并前不执行。

## G4 完成范围

- 可复现的 Windows x64 安装包、版本/哈希/前置工具说明；不把 debug EXE 冒充安装包。
- 安装、启动、退出、重开、明确离线/后端未启动提示的 smoke 证据；任何未验证项明确列出。
- 面向试用者的快速开始：Backend 先迁移后启动、配置、注册/Radar/Source/采集/Signals/Memory/Opportunity/通知、停止与排障；教程正式制作仍在软件验收之后。
- 仅修已观察的 P2：收藏移除后的搜索标签更新，以及产品页面中 G3/lease/候选等内部执行文字；不新建产品模块、不重设计画布。
- P0/P1=0，完整回归/锁定构建/实际安装证据绑定精确候选；INT 与 Release 仍需各自新任务及准入。

## 首项操作模板（启动时由总控绑定精确 SHA）

Task ID: FE-G4-RC-01
Parent Goal: FlowTracer Alpha v0.1 completion
Exact Baseline: 本控制变更 post-merge main，由总控消息提供完整 SHA
Exact Branch: feat/fe-001-g4
Worktree: D:\FlowTracer-wt\integration
Authorized Operation: 一次 Windows 发行候选配置/最小 P2 修正/快速开始增量，加一次针对性验证和锁定安装包构建
Allowed Files: frontend/README.md；frontend/package.json（仅脚本）；frontend/src-tauri/tauri.conf.json；frontend/src-tauri/windows/（确需的最小 bundler 资源）；frontend/src/features/memory/MemoryPage.tsx；frontend/src/app/App.tsx；frontend/tests/memory.spec.ts；frontend/tests/entry.spec.ts；frontend/QUICKSTART.md；frontend/RELEASE-CANDIDATE.md
Allowed Tools: 指定文件编辑、只读 Git、既有 Node/Rust/Edge、locked/offline Cargo、Tauri NSIS bundler；若缓存缺少 NSIS 工具，可使用锁定 Tauri 版本的官方校验下载机制获取构建所需工具，不安装系统服务或修改用户安全设置
Forbidden Operations: Backend/API/Schema/migration、依赖版本或 lock 更新、Browser/R3/R4/R5、Plugin、新网络代理/认证、真实用户账号/认证表单、其他 worktree、用户系统设置、commit/push/PR/merge/release、自动安装/卸载或提权
Max Iterations: 1
Hard Deadline: 签发起60分钟，含构建及针对性验证
Expected Evidence: 精确 diff/hash；typecheck/unit/Web build、仅受影响 UI 回归、locked 原生/NSIS 构建、产物路径/哈希；安装与真实窗口操作本操作 NOT_AUTHORIZED，后续另签
Stop Condition: 增量与一次验证完成，或失败/到期/撤销/基线冲突即 STOP；不得自行修复循环
Next Authority Owner: FlowTracer Controller

如果必须更改依赖/后端/合同或系统设置，先 STOP 给最小原因与范围。Browser disabled、PLUGIN-1 deferred、真实模式与 Demo 隔离保持。

## 2026-10-25 代码与构建检查点（G4 尚未最终验收）

- PR #88 已合并；实际启动基准 `6cc2e0609a25c93d877a2476232bd579928e8547`，独立 G4 任务在 `feat/fe-001-g4` 实施。当前产品代码提交 `679b03210ae8710a1dc7fab697543e3cdb0cd9ad`。
- 原定向失败及筛选出 0 测试的命令错误均保留。Root 修正测试动画就绪同步，未改生产认证或降低断言；新 Settings 用例 1/1、Memory 5/5、最终精确提交完整 UI 71/71（0 retry、6.5m）通过。typecheck、23 unit 与 Web build 证据对应未变生产输入。
- 独立源码 Review04 ALLOW_WITH_P2，新 diff P0/P1/P2=0/0/1；删除与另一搜索重叠时的同账户过滤快照显示问题记录为 P2，不涉及后端事实或跨账户写入。继承 native 日期校验 P2 不变。
- 首次 NSIS 官方工具下载 EOF 失败保留；唯一有界重试通过官方哈希校验并生成 3,158,992 bytes 的 Windows x64 currentUser 安装包。SHA256 `095141123C5A18CC1C860C35584F195F99FE4EE736DBC4FFE383E7A7DF81C437`，位置和完整结果见 [发行候选记录](../frontend/RELEASE-CANDIDATE.md)。依赖锁、Backend/API/Schema/权限未变。
- 安装、启动、退出与重开 smoke 尚未执行；安装即时确认已向用户提出，在其完成并取得运行证据前不得宣布 G4 PASS、准入 INT 或发布。旧实现/验证 lease 已在各自 checkpoint 到期。

## G4 最终验收 · 2026-10-25

- 总控 **ALLOW_WITH_P2 / PRODUCT ACCEPTED**，产品代码 `679b03210ae8710a1dc7fab697543e3cdb0cd9ad`。未变输入引用独立源码 Review04、71/71 UI、typecheck/23 unit/Web build 与锁定 NSIS 构建，不重复测试。
- 用户明确确认该哈希安装包。安装结果位于 `C:\Users\liuj\FlowTracer`，与拟定测试目录不同；中间向导页未完整捕获，该观察限制如实保留。HKCU 安装记录、0.1.0 版本、EXE 三字节 NSIS 标记归一化完全匹配均已核验。
- 原生实测：安装版本启动 → 原始启动画布 → 本机 API 未就绪 → 手动进入明确标识 Demo；Alt+F4 正常退出且进程为零，再开回到启动画布。未输入凭据、未卸载，未声称清洁 Windows 安装或真实后端闭环。详见 [安装证据](../frontend/RELEASE-CANDIDATE.md#smoke-status)。
- P0/P1=0；同账户重叠搜索/删除的快照显示和继承的日期启发式两个 P2 保留。路径/向导观察限制单列，不更改安全边界。
- G1–G3 已由 PR #88 合并（`6cc2e0609a25c93d877a2476232bd579928e8547`）。G4 当前本地验收候选，尚未 push/PR/merge；不冒充共享事实。G4 不等于 INT-001/REL-001/教程完成。所有本轮 lease 在 checkpoint 失效，后续阶段须从 post-merge main 另签。Browser disabled / PLUGIN-1 deferred。
