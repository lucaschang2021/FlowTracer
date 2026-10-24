# FE-001-G3 Galaxy、持久布局与真实导航

控制纪元：GOV-2.1。来源：用户 FE-001-HANDOFF-v1.0 与继续直至完成的软件目标；不新增产品范围。

## 基线与完成范围

- G2验收代码：`74059db8d9c5f2e62e027f89c6b5b8f4d9cf49bb`；G2记录/本阶段父基线：`f8ec2ed972be9c1f52429097820a767b6c3ab381`。
- 工作树：`D:\FlowTracer-wt\integration`；分支：`feat/fe-001-g3`。本准入控制提交的精确SHA由总控在任务签发时提供；该SHA必须为上述父基线后代，不能自行重定位。
- G3目标：框选与Galaxy建立/改名/成员/解散；按用户隔离的版本化位置、视图和分组持久化；Memory收藏/搜索与Opportunity列表/详情/只读action-payload；设置与必要REST通知更新。
- 后端契约只读：`backend/FRONTEND-HANDOFF.md`、冻结OpenAPI相关端点。不得新增galaxies API、修改Backend/schema/评分、启用Browser或外部自动执行。
- 原宇宙画布、轻微自主旋转、双语、键盘与 reduced-motion 保留，不重新设计主界面。依用户 2026-10-23 的最新视觉决定，移除共享背景的鼠标跟随/指针视差；不影响 Radar 拖动、框选、平移和缩放。

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

### SPATIAL03 / REVIEW04 检查点（2026-10-21）

- 当前分支基准 `2ffd228080360f2892e9a432f9bf7596a806a609`，八个前端文件形成 Galaxy/本机空间候选；Backend、Rust、依赖与冻结接口未改。
- SPATIAL03：typecheck、Web build（56 modules）、layout 8/8、Edge 定向 5/5、diffcheck PASS。此前 locator FAIL/两项未运行、后续 whitespace FAIL 均保留，不能改写为第一次全绿。
- 独立 REVIEW04 绑定精确文件 SHA，关闭“未加载坐标被覆盖丢失”“effect cleanup 后存储警告未重新武装”两项 P1；并确认已保存空远端视图下首个新 Radar 自动 fit。P0/P1/P2=0/0/1，仅 ALLOW 本源码检查点，不是 G3 最终验收。审查者未重试其先前被拒的 Git，branch/HEAD 由总控独立核对；未独立重跑测试。
- 保留验收事项：live A→B 带延迟保存的界面保证（P2）、已确认删除 Radar 的持久孤儿清理、真实原生进程重开恢复。当前仅在挂载恢复存档坐标；未来引入分页追加或同账号重拉 Radar 时，必须再次对后加载节点应用存档位置，不得丢失未加载引用。
- Memory/Opportunity/REST 通知尚未实现。G3 产品、G4、INT、Release、教程均未因此通过；Browser disabled / Plugin deferred 不变。

Task ID: FE-G3-SPATIAL-CHECKPOINT05
Control Epoch: GOV-2.1
Parent Goal: FE-001 Windows Alpha completion
Exact Baseline: 2ffd228080360f2892e9a432f9bf7596a806a609 + REVIEW04 核对的八文件候选
Exact Branch: feat/fe-001-g3
Authorized Operation: 总控记录上述检查点，定向 diffcheck/白名单核对后仅作本地 commit
Allowed Files: 本文件；App.tsx、Universe.tsx、GalaxyPanel.tsx、galaxy.css、layout.ts、layout.test.ts、galaxy-layout.spec.ts、radar-create.spec.ts 的已复核候选
Allowed Tools: apply_patch、只读 Git/hash、定向文档检查、明确白名单 add/commit
Forbidden Operations: 产品代码再修改、测试重跑、依赖安装、runtime、push/PR/merge、下游准入
Max Iterations: 1
Hard Deadline: 本检查点操作开始起15分钟
Expected Evidence: 精确提交、九文件清单、diffcheck、工作树状态
Stop Condition: 本地 commit 完成或任一失败即停；后续实现另签操作
Next Authority Owner: FlowTracer Controller

G3后续每个增量另签有界操作：typed native Memory/Opportunity/Notification接口与最小真实页，保持既有固定loopback、Authorization、refresh/generation、错误和只读action边界。任何缺失契约STOP，不伪造数据填页。

G3验收须有用户隔离/损坏存储/删除引用/无网络写入的测试、跨刷新与真实原生进程重开布局恢复、真实或严格隔离后端Memory/Opportunity链路，以及最终候选完整回归与评审。单项通过不代表G3通过。G4/集成/发布与教程不由本文件自动准入。

### 原生演示重开检查点（2026-10-24）

