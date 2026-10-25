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
