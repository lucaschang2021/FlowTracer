# FE-001-G3 Galaxy、持久布局与真实导航

控制纪元：GOV-2.1。来源：用户 FE-001-HANDOFF-v1.0 与继续直至完成的软件目标；不新增产品范围。

## 基线与完成范围

- G2验收代码：`74059db8d9c5f2e62e027f89c6b5b8f4d9cf49bb`；G2记录/本阶段父基线：`f8ec2ed972be9c1f52429097820a767b6c3ab381`。
- 工作树：`D:\FlowTracer-wt\integration`；分支：`feat/fe-001-g3`。本准入控制提交的精确SHA由总控在任务签发时提供；该SHA必须为上述父基线后代，不能自行重定位。
- G3目标：框选与Galaxy建立/改名/成员/解散；按用户隔离的版本化位置、视图和分组持久化；Memory收藏/搜索与Opportunity列表/详情/只读action-payload；设置与必要REST通知更新。
- 后端契约只读：`backend/FRONTEND-HANDOFF.md`、冻结OpenAPI相关端点。不得新增galaxies API、修改Backend/schema/评分、启用Browser或外部自动执行。
- 原宇宙画布、轻微旋转/指针视差、双语、键盘与reduced-motion保留，不重新设计主界面。

## 第一操作许可 FE-G3-SPATIAL-01

Task ID: FE-G3-SPATIAL-01
Control Epoch: GOV-2.1
Parent Goal: FE-001 Windows Alpha completion
Exact Baseline: 本准入控制提交（总控发送精确SHA）；父基线见上
Exact Branch: feat/fe-001-g3
Authorized Operation: 一次Galaxy与持久布局实现增量，加一次定向验证；不实现Memory/Opportunity/通知
Allowed Files:
- frontend/src/app/App.tsx
- frontend/src/features/universe/Universe.tsx
- frontend/src/features/universe/model.ts
- frontend/src/features/universe/layout.ts
- frontend/src/features/universe/layout.test.ts
- frontend/src/features/universe/GalaxyPanel.tsx
- frontend/src/features/universe/galaxy.css
- frontend/src/styles/app.css
- frontend/src/styles/demo.css
- frontend/tests/galaxy-layout.spec.ts
Allowed Tools: 相关只读检查、apply_patch、现有Node/npm/Edge缓存的本地定向测试与Web build；不得安装依赖
Forbidden Operations: Backend/API/schema、Rust bridge或auth改写、dependency/lock、Browser/Docker/native账号、Memory/Opportunity/通知实现、其他worktree、commit/push/PR/merge/release
Max Iterations: 1
Hard Deadline: 2026-10-21 00:20 +08（包含本次实现与一次定向验证，不自动延长）
Expected Evidence: 文件diff与hash；类型检查/Web build、layout纯测试、唯一Galaxy UI定向集；存储/隔离/键盘/取消/解散证据；真实native重启证据若未运行须明确NOT_RUN
Stop Condition: 增量及一次定向验证结束，或任一失败/截止/撤销/输入冲突；不得自续repair、commit或其他功能
Next Authority Owner: FlowTracer Controller

## 空间状态约束

- Galaxy只是前端组织，不是Radar/Cross Radar。解散不得发Radar DELETE；清理孤儿引用不得删除Backend事实。
- 允许使用经验证的版本化WebView本地持久化；无须为此增添Rust插件或文件系统接口。只保存schema version、owner UUID、radar UUID与坐标、视图、galaxy UUID/名称/成员；不得保存token、密码、正文、Backend事实副本。
- live状态按账户UUID分区，Demo单独隔离；账号切换必须清空旧界面再读新key，迟到保存不得写进另一账号key。
- 不信任存储：版本、对象结构、UUID、去重、finite坐标/zoom边界、长度/容量校验；损坏/拒绝/额度满时安全退回内存并明确告知，不崩溃、不跨用户恢复。
- 只渲染当前用户可见Radar引用。仅在Radar清单完整或删除已确认时持久清理孤儿；不要把未分页加载的Radar误当删除。
- 左键空白拖动为框选，节点拖动与Space平移保持独立，至少两节点才建立Galaxy；提供非鼠标/非右键选择与创建入口、Escape取消、可见焦点。
- 视图/拖动保存应合并，不每帧重渲染整个应用；恢复优先保留用户布局，首Radar自动fit和首次无布局的fit仍可用。
- 改名、成员列表、查看成员、解散和重载恢复均需覆盖；主界面统计只显示真实分组数，不冒充Backend信号数。

## 后续准入与验收

G3后续每个增量另签有界操作：typed native Memory/Opportunity/Notification接口与最小真实页，保持既有固定loopback、Authorization、refresh/generation、错误和只读action边界。任何缺失契约STOP，不伪造数据填页。

G3验收须有用户隔离/损坏存储/删除引用/无网络写入的测试、跨刷新与真实原生进程重开布局恢复、真实或严格隔离后端Memory/Opportunity链路，以及最终候选完整回归与评审。单项通过不代表G3通过。G4/集成/发布与教程不由本文件自动准入。