- 使用本地离线构建 `flowtracer-desktop.exe`（SHA-256 `3BFE40C7853FA61F8AE70FE89F678DD7302E11D0F652136C14FA058695608B1B`）：演示星图中移动 AI Infrastructure，界面确认保存；关闭进程并重开后，同一行星保持移动后位置，界面显示“已恢复此账户的本机空间布局”。随后将行星移回原位并关闭测试窗口。
- 此证据仅覆盖离线演示的原生进程重开，不覆盖真实账户隔离、隔离后端 Memory/Opportunity 链路或 G3 最终验收。该原生演示检查点未启动 Docker 或隔离数据库；G4/Integration/Release 仍未准入。

### Memory / Opportunity 隔离后端检查点（2026-10-24）

- 首次使用 Docker internal 网络的临时 PostgreSQL/Redis：PostgreSQL 容器内 ready，但 Windows 主机到映射端口连接被拒，迁移前停止；目标测试 0 项运行，专属容器/网络清理为 0。
- 第二次使用仅绑定 `127.0.0.1` 的专属临时容器和 tmpfs 数据，唯一 `flowtracer_g3_6b73e0f342_test` 空库迁移至 `20261006_0009`。定向执行 Memory API 收藏/搜索、Opportunity 事实→评分→action-payload→通知、Opportunity REST 所有权/筛选及 WP-8 Opportunity 后端闭环：4 passed、2 条第三方 lxml deprecation warning；测试结束专属容器为 0，现有构建容器未操作。
- 该结果证明当前 Backend 的隔离数据库链路，不等同桌面原生桥到真实 API 的端到端验证，也不批准 G3 产品验收。首次失败与第二次成功均保留，不将定向 4 项称为全量回归。

### 真实账户原生桌面检查点（2026-10-24）

- 使用同一离线 debug 桌面程序、固定 `127.0.0.1:8000/api/v1`、唯一 `flowtracer_g3_ftg3_mvltwgxi_7ukswm_test` 数据库与仅 loopback 端口的 tmpfs PostgreSQL/Redis。API live/ready 均正常；用户在原生窗口手动注册临时账户并在进程重启后手动登录，执行者未读取或操作邮箱、密码表单。API 日志确认注册 `201`、`users/me` 与 Radar 列表 `200`。
- 首次登录显示“真实连接”、0 个真实 Radar，未载入 Demo 数据；Signals、Memory、Opportunity 均显示该空账户的空结果，没有以示例内容填充。通过桌面原生桥创建 `G3 Layout Test` Radar 后，真实计数变为 1，星图出现对应行星。
- 将该行星从画布中央拖到右上，界面提示“已移动并保存在此账户的本机布局”；关闭桌面进程、重新启动并由用户以同一临时账户手动登录后，界面提示“已恢复此账户的本机空间布局”，行星仍在右上位置。这是隔离真实账户的原生进程重开证据，与上文 Demo 重开证据分开记录。
- 测试后关闭桌面与 API，精确停止两个专属临时容器；`flowtracer.g3=ftg3-mvltwgxi-7ukswm` 容器数为 0，`8000`、`15439`、`16389` 无监听端口。PostgreSQL/Redis 数据位于 tmpfs，临时账户与 Radar 随容器删除；未触碰用户其他容器或持久卷。
- 本检查点尚未验证有内容的 Memory/Opportunity/Notification 在桌面显示，也未证明跨两个真实账户的并发切换、完整前端回归或独立产品验收。G4、Integration、Release 与教程仍未准入。

### 最终回归与响应式测试修正（2026-10-24）

- FINAL-VERIFY-24 在冻结候选上完成 typecheck、23/23 unit、22/22 locked/offline Rust tests、Web build（60 modules）。唯一一次完整 Edge 集为 63 passed、1 failed、5 未运行、0 retry；1366×768 测试仍查找 G1 的 Galaxy 名称，原始失败保存在 `frontend/test-results/g3-final-verify-24/`。
- RESPONSIVE-TEST-REPAIR25 仅更新 `frontend/tests/universe.spec.ts` 的 Galaxy 按钮、面板 testid 和关闭按钮定位，匹配现有 G3 控件；没有降低几何、遮挡、截图或焦点断言。一次全文件定向为 6/6 passed、0 retry，覆盖三种尺寸和此前未运行项；生产源码、依赖和既有原生程序未变。结果保存在 `frontend/test-results/g3-responsive25/`。原全量失败仍保留，最终提交的独立完整回归尚待执行。
- 非空原生验证已在新 tmpfs `_test` 库通过现有后端服务准备 Memory/Embedding、Opportunity ingest/evaluation/action-payload 和两条 Notification；首次 seed 在创建事实前因诊断脚本误用 SecretStr 停止，修正后成功，未改产品代码。缓存 PostgreSQL 标签核实后使用 `--pull=never`，未采用不同版本依赖。窗口最小化与用户输入保护暂阻止后续桌面操作；不得把已准备的数据库事实冒充桌面显示或操作成功。
