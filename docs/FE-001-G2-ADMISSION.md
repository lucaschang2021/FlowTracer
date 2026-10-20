# FE-001-G2 真实接口接入准入

更新时间：2026-10-20。控制纪元：`GOV-2.1`。

## 身份与状态

- 已核实合并的 Backend `main` 产品基线：`fc180a1d2eba32935fba6ee6c128f9b2d7015574`；本轮未联网核验或声明当前远端 SHA。
- 当前本地代码候选：`feat/fe-001-g2-api@74059db8d9c5f2e62e027f89c6b5b8f4d9cf49bb`；wire27、motion30、pointer39、CAMERA53/56 与测试工具安全修复均已本地提交；现状文档可另作后续提交，不把文档提交 SHA 混作代码测试基线。均未 push、未 merge。
- G1 骨架已独立验收。总控在 2026-10-13 对 `24e2...` 完成 source/scope、typecheck、13 unit、web build 与 13 UI E2E 检查；后续 G2 原生链路证据不回填为 G1 基线的独立原生复跑，浏览器测试也不能替代原生证据。
- 本文件冻结 G2 范围与安全边界。下方早期 `AUTH-01`、旧失败与旧阻断段落均为历史 checkpoint，不代表当前实现状态；现行事实以本顶部快照及后续具名 checkpoint 为准。这不等于 FE-G2/FE-001 产品验收，也不准入 G3、INT-001 或 REL-001。

## 当前候选证据快照（2026-10-20；不提供执行许可）

- `AUTH-UI-REGISTER-11` 在隔离 `_test` 库取得原生 UI 注册→`users/me`→真实空 Radar 的请求和界面证据；`AUTH-API-SEED-09` 在另一隔离 `_test` 库取得原生登录、退出与进程重开后需重新登录的证据。两轮临时账号/无卷容器及专名网络均已清理。具体请求与停点见下方各轮记录，不将不同测试轮次冒充同一次完整操作。
- 当前已实现 Radar CRUD、Source create/bind/分页/collect poll、Signals 列表/详情与 lifecycle/focus 防护。`755ba90205a1b13f8215e32c620efe941535bffb` 的 VERIFY62 唯一 full UI 为 `45/45 passed`（4.1m，0 retries）；替代旧 HEAD39 的当前覆盖地位，但不抹除历史失败。最终 `74059db...` 仅改 Vitest 开发依赖链，VERIFY67 取得 15 unit/typecheck/build 与全依赖/生产依赖 audit 全绿，生产依赖与产品源码未变；不同基线及继承依据明确分列。
- wire27 修复 Backend snake_case CollectionRun 到公开 camelCase bridge 的输入/输出 DTO 边界，Rust 定向 `2 passed`；motion30 将共享经画像旋转调为 `120s linear infinite`，Edge 定向 `2 passed`，并保留 quiet/reduced-motion 停转。两者均是 dirty 定向证据。PACKAGE32（SHA-256 `BB2B948AF880F0DF4C0878CCBE47C4385F4DCEEBDD8EC042628251369B30280D`）随后在 NATIVE35/36 真实启动，关闭应用内减少动态效果后取得 Demo 背景旋转、前景固定及详情选择证据；不是原生独立完整 120s 周期计时或性能测试。最新 PACKAGE42 已包含 pointer39，身份与验证边界见下方 checkpoint。
- FLOW31 在此前 wire-fixed、pre-motion 原生包上真实通过：创建并绑定 1 个 RSS Source、唯一 collect、guarded 离线生产处理，UI 自动 `queued → succeeded` 并显示 fetched/created/duplicates/failed=`1/1/0/0`，Signals 真实列表与详情显示 77.6、正文并成功返回 Canvas。该证据关闭指定 Source/collect/Signals 原生链路，不代表 Worker/Beat/Broker dispatch、Router、embedding、Notification、真实 WS、完整错误/分页/ownership 矩阵或全面 native E2E；PREP28 资源和临时数据已精确清理，无需重复注册补证。
- AUTH session fence、poll generation/intent 与 NATIVE51 pause→resume/keyboard 结论保持。旧 audit 告警本轮已归因并在 SECURITY66/VERIFY67 修复；来源未明本机 404 仅保留历史观察。最终代码候选已本地提交，未 push/PR/merge；G2 产品 StageGate 与 G3/INT/Release 准入仍分离，不以测试绿灯自动进入下一阶段。

### CANDIDATE58–70（2026-10-20；当前验证与身份）

- 最终裁定：独立 SECURITY-CLOSURE69 核SHA/锁图通过，确认安全P1关闭、源码/依赖P0/P1/P2=0/0/0，认可UI/Rust/native证据继承。DOC70 四份文档身份/必要引用/无新代码/diffcheck PASS。`74059db...` 当前为 **READY_FOR_G2_PRODUCT_REVIEW**，不是G2产品通过；REVIEW46 pointer resize/visibility直接断言仍为附加assurance P2，不阻止该产品评审。DOC71仅记录结论并定向检查；COMMIT72为单独四文档本地checkpoint，MaxIterations=1、23:18+08截止，无push/PR/merge或下游准入。
- GOV-2.1：总控在56/57 checkpoint 后分别签发 COMMIT58（七文件本地候选）、VERIFY59（一次完整前端检查）、REPAIR60（单条旧测试断言+一次目标验证）、COMMIT61、VERIFY62（新提交唯一 full UI）、只读 AUDIT64/65、SECURITY66（仅 Vitest pin+lock）、VERIFY67（验证包装修正）、COMMIT68、只读 REVIEW69 及 DOC70。每操作 MaxIterations=1、独立 checkpoint；最长截止23:18+08。无 push/PR/merge/新阶段许可；DOC70 仅本文件、CURRENT-GATE、看板、frontend README 的一次现状同步和定向检查。
- `670c61d8506f169f046461acaa2660f387282aa8`：wire/视觉/camera 源码与测试七文件进入本地提交；typecheck、15 unit、20 Rust、locked/offline desktop build PASS。首次 full UI=10 PASS/1 FAIL/34未运行（39.9s）：旧 `entry.spec.ts:18` 仍要求230s，实际获准值120s；原失败截图、trace保留于 `frontend/test-results/final-candidate59/`，不追认为PASS。
- `755ba90205a1b13f8215e32c620efe941535bffb`：仅同步该断言120s；单目标1 PASS后，本提交唯一 full UI 45/45 PASS（4.1m，1 worker，0 retries），输出 `frontend/test-results/final-candidate62/`。REVIEW57 对 CAMERA56 P0/P1/P2=0/0/0；REVIEW63 当时所列“full尚在运行/现状文档旧身份”是具名时点的验证阻断，不是新产品bug；现已取得 full结果并在本快照对齐身份。
- 新 desktop debug exe 15,544,320 bytes，SHA256 `AC2A2361B02A7BBFC053C27F0AA647F26E9EFBAC809A013FE74BDB41103ACD14`，已含 CAMERA53，不再是 PACKAGE42。未再启动原生程序或重复认证；既有 AUTH/FLOW31/NATIVE51 证据分别引用。
- AUDIT64 官方registry最新锁图：moderate1、critical2，定位 Vitest3.2.7 / mocker3.2.7 / tinypool1.1.1；omit-dev=0。独立安全65裁定开发/验证链 P1（非已证实桌面可利用漏洞），不能以dev-only忽略。[上游 mocker advisory](https://github.com/advisories/GHSA-82fw-gwwq-j7x9)、[tinypool worker](https://github.com/advisories/GHSA-5gmw-xhrv-c9v3)、[tinypool run](https://github.com/advisories/GHSA-85c8-ppgw-ccpr) 保留归因。
- SECURITY66 精确pin Vitest4.1.11，ignore-scripts/no-audit安装；只改变package/lock与测试依赖，生产依赖version/resolved/integrity变化0、mocker4.1.11、tinypool移除、npm ls --all PASS。首个验证包装因PowerShell参数处理返回非JSON而停止，unit/typecheck/build当时未运行，不抹除该失败。新VERIFY67显式参数审计：全依赖和omit-dev均exit0/total0；Vitest4.1.11单测15/15、typecheck/build/diffcheck PASS。
- 最终代码 `74059db8d9c5f2e62e027f89c6b5b8f4d9cf49bb` 仅开发测试依赖变化；按独立安全65规定继承755的45项UI与670的Rust/desktop证据，不为纯测试工具变化重复认证/Docker/未变输入全量。bundle仍 `index-BTIv_ru1.js`，新SHA256 `BDF1CD1A5159218DF185EDDDB01AAD0F87F5183FE0352A754C848E781E402F21`；package SHA `72B901109870D94412D0A686D3AE9D5D7993F78701CC678B9B9C7EB3FD9EBDF9`、lock SHA `FC6D19DF4E55E495DE1735D4AA00B7A7548F69BFDCB9464865F5758015173D47`。独立69核验该修复，不自动签发G3。

### CAMERA-REGRESSION56（2026-10-20；checkpoint）

- 总控根据用户继续收口请求签发 GOV-2.1 单次有界增量；基准 `30bd1d3e7555c0bebb029d1bb68ba9711db3f7ea` + preserved dirty，分支 `feat/fe-001-g2-api`。仅允许增强 `radar-create.spec.ts` 与四份当前记录，不改产品实现；一次 targeted verification，MaxIterations=1，截止 23:05 +08，完成即 STOP。禁止依赖安装、认证/Docker/native runtime、新阶段及 commit/push/PR/merge。
- REVIEW54 P2 的定向补强：先确认真实模式为空、画布 ready 且具有键盘焦点；按右方向键 `ceil(width/40)+20` 次。以创建后真实 worldX 计算保留旧相机时节点横坐标，必须小于 -500px；正常创建后不按 F，节点必须完整位于视口。既有冲突、输入保留、pending 防重、UUID、焦点断言不变。
- 唯一 targeted set：typecheck PASS、Vite build PASS（53 modules）、Edge 单目标 create 用例 1 PASS（6.7s，整轮 10.4s，0 retries）。输出 `frontend/test-results/first-radar56/`；测试 SHA256 `AC3AFBCD0601E0341944263F2253E4C7E0EF545AEB7AD57B192B9DE42A311FED`。Universe 未变，SHA 仍 `D1E8D1758BFA5E4CB8D0CA4479831624CEEFA78732709D4C72E5F85F62355092`。
- RECORD55 上一轮文档检查失败是 README 未包含 CAMERA53 标识，不能追认通过；本轮补上该标识及 camera 候选摘要，重新执行具名文档一致性检查。REVIEW57 单独只读裁定补强，不重复测试。源码候选未提交、原生包未更新，最终精确提交 Stage Gate 与 G2 产品验收仍待完成。

### NATIVE-LIFECYCLE51 / CLEANUP52 / CAMERA53（2026-10-20）

- CAMERA-REVIEW54：独立两文件只读源码审查 SHA 匹配，P0/P1/P2=0/0/1，无源码 BLOCK。剩余 P2 为 create viewport 断言未显式建立旧 camera 必定离屏的前置条件；现有 13 项 PASS 不能证明未修复版必定失败。保留该发现供后续定向补强，不将源码 Review 冒充最终提交 Stage Gate。
- 用户手动注册进入 PREP50 隔离真实账户；初始 users=1、radars=0，agent 未输入认证信息。原生 UI 仅创建一个 `Native Lifecycle 20261020 51`（custom）作为必要前置：Radar `47d132ab-3d7d-460c-a0e6-12ae717869cf`、owner `166db2c8-0198-4e41-8ee8-f431a3d64ccb`、未删除。原生 F 适配、Tab 聚焦行星并 Enter 打开对应详情，均有实际画面与动作结果，不把用户回复本身当验收证据。
- Escape 取消暂停确认后，焦点返回原 Pause 按钮，直接 Enter 能重新打开确认；Tab 选中确认并 Enter 后，恰好一次 POST pause=200，DB 同 UUID/owner 状态为 paused。原生新 Resume 按钮有可见焦点，无鼠标重聚焦直接 Enter 打开恢复框；Shift+Tab 在框内循环到确认，Enter 后恰好一次 POST resume=200，DB 返回 active、未删除。焦点回到新 Pause；Escape 关闭详情后焦点回到同一行星。未执行删除或重复 Source/collect/Signals 链路。
- Native51 使用 PACKAGE42 二进制 SHA `8B2A0D1D5E641BB0366BCF10691E7C313F9C960C17BF2A447C4BBAFA6B8384C6`。SKY 的 focused_element 对该 WebView 一直返回 RootWebArea，故不声称取得精确 DOM focus metadata；以可见焦点环、立即按键激活目标控件、API 日志与 DB 对照证明指定 native keyboard/lifecycle。不是完整 G2/INT/Release 验收。
- 发现 P2：首个新建行星在初始空地图相机视野外，按 F 才显示；P3：详情说明仍误称 CRUD/Source/Signals 待接入。CAMERA53 仅改 `Universe.tsx`，只在 Radar 数从 0→非0 时调用既有 fit，不在已有行星编辑、状态更新或拖动时重排；同时修正两种语言说明。原 create 成功用例新增 `toBeInViewport({ratio:1})` 且不按 F。typecheck、Web build（53 modules）、创建/编辑/生命周期三文件 Edge 定向 13/13 PASS（1.3m、0 retries），diffcheck PASS。未重复完整 UI 套件；当前 native exe 仍为 CAMERA53 之前的 PACKAGE42，后续需在最终候选打包，不把 Web 修复说成已重新原生运行。
- CLEANUP52 于 20:37 精确关闭 native PID35668，并按 PREP50 的完整 ID 与 lease/owner 清理四个容器、两张网络；专名容器/网络/卷最终均为0，匹配的 watchdog PID16152 已停。临时账号/Radar 随 tmpfs 删除且不可恢复；证据保留，默认开发卷及其他资源未动。全程无 commit/push/PR/merge、新依赖、Backend/API/schema 修改；该 checkpoint 后无后台执行 authority。

### NATIVE35/36、POINTER39/40、PACKAGE42 / PREVIEW43（2026-10-20）

- 用户明确要求主界面背景像启动画布一样随鼠标轻微移动，不是移动 Radar 或重做画布拖动。此增量仅改 `OriginalBackdrop.tsx`、`original-intro.css`，新增 `tests/backdrop-pointer.spec.ts`；既有 wire27/motion30/其他 dirty 全部保留。背景偏移限制水平 ±12px、垂直 ±9px，独立 `translate` 不覆盖既有旋转；180ms 平滑、RAF 合并输入、16px 外扩防露边。应用 quiet、系统 reduced-motion 关闭跟随，pointer leave/blur/resize/hidden/按键拖动复位，清理监听与待执行 RAF。不增加依赖，不改 Backend/API/Schema/资产、Radar 或画布手势。
- typecheck、Vite build（53 modules）通过。POINTER39 一次 Edge 定向执行：原旋转/系统减少动态两项与指针跟随/前景固定/覆盖边缘、失焦/离开/拖动复位两项共 4 PASS；quiet 检查 FAIL、最后 system pointer 检查未运行。失败原因是测试把 computed CSS 零位移固定读为两个值，但浏览器合法简写为 `0px`。ASSERTION40 在新 bounded lease 内仅将缺省 y 规范化为 0，不改产品代码或预期零位移；仅复核未完成两项，2/2 PASS、0 retries。保留首轮失败证据；不称一次六项全绿，也不混入旧 HEAD 的 full39。测试产物分别位于 `frontend/test-results/backdrop-pointer39/` 与 `backdrop-pointer40/`。
- PACKAGE42 一次 locked/offline debug 构建通过，Rust 编译 20.93s；exe：`frontend/src-tauri/target/debug/flowtracer-desktop.exe`，SHA-256 `8B2A0D1D5E641BB0366BCF10691E7C313F9C960C17BF2A447C4BBAFA6B8384C6`。旧离线预览通过正常关闭退出；PREVIEW43 经 SKY 启动新包、跳过启动、显式进入 Demo，实际显示星图/6 个演示 Radar/104% 视图并留给用户体验。无认证输入、测试账号或 Docker，本轮 Backend 未启动；登录页本机 API 未就绪为预期，不把 Demo 视为真实链路证据。
- NATIVE35/36 的原生旋转观察为 16:37:22/40/56，初始静止由应用 Reduce Motion 开启造成，取消仅此普通偏好，未改系统/安全/隐私设置。原生显示可见旋转且前景/面板固定；精确 120s 周期来自 CSS 和 Edge，不冒称原生完整周期实测。此次指针位移/减少动态量化来自 Edge；新 native 包只完成启动与 Demo 预览，不替代全面 native 指针或产品验收。
- EVIDENCE37/38 在原 FE 任务因 `git -C` 返回 Permission denied 停点，未改文档。总控侧显式 Git/文件读取已确认工作树与精确 HEAD，现按用户直接要求执行此小范围前端增量与记录，不改权限、不提权、不重试原任务失败命令，也不追认其成功。未 commit/push/PR/merge；G2 产品验收、G3、INT 与 Release 未获准入。POINTER-EVIDENCE44 文档检查后 STOP；预览保留不是后台执行 authority。

## DELTA-REVIEW46 当前增量只读复核（2026-10-20）

- 原 FE 任务在新 bounded read-only review 中成功读取并核对 `api.rs`、`OriginalBackdrop.tsx`、`original-intro.css`、`backdrop-motion.spec.ts`、`backdrop-pointer.spec.ts` 五个原文 SHA，与总控提供的精确输入一致；未重试被拒的 Git 命令，未编辑或执行测试/runtime。Git HEAD/branch 由总控核实，不冒称 reviewer 独立核实提交身份；此审查不是最终精确提交 StageGate。
- 结论 P0/P1/P2=`0/0/1`，当前源码增量无 BLOCK：Backend snake_case 与 bridge camelCase 分离正确，run/source identity 与 session fencing 保持；背景独立 translate 不覆盖旋转，16px 外扩覆盖 ±12px/±9px，quiet/system reduce 与监听/RAF 清理保持。单值 CSS 零位移规范化未放宽断言。
- P2：pointer 测试尚无 resize、visibilitychange 的直接复位断言；产品已实现两条复位路径，目前未发现功能缺陷。保留为低风险回归补测建议，不扩大为新的安全 Gate，也不因追求完整视觉性能基准反复运行。
- G2 的既定原生 pause→resume/keyboard 焦点验收、最终精确提交的回归及 StageGate 仍待完成。不要在最新包重复既有 AUTH/FLOW31 全链路；本次原生补验只针对未取得的生命周期证据。Memory/Opportunity/Galaxy 持久化仍是未准入 G3；Integration/Release 及教程实现未准入。下一次桌面补验等待用户可操作时间，尚未为此建立新测试库或 Docker 资源。

## AUTH-01 checkpoint（branch-local）

- 当前候选只覆盖最小 native HTTP bridge、ready、register/login/logout/refresh、`users/me` 与 Radar 列表读取映射；Radar 写入、Source、采集与 Signals 仍未实现。
- 原启动画布、双语、星图/切换动画与 assets 保留；真实模式默认，Demo 仍须显式进入并持续标识。WebView 不接收 Access/Refresh Token。
- 依赖仅增加锁定的 `@tauri-apps/api` 及获准的 reqwest/serde/serde_json/tokio direct dependencies。Backend、OpenAPI、schema、migration、评分与 Pipeline 无改动。
- `AUTH-01` 的实现增量已停点；后续 compiler 与 IPv6 最小修复分别在新 lease 验证，见下方独立 checkpoint。此段不签发继续实现的许可。

### AUTH-AUDIT-01 依赖告警归因停点（2026-10-13）

- 原 `npm install` 曾提示 1 moderate、2 critical，但未给出 advisory ID 或包名。本次对同一锁定依赖图使用 npm 11.17.0、官方 registry 执行在线 `npm audit --json`、`--omit=dev` 和离线缓存查询，三者均返回 0 漏洞；因此无法将旧提示可靠归因到具体 package、路径或修复版本，不推断其已被某次升级修复。
- `package.json`/`package-lock.json` 相对 `24e2ebd` 仅新增 `@tauri-apps/api@2.12.3`；本审计未改依赖、锁或源码。已确认的当前 npm 漏洞 P0/P1=0；旧提示与当前报告不一致为待解释的审计证据 P2。
- 建议允许继续 AUTH 功能验证；正式产品准入前应在最终锁文件上再次取得可归档的在线审计结果并由总控裁定。此记录不签发下一操作许可。

### AUTH-VERIFY-01 定向验证停点（2026-10-13）

- `npm run test:unit`：3 文件、15/15 passed；`npm run build`：48 modules，PASS。已通过的 TypeScript 检查与 Rust 6/6 fixture/security/session 测试未另行重复。
- `npm run test:e2e`：15/15 passed，1.5 分钟、单 worker、零 retry。最初默认浏览器路径缺 Chromium；改用已存在、版本匹配的只读 Playwright Chromium 1248 缓存后完成同一验证组，未安装浏览器。现有 Entry/Universe E2E 中的网络监测未发现非本机预览请求；不将此浏览器结果作为真实 Backend 或 native 交互证据。
- `npm run build:desktop:debug -- -- --locked`：PASS，内含一次 Web 构建及 Rust dev 编译。Windows 可执行文件 `frontend/src-tauri/target/debug/flowtracer-desktop.exe`，14,808,576 bytes，SHA-256 `149A43A54C450069D3F5B4C9AA204983EA92BB093CD1E55499DB7108C175E065`。构建未启动桌面窗口。
- 沙箱 `spawn`/测试目录 EPERM 仅在获准的同命令最小权限重试后通过。`NO_COLOR`/`FORCE_COLOR` 提示为输出颜色警告。此次验证 P0/P1/P2=`0/0/0`，P3 为该无功能影响警告；前述审计证据 P2 仍单独保留。AUTH-01 范围内的 Web、fixture 与构建验证 PASS，真实 Backend、隔离 `_test` 数据库、desktop 请求与 native 点击/重开仍未取得，FE-001 产品验收及 INT-001/REL-001 未准入。

### AUTH-RUNTIME-02 预检停点（2026-10-13）

- 本轮在 `feat/fe-001-g2-api@24e2ebd14ac559ae9251424f30a4295f3006e0a0` 开始；5 小时/每周额度剩余分别为 51%/92%，Docker Linux Engine `29.8.2` 可用。未触碰已有的默认 `flowtracer-*` 容器或卷。
- 现有本地 `flowtracer-backend:be6` 镜像在网络禁用、当前 `backend/app` 与 `backend/alembic` 只读挂载的一次性容器中导入当前 API 失败：`ModuleNotFoundError: No module named 'scrapling'`。另两个现有镜像 `flowtracer-worker:latest` 和 `flowtracer-api:latest` 同样缺少该依赖；当前 worktree 没有 `backend/.venv/Scripts/python.exe`。这些镜像不能作为当前 Backend 源码的可信运行时。
- 按本 lease 的失败停点停止；未安装依赖、构建镜像或启动 PostgreSQL/Redis/API/桌面窗口，未创建 `_test` 数据库或测试账号。一次性预检容器使用 `--rm`；精确名称 `ft-fe-g2-auth-runtime02` 的容器、网络、卷检查均为空，无本轮持久资源待清理。
- 真实 Backend/原生 Tauri 请求、`users/me`、空 Radar、退出/重开验证均**未执行**，不能声明 AUTH 接口运行态通过。下一步需总控另签构建或准备含当前锁定依赖的隔离 Backend 运行时许可，再重新签发运行态验证；本记录不自动续期或授权修复。

### AUTH-RUNTIME-PREP-01 镜像准备停点（2026-10-13）

- 在同一 `feat/fe-001-g2-api@24e2ebd14ac559ae9251424f30a4295f3006e0a0` 上复核额度：5 小时/每周剩余 41%/91%。`backend/uv.lock` 锁定 `scrapling==0.4.15`；专用标签 `ft-g2-auth-test:fc180a1-01` 构建前不存在。
- 唯一一次 `docker build --pull=false` 使用当前 `backend/Dockerfile`、构建上下文与锁文件，成功生成专用 Linux/amd64 镜像。镜像 ID `sha256:7f62b51da989aa04c733824bd3f31a38e995bbd893a07b60853f8309c36c9095`；Docker 命中本地锁定依赖和源码层缓存，未触发依赖下载。构建约 30 秒；未见构建告警或错误。镜像保留供下一独立运行态 lease 使用，默认 `flowtracer-*` 镜像未改动。
- 唯一一次 `--rm --network none`、Fake/test 配置导入检查通过：`scrapling 0.4.15`、当前 `app.main` 的 `FlowTracer API`、Alembic head `20261006_0009`。未启动 lifespan、连接数据库或执行 migration；一次性容器已自动移除。此准备步骤 P0/P1/P2=`0/0/0`，不代表 API readiness、迁移或桌面运行态通过。
- 本轮未启动 PostgreSQL/Redis/API/桌面程序，未建 `_test` 数据库/账号，未改源码、锁文件或 Dockerfile，未 commit/push/PR。下一步仅由总控另签隔离资源及原生 AUTH 验证许可；本镜像准备记录不自动续期。

### AUTH-RUNTIME-03 运行态阻断停点（2026-10-13）

- `AUTH_RUNTIME_BLOCKED`。开始时 `feat/fe-001-g2-api@24e2ebd14ac559ae9251424f30a4295f3006e0a0`、专用镜像 ID `sha256:7f62b51da989aa04c733824bd3f31a38e995bbd893a07b60853f8309c36c9095` 均匹配；5 小时/每周额度剩余 36%/90%。已有桌面 exe 14,808,576 bytes，SHA-256 `149A43A54C450069D3F5B4C9AA204983EA92BB093CD1E55499DB7108C175E065`，但本轮未启动。
- 唯一隔离资源：内部网络 `ft-g2-auth03-20261013-net`（ID `b5d54c48ca347dda3c813c9ba5051e08bb3875f0704f2c2c646b4a57a08aa217`）、无主机端口/无卷的 PostgreSQL（ID `2a4d263c9f0c3889ecd8eabc77ae3a7ebdefe1f3383dcc9ce69ff95d029`）和 Redis（ID `63d03b5ff25ad6200142c6ae0880c8c31c8e45e6530090405881c6119b1c6e56`）。数据库 `flowtracer_auth_test_20261013` 名称含 `_test`；`pg_isready`、Redis PONG 通过。Fake/test 配置的一次性迁移容器在 API 前成功运行，数据库 `alembic_version=20261006_0009`。
- API 容器 ID `4dc07704e601184dfaa38beced86e80f4f265cf7e782aa0f7110fa516f1e78dd`，日志显示应用启动并在容器内 `0.0.0.0:8000` 监听。虽请求了 `127.0.0.1:18083:8000`，Docker `HostConfig.PortBindings` 有该配置，但 `NetworkSettings.Ports` 对 `8000/tcp` 为 `[]`；本机 `health/live` 和 `health/ready` 均被拒绝连接。该内部网络拓扑未形成桌面所需的回环 API 端点；未更改网络拓扑或启动第二次 API 尝试。
- 因端点阻断，Tauri native bridge、注册、`users/me`、空 Radar、退出和重开均**未执行**，没有账户、请求 trace 或真实桌面接入结论。未发现候选产品源码缺陷；本轮 P0/P1/P2=`0/1/0`，其中 P1 是运行态验证阻断，不是已证实的产品缺陷。不得据此批准 FE-001 产品或 INT-001/REL-001。
- 精确停止本轮三个 `--rm` 容器并删除上述专名网络；按 lease 标签/名称复核容器、网络、卷均为空。未触碰默认 Docker 资源，专用镜像保留；未安装、构建、修改源码、提交或推送。需总控另签网络拓扑修正后的独立运行态 lease；本轮不得自动续跑。

### AUTH-RUNTIME-04 原生证据阻断停点（2026-10-13）

- `AUTH_RUNTIME_BLOCKED`。开始时 `feat/fe-001-g2-api@24e2ebd14ac559ae9251424f30a4295f3006e0a0`、专用镜像 ID `sha256:7f62b51da989aa04c733824bd3f31a38e995bbd893a07b60853f8309c36c9095` 匹配；5 小时/每周额度剩余 28%/89%。现有桌面 exe 哈希仍为 `149A43A54C450069D3F5B4C9AA204983EA92BB093CD1E55499DB7108C175E065`。
- 新建专名非 internal bridge 网络 `ft-g2-auth04-20261013-net`（ID `ab416b352fcc0c774e2ea531799c903e31b1454dd16edd8b298b72d80e0bb864`），设置 `enable_ip_masquerade=false`；PostgreSQL ID `f7cf1f72568ca8fe95970a53aa871866caa857fcdef5078db5bca955fbb1f513` 与 Redis ID `5a57e1220dec3481ab662dd8a9d82a95ead4745d7e8cd910be9682269dd98880` 无主机端口或卷。隔离数据库 `flowtracer_auth_test_20261013_04` 在 API 前迁移到 `20261006_0009`。
- API ID `6e4235f55183fba76f9082a002997e9fa11d77a1938c56c95400cb796a5886cd` 实际映射仅 `127.0.0.1:18083:8000`；本机 live 返回 `ok`，ready 返回 `ready` 且 database/redis 均为 `ok`，日志记录两次 GET 200。Fake/test 配置，未观察到真实采集/付费目标请求。数据库 `users` 计数为 0；日志仅有启动和两条 health 请求，无认证凭据/令牌。
- 桌面可执行文件经 computer-use 启动并显示 `http://tauri.localhost/` 原生窗口与启动画布，但未取得 native bridge 到本轮 API 的请求证据。带进程级 `FLOWTRACER_API_ORIGIN=http://127.0.0.1:18083/api/v1` 的命令行启动进程立即退出，未留下可操作窗口；computer-use 启动器不提供进程环境参数，源码默认 origin 为 `127.0.0.1:8000`。两次 UI 输入尝试均收到“user input was detected in this window”并按技能要求重新观察/停止，未抢占用户交互。因此没有注册、`users/me`、Radar、退出/重开结果，不能用 curl 的 ready 代替原生 AUTH 证明。
- 此次运行态 P0/P1/P2=`0/1/0`，P1 为原生请求证据未建立的验证阻断，未证实产品源码缺陷。精确停止本轮桌面 PID `35816`、三个 `--rm` 容器并删除专名网络；复核该进程及本轮容器/网络/卷均不存在。未改源码、包、锁或默认 Docker 资源，未 commit/push/PR；专用测试镜像仍保留。下一运行态尝试须由总控另签可向可操作 Tauri 进程传入 API origin 的方案及独立许可。

### AUTH-RUNTIME-05 原生 ready 局部证明与授权阻断（2026-10-14）

- `AUTH_RUNTIME_BLOCKED`，但 native readiness 已得到局部真实证据。开始时 `feat/fe-001-g2-api@24e2ebd14ac559ae9251424f30a4295f3006e0a0`、测试镜像 ID `sha256:7f62b51da989aa04c733824bd3f31a38e995bbd893a07b60853f8309c36c9095` 与桌面 exe SHA-256 `149A43A54C450069D3F5B4C9AA204983EA92BB093CD1E55499DB7108C175E065` 均匹配；5 小时/每周额度剩余 73%/82%，启动前端口 8000 无监听。Docker Desktop 最初未运行，按此前人类授权启动后 Engine 恢复。
- 本轮专名资源：非 internal、`enable_ip_masquerade=false` bridge 网络 `ft-g2-auth05-20261014-net`（ID `f6526761116ba259076f3c65008ac84eb2fb60469da058b4ce05cabe6a4d1a9a`）；无主机端口/无卷 PostgreSQL ID `327c82cded5457b490fc082b47e4e55642c7bbee5a8d02136d79696065d7eda0`、Redis ID `d5f7bfb4194626b06a51bb1d25e0d6e89069fe0bf9c9aad8deae5b7ae6b8f0e4`。空库 `flowtracer_auth_test_20261014_05` 先迁移至 `20261006_0009`；API ID `5c8448fc426e9a8c32e4463dfbee4e6abad61478ca7b1e2eeca1fe7483008d7e` 仅映射 `127.0.0.1:8000:8000`，Fake/test 配置，live/ready 均 200，ready 的 database/redis 为 `ok`。
- 使用 computer-use 启动已有 exe，Tauri 窗口的真实登录页显示 native origin `http://127.0.0.1:8000/api/v1` 和“本机 API 已就绪”。在 CLI 两次 health GET 之后，Backend 日志于 `2026-10-14T03:43:39Z` 另记 `GET /api/v1/health/ready` 200（request_id `46723126-2b77-4220-8dd2-007c38e4ac9d`），与切入原生登录页吻合；该证据支持 native bridge readiness，而不证明 AUTH 会话链。
- 为避免 computer-use 的 UI 创建账户确认闸门，拟仅在授权的 `_test` API 建立一个随机/一次性账号，再从原生窗口登录。Node 环境的本机 fetch 和沙箱 PowerShell socket 请求均在网络权限层失败，没有到达 Backend；随后最小提权的账户创建请求被自动审核明确拒绝，理由是缺少可核验的人类直接授权，并要求不得用其他通道绕过。因此未再尝试 UI 注册或其他变通。日志没有 auth POST；数据库 `users=0`、`radars=0`。原生登录、`users/me`、空 Radar、logout 与重开仍未执行，不能判定 AUTH_RUNTIME_PASS。
- 本轮 P0/P1/P2=`0/1/0`，P1 是账号创建授权与后续原生会话证据阻断，不是已证实的产品源码缺陷。已关闭本轮 Tauri 窗口，精确停止三个 `--rm` 容器并移除专名网络；复核本轮容器/网络/卷及 FlowTracer 桌面进程均为空，专用镜像保留，既有 dirty worktree 未变、无 commit/push/PR。后续必须先取得人类对“在隔离 `_test` 库创建一个临时账号”的明确直接批准，再由总控签发新的运行态验证许可；本 lease 不自动续跑。

### AUTH-RUNTIME-06 UI 最终确认停点（2026-10-14）

- `AUTH_RUNTIME_BLOCKED`。总控线程的用户直接回复“授权创建一次性测试账号”已核实，且总控另签本轮 lease；这不追认上轮被拒的请求。开始时 `feat/fe-001-g2-api@24e2ebd14ac559ae9251424f30a4295f3006e0a0`、专用镜像 ID `sha256:7f62b51da989aa04c733824bd3f31a38e995bbd893a07b60853f8309c36c9095`、桌面 exe SHA-256 `149A43A54C450069D3F5B4C9AA204983EA92BB093CD1E55499DB7108C175E065` 匹配；5 小时/每周额度剩余 42%/77%，端口 8000 启动前无监听。
- 本轮全新非 internal、`enable_ip_masquerade=false` 网络 `ft-g2-auth06-20261014-net`（ID `b46bc37f15975bca9d4a72d5029b8c8cb4abaf50d324cbcb2c5afb3f4b933ce3`），无主机端口/无卷 PostgreSQL ID `f250ea9b6903d5e9bcd0823dd7b79b5f2b441521eff45c079551890fc1c71fd5` 与 Redis ID `8f661b16e29535c434f0efc9498fce8569e7769de62005bee707944e3e7645f1`。空库 `flowtracer_auth_test_20261014_06` 先迁移至 `20261006_0009`；API ID `9d95a5f81dce33e440b8b18420c4015b31e89576f10d14367573cdc4dafa4b21` 仅映射 `127.0.0.1:8000:8000`，Fake/test 配置，live/ready 200。
- computer-use 启动现有 Tauri exe，原生登录页显示 `http://127.0.0.1:8000/api/v1` 及“本机 API 已就绪”；Backend 在 CLI 健康检查之后独立记录 `2026-10-14T04:01:43Z` 的 `GET /api/v1/health/ready` 200（request_id `146cca92-2fb4-4271-bbed-ab3a7d8c5908`）。这是 native bridge readiness 的真实局部证据。
- 在原生注册页填入随机临时凭据，但**没有点击提交**。computer-use 技能要求创建账号的最终 UI 动作即使预先批准也须当场确认；已发出当场确认问题并等待数分钟，未收到回复。因 15 分钟硬截止与安全清理余量，主动停点并关闭未提交的窗口，未改走 API 或其他通道。Backend 日志无 auth POST，数据库 `users=0`、`radars=0`；没有登录、`users/me`、真实空 Radar、logout 或重开证据。未打印密码/令牌，未观察到外部目标请求。
- 本轮 P0/P1/P2=`0/1/0`，P1 是 UI 最终确认与后续 AUTH 运行证据缺失，未证实产品源码缺陷。已精确停止本轮三个 `--rm` 容器并删除专名网络，复核容器/网络/卷及 FlowTracer 桌面进程均为空；专用镜像保留，其他 Docker 资源与既有 dirty worktree 未触碰，无 commit/push/PR。下一操作仍需总控另签，不得自动续跑；若再经 UI 创建账号，须在最终点击时取得当场确认。

### AUTH-RUNTIME-08 UI 最终确认停点（2026-10-14）

- `AUTH_RUNTIME_BLOCKED`。`feat/fe-001-g2-api@24e2ebd14ac559ae9251424f30a4295f3006e0a0` 与专用镜像 ID `sha256:7f62b51da989aa04c733824bd3f31a38e995bbd893a07b60853f8309c36c9095` 匹配；开始时 5 小时/每周额度剩余 69%/67%，结束时 55%/65%。端口 8000 启动前无监听，原有桌面 exe 哈希匹配既有记录。
- 本轮新建专名非 internal、`enable_ip_masquerade=false` bridge 网络 `ft-g2-auth08-20261014-net`；PostgreSQL 与 Redis 无主机端口/无卷。空库 `flowtracer_auth_test_20261014_08` 先迁移至 `20261006_0009`；Fake/test API 实际仅映射 `127.0.0.1:8000:8000`，live/ready 均通过，ready 的 database/redis 为 `ok`。
- 既有 Tauri exe 原生窗口显示 `http://127.0.0.1:8000/api/v1` 与“本机 API 已就绪”。在原生注册页填入随机一次性凭据，未点击最终提交；按 computer-use 技能发出当场确认，但截至清理时没有收到直接回复。没有改走 API 或其他通道。关闭未提交窗口前，数据库 `users=0`、`radars=0`；没有注册、登录、`users/me`、真实空 Radar、logout 或重开证据，不能判定 AUTH_RUNTIME_PASS。
- 本轮 P0/P1/P2=`0/1/0`，P1 为当场确认及后续 AUTH 运行证据缺失，并非已证实产品缺陷。已精确停止本轮三个 `--rm` 容器，删除专名网络；按 lease 标签/名称复核容器、网络、卷和 FlowTracer 桌面进程均为空。专用镜像保留，既有 dirty worktree 未重置；无源码/锁文件修改、commit/push/PR。下一操作须总控另签，不得自动续跑。

### AUTH-API-SEED-09 原生会话定向验证（2026-10-15）

- 本轮针对总控新签的 `FE-001-G2-AUTH-API-SEED-09`，在 `feat/fe-001-g2-api@24e2ebd14ac559ae9251424f30a4295f3006e0a0` 执行；开始时 5 小时/每周额度剩余 51%/64%。专用镜像 ID `sha256:7f62b51da989aa04c733824bd3f31a38e995bbd893a07b60853f8309c36c9095` 匹配，端口 8000 启动前无监听。
- 全新专名网络 `ft-g2-auth09-20261014-net` 为非 internal bridge、`enable_ip_masquerade=false`；PostgreSQL、Redis 无主机端口和卷。新库 `flowtracer_auth_test_20261014_09` 先迁移至 `20261006_0009`；Fake/test API 实际只映射 `127.0.0.1:8000:8000`，live/ready 均 200，database/redis 为 `ok`。
- 依人类对一个 `_test` 临时账号的直接授权，仅通过本机 API 注册。首次随机邮箱使用 `.invalid` 保留域，被请求校验以 422 拒绝；核实 `users=0` 后在同一序列中换用示例域，一次 201 创建成功。账号为随机测试凭据，未打印密码或令牌；最终库计数 `users=1`、`radars=0`。**没有点击原生 UI 注册**，该路径仍未验证。
- 既有 Tauri exe 的真实窗口显示本机 API 就绪。原生登录两次均成功并显示真实空 Radar 星图；隔离 API 日志仅按 method/path/status 提取，`POST /auth/login` 200×2、`GET /users/me` 200×2、`GET /radars` 200×2、`POST /auth/logout` 204×1（均带 `/api/v1` 前缀）。退出后返回空登录页；再次登录后不退出而关闭进程、重新启动，跳过启动画布后仍是空邮箱/密码登录页，未恢复已登录星图。这是 native 会话链和进程内存令牌的定向证据，不等于 UI 注册或完整 FE 产品验收。
- API 另收到来源未确认的本机 `/mcp` 与 OAuth discovery 路径探测，全部 404；未观察到相关写入或成功响应，未推断其来源。该观察与 AUTH 主链独立。P0/P1/P2=`0/1/1`：P1 为原生 UI 注册仍缺证据，P2 为上述意外本机 404 探测；均非已证实产品源码缺陷。已关闭本轮桌面进程，精确停止三个 `--rm` 容器、删除专名网络，复核本轮容器/网络/卷和桌面进程均为空；测试镜像保留。无源码/锁文件改动、commit/push/PR/merge，下一操作须总控另签。

### AUTH-UI-REGISTER-10 Docker Engine 预检停点（2026-10-15）

- 总控签发的 `FE-001-G2-UI-REGISTER-10` 于 `feat/fe-001-g2-api@24e2ebd14ac559ae9251424f30a4295f3006e0a0` 预检；既有 dirty/untracked 文件保持原状，`CURRENT-GATE` 顶部仍为 FE-G2 AUTH-01 候选、INT/Release 未准入。可靠额度在开始时 5 小时/每周剩余 89%/59%；本机端口 8000 无监听，未见 FlowTracer 桌面进程。
- Docker Linux Engine 管道 `npipe:////./pipe/dockerDesktopLinuxEngine` 不存在，`docker version` 与专用镜像 inspect 均无法连接 Engine。专用镜像在上次 lease 已核实并保留，但本轮不能声称当前镜像或 Engine 已通过检查。启动 Docker Desktop 会改变共享运行环境，未获本 lease 单独授权，因此按预检失败停点停止，没有尝试恢复、重试或另用运行时。
- 本轮未创建网络、容器、卷或 `_test` 数据库，故没有本轮 `users`/`radars` 计数；未启动 Tauri、未生成/输入凭据、未发出当场确认、未点击注册。原生 UI 注册仍**未验证**。P0/P1/P2=`0/1/0`，P1 是 Engine 预检阻断而非已证实产品缺陷。无源码、锁文件改动，无 commit/push/PR/merge；下一操作须总控另签 Docker 恢复及重新运行许可。

### AUTH-UI-REGISTER-11 原生注册定向证据（2026-10-15）

- 总控新签 `FE-001-G2-UI-REGISTER-11`，在 `feat/fe-001-g2-api@24e2ebd14ac559ae9251424f30a4295f3006e0a0` 执行。开始时 5 小时/每周额度剩余 85%/59%，结束时 70%/56%；既有 dirty/untracked 保留。Docker Linux Engine `29.8.2` 已可用，本轮**没有**启动 Docker Desktop。专用镜像 ID `sha256:7f62b51da989aa04c733824bd3f31a38e995bbd893a07b60853f8309c36c9095` 和桌面 exe SHA-256 `149A43A54C450069D3F5B4C9AA204983EA92BB093CD1E55499DB7108C175E065` 匹配。
- 新建专名非 internal、`enable_ip_masquerade=false` 网络 `ft-g2-auth11-20261015-net`；PostgreSQL/Redis 无主机端口或持久卷。独立库 `flowtracer_auth_test_20261015_11` 先迁移至 `20261006_0009`，初始 `users=0`、`radars=0`。Fake/test API 实际仅映射 `127.0.0.1:8000:8000`，本机 live/ready 200，database/redis 为 `ok`。
- 既有 Tauri exe 原生窗口的注册页显示本机 API 已就绪及 `http://127.0.0.1:8000/api/v1`。仅在此页填入随机一次性 `example.com` 测试邮箱、显示名和密码；没有调用 API 建号。按 computer-use 技能在最终提交前发出当场确认，用户对**这个库和此窗口**直接回复“确认点击并验证”。确认传递期间，本 agent 尚未点击；随后复核发现唯一用户已创建，故没有重复提交。原生窗口已进入真实空 Radar 星图；可见“真实连接”“此账户目前没有 Radar”“没有加载演示数据”。后端同一序列记录 `POST /api/v1/auth/register` 201×1，紧接 `GET /api/v1/users/me` 200×1、`GET /api/v1/radars` 200×1；最终 `users=1`、`radars=0`，唯一用户的非敏感模式与本轮表单一致。服务端日志不记录点击者身份，因此不将最终点击归因于本 agent；没有第二次点击或注册请求。
- 本轮原生 UI 注册→用户信息→真实空 Radar 的定向链路有实证；前轮 API-SEED-09 的登录、logout、重开证据仍单独保留。此结果不自动批准完整 FE-001 产品或 INT/Release 阶段。此次未发现 P0/P1/P2 产品缺陷（`0/0/0`）；前轮来源未明的本机 404 探测观察仍保留为独立历史记录。已关闭本轮 Tauri 进程，精确停止三个 `--rm` 容器并删除专名网络，复核本轮容器/网络/卷及桌面进程均为空；隔离账号随无卷 PostgreSQL 容器删除，专用镜像保留。未改源码/锁文件，无 commit/push/PR/merge；下一操作须总控另签。

### FE-001-G2-NATIVE-VISUAL-01 Docker Engine 预检阻断（2026-10-15）

- 本轮从干净的 `feat/fe-001-g2-api@551d29f54aa530b6a9fc2329358c1861b42c24a5` 本地 checkpoint 开始；5 小时/每周额度剩余 63%/94%，本机端口 8000 无监听。此 SHA 是前述 `24e2ebd` 交付基线的后续本地提交；顶部“AUTH-01 仍未 commit”是提交前快照，不代表本轮状态。本次 lease 仅允许追加证据，不改写该历史快照。
- Docker Linux Engine 的 `npipe:////./pipe/dockerDesktopLinuxEngine` 管道不存在，`docker version` 和专用镜像 `ft-g2-auth-test:fc180a1-01` 的当前 inspect 均无法连接 Engine。按 lease 在预检失败处停止，未启动或修改 Docker Desktop/共享设置，也未执行获准的一次 Windows debug rebuild；现有旧 exe 不作为 P1 修复后构建，故无本轮 exe SHA。
- 结论为 `VISUAL_NATIVE_BLOCKED`：没有新建网络、容器、卷、`_test` 库或账号；没有启动 Tauri 窗口、原生登录、墨水消散或 reduced-motion 检查，也没有本轮截图标识和实际 auth/`users/me`/Radar 请求计数。不能把源码或既有浏览器测试当作原生视觉证明。因本轮未创建专属资源，无本轮资源需要删除；未操作其他窗口、默认容器/卷或其他 worktree。
- 本轮 P0/P1/P2=`0/1/0`，P1 是 Engine 不可用造成的验证阻断，不是已证实产品缺陷；既有两项历史 P2 观察保持原状。除本 checkpoint 文档外无源码/锁/依赖改动，无 commit/push/PR/merge。FE-G2 产品验收及 INT-001/REL-001 仍未准入；下一次原生视觉验证须总控新签 lease。

### FE-001-G2-NATIVE-BUILD-01 锁定依赖原生构建停点（2026-10-15）

- 在 `feat/fe-001-g2-api@551d29f54aa530b6a9fc2329358c1861b42c24a5` 上执行独立 build-only lease；开始时只有上一轮 admission 阻断记录未提交，5 小时/每周额度剩余 57%/93%。没有安装或升级依赖。
- 唯一构建命令为 `npm run build:desktop:debug -- -- --locked`，设置 `CARGO_NET_OFFLINE=true`。沙箱调用在设置工作目录时以访问拒绝结束，未进入构建；对同一命令最小权限重试后，内含 Vite Web 构建 48 modules PASS、Rust Windows debug build PASS，最终 exit 0。未重复全量测试。
- 输出 `frontend/src-tauri/target/debug/flowtracer-desktop.exe` 为 14,836,736 bytes，SHA-256 `0326843838A6309E8B6FCD98710003516B8A35D5936EB26FB7B92C9FF4866409`。此为当前 checkpoint 源码的构建证据，**不是** Tauri 窗口、原生 AUTH 请求、墨水转场或 reduced-motion 的验收。
- 本轮未操作 Docker、测试库、账号、API 或 UI，未修改源码/锁文件，未 commit/push/PR/merge。P0/P1/P2=`0/0/0` 为本轮构建检查结论；上一轮 Engine 阻断和两项历史 P2 观察未因此消失。FE-G2 产品验收及 INT-001/REL-001 仍未准入，下一操作须总控另签。

### FE-001-G2-NATIVE-VISUAL-02 原生视觉定向验证停点（2026-10-15）

- 在 `feat/fe-001-g2-api@551d29f54aa530b6a9fc2329358c1861b42c24a5` 上执行独立 VIS02 lease；开始时只有本 admission 文档已有未提交改动。复用上一轮锁定依赖构建的 exe（14,836,736 bytes，SHA-256 `0326843838A6309E8B6FCD98710003516B8A35D5936EB26FB7B92C9FF4866409`），本轮没有构建、安装、源码或锁文件改动。最后可靠额度检查：5 小时/每周剩余 22%/88%。
- 仅创建本轮专名网络 `ft-g2-vis02-20261015-0724-net`、无持久卷且无主机端口的 PostgreSQL/Redis、以及仅映射 `127.0.0.1:8000:8000` 的 Fake/test API；隔离库 `flowtracer_visual_test_20261015_02` 先迁移至 `20261006_0009`。开始 `users=0`、`radars=0`；一次性 `example.com` 测试账号建立后最终 `users=1`、`radars=0`。专用镜像 ID `sha256:7f62b51da989aa04c733824bd3f31a38e995bbd893a07b60853f8309c36c9095`；本机 live/ready 均通过。
- 真实 Tauri 窗口（ID `68938`，1530×864）展示启动画布、登录页、真实空 Radar 星图和设置页，截图留在本任务工具记录中；登录页显示本机 API 已就绪。正常动效登录后看到了“连接中”和最终空星图，但未捕捉到约 1.05 秒墨水消散的中间帧，因此**不能**称该转场视觉已获原生完整证明。设置页可见共享纹理/径向线背景；勾选“减少动态效果”后退出，再次登录直接到达空星图。主界面仍能看到共享径向线，截图未显示可明确区分的额外旧背景遮盖层；不据此声称旧层缺失已被充分证明。
- API access log 仅按方法/路径/状态统计：注册 201×1、登录 200×2、`users/me` 200×2、Radar 列表 200×2、退出 204×1，外加本机 health 检查；无真实采集/付费请求。第二次原生登录后的主界面仍为真实连接且 0 Radar、无演示数据。正常登录、退出及 reduced-motion 下重登有真实请求链与画面，但缺少墨水转场中间帧，结论 `VISUAL_NATIVE_BLOCKED`（定向部分证据成立，完整视觉闸门未过），本轮 P0/P1/P2=`0/1/0`；P1 为验证证据缺口，非已证实产品缺陷。不得据此批准 FE-G2 产品、INT-001 或 REL-001。
- 已关闭本轮原生窗口，精确停止本轮三个 `--rm` 容器并删除专名网络；按前缀复核容器/网络为空，端口 8000 无监听，无本轮持久卷，测试账号随无卷数据库删除。未操作其他 worktree 或默认 Docker 资源，未 commit/push/PR/merge。后续须总控另签验证许可。

### FE-001-G2-RADAR-CREATE-01 额度停工与 VERIFY-01 定向验证停点（2026-10-15）

- CREATE-01 在 `feat/fe-001-g2-api@551d29f54aa530b6a9fc2329358c1861b42c24a5` 写入 Radar 创建候选：显式 native `POST /api/v1/radars`、受保护的请求体/401 单航班刷新与会话代次围栏、WebView typed API、真实模式新建表单、收到后端成功响应后才映射 UUID 行星；Demo 加号仍保留说明入口。原有 admission 未提交改动保留。5 小时额度降至 5% 时立即停工，未运行测试、构建或提交；该候选当时**未验证**。
- VERIFY-01 从上述原工作树继续，只读核对 branch/HEAD 和 dirty 范围一致：仅本 admission、`frontend/src-tauri/src/{api.rs,main.rs}`、`frontend/src/api/desktop.ts`、`frontend/src/app/App.tsx`、`frontend/src/features/universe/Universe.tsx`、`frontend/src/styles/demo.css`、新增 `frontend/src/features/radars/RadarCreatePanel.tsx` 与 `frontend/tests/radar-create.spec.ts`；没有 Backend/OpenAPI/schema/锁文件改动。开始可靠额度 5 小时/每周剩余 95%/84%。
- `npm run typecheck` exit 0。`cargo test --manifest-path src-tauri/Cargo.toml --locked api::tests` 首次仅因沙箱拒绝打开 Cargo build lock 而未编译；同命令最小权限重试 exit 0，Rust `api::tests` 9 passed / 0 failed，包含 typed POST/path/body/返回、401 refresh、logout-inflight 创建响应围栏，以及原有安全/会话测试。`git diff --check` exit 0（仅 LF→CRLF 提示）。未运行全量测试或 native runtime。
- Playwright 配置使用 `npm run preview` 读取既有 `frontend/dist`；该产物早于 CREATE-01 候选，JS 中没有 `radars_create`。本 lease 未授权 Web build 或配置改动，因此**没有**运行只会检验旧 bundle 的 `frontend/tests/radar-create.spec.ts`，不得宣称 E2E PASS。测试源码含成功后插入 UUID、409 失败保留输入/不插入、提交中禁重复及 Demo 入口用例；缺少 Web 账号切换旧创建响应不写回用例，Demo 用例也未在有 native bridge 的 mock 下证明无写请求。这些均是待补证据，不是已证实产品缺陷。
- 结论 `RADAR_CREATE_VERIFY_BLOCKED`，本轮 P0/P1/P2=`0/1/0`（P1 为定向 E2E 前置产物及覆盖缺口）。Rust 与类型检查通过不等于真实 native Radar 创建；无 `_test` API、账户、Docker、原生 UI 或后端写入验证。FE-G2 产品、INT-001/REL-001 均未准入；源码/锁未在 VERIFY-01 修改，未 commit/push/PR/merge。下一操作须总控新签允许与当前源码一致的 Web 测试产物及缺口补测，再另行授权真实原生创建验证。

### FE-001-G2-RADAR-CREATE-REPAIR-01 定向补强失败停点（2026-10-15）

- 在 `feat/fe-001-g2-api@551d29f54aa530b6a9fc2329358c1861b42c24a5` 上保留全部既有 dirty，仅按 lease 修改 `frontend/src/app/App.tsx` 与 `frontend/tests/radar-create.spec.ts`。创建成功响应现在先在异步 handler 中执行 `toUniverseRadar` 校验/映射，再进入函数式 `setRadars`；非法 UUID/枚举异常可回到表单 Promise catch，不再从 React updater 内抛出。原有 request epoch 账号切换围栏保持。
- 单文件 E2E 源码增加：桥接调用计数验证重复提交；旧账户创建响应晚到不得写入新会话；非法 UUID 不插入、不崩溃且表单仍可操作；Demo 加号保持说明入口且 `radars_create` 调用为 0。没有扩大到其他 CRUD、Source、Signals 或 G3。
- 可靠额度开始为 5 小时/每周剩余 74%/81%，长命令前均高于 5%。`npm run typecheck` exit 0。`npm run build` 首次仅因沙箱拒绝写 `node_modules/.vite-temp` 而未编译；同命令最小权限重试 exit 0，Vite 49 modules transformed。未重复 Rust 测试；沿用 VERIFY-01 的 `api::tests` 9/9 PASS。
- Edge 单文件命令 `npx playwright test tests/radar-create.spec.ts --retries=0` 首次仅因沙箱拒绝测试输出目录而未启动；同命令最小权限重试后真实执行 4 个已发现用例，但首个用例在模拟登录后仍停留登录页，等待 `universe[data-mode=live]` 5 秒超时。配置的 `maxFailures=1` 随即停止：`1 failed / 3 did not run`，exit 1。失败发生在进入 Radar 创建断言之前；当前证据不能区分测试 harness 登录模拟问题与候选登录回归，也不能证明任何创建补强用例通过。
- 按 lease 的真实编译/断言失败即 REPORT+STOP，未修复、未重跑。结论 `RADAR_CREATE_REPAIR_BLOCKED`，本轮 P0/P1/P2=`0/1/0`；P1 为定向 E2E 红灯及未执行覆盖。未运行 Docker、native UI、真实账号或后端写入；无 commit/push/PR/merge。FE-G2、INT-001、REL-001 均未准入，后续须总控新签独立诊断/修复 lease。

### FE-001-G2-RADAR-UI-FIXTURE-01 单次测试修复停点（2026-10-15）

- 在同一 `feat/fe-001-g2-api@551d29f54aa530b6a9fc2329358c1861b42c24a5` 和保留 dirty 上，仅修改 `frontend/tests/radar-create.spec.ts`：每次登录/进入工作区显式等待 `.stage-scene[data-motion=idle]`，提交登录前核对邮箱与密码值；首个创建测试以可控 promise gate 取代时间延迟，pending 期间再次 `requestSubmit` 后桥调用计数必须保持不变，release 后才允许 UUID Radar 出现；第二账户的用户名检查改为导航 Settings 后再执行。业务源码、fixture 数据、构建产物、Rust 与锁文件未改。
- 开始可靠额度 5 小时/每周剩余 58%/79%，测试前剩余 56%/78%，均高于 5%。复用前轮已成功的 Web build/typecheck/Rust 9/9，不重复执行。唯一命令为 Edge `npx playwright test tests/radar-create.spec.ts --retries=0`，发现 4 个用例并使用 1 worker、`maxFailures=1`。
- 第 1 条 `live Radar create preserves input on failure and inserts only confirmed UUID once` PASS：409 后保持输入且无插入；成功尝试进入可控 pending 后，二次 `requestSubmit` 未增加桥调用，实际总 `radars_create` 调用计数保持为 2（含前一次 409）；release 后仅出现一个后端 UUID Radar。
- 第 2 条账号切换用例真实 FAIL：旧账户创建请求已进入 pending 且调用计数为 1；测试强制点击“设置”并等待 page-scene idle 后，30 秒内仍找不到“退出登录”按钮，故在实际执行账号切换、释放旧响应和核对新会话之前超时。按 `maxFailures=1` 停止，最终 `1 passed / 1 failed / 2 did not run`、exit 1；非法 UUID 与 Demo 零写入两条本轮未执行。
- 按 lease 的修复后仍失败即 REPORT+STOP，没有第二次修复或重跑。结论 `RADAR_UI_FIXTURE_BLOCKED`，P0/P1/P2=`0/1/0`；当前红灯位于测试无法在创建 modal pending 状态下到达退出操作，尚未证明产品的 epoch 围栏失败，也未取得非法响应与 Demo 用例本轮 PASS。无 native UI、Docker、真实账户、后端写入、commit/push/PR/merge；后续须总控另签新的有界诊断/修复权限。

### FE-001-G2-RADAR-UI-FIXTURE-02 键盘路径定向验证停点（2026-10-15）

- 在同一 `feat/fe-001-g2-api@551d29f54aa530b6a9fc2329358c1861b42c24a5` 和保留 dirty 上，仅修改 `frontend/tests/radar-create.spec.ts` 的账号切换交互：pending 创建 modal 存在时，不再用无法穿透 scrim 的 Playwright `force` 鼠标点击；改为对实际可聚焦的 Settings 与“退出登录”按钮执行 `focus()`、核对焦点并发送键盘 Enter，同时等待 page/stage scene idle。业务源码、fixture session 内容、超时、断言及其他测试均未弱化。
- 开始可靠额度 5 小时/每周剩余 52%/78%，高于 5%。唯一验证命令为 Edge 单文件筛选账号切换、非法 UUID、Demo 三项，`retries=0`、1 worker；exit 0，`3 passed / 0 failed`（19.4 秒）。未重复首个已经通过的创建成功/失败/pending 去重用例，未 build/typecheck/Rust/native/Docker。
- 账号切换测试 PASS：旧账户仅发起 1 次 `radars_create` 并保持 pending；键盘进入实际 Settings、退出、等待登录场景 idle、提交并核对第二账户输入；第二账户进入 live workspace 后才释放旧 promise，Radar 数仍为 0；再实际导航 Settings，`Second` 用户名可见。该证据覆盖 Web request epoch 对旧创建响应的隔离。
- 非法 UUID 测试 PASS：错误响应未插入 Radar，表单显示 identity 错误且仍可编辑；Demo 测试 PASS：加号仍为说明入口，`radars_create` 实际调用计数为 0。结合 FIXTURE-01 已通过且未修改的首项（409 保留输入、pending 重复提交不增调用、累计 calls=2、release 后唯一 UUID Radar），Radar 创建 Web 定向覆盖为 `4/4 PASS`。
- 结论 `RADAR_CREATE_WEB_TARGETED_PASS`，本轮 P0/P1/P2=`0/0/0`。这仍是 Web mock 定向证据，不等于真实 native/API 创建：没有 `_test` 后端写入、原生窗口、真实账号或所有权验证。无 commit/push/PR/merge；FE-G2 产品、INT-001、REL-001 仍未准入，完成即 STOP 交总控复核。

权威契约是 [Frontend Handoff](../backend/FRONTEND-HANDOFF.md) 与 [Frozen OpenAPI](../backend/openapi/flowtracer-alpha-v0.1.json)。不得推断 schema、修改 Backend，或以 UI 绕过契约缺陷；发现真缺陷应报告 Backend owner。

## G2 已冻结产品范围（非当前执行许可）

1. 保留用户认可的启动画布、中文/英文偏好、星图与切换动画及原始 assets 字节，不改成列表主页。默认使用真实模式；离线 Demo 必须显式选择并持续标识。API 故障不得静默回退 fake 数据。
2. 接入注册、登录、退出、refresh、`users/me` 与 ready 状态；真实 Radar CRUD、暂停/恢复及全部八种 `RadarType`；RSS/URL Source 创建与绑定；手动 collect 的 HTTP 202 queued 响应及真实 CollectionRun 轮询；UI 的 Signals 列表/详情严格映射冻结的 `GET /intelligence` 与 `GET /intelligence/{analysis_id}`。
3. Backend 当前无 CORS 配置。桌面端使用最小、受限的 Tauri native HTTP bridge，不放宽 Backend CORS，也不以 dev proxy 冒充桌面验收。bridge 只接受配置的本机 API origin 与冻结方法/路径 allowlist，禁止任意 URL、跨 origin redirect 和打开外部 URL。每次请求 timeout 为 15 秒，请求体上限 256 KiB、响应体上限 2 MiB，超限 fail-closed；只解析冻结错误封套并保留 `request_id`。轮询初始间隔 2 秒、最大间隔 10 秒、总时限 5 分钟；切页、退出或组件销毁必须取消请求和定时器。
4. Access/Refresh Token 均只存在 native 内存，WebView 不取得 Refresh Token，也不得写入 localStorage、URL、日志、截图或 JSON 磁盘；应用重开必须重新登录。refresh 以单航班串行，使用会话代次阻止并发 token rotation 与 logout 后会话复活。密码只用于一次认证请求，随后从 UI/native 临时缓冲清空。持久安全登录不在 G2 范围。
5. WebSocket 仍受 header-only token 限制，首发只用 REST 更新，禁止 query/cookie token。Memory、Opportunity 实功能和 Galaxy 持久化留给 G3；本阶段 Galaxy 只保留当前内存布局状态，不得标记这些能力已完成。
6. 下一 lease 的最小改动边界为 `frontend/**` 内的原生 bridge、types/API 模块、现有 UI 接入、必要 tests 与交接文档。任何新增 native 依赖必须按实际必要性在该 lease 中列名授权；本准入操作不安装依赖。Backend、API、schema、migration、评分与 Pipeline 不变。

## 下一阶段验证门槛

- 定向 native HTTP、security 与 session tests；UI 回归覆盖认证失败、空账号、429、503、401 refresh、退出清理、owner 隔离、来源绑定及 queued 轮询。
- 必须取得真实本地 API、隔离 `_test` 数据库上的 desktop 请求证据；浏览器 mock 不能声明接口接入完成。
- 迁移必须先于 Worker；不得触碰默认开发用户数据库或卷。上游采集与 AI 仅用既有离线 fixture/Fake provider，不访问真实目标或付费 API。
- 保留真实模式/Demo 隔离、native allowlist、内存 token、单航班 refresh、取消清理的可复核证据。P0/P1 未清零不得进入产品集成。

## 历史 admission operation record（不提供当前执行许可）

```text
Task ID: FE-001-G2-ADMISSION-02
Control Epoch: GOV-2.1
Parent Goal: FE-001-G2 real API integration prerequisite
Exact Baseline: frontend 24e2ebd14ac559ae9251424f30a4295f3006e0a0; backend/origin-main fc180a1d2eba32935fba6ee6c128f9b2d7015574
Exact Branch: feat/fe-001-g2-api
Authorized Operation: One three-document admission increment and one targeted document validation
Allowed Files: docs/FE-001-G2-ADMISSION.md; docs/CURRENT-GATE.md live top; docs/02-DELIVERY-BOARD.md FE entries
Allowed Tools: read-only Git/file/contracts; branch creation; apply_patch; diff/link checks
Forbidden Operations: source implementation, install, business tests/runtime, commit/push/PR/merge, INT-001/Release
Max Iterations: 1
Hard Deadline: 15 minutes from operation start
Expected Evidence: exact identities, three-file diff, gate/board/admission consistency, link/diff checks, P0/P1
Stop Condition: one validation result or failure/deadline/revocation/usage remaining <=5%; no implicit implementation
Next Authority Owner: FlowTracer controller
```

该历史 operation 已停点。下一操作只有总控按 [GOVERNANCE-V2 §12](GOVERNANCE-V2.md#12-governance-v21--live-authority--in-flight-task-control) 新签有界 lease 后方可开始。

### FE-001-G2-RADAR-CREATE-NATIVE-01 / RECOVER-01 原生创建与恢复清理停点（2026-10-16）

- 原生验证在 `feat/fe-001-g2-api@551d29f54aa530b6a9fc2329358c1861b42c24a5` 上完成一次且仅一次 Radar 创建。构建前候选源码身份在恢复 lease 中逐字节复核未变：`api.rs` `881A5831E83F8405291B6A255C8045789D776A2D16FBB136A0954DC1E0A244D4`、`main.rs` `2AE8157942CC0665F9F8E46CFDA7B3C8464BC4C804BBA825538A95EFD26E6693`、`desktop.ts` `D624EE3B6DFB092D1D7331C1F271584676134DE87CC0FDCDBC8C92DAE73AB04A`、`App.tsx` `1E965995A08F0296C2BAC74AC13F0368032F37CB177951AAB407CA0F5AFC1604`、`Universe.tsx` `65142F964FE59BF50418D61732A26E415663858365C8142016CDA43D5F39D1E7`、`demo.css` `2BA57FCA747EC238E9BC54020DC05A1E82485F65ABA7DE0B84A9A10145414B00`、`RadarCreatePanel.tsx` `C34CE5EA3E752EE92FAC80BD87C691FFDE137989B825C530298B975ED63E7B2C`。唯一 `--locked` Windows debug 构建生成 `flowtracer-desktop.exe` 14,862,336 bytes，SHA-256 `F8B9B1F96E296AD9FA2C96B36BDC7826A7DF90F153E0EF9E625EE2CEAACB34B5`；恢复 lease 未重建、未重跑测试或 UI。
- 上轮工具记录中的 1530×864 原生截图与 accessibility 状态形成连续证据：第一次登录后星图显示唯一 `Native Radar 20261015 01`；键盘聚焦该真实 Radar 后打开详情，面板显示目标 `Track verified native opportunity changes`、类型“机会”、数据来源“本机 API”、状态“活跃 · 真实”。退出后第二次且最终登录的截图仍显示同名唯一行星、`真实 RADAR 1`、`真实连接`，accessibility tree 中按钮为 `查看真实 Radar Native Radar 20261015 01，opportunity`，证明的是本轮隔离运行时中的创建后重登可见性，不外推为生产验收。
- 保存的 API access 计数为：注册 `201×1`、登录 `200×2`、`users/me 200×2`、Radar 列表 `200×2`、Radar 创建 `201×1`、退出 `204×1`。隔离数据库 `flowtracer_radar_test_20261015_01` 当时为 `users=1`、`radars=1`；唯一 Radar UUID `e3a1e41c-e744-4483-ba65-0c69fd256698`，owner `e3281f08-13aa-412f-9819-6166f50d15ef` 且 join 匹配为 true，名称/目标/类型/状态/阈值/未删除分别为 `Native Radar 20261015 01` / `Track verified native opportunity changes` / `opportunity` / `active` / `75` / true。未运行 Worker，未访问真实采集目标或付费 API。
- 当可靠 5 小时额度降至剩余 2% 时按 GOV-2.1 立即停止；精确路径的专属 exe 进程已停止，但容器清理命令因 usage-limit 审批失败而未执行。恢复 lease 开始额度为 5 小时/每周剩余 69%/65%，没有续跑任何验证。Docker 由用户自行启动后，只读检查发现三个 `--rm` 容器 `ft-g2-radar01-20261015-{api,redis,pg}` 均已不存在；残留网络 `ft-g2-radar01-20261015-net` 的 label 为 `FE-001-G2-RADAR-CREATE-NATIVE-01`、driver 为 bridge，确认归属后已精确删除。终态复核同前缀容器/网络为空、该 lease 标签卷为空、端口 8000 无监听；未停止 Docker，未触碰其他容器、网络或卷。
- 当前证据合并口径：本地 AUTH/视觉 checkpoint 为 `551d29f54aa530b6a9fc2329358c1861b42c24a5`（未 push），其上 Radar 创建候选仍为 dirty；Rust `api::tests` 9/9 与 Web 定向覆盖 4/4 已取得，不在本次文档同步中重复运行。Radar 编辑、删除、暂停/恢复、Source、collect、Signals 仍未完成；约 1.05 秒墨水消散的原生中间帧仍缺失，不能把现有界面截图写成完整视觉 PASS。
- 可访问性债务记录为 P2：`RadarCreatePanel` 声明 `aria-modal`，但 FIXTURE-02 的键盘路径证明背景导航仍可获得焦点。后续实现须建立真实焦点边界，并让 session-race 测试不再依赖 modal 焦点泄漏；当前没有证据将其升级为 P1 数据安全缺陷，也不得宣称 P2 全部清零。
- 本次定向结论为 `NATIVE_RADAR_CREATE_PASS`：真实原生登录 → 单次创建 → 唯一 live 行星及详情 → DB/API 一致 → 退出后二次登录同一 Radar 可见的限定路径成立，且专属资源已清理。它不等于 AUTH-01/FE-G2 全量产品验收，不批准 INT-001/REL-001，也不覆盖其他 CRUD、Source、采集或 Signals。无 commit/push/PR/merge；恢复后仅追加本 checkpoint，立即 STOP 交总控复核。

### FE-001-G2-RADAR-FOCUS-01 创建面板焦点边界候选（2026-10-16）

- 基于本地 checkpoint `9930cb806cbf6923e53212659d1c661d3945f011`，仅在 Radar 创建面板、Workspace modal 边界、对应单文件测试和本记录内修复既有 P2。创建面板现在显式聚焦名称输入；Tab/Shift+Tab 在可用控件首尾循环，document `focusin` guard 将程序化逃逸送回面板内最后焦点；header/main/footer 在面板打开时均为 inert。非 busy 的 Escape、关闭与取消会关闭面板并把焦点归还加号触发器；busy 仍禁止关闭，listener 在 unmount 时只清理、不抢新场景焦点。
- 账号切换 race 测试不再通过背景键盘泄漏进入 Settings；改为明确标注的 test-only lifecycle fault injection，以 Playwright `dispatchEvent` 调用既有 React 导航/退出处理，不增加 production test hook，也不把 inert 背景描述为用户可操作。旧请求 pending → 新账户登录 → release → 新账户 0 Radar / `Second` 的会话围栏断言保持。验证结果见本 lease 最终报告；未改变创建 pending/重复请求语义、原始视觉资产或后端/API/锁文件，未进入 INT/Release。
- FOCUS-01 的 typecheck PASS，Web build 在首次沙箱 `spawn EPERM` 后以同命令最小权限重试 PASS（49 modules）；随后 Playwright 命令未设置项目既有 `FLOWTRACER_TEST_EDGE=1`，误寻未安装的 `chromium_headless_shell`，首项在启动浏览器前失败、其余 4 项未运行。这是 runner 环境错误，不是产品断言失败；没有安装浏览器或据此修改生产代码。
- FOCUS-VERIFY-02 仅把 inert 背景中的 Settings/退出测试定位改为明确 DOM locator；正常焦点拒绝与 Canvas 状态断言不弱化，lifecycle injection 仍为 test-only。设置 `FLOWTRACER_TEST_EDGE=1` 后唯一一次 Edge 单文件运行发现 5 项并全部 `ok`，`.last-run.json` 为 `status: passed`、`failedTests: []`：覆盖初始焦点、Tab 双向首尾循环、背景 inert/程序化焦点逃逸拒绝、非 busy Escape/取消焦点恢复、pending Escape 禁止关闭及焦点边界，并保留 409、重复提交去重、旧会话响应围栏、非法 UUID 与 Demo 零创建回归。该 Radar 创建面板焦点边界 P2 在定向 Web 范围内关闭；未发现新增 P0/P1，但历史其他 P2 与完整 FE-G2/原生视觉缺口不因此清零或通过。

### FE-001-G2-RADAR-EDIT-01 定向编辑候选停点（2026-10-16）

- 基于本地 checkpoint `9930cb806cbf6923e53212659d1c661d3945f011` 与已验证、未提交的 FOCUS-01 四文件候选，新增 typed native `GET/PATCH /api/v1/radars/{radar_id}`。Radar ID 必须为小写 canonical UUID，拒绝斜杠、查询、片段、百分号、绝对 URL 与非 canonical 大写形式；detail/update 继承既有 loopback、redirect、timeout、size、401 单航班 refresh 和 session generation 围栏，响应 ID 必须与请求 ID 相同。PATCH 只发送 `name/goal/radar_type/description/notification_threshold` 五字段，空说明映射 `null`，不发送或覆盖 categories、keywords、status。
- 真实星图详情新增编辑入口；弹窗先读取完整 detail 再填入 name、goal、description、type、threshold。保存 pending 去重且禁止 Escape/关闭；失败保留输入和原行星；仅确认成功且 ID 匹配后映射 name/type/color/description/status，并保留原 ID、x/y、signals 与当前选择。弹窗复用 FOCUS-01 的初始焦点、Tab 双向循环、document focus guard、背景 header/main/footer inert 和关闭后触发器焦点恢复；load effect 有 disposed fence，detail/update 都受 FlowApp request epoch 账号切换围栏。Demo 不显示编辑入口、不发更新。
- 开始可靠额度 5 小时/每周剩余 22%/57%；长验证前为 7%/55%，完成后为 6%/55%，均高于 5% 停点线且未使用 reset credit。`npm run typecheck` exit 0；`npm run build` 首次只因沙箱 `spawn EPERM` 未构建，同命令最小权限重试 exit 0（50 modules）；Rust 首次只因 Cargo lock 权限未运行，同命令最小权限重试 `api::tests` 12 passed / 0 failed，含严格 ID/五字段 body、401 refresh、detail/update identity 与 logout-inflight update stale-session。Edge 首次只因测试输出目录权限未启动，设置 `FLOWTRACER_TEST_EDGE=1` 的同命令最小权限重试 `radar-edit.spec.ts` 4 passed / 0 failed（27.1 秒），覆盖成功写回与坐标/选择保留、409 与响应 ID 不匹配不写回、旧账户迟到更新隔离、Demo 零写入。
- 结论 `RADAR_EDIT_TARGETED_PASS`，本 lease 新增 P0/P1/P2=`0/0/0`。这是 typed native 单元与 Web mock 定向证据，不是本轮原生窗口或真实 API 编辑证明；EDIT-01 明确禁止 Docker、native UI 和账号操作，收到的旧创建验证授权不扩大本 lease。未触碰 backend/OpenAPI/schema/migration/依赖/锁文件，不包含删除、暂停/恢复、Source、collect、Signals、G3 或 INT；无 commit/push/PR/merge，完成即 STOP 交总控复核。

### FE-001-G2-RADAR-EDIT-DOC-02 四文档当前摘要同步（2026-10-16）

- 当前身份统一为 `feat/fe-001-g2-api@9930cb806cbf6923e53212659d1c661d3945f011`：`9930cb8` 是已本地提交的 Radar 创建 checkpoint，不是 dirty 创建历史；其上 FOCUS-01 与 EDIT-01 是已验证但未提交的候选。Backend/main 产品基线仍记为 `fc180a1d2eba32935fba6ee6c128f9b2d7015574`；branch-local 内容未 push、未 merge，不得冒充 main。
- 四文档只复用既有一次性证据，不重跑：创建 Rust 9/9、Web 4/4 与隔离原生创建/重登；焦点 Edge 5/5 并关闭创建面板既有焦点泄漏 P2；编辑 typecheck/Web build、Rust 12/12、Edge 4/4。总控已读编辑源码，strict UUID、typed GET/PATCH、五字段 body、响应身份与会话围栏未确认 P0/P1；仍无真实原生/API 编辑证据，所以只保留 `RADAR_EDIT_TARGETED_PASS`，不声明 native edit 或 FE-G2 产品 PASS。
- 新记两个低风险 P2，留给后续最小稳定化 lease：`RadarEditPanel` 的 load effect 依赖父层每次 render 新建的 `onLoad` 函数，偏好或系统 motion 等父层重渲染可能重取 detail 并覆盖未保存输入；更新成功路径在 React state updater 内执行 `toUniverseRadar` 校验，今后不应复制该模式。严格 native enum/identity 校验使本轮没有已证实 P1，但文档同步不修源码。
- 启动墨水消散中间帧证据仍缺；删除、暂停/恢复、Source、collect、Signals、G3 均未完成，INT-001/REL-001 未准入。本 DOC-02 仅修改 `CURRENT-GATE.md`、交付看板、Frontend README 与本准入记录；不运行测试/build/runtime/native，不改源码，不 commit/push/PR/merge。完成一次文档差异/链接检查后 STOP 交总控；后续 Radar 删除/暂停恢复须另签 lease。

### FE-001-G2-RADAR-LIFECYCLE-01 暂停、恢复与软删除定向候选（2026-10-16）

- 在 `feat/fe-001-g2-api@9930cb806cbf6923e53212659d1c661d3945f011` 与完整保留的 focus/edit/四文档 dirty 上，新增 strict canonical UUID 的 typed native `POST /radars/{id}/pause`、`POST /radars/{id}/resume`、`DELETE /radars/{id}`。暂停/恢复只接受冻结合同 HTTP 200 + JSON，并校验响应 ID 与目标状态；即使 HTTP 202 带合法 Radar JSON 也 fail-closed。删除只接受 HTTP 204 且响应体必须为空，200/202、404 或非空 204 均不冒充成功。三者继承 loopback origin、no-proxy/no-redirect、timeout/size、native-memory token、401 单航班 refresh 与 session generation fence，不开放任意 URL。
- Live 星图仅对 active 显示暂停、paused 显示恢复，archived 不显示恢复；软删除使用包含 Radar 名称的确认文案，明确服务端可能按保留策略保存记录，默认焦点在取消。所有 lifecycle modal 复用创建/编辑的 header/main/footer inert、focus trap、Escape、pending 禁关闭/去重与逻辑触发器焦点恢复；失败保留原状态并可重试。只有后端确认后才更新状态并保留 UUID/x/y/signals/selection；204 后只移除对应 UUID、清除失效 selection，其他 Radar 保留。Demo 不显示动作且不发送写请求。
- 同一增量关闭 DOC-02 两项低风险 P2：编辑 detail effect 以稳定 ref 读取 loader，仅在 radar ID 改变时重取并取消旧结果，父 preferences/system-motion rerender 不再覆盖未保存输入；update/lifecycle 的 `toUniverseRadar` 校验与映射移到 React state updater 之外，非法 enum/identity 进入 modal Promise catch，不触发 React updater 崩溃。未引入 repository 抽象、依赖或样式系统；`ui-styling` 无障碍规则用于确认弹窗的语义、初始取消焦点、焦点圈和焦点恢复。
- 开始可靠额度 5 小时/每周剩余 65%/49%，长验证前 52%/47%，完成后 49%/46%，均高于 5% 且未使用 reset credit。`npm run typecheck` exit 0；Web build 首次仅因沙箱 `.vite-temp` EPERM 未构建，同命令最小权限重试 exit 0（51 modules）；Rust 首次仅因 Cargo lock 权限未运行，同命令最小权限重试 `api::tests` 15/15 PASS，覆盖真实 loopback 方法/路径、200/204、401 refresh、ID/status、202/错误状态拒绝、malformed ID 与 logout-inflight stale generation。Edge 首次仅因输出目录 EPERM 未运行，同命令最小权限重试在 Edge、`retries=0` 下运行 lifecycle + edit 两文件，8/8 PASS（53.1 秒）：成功/409 保持与重试、具名删除取消零写、pending 去重、账号切换迟到响应、Demo 零写，以及编辑父层 rerender 输入保持/invalid enum 安全报错。
- 验证时源码 SHA-256：`api.rs 013ECD2D542ED7493EF566858766D4E2425FB9981F04005A5F380DD25123B577`；`main.rs D3556A8704D744A6A25FA9D11DE373543D13132D0BFB3C585F5904D2D98C2B9F`；`desktop.ts 2E6275B3F7CE14F4A589650B1633EFF075F55775B804D71A0962DC5CCAEFB70A`；`App.tsx F2D7F5C2298BD825174EAE3F97023F4FE9F67ED7110DE6D36412C7197A84DE61`；`Universe.tsx 2C005C1C7D510C3CCA5A26A7FC5B03CC5498358E93C16900FD44FA452A7119A1`；`RadarEditPanel.tsx 5EC9FEA9C62E8B05209F1B35EFF722C3DC239DBBC5B66C35EFBF6CC6E3E201B2`；`RadarActionPanel.tsx 8DE90735E0AC7E9F77153C8DA56B343CE88CDBC07C8465E630A8F2129516BFF2`；`radar-edit.spec.ts 55C1D9FA3EFE6A14BA86153FC4EB2593992433DD9D75CDE7A447BD412703C5E7`；`radar-lifecycle.spec.ts 3250855B776DCBA16E76B9F3BAA3714884BE64E0BD7B6F5F8EF0A522957E57EF`。
- 结论 `RADAR_LIFECYCLE_TARGETED_PASS`，本 lease 新增 P0/P1/P2=`0/0/0`，并关闭上述两个 edit P2。它仍是 native transport 单元 + Web mock 定向证据，不是 Docker/真实 API/native UI 生命周期验收；Source、collect、Signals、G3、INT/REL 均未准入。未改 Backend/OpenAPI/schema/migration/依赖/锁/assets，未 commit/push/PR/merge，完成即 STOP 交总控复核。

### FE-001-G2-SOURCE-POLL-REPAIR-01 轮询与 intent 生命周期修复停点（2026-10-16）

- 基于 `feat/fe-001-g2-api@9930cb806cbf6923e53212659d1c661d3945f011` 加当前未提交 Source 候选，仅修改 `SourceCollectPanel.tsx`、`source-collect.spec.ts` 与本证据记录。轮询使用单一 generation、active run/source identity 和同代次 single-flight；手动刷新先使旧代次失效，所有 await 后回写与 timer 调度均复核 mounted、generation、run 与 source。关闭/卸载会递增代次、清 timer 和 active run，迟到响应不得覆盖当前状态或复活轮询。非 terminal run 期间禁止再次 POST，但仍允许手动读取与关闭。
- intent 只保存在面板局部内存。POST 未确认（含 503）保留同一 source/key 并显式“重试同次采集”；接受 202 后不再把 GET 失败误当成可重复 POST。CollectionRun 到达 terminal 后清除旧 intent，用户下一次明确点击才生成新 key；新 intent 清除旧 run 展示。该修复不增加全局队列、production test hook、依赖或后端改动。
- 新增 controlled-promise 负例：首次 GET running，后续旧代次 GET 阻塞；手动刷新取得新代次 terminal 结果后释放旧 failed 响应，旧响应既不覆盖 terminal 结果也不安排新 timer。另验证新一轮 running 后关闭面板，等待超过初始 2 秒仍无新增 GET；503 后第二次 POST key 与第一次完全相同，而 terminal 后第三次显式 POST 使用不同 key。保留 create→bind 重试不重复 create、pending collect 去重+立即 GET+轮询 terminal、Demo 零 Source/collect 写入回归。
- 验证前可靠额度为 5 小时/每周剩余 10%/40%，均高于 5%。`npm run typecheck` exit 0；Web build 与 Edge 首次只因沙箱拒绝写 `.vite-temp`/测试输出目录而未执行，同一原命令最小权限重试后 build exit 0（52 modules），Edge `FLOWTRACER_TEST_EDGE=1`、`retries=0` 为 `5 passed / 0 failed`（39.4 秒）。Rust 源码未改，按 lease 沿用 SOURCE-COLLECT-01 的 `api::tests 17/17 PASS`，未重复运行。
- 验证源码 SHA-256：`SourceCollectPanel.tsx 360401D6778EC14D90C24966BAA182D6DBCA3ED1E5A6804C4648307D6DBF525C`；`source-collect.spec.ts E3AA4A0E40C78171ACEF9BBB8C7333A6AEF0D644BB99D54A0A777D42CED99DB2`。结论 `SOURCE_POLL_REPAIR_TARGETED_PASS`，本修复 lease 新增 P0/P1/P2=`0/0/0`；此前确认的轮询覆盖/复活与 intent key 生命周期缺陷在定向 Web 范围内关闭。仍无本轮 Docker、真实 API、native UI、账号或实际采集证据，不批准完整 FE-G2、Signals、INT-001 或 REL-001；无 commit/push/PR/merge，完成即 STOP 交总控复核。

### FE-001-G2-SIGNALS-01 / VERIFY-02 / FIXTURE-03 / DEMO-04 定向候选停点（2026-10-18）

- 基于 `feat/fe-001-g2-api@9930cb806cbf6923e53212659d1c661d3945f011` 加既有未提交候选，新增 frozen `GET /api/v1/intelligence` 与 `GET /api/v1/intelligence/{analysis_id}` typed native allowlist。查询只由验证后的 page/page_size、canonical radar UUID、冻结 status/recommendation、1–120 category 与 finite 0–100 min score 经 URL 编码构造；只接受 HTTP 200，并校验分页、item 数、analysis/document/radar UUID、冻结枚举、组件分数、Decimal 字符串或数值、nullable radar score、detail analysis ID 与预期 radar ID。它继承 loopback/no-proxy/no-redirect/timeout/size、native-memory token、401 single-flight refresh 与 session generation fence；canonical URL 仅显示，不自动请求或打开外站。
- Live Signals 页面在既有 utility 视觉体系内提供真实列表、Radar/status/recommendation/min-score 筛选、page reset、分页、详情与返回焦点，以及 loading/error/empty 分离。详情正文只作为 React 文本节点渲染，不使用 `dangerouslySetInnerHTML`；404/503/request ID 不伪装为空列表，旧 filter/page/detail 和 logout 后迟到结果由组件 generation 与 FlowApp request epoch 阻止回写。Demo 保持未连接占位并验证零 `intelligence_*` 调用；未增加 Retry、Bookmark、Memory、Opportunity、通知或 G3 功能。
- SIGNALS-01 的 typecheck PASS、Web build PASS（53 modules）与 Rust `api::tests 20/20 PASS` 有效；Rust 覆盖 loopback GET 方法/精确编码查询、200、Decimal/string/number/null、UUID/分页/枚举/分数/详情身份、401 refresh、404/503 request ID 与 logout stale session。首次 Edge 因 build 与 preview/E2E 并行，实际服务旧 dist，首例仍显示旧 Signals 占位并失败，其余三项未运行；这是 verification ordering 错误，不作为新 UI 产品失败，也未被隐去。
- VERIFY-02 先确认 `dist/index.html` 指向新 `index-BfGlSPc1.js`，bundle 时间晚于 App/Signals 源码，SHA-256 `8BEDD490C2446F72A5DCD3EBCB9C3A05A7C29A5E270EAF20DF22526F597A4FD5`，并实际含 `intelligence_list`、`intelligence_get`、`Not scored`、`Signals unavailable` 与 `Loading live signals`。fixture 增加 stage/page idle 和登录输入值断言；首项 null score、详情、raw HTML 不执行与返回焦点 PASS，第二项只因 Radar filter locator 同时匹配 header“新建 Radar”而 strict-mode 失败，后两项未运行。
- FIXTURE-03 仅将 filter locator 限定到 `.signal-filters` 内的 exact combobox/spinbutton。唯一剩余三项运行中 pagination/filter reset PASS，404/503 显式错误、慢 list/detail 切换与 logout/account-switch stale response PASS；Demo 项只因导航“信号”locator 同时匹配六个含“演示信号”的 Radar aria-label 而 strict-mode 失败。DEMO-04 仅把该导航定位限定为 `.main-nav` 内 exact“信号”，保留 transition idle、诚实占位与零 Intelligence 调用断言；唯一 Demo 单项 `1/1 PASS`（8.6 秒）。
- 因此 Signals Web 定向覆盖按分轮不重复证据合并为 `4/4 PASS`：VERIFY-02 首项 1、FIXTURE-03 中间两项 2、DEMO-04 单项 1；这不是同次 full-suite。当前结论 `SIGNALS_TARGETED_PASS`，未发现新增 P0/P1/P2；仍无 Signals 的真实 API/native UI 证据，不能声明 native Signals 或完整 FE-G2 产品 PASS，也不批准 INT-001/REL-001。未运行 Docker、真实账号或外部 URL，未 commit/push/PR/merge，完成即 STOP 交总控复核。

### FE-001-G2-FULL-FRONTEND-VERIFY-07 顺序全量验证失败停点（2026-10-18）

- 验证身份为干净的 `feat/fe-001-g2-api@50a14f52932fabd108cd6b2d81933f562773507f`，父提交 `9930cb806cbf6923e53212659d1c661d3945f011`。按 lease 严格顺序执行 unit → locked/offline desktop debug build → Edge full E2E，未并行 build 与 preview；复用同源 typecheck、Web build 53 modules 与 Rust `api::tests 20/20` 既有证据，不重复运行。
- `npm run test:unit` 首次仅因沙箱拒绝写 `node_modules/.vite-temp` 而未进入测试，同命令最小权限重试 exit 0：3 files passed，15/15 tests passed。`npm run build:desktop:debug -- -- --locked --offline` 首次仅因沙箱拒绝设置工作目录而未开始编译，同命令最小权限重试 exit 0；beforeBuild Web build 为 53 modules，Rust dev profile 完成，未启动应用。产物 `frontend/src-tauri/target/debug/flowtracer-desktop.exe`，version/product version `0.1.0`，15,542,784 bytes，SHA-256 `CE2195E3DBEBE2E094998EF8A1952AAEF212F6E07000E6484DF76A41A5922B98`。
- `FLOWTRACER_TEST_EDGE=1` 下运行 `npm run test:e2e -- --retries=0`；首次仅因沙箱拒绝更新 `test-results`/`playwright-report` 而未收集用例，同命令最小权限重试收集 39 tests、1 worker。结果为 20 passed、1 failed、18 did not run，另报告 1 个非测试错误；由于配置在首个失败后提前停止，未形成 full-suite PASS。唯一测试失败是 `tests/radar-lifecycle.spec.ts:16` 的暂停/恢复流程：暂停确认响应完成、弹窗关闭后，`getByRole('button', { name: '恢复 Radar' })` 在 5 秒内未获得焦点，断言位于 line 36。失败截图、trace 与 error context 保留在 `frontend/test-results/demo-v2-final/radar-lifecycle-pause-resu-8ce7c-y-after-confirmed-responses/`。按 lease 未修复、未重跑。
- 可靠额度检查：开始与 unit 后均为 5 小时/每周剩余 20%/88%，desktop build 后为 19%/87%，均高于 5% 停点线；未使用 reset credit。关键身份 SHA-256：`api.rs BD3E898C322615B6F9D155E6EA84C00ABF2D425DD4704843322B2A8064387156`；`main.rs 9E21D84860F36510683ACFE8F8AA9E381CD3E199E5000E1AE047B9DBFA18F350`；`desktop.ts 9BEA6DCAF6124AE252960FFB6952522DD82C7F23E90934E41E6A3FDB34F5F0AB`；`App.tsx 2E4F74C698A4B1C40B3E5EA648DE79C0A8BBAC1B1E4967B8FFA603A2680F6AE1`；`SignalsPage.tsx 54ADA4C129613D6470C1BD2734F3E7A9CA1F53307958FC1BC09FB85073119493`；Web bundle `index-BfGlSPc1.js 8BEDD490C2446F72A5DCD3EBCB9C3A05A7C29A5E270EAF20DF22526F597A4FD5`。
- 结论 `FULL_FRONTEND_VERIFY_FAILED_STOP`：unit 与锁定离线 desktop compile 通过，但 Edge 全量链未通过，新增一个可复现范围尚未确认的焦点恢复失败；不得批准完整 FE-G2、G3、INT-001 或 REL-001。本轮没有 Docker、真实 API/native UI、账号、外部网络、源码/依赖/锁/assets 修改，也没有 commit/push/PR/merge。启动墨水消散中间帧证据仍缺；仅本准入记录追加本次失败事实后 STOP 交总控。

### FE-001-G2-LIFECYCLE-FOCUS-REPAIR-08 最小焦点时序修复停点（2026-10-18）

- 基于 `feat/fe-001-g2-api@50a14f52932fabd108cd6b2d81933f562773507f` 加仅 VERIFY-07 admission 报告 dirty，确认真实原因为 `closeAction` 在 `setRadarAction(null)` 后只安排一次 `requestAnimationFrame`：该回调可能早于 React 并发提交与背景 `inert` 移除，逻辑后继按钮随后出现时已没有第二个恢复点。仅修改 `frontend/src/app/App.tsx`：把 cancel/completed action 的目标保存为当前 Workspace 内的 pending focus intent，在 action modal 已卸载、目标已存在且不位于 `inert` 树下的 layout commit 后聚焦一次并清除；查询限制在当前 Workspace，卸载时清除 pending，避免跨 session 偷焦点。cancel 仍返回原 trigger，pause/resume 返回逻辑后继按钮，delete 返回 canvas；未添加 sleep、无限 retry 或全局 document 查询。
- `frontend/tests/radar-lifecycle.spec.ts` 未修改，保留 cancel、pause→resume、resume→pause 与 delete→canvas 的全部 `toBeFocused` 断言，没有调用测试侧 `focus()` 刷 PASS。唯一授权 target set：`npm run typecheck` exit 0；`npm run build` 首次仅因沙箱 `.vite-temp` EPERM 未进入构建，同命令最小权限重试 exit 0（53 modules，bundle `index-CcWyIlor.js`）；Edge `FLOWTRACER_TEST_EDGE=1`、`radar-lifecycle.spec.ts --grep 'pause, resume and named' --retries=0` 首次仅因测试结果目录 EPERM 未收集，同命令最小权限重试 `1/1 PASS`（用例 7.4 秒，整次 11.4 秒）。未重跑 full UI；Rust 未变，沿用同源 `api::tests 20/20 PASS`。
- 最终 SHA-256：`App.tsx 3AE66E0FF8A7B144CDCE5996AF75EC2F3AA785BF55CD1CA32FE5C36A18552001`；未改测试 `radar-lifecycle.spec.ts 3250855B776DCBA16E76B9F3BAA3714884BE64E0BD7B6F5F8EF0A522957E57EF`；bundle `index-CcWyIlor.js 5858F72137DA2E06D8AD7DA6466D9FF542F32094F5EB5F1BEACF27A2D5C9E1E7`。长验证前本线程可靠额度为 11%/86%，build 后为 9%/86%；随后总控可靠更新为 5 小时/每周剩余 6%/85%，因此不增加验证或提交且不使用 reset credit。
- 结论 `LIFECYCLE_FOCUS_TARGETED_PASS`：VERIFY-07 的具体焦点失败在唯一目标用例范围内关闭，但原 39 项 full-suite 仍保持失败历史，不能据此改写为 full-suite PASS，也不批准完整 FE-G2、G3、INT-001 或 REL-001。无 backend/Docker/native UI/账号/依赖/锁/assets/commit/push/PR/merge；保存本最小 checkpoint 后立即 STOP 交总控。

### FE-001-G2-FULL-VERIFY-10 新 head 顺序全量验证停点（2026-10-19）

- 验证身份为干净的 `feat/fe-001-g2-api@30bd1d3e7555c0bebb029d1bb68ba9711db3f7ea`，父提交 `50a14f52932fabd108cd6b2d81933f562773507f`。严格串行执行 typecheck → unit → locked/offline desktop debug build（完整等待 beforeBuild Web 与 Rust 编译结束）→ Edge full E2E，未修改 maxFailures、断言、配置或重试策略，也未复跑全套。Rust 源码未变，沿用同源 `api::tests 20/20 PASS`，未重复运行 Rust suite。
- `npm run typecheck` exit 0。`npm run test:unit` 首次仅因沙箱拒绝写 `node_modules/.vite-temp` 而未进入测试，同命令最小权限重试 exit 0：3 files passed，15/15 tests passed。`npm run build:desktop:debug -- -- --locked --offline` 首次仅因沙箱拒绝设置工作目录而未开始编译，同命令最小权限重试 exit 0；beforeBuild Web build 为 53 modules，bundle `index-CcWyIlor.js` SHA-256 `5858F72137DA2E06D8AD7DA6466D9FF542F32094F5EB5F1BEACF27A2D5C9E1E7`，Rust dev profile 完成，未启动应用。产物 `frontend/src-tauri/target/debug/flowtracer-desktop.exe`，version/product version `0.1.0`，15,542,784 bytes，SHA-256 `206FCDF70899C9F9748BDA967658EA94FA84342EB6F200B2A03CD3082A08B138`。
- `FLOWTRACER_TEST_EDGE=1` 下运行完整 `npm run test:e2e -- --retries=0`；首次仅因沙箱拒绝更新 `test-results`/`playwright-report` 而未收集用例，同命令最小权限重试实际收集 39 tests、1 worker，结果 `39 passed / 0 failed / 0 not run`（4.0 分钟）。成功结果元数据位于 `frontend/test-results/demo-v2-final/`，HTML 报告位于 `frontend/playwright-report/`。运行前已确认 VERIFY-07 的旧失败附件目录不再存在，无法另行复制；旧 `50a14f5` 的 20 passed / 1 failed / 18 did not run 历史仍保留在本文件及 gate，不被本轮结果覆盖。
- 本轮焦点修复源码 `App.tsx` SHA-256 `3AE66E0FF8A7B144CDCE5996AF75EC2F3AA785BF55CD1CA32FE5C36A18552001`。可靠额度在开始、unit 前、build 前、E2E 前与完成后分别为 5 小时/每周剩余 90%/84%、89%/83%、87%/83%、84%/83%、78%/82%，均高于 5% 停点线；未使用 reset credit。
- 结论 `FULL_FRONTEND_NEW_HEAD_PASS`：在精确新 head 上，typecheck、unit、locked/offline desktop compile 与同次 Edge 39/39 full suite 全部通过，VERIFY-07 的 lifecycle focus 失败已在新 head 全量范围关闭。该结论仍不是 Docker、真实 API/native UI、账号或启动墨水消散中间帧验收；不自动批准完整 FE-G2 产品门、G3、INT-001 或 REL-001。本轮无源码/backend/API/schema/依赖/锁/assets 修改，无 commit/push/PR/merge；仅追加本证据后 STOP 交总控。

### FE-001-G2-NATIVE-PREP-11 隔离运行态准备失败停点（2026-10-19）

- 开始身份为 `feat/fe-001-g2-api@30bd1d3e7555c0bebb029d1bb68ba9711db3f7ea`，仅本 admission 保留 VERIFY-10 的 8 行 dirty；桌面 exe SHA-256 `206FCDF70899C9F9748BDA967658EA94FA84342EB6F200B2A03CD3082A08B138` 只读匹配，未重跑 15 unit 或 39/39 full UI。Docker Engine `29.8.2` 可用，8000 启动前空闲；复用既有专用镜像 `ft-g2-auth-test:fc180a1-01` / `sha256:7f62b51da989aa04c733824bd3f31a38e995bbd893a07b60853f8309c36c9095`，没有 build/pull/install。既有 `buildx_buildkit_flowtracer-r1-final-builder0` 未触碰。
- 创建带 lease/owner label 的 internal 网络 `ft-g2-nativeprep11-20261019-net`（ID `4beb530b912f93dcb7809793bc05e968b1012bc5e12bce2e03c784739b0e32ff`）；PostgreSQL `ft-g2-nativeprep11-20261019-pg`（ID `e2f94106e8b102d8a9fa0db5e92b75eb051ed6f5a2fb3e99d37df09d2736b9de`）和 Redis `ft-g2-nativeprep11-20261019-redis`（ID `675ecf9d7c9e8b3e5f90c1182e8300c7e7e8ecad9ff5faa9fe7da7695be3d3f6`）均无 Mounts、仅使用 tmpfs、无主机端口并达到 healthy。隔离库 `flowtracer_fe_g2_20261019_test` 在 API 前成功迁移至 Alembic `20261006_0009`，当时 `users=0`、`radars=0`；未启动 Worker/Beat，Fake provider 与 Browser disabled 边界保持。
- API 启动命令在 Docker 执行前因 PowerShell 对 health-check 内嵌 Python 引号解析失败，报 `ParserError: Missing expression after ','`；API 容器未创建。该错误不是沙箱权限失败，依据 MaxIterations=1 未修正命令或重试。没有 health/live、health/ready、loopback publication 或 native bridge 证据；computer-use 未启动桌面窗口，更未操作认证表单或创建账号。
- 结论 `NATIVE_PREP_FAILED_STOP`。已精确删除本轮 PG、Redis 与专名网络；复核本 lease 容器/网络/标签卷为空、端口 8000 无监听，buildx 容器仍运行。tmpfs 数据库随容器删除，不可恢复；无令牌或账号产生。未改源码/config/依赖/assets，无 commit/push/PR/merge，也不批准 FE-G2 产品门、G3、INT-001 或 REL-001；仅追加本失败证据后 STOP 交总控。

### FE-001-G2-NATIVE-PREP-12 internal loopback 阻断停点（2026-10-19）

- 延续 `feat/fe-001-g2-api@30bd1d3e7555c0bebb029d1bb68ba9711db3f7ea` 与仅本 admission dirty，保留 PREP11 失败历史。只读结构化 inspect 确认可信镜像 `sha256:7f62b51da989aa04c733824bd3f31a38e995bbd893a07b60853f8309c36c9095` 的 Entrypoint 为 null，默认 CMD 为独立 argv `uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log`；本轮直接使用该 CMD，未再嵌套 `python -c` 或多层引号。exe SHA-256 仍为 `206FCDF70899C9F9748BDA967658EA94FA84342EB6F200B2A03CD3082A08B138`；未运行 build/fullsuite/install。
- 新建带 lease/owner label 的 internal 网络 `ft-g2-nativeprep12-20261019-net`（ID `982023ecdd8f53c2c6f7ab898cf5c589bdc142115dbe98076c18edd6ad3aa970`）。PostgreSQL `ft-g2-nativeprep12-20261019-pg`（ID `d57720779343aac4a3d81d8ec6bda423bb3618831f53689c6fc2fa79db84dda4`）和 Redis `ft-g2-nativeprep12-20261019-redis`（ID `883a648bd742a6fa697e38c1ef4d5d65f1f7eb54c2443d690fc4ad12c6d78383`）均 healthy、无 Mounts、仅 tmpfs、无主机端口。新空库 `flowtracer_fe_g2_20261019_prep12_test` 在 API 前迁移至 `20261006_0009`，`users=0`、`radars=0`。
- API `ft-g2-nativeprep12-20261019-api`（ID `ba73e029690d239fb22ecb8a278975f27e1dadaa70c5fd69c6a61b9bd5b2aedd`）使用 Fake/test 配置与镜像默认 argv 正常完成 application startup，容器内监听 `0.0.0.0:8000`，无 Mounts、无 Worker/Beat。但 internal 网络下请求的 `127.0.0.1:8000:8000` 仅出现在 `HostConfig.PortBindings`，实际 `NetworkSettings.Ports[8000/tcp]=[]`；因此没有真实 loopback API 端点，未执行 host health，也未启动 computer-use/Tauri 窗口。该阻断与 PREP11 控制脚本引号错误不同，是当前强制 internal 拓扑无法形成桌面所需回环发布，不据此声明产品缺陷。
- 结论 `NATIVE_PREP_INTERNAL_LOOPBACK_BLOCKED_STOP`。按 MaxIterations=1 未切换为非 internal 网络或发起第二次拓扑尝试；已精确删除 API、Redis、PostgreSQL 与专名网络，复核本 lease 容器/网络/标签卷为空、8000 无监听，既有 buildx 容器未触碰。tmpfs 数据随容器删除，无账号/令牌产生；无源码/config/依赖/assets/commit/push/PR/merge，不批准 FE-G2 产品门、G3、INT-001 或 REL-001。

### FE-001-G2-NATIVE-RELAY-PREP-13 手动认证交接准备（2026-10-19）

- 基于 `feat/fe-001-g2-api@30bd1d3e7555c0bebb029d1bb68ba9711db3f7ea` 与仅本 admission dirty，保留 PREP11/PREP12 失败历史；未运行 build/fullsuite/install。新建 internal 网络 `ft-g2-nativeprep13-20261019-internal`（ID `c8b4ddaefffa2817693048c676a8bff44a73d7c5a7dbac107fc793913a9b72f1`）及 relay bridge `ft-g2-nativeprep13-20261019-relay-net`（ID `6c4e3f96b73a7975905c3387e37b90afce998d41c89af138ba10b1ea51b9542d`），均带 lease/owner label。PG `70c64bc484a41a7680a4496546892a4a6d8319f08b723f60654037a075621e56`、Redis `652a1e9b7785151d6e21316deadc0f547df52b5bcb19ddb90657489d251fa4fb`、API `2f686d43f246d80cf3a3053665f9de29f8e98eefcb22422484debb53e1c24075` 仅连接 internal 网络且无主机发布；PG/Redis 无 Mounts、仅 tmpfs。空库 `flowtracer_fe_g2_20261019_prep13_test` 在 API 前迁移至 `20261006_0009`，当前 `users=0`、`radars=0`；Fake providers、Browser disabled、无 Worker/Beat。
- gitignored 验收脚本 `frontend/test-results/native-relay-prep13/relay.py` SHA-256 `8AA98E985120F7B29804EB1E63AAFDD2D208D04E945C07F93B513E84BAE2B3A9`，目标硬编码为 `ft-g2-nativeprep13-20261019-api:8000`，不接受任意目标、不解析 HTTP、不记录 body/header/password/token；最多 8 个并发连接，连接超时 3 秒、空闲读写超时 15 秒。relay `5f1fc96d70d034f5a8c038a88a5a5d77d1e6c5f6c284cbede87a21a471251f62` 同时连接两专属网络，UID/GID `10001/10001`，cap-drop ALL、no-new-privileges、read-only rootfs、脚本只读挂载，仅其 `8000/tcp` 实际发布到 `127.0.0.1:8000`。它是临时验收工具，不是 Browser proxy 或产品配置。
- 主机 `GET /api/v1/health/live` 与 `/health/ready` 均 200；live 为 service `flowtracer-api` version `0.1.0`，ready 的 database/redis 均为 `ok`。exe SHA-256 `206FCDF70899C9F9748BDA967658EA94FA84342EB6F200B2A03CD3082A08B138` 经 computer-use 启动为 PID `40444`，窗口 `FlowTracer · Local Intelligence Universe` 到达未输入的登录页，显示“本机 API 已就绪”和 `http://127.0.0.1:8000/api/v1`。未填写邮箱/密码、未切换注册、未点击登录/注册，也未通过 API 创建账号。
- 结论 `NATIVE_RELAY_PREPARED_FOR_MANUAL_AUTH`，不是产品验收。四个专名容器、两个网络与原生窗口暂时保留给用户手动认证；从 internal 网络创建时刻计算的最晚交接截止为 `2026-10-19 12:35:51 +08:00`，到期须由总控精确清理，不永久等待。既有 buildx/其他容器卷未触碰；无源码/backend/schema/config/依赖/assets/commit/push/PR/merge，不批准 G3、INT-001 或 REL-001。

### FE-001-G2-NATIVE-RADAR-VERIFY-14 用户输入冲突停点（2026-10-19）

- 在用户直接报告已手动进入真实星图后，fresh list 唯一选择现有 FlowTracer 原生窗口；只读观察确认 live 空星图、真实连接、真实 Radar 计数 0、无 Demo 数据。隔离库 active user UUID 仅记录为 `74bf57af-0327-42ed-878b-ebf20d9996dd`，初始 Radar 数 0；未读取或输出邮箱、密码、令牌、全环境或其他个人资料。HEAD/源码/exe 保持 `30bd1d3e7555c0bebb029d1bb68ba9711db3f7ea` / `206FCDF70899C9F9748BDA967658EA94FA84342EB6F200B2A03CD3082A08B138`。
- 通过唯一原生窗口创建一次且仅一次 `Native Opportunity 20261019 14`，目标 `Verify native Radar lifecycle`、类型 opportunity、说明 `Initial native verification`；UI 显示唯一真实行星、真实 Radar 计数 1、详情为本机 API/活跃/真实。只读 DB 核对唯一 ID `58a0f557-b1d9-4910-8c9b-ecec90205f6b`、user_id 与上述 active user UUID 一致、type `opportunity`、threshold `75`、status `active`、未删除。随后原生 UI 单次编辑为 `Native Opportunity 20261019 14 Edited`、说明 `Edited native verification`、threshold `82`；UI 即时显示新名称/说明，最终 DB 同步为相同值。
- 原生 UI 单次确认暂停后，详情显示“已暂停 · 真实”并出现“恢复 Radar”；最终 DB status 为 `paused`，其余唯一记录字段及未删除状态保持。Windows accessibility 的 `focused_element` 对该 WebView 始终报告根文档，因此准备以 fresh state 的 Enter 行为验证逻辑焦点并进入恢复确认；此时 computer-use 返回 `user input was detected in this window`。按技能强制规则立即停止所有后续 UI 输入，没有重试或争抢用户窗口。
- 结论 `NATIVE_RADAR_PARTIAL_PASS_USER_INPUT_STOP`：创建、DB owner/字段一致、编辑持久化与暂停均成立；恢复动作/逻辑焦点、Signals 空列表及返回 Canvas **未完成**，不能写成完整 Radar native E2E PASS。API access log 已关闭，证据限定为原生 UI 连续状态与隔离 DB 前后事实，不声称逐请求来源证明。未删除 Radar、未触碰 Source/collect、未 seed Signals；本轮新增问题 P0/P1/P2=`0/0/0`，停点原因为用户输入冲突而非已证实产品缺陷。
- PREP13 四容器、两网络、relay 与原生窗口继续保留给总控下一 lease 或精确 cleanup；本轮未清理也未触碰 buildx。无源码/锁/config/backend/schema/fulltest/commit/push/PR/merge，不批准完整 FE-G2、G3、INT-001 或 REL-001。

### FE-001-G2-NATIVE-CLEANUP-15 额度保护精确清理（2026-10-19）

- 总控可靠额度更新为 5 小时/每周剩余 7%/70% 后，未再执行任何 sky/UI 动作、测试或业务验证。RADAR-VERIFY-14 的既有最小证据保持：唯一 Radar `58a0f557-b1d9-4910-8c9b-ecec90205f6b`，owner `74bf57af-0327-42ed-878b-ebf20d9996dd`，最终 name `Native Opportunity 20261019 14 Edited`、type `opportunity`、threshold `82`、description `Edited native verification`、status `paused`、未删除；恢复/逻辑焦点和 Signals 往返仍未验证。
- 清理前以完整 ID 和 `FE-001-G2-NATIVE-RELAY-PREP-13` / `codex-integration-nativeprep13` 标签逐一核对 PREP13 四容器与两网络。原生 PID `40444` 的路径 `D:\FlowTracer-wt\integration\frontend\src-tauri\target\debug\flowtracer-desktop.exe`、启动时间 `2026-10-19 12:08:19 +08:00` 与既有记录精确匹配后，使用该 PID 单独终止；未按进程名批量停止。
- 已按完整 ID 精确删除 relay `5f1fc96d70d034f5a8c038a88a5a5d77d1e6c5f6c284cbede87a21a471251f62`、API `2f686d43f246d80cf3a3053665f9de29f8e98eefcb22422484debb53e1c24075`、Redis `652a1e9b7785151d6e21316deadc0f547df52b5bcb19ddb90657489d251fa4fb`、PG `70c64bc484a41a7680a4496546892a4a6d8319f08b723f60654037a075621e56`，以及 internal 网络 `c8b4ddaefffa2817693048c676a8bff44a73d7c5a7dbac107fc793913a9b72f1`、relay 网络 `6c4e3f96b73a7975905c3387e37b90afce998d41c89af138ba10b1ea51b9542d`。tmpfs 测试账号/Radar 数据随 PG 删除且不可恢复，符合本轮隔离测试清理范围。
- 终态复核 PREP13 标签容器/网络/卷为空、PID `40444` 不存在、8000 无监听；既有 `buildx_buildkit_flowtracer-r1-final-builder0` 仍运行且未触碰。无 global prune、无其他容器卷操作、无源码/reset/commit/push/PR/merge；结论 `NATIVE_PREP13_CLEANUP_COMPLETE_STOP`。

### FE-001-G2-NATIVE-PREP-16 手动认证交接停点（2026-10-19）

- 身份保持 `feat/fe-001-g2-api@30bd1d3e7555c0bebb029d1bb68ba9711db3f7ea`，除本 admission 外无 tracked 改动；exe SHA-256 仍为 `206FCDF70899C9F9748BDA967658EA94FA84342EB6F200B2A03CD3082A08B138`。复用可信镜像和未改字节的 gitignored relay 脚本（SHA-256 `8AA98E985120F7B29804EB1E63AAFDD2D208D04E945C07F93B513E84BAE2B3A9`），未 build/pull/install/fulltest，既有 buildx 未触碰。
- 新建带 `FE-001-G2-NATIVE-PREP-16` / `codex-integration-nativeprep16` 标签的 PG `742bffb0db468a60b00c407fafbb46b39671f7365ea7c7dd546b7a98eba72900`、Redis `3ac9443f176c8d7bd6a2b88509841d8d7c80a4309b65a74c4dd0a100c4233dfe`、API `b47273f9f8347cb7eda806caecfe5f2c7ba7f7afb86c27301516b07609603d90`、relay `37a01fa1924078d55af89c1bc206d6a84b6c12af9f796b5374be1cf317f84e28`，以及 internal 网络 `4323bc9cd2992fd71a821852190e1f8c0b05f393d0720fa698e9f250a412c017`、relay 网络 `0f3d19f2c7d24b05bc0da5d8e982798dfe8d9d1dfdd8e176e30ae5e74ab89026`。PG/Redis 使用 tmpfs 且无 Mounts；空库 `flowtracer_fe_g2_20261019_prep16_test` 迁移至 `20261006_0009`，`users=0`、`radars=0`。API 仅在 internal 网络，`8000/tcp` 无宿主发布；固定旧主机名仅作为该 API 的本轮内部 alias。
- relay 同时仅连接上述两网络，UID/GID `10001/10001`、cap-drop ALL、no-new-privileges、read-only rootfs、脚本只读挂载；唯一实际发布为 `127.0.0.1:8000`。主机 live/ready 均为 HTTP 200，database/redis 均为 `ok`。资源从 internal 网络创建时间 `2026-10-19 22:01:27 +08:00` 起最多保留 30 分钟，最晚清理截止 `2026-10-19 22:31:27 +08:00`。
- computer-use fresh list 唯一启动 exe 为 PID `34952`，路径 `D:\FlowTracer-wt\integration\frontend\src-tauri\target\debug\flowtracer-desktop.exe`，启动时间 `2026-10-19 22:05:09 +08:00`，窗口 `FlowTracer · Local Intelligence Universe`。在首次只读页面观察前检测到 `user input was detected in this window`，按强制规则立即停止所有 UI 动作；未争抢焦点、未按键、未填写或点击认证字段，因此未由自动化确认空登录页或本机 API 状态文案。
- 结论 `NATIVE_PREP16_BACKEND_READY_USER_INPUT_STOP`：隔离后端与回环中继已就绪，可由用户在现有窗口手动注册/登录；只使用临时测试凭据，不使用真实密码。该结论不是认证成功或 FE-G2 产品验收；无源码/config/依赖/commit/push/PR/merge，不批准 G3、INT-001 或 REL-001。到期由总控按上述精确 ID 清理。

### FE-001-G2-NATIVE-FLOW-17 窗口缺失与精确清理停点（2026-10-19）

- 总控在 `2026-10-19 22:36:35 +08:00` 发现 PREP-16 原截止 `22:31:27 +08:00` 已超时约 5 分钟；FLOW-17 不把旧 lease 视为自动续权，只明确接管仍在场且可核验的六个 PREP-16 资源，并给出最迟 `22:58:00 +08:00` 的新硬截止。开始可靠额度为 5 小时/每周 `75%/66%`，未使用 reset credit。
- `2026-10-19 22:38:00 +08:00` 预检确认 `feat/fe-001-g2-api@30bd1d3e7555c0bebb029d1bb68ba9711db3f7ea`，tracked dirty 仅本 admission；四容器、两网络的完整 ID 与 PREP-16 记录一致，全部仍带原 lease/owner 标签且容器 running。host live/ready 均为 HTTP 200，database/redis 均为 `ok`；隔离库恰好一个用户 UUID `57da3a15-a576-4b12-8d7c-5450e5c594c5`、`radars=0`，未读取邮箱、密码、令牌或全环境。
- computer-use fresh `list_windows()` 按 exact process path 和窗口标题两种限定复核均得到 FlowTracer 窗口数 `0`；随后 Windows 进程核验也为 `FLOWTRACER_PROCESS=ABSENT`。因此无法接管人类刚完成认证的进程内会话；重新启动可能回到认证页，而本 lease 禁止自动认证。按 fail-closed 立即停止，未创建 fixture Radar/Source、未点击或输入 UI、未写 runner、未执行 acquisition/clean/analysis，也没有 native 恢复、collect、poll、Signals/detail 新证据。
- 已使用既有记录中的完整 ID 精确删除 relay `37a01fa1924078d55af89c1bc206d6a84b6c12af9f796b5374be1cf317f84e28`、API `b47273f9f8347cb7eda806caecfe5f2c7ba7f7afb86c27301516b07609603d90`、Redis `3ac9443f176c8d7bd6a2b88509841d8d7c80a4309b65a74c4dd0a100c4233dfe`、PG `742bffb0db468a60b00c407fafbb46b39671f7365ea7c7dd546b7a98eba72900`，以及 internal 网络 `4323bc9cd2992fd71a821852190e1f8c0b05f393d0720fa698e9f250a412c017`、relay 网络 `0f3d19f2c7d24b05bc0da5d8e982798dfe8d9d1dfdd8e176e30ae5e74ab89026`。终态复核该 lease 标签容器/网络/卷为空、8000 无监听，仅既有 builder `7beb76c2ed37` 继续运行且未触碰；tmpfs 测试账号数据随 PG 删除且不可恢复。
- 结论 `NATIVE_FLOW17_NO_WINDOW_CLEANUP_COMPLETE_STOP`。无产品源码/config/依赖/锁/API/schema/fullsuite/commit/push/PR/merge，不关闭任何恢复、Source/collect、Signals 缺口，不批准 FE-G2、G3、INT-001 或 REL-001。

### FE-001-G2-NATIVE-PREP-18 迁移配置失败与精确清理停点（2026-10-19）

- 人类澄清 FLOW-17 窗口缺失是主动关闭而非已知产品 crash，并授权重新准备登录交接。`2026-10-19 22:42:19 +08:00` 预检确认 `feat/fe-001-g2-api@30bd1d3e7555c0bebb029d1bb68ba9711db3f7ea`，tracked dirty 仅本 admission；exe/relay SHA-256 分别仍为 `206FCDF70899C9F9748BDA967658EA94FA84342EB6F200B2A03CD3082A08B138` / `8AA98E985120F7B29804EB1E63AAFDD2D208D04E945C07F93B513E84BAE2B3A9`，端口 8000 空闲。开始可靠额度为 5 小时/每周 `69%/65%`。
- 创建带 `FE-001-G2-NATIVE-PREP-18` / `codex-integration-nativeprep18` 标签的 internal 网络 `a81ce8553fa641a099ad240efcda88666394b1e736bded4fdf368ba012feb232`、relay 网络 `81b023be82181d1479e75a4533e618ff98efbb69be3345d8f38ed3391ce45340`、PG `7339bce582943a5012b96de9a4aa078c1f06dd182b653a93d36690d9be1ea65a` 与 Redis `2ed6cfc0e80d39f3f821120dce742b0f66b9df7086f2a4e96efc2ea86b184dd0`；PG/Redis 达到 healthy，使用 tmpfs 且未创建持久卷。
- 唯一一次迁移命令在执行迁移前被应用配置校验拒绝，错误为缺少现有必需测试变量（AI/Embedding provider、Redis/Celery、API host/port/version/log、JWT secret 等）。这是控制命令遗漏，不是产品迁移失败；依据 `MaxIterations=1` 未补变量重试，API、relay 与原生窗口均未启动，也未产生用户、业务数据或认证操作。
- 已按完整 ID 精确删除上述 PG、Redis 与两个网络；终态复核本 lease 标签容器/网络/卷为空、8000 无监听，仅既有 builder `7beb76c2ed37` 运行且未触碰。tmpfs 空数据随容器删除且不可恢复。
- 结论 `NATIVE_PREP18_MIGRATION_CONFIG_FAILED_CLEANUP_COMPLETE_STOP`。无源码/config/依赖/锁/build/pull/install/fullsuite/commit/push/PR/merge，不批准认证、FE-G2、G3、INT-001 或 REL-001。

### FE-001-G2-NATIVE-PREP-19 统一环境脚本参数绑定失败停点（2026-10-19）

- 总控将 PREP-18 定性为测试启动脚本缺陷并批准一次最小可复用脚本增量。只读核对当前 `Settings`、`tests/conftest.py` 测试矩阵和 `ALPHA-OPERATIONS.md` 必需字段后，新增 gitignored `frontend/test-results/native-prep19/prepare.ps1`，SHA-256 `C59E5FB685F296FA6C20DE72E7CD142ED5FE1F7701A498CAAA5154D8956E95E5`。脚本在单一 PowerShell 进程内生成随机数据库口令/JWT secret（不落盘、不输出），并以同一个 env argument array 供 Settings 预检、migration 与 API 复用；没有读取真实 `.env` 或用户 secret。
- 唯一一次执行先以可信镜像、`--network none` 和 owner/lease label 完成 Settings 构造并输出 `CONFIG_OK`，证明统一环境集合满足当前配置合同。随后创建 internal 网络 `0a6b88a588a6615bf73cdc2599511e027a143fcac56592508c1aec5c8c14069c` 与 relay 网络 `a28a95d8ac758372a754fc7edd84b53e48192c20b47a7c61cebc18d03ef7c297`，但在 PG `docker run` 执行前，PowerShell 将 splatted env array 的 `-e` 误解释为脚本包装函数参数缩写并报 ambiguous parameter；因此没有创建 PG/Redis/API/relay、没有迁移、没有启动原生窗口，也没有账号或业务数据。
- 依据 `MaxIterations=1` 未修改脚本后重跑。脚本失败清理未移除两个空网络，终态核验发现后立即使用上述完整 ID 精确补删；最终本 lease 标签容器/网络/卷为空、8000 无监听，仅既有 builder `7beb76c2ed37` 运行且未触碰。gitignored 脚本保留为失败候选，不作为已验证准备工具。
- 结论 `NATIVE_PREP19_SETTINGS_PASS_WRAPPER_BINDING_FAILED_CLEANUP_COMPLETE_STOP`。这是验收脚本包装层失败，不是产品 Settings、迁移或原生客户端失败；无产品源码/config/依赖/锁/build/pull/install/fullsuite/commit/push/PR/merge，不批准认证、FE-G2、G3、INT-001 或 REL-001。

### FE-001-G2-NATIVE-PREP-20 手动认证交接准备（2026-10-19）

- 在 `feat/fe-001-g2-api@30bd1d3e7555c0bebb029d1bb68ba9711db3f7ea` 与仅本 admission tracked dirty 上，最小修复 gitignored `frontend/test-results/native-prep19/prepare.ps1`：普通函数以自动 `$args` 原样转发 Docker 参数；失败路径先按 exact ID + lease/owner label 清理，再用安全 stderr 摘要退出。脚本 SHA-256 为 `B50836667B59F00E5948470406D619B3A291F70151A9AA39C49EADBFE8AF1B75`，随机数据库口令/JWT secret 仅在单次 PowerShell 进程内生成，不落盘、不输出。
- 第 1 次有界执行的无网络可信镜像预检同时验证字面 `-e FLOWTRACER_WRAPPER_PREFLIGHT=ok` 与当前 Settings，依次输出 `WRAPPER_OK`、`CONFIG_OK`；同一 env argument array 随后复用于 migration 与 API。空库 `flowtracer_fe_g2_20261019_prep20_test` 成功迁移至 `20261006_0009`，交接时 `users=0`、`radars=0`；Fake AI/Embedding、无 Worker/Beat、Browser disabled 边界保持，未 build/pull/install/fullsuite。
- 创建带 `FE-001-G2-NATIVE-PREP-20` / `codex-integration-nativeprep20` 标签的 internal 网络 `c904e8b37209dd4eb9ea8810ecc6fc8e3e4d43101c19fe974f18ac999d73fcf3`、relay 网络 `b5a463885e4ce56615751fc5cf53d7170b552d82e50f3d2f688df94a033d6f46`、PG `0cd71ab19db376a15c86085f3de395bf5e05c2b6d05344310d6294d2a4f67ad6`、Redis `d049d34013b118cef6cf051e82aec3db9c634624c045099b1ce3a750837448d6`、API `500b25deea2eb722e9773f35df2784af3c9c28cd5f2b05cf2ca9e99e48bead35`、relay `129b218dba37af4dc6cb04027b9772be0c04a87d166c6bdd898bf61034d5e3a2`。PG/Redis 使用 tmpfs、无持久卷；API 仅在 internal 网络且 `8000/tcp` 无宿主发布。
- relay 仅连接上述两网络，UID/GID `10001/10001`、cap-drop ALL、no-new-privileges、read-only rootfs、脚本只读挂载且 SHA-256 `8AA98E985120F7B29804EB1E63AAFDD2D208D04E945C07F93B513E84BAE2B3A9`，唯一实际发布为 `127.0.0.1:8000`。host live/ready 均为 HTTP 200，database/redis 均为 `ok`。
- computer-use fresh list 确认无旧窗口后启动 exe（SHA-256 `206FCDF70899C9F9748BDA967658EA94FA84342EB6F200B2A03CD3082A08B138`）为 PID `33532`，启动时间 `2026-10-19 22:49:13 +08:00`。唯一窗口经一次非认证 Enter 从启动页进入空登录页，邮箱/密码均未输入，显示“本机 API 已就绪”和 `http://127.0.0.1:8000/api/v1`；未切换注册、未点击登录/注册、未创建账号。
- 结论 `NATIVE_PREP20_PREPARED_FOR_MANUAL_AUTH`，不是认证成功或产品验收。资源从 internal 网络创建 `2026-10-19 22:48:33 +08:00` 起最长保留 30 分钟，最晚清理截止 `2026-10-19 23:18:33 +08:00`；到期须由总控按上述完整 ID 精确清理。无产品源码/config/依赖/锁/commit/push/PR/merge，不批准 FE-G2、G3、INT-001 或 REL-001。

### FE-001-G2-NATIVE-FLOW-21 用户焦点冲突与精确清理停点（2026-10-19）

- `2026-10-19 22:52:46 +08:00` fresh 预检确认 `feat/fe-001-g2-api@30bd1d3e7555c0bebb029d1bb68ba9711db3f7ea`、tracked dirty 仅本 admission、exe SHA-256 `206FCDF70899C9F9748BDA967658EA94FA84342EB6F200B2A03CD3082A08B138`。PREP-20 四容器、两网络完整 ID/标签与交接记录一致，PID `33532` 的路径和 `2026-10-19 22:49:13 +08:00` 启动时间匹配；live/ready 均为 HTTP 200。隔离库仅一个用户 UUID `c76702d0-6093-43c6-8dd7-d05afc08cdc3`，开始时 Radar/Source/run 均为 0；可靠额度为 5 小时/每周 `55%/62%`。
- computer-use fresh list 唯一原生窗口已在 live 真实星图，显示真实连接、Radar 0、无 Demo 数据。原生 UI 创建唯一测试 Radar `Native Flow 20261019 21`，目标 `Verify native resume source and signals`，默认 type `custom`；UI 显示真实 Radar 1。只读 DB 核验唯一 Radar ID `0a0e3168-e409-40a2-8403-3de8164051dd`，owner 为上述唯一用户、status `active`、未删除；这是为本轮恢复/Source 验收准备的最小创建事实，不重复声明完整 create/edit 回归。
- 尝试选择唯一 Radar 时，fresh screenshot 两次显示系统任务切换器或 ChatGPT 窗口覆盖目标原生窗口，形成用户焦点/输入冲突风险。虽未返回显式 user-input guard，仍按 computer-use fail-closed 规则立即停止所有 UI 输入；没有尝试暂停或恢复。最终 DB 仍为上述唯一 active Radar，Source=0、CollectionRun=0。
- 结果粒度：native Radar 最小创建 + DB ownership/status `PASS`；native pause→resume `NOT_RUN`；native Source create/bind `NOT_RUN`；single collect/queued run/UI poll `NOT_RUN`；offline FixtureFetcher production service runner `NOT_RUN`（未创建 runner/fixture 文件）；Document/Analysis 与 Signals list/detail `NOT_RUN`。没有产品/UI/security 缺陷结论，停点原因是前台窗口冲突，不能写成恢复、Source 或 Signals 验收。
- 清理前再次按 PID/path/start 精确匹配原生进程，随后单独终止 PID `33532`；按既有完整 ID 精确删除 PREP-20 relay/API/Redis/PG 与两个网络。终态复核该 lease 标签容器/网络/卷为空、8000 无监听、PID 不存在，仅 builder `7beb76c2ed37` 运行且未触碰；tmpfs 测试账号和唯一 Radar 数据随 PG 删除且不可恢复。
- 结论 `NATIVE_FLOW21_RADAR_CREATE_PASS_FOCUS_CONFLICT_CLEANUP_COMPLETE_STOP`。无产品源码/config/依赖/锁/build/install/fullsuite/commit/push/PR/merge，不关闭恢复、Source/collect、Signals 剩余缺口，不批准 FE-G2、G3、INT-001 或 REL-001。

### FE-001-G2-NATIVE-PREP-23 手动认证交接准备（2026-10-19）

- 基于 `feat/fe-001-g2-api@30bd1d3e7555c0bebb029d1bb68ba9711db3f7ea` 与仅本 admission tracked dirty，机械复制已验证 PREP-20 helper 为 gitignored `frontend/test-results/native-prep23/prepare.ps1`，仅替换 lease/owner/resource/database 名称；脚本 SHA-256 `CA19609ACD4566FAE416D8A3B0E7AA0B07E2869EA5E8072668574AB6D7BED9DD`。未改变统一 env、wrapper/settings preflight、拓扑或 cleanup 实现，未 build/pull/install/test。
- 唯一一次运行输出 `WRAPPER_OK`、`CONFIG_OK`，空库 `flowtracer_fe_g2_20261019_prep23_test` 迁移至 `20261006_0009`，交接时 users/radars 均为 0。host live/ready 均为 HTTP 200，database/redis 均为 `ok`；Fake providers、Browser disabled、无 Worker/Beat、无公网访问。
- 创建带 `FE-001-G2-NATIVE-PREP-23` / `codex-integration-nativeprep23` 标签的 internal 网络 `693ca69330c1a063479efedf36a8d43d69fb80cd90b0fb7b3d430adcd67a83ff`、relay 网络 `10d42fdc60f42ecf119e5ede25f5c9513b813fdac5dbc0495362bf6dfe15980e`、PG `f59b3cdc82c9507478e1f2e9b7245fac0c8fb46343a047f7072e512862eb5601`、Redis `2f48bd8c720b3f86ddcf8e4c2139b90a467a038cd80e733367f1ac52a950a495`、API `bbc9653ecab2debf4f5bb0dd327fbbf408566960d9671dbbf5f3074783ca5a65`、relay `480c194886285f0db809edaf27181c4f3cbdef3ce5ce02078bebbc10582ba5c5`。API 无宿主发布；relay 仅发布 `127.0.0.1:8000`，UID/GID `10001/10001`、cap-drop ALL、no-new-privileges、read-only rootfs，relay 脚本哈希仍为 `8AA98E985120F7B29804EB1E63AAFDD2D208D04E945C07F93B513E84BAE2B3A9`。
- 按重新核对的 computer-use screenshot/cache/geometry guidance，仅使用 fresh window identity 与非坐标 `Return` 从启动页进入登录页；未硬编码 screenshot ID、未发生遮挡或输入 guard。exe SHA-256 `206FCDF70899C9F9748BDA967658EA94FA84342EB6F200B2A03CD3082A08B138` 启动为 PID `2792`，时间 `2026-10-19 23:00:52 +08:00`；唯一窗口停在空登录页，显示“本机 API 已就绪”，未输入或点击认证内容。
- 结论 `NATIVE_PREP23_PREPARED_FOR_MANUAL_AUTH`，不是认证成功或产品验收。资源从 internal 网络创建 `2026-10-19 22:59:54 +08:00` 起最长保留 30 分钟，最晚清理截止 `2026-10-19 23:29:54 +08:00`；到期须按上述完整 ID 精确清理。无产品源码/config/依赖/锁/commit/push/PR/merge，不批准 FE-G2、G3、INT-001 或 REL-001。

### FE-001-G2-FIXTURE-RUNNER-24 离线 runner 预检停点（2026-10-19）

- 在 PREP-23 原 TTL `2026-10-19 23:29:54 +08:00` 内，仅新增 gitignored `frontend/test-results/native-flow24/runner.py` 与既有 `backend/tests/fixtures/alpha_feed.xml` 的机械副本；SHA-256 分别为 `3372BE587B156E7C089B8219135A3B878F88939C5F1ED7B8B94082FD9EC5379A`、`C82CD1D4C3EFAA85E8B0572703CBC68AC76C36AA9E51876C2F2A2C3013CB5E47`。未修改产品源码、依赖、锁、配置或数据库 schema。
- runner 导入并保留现有生产链路 `SqlAlchemyAcquisitionRunRepository`、`execute_run` + `NativeAcquisitionBackend`、`clean_raw_item`、`FakeAnalysisProvider`、`run_analysis` 与 analysis completed publish；`FixtureFetcher` 只允许 `https://native-g2-fixture.invalid/feed.xml` + RSS，并从同目录 fixture 读取字节，其他 URL 或类型 fail-closed。`--run` 设计为先确认 exact PREP-23 `_test` 数据库、唯一 owned Source/queued run、固定 URL/type、user/run/source/radar 绑定，再调用生产服务；不直接伪造 Analysis/Signal，也不包含 embedding/notification/WS/Router 验收。
- 文件复制到现有 PREP-23 API `/tmp/native-flow24` 后以 UID/GID `10001/10001` 执行 `--check`。第 1 次仅因临时脚本目录未包含应用模块路径，在 import 阶段报 `ModuleNotFoundError: No module named 'app'`；未连接数据库、未写数据。允许的第 2 次仅设置工作目录 `/app` 与 `PYTHONPATH=/app`，输出 `CHECK_OK allowed=1 denied_url=1 denied_type=1 db_connected=0`。
- 结论 `FIXTURE_RUNNER24_CHECK_PASS`：Settings/生产导入与 FixtureFetcher 正反例通过，但 `--run` 未执行，因此不产生或证明 run/RawItem/Document/Analysis/Signal。全程未调用 sky、未操作认证/UI、未读取邮箱/密码/token/全环境；PREP-23 四容器继续运行且 PG/Redis healthy，TTL 不延长。无 build/install/pull/fullsuite/commit/push/PR/merge，不批准 Source/collect/Signals、FE-G2、G3、INT-001 或 REL-001。

### FE-001-G2-COLLECTION-WIRE-27 CollectionRun 线格式修复停点（2026-10-20）

- 在 `feat/fe-001-g2-api@30bd1d3e7555c0bebb029d1bb68ba9711db3f7ea` 与既有 admission dirty 上，只修改 `frontend/src-tauri/src/api.rs`。真实原生验收的 POST collect 202、唯一 run 与 GET collection-runs 200 已成立，但 panel 报 `Backend returned an invalid response`；冻结 `CollectionRunResponse` 明确输出 `source_id/fetched_count/...` snake_case，而原 Rust `CollectionRunView` 同时 derive Deserialize/Serialize 并使用 `rename_all="camelCase"`，导致 bridge 错把 backend 输入当 `sourceId/fetchedCount/...`。同文件 mock 也伪造 camelCase，因而掩盖真实缺陷。
- 最小修复拆分内部 `CollectionRunResponse`（按 Rust 字段名接收 backend snake_case）与公开 `CollectionRunView`（仅 Serialize，继续以 camelCase 输出给前端），并在 identity 校验后显式转换；前端 bridge public shape 不变。紧邻 Signals 已是 `IntelligenceResponse` → `IntelligenceView` 的独立输入/输出 DTO，没有确证同类混用，未扩改。
- happy mock 改为冻结后端形状，包含 snake_case collection 字段和实际额外字段；测试断言 backend snake_case 可接收、bridge 序列化含 `sourceId/fetchedCount` 且不含 `source_id`。identity-negative mock 同步改为 snake_case，使 mismatched UUID 拒绝继续经过 identity guard；既有未知 enum、错误 status/location 与输入拒绝断言保持。
- 唯一验证命令 `cargo test --locked --offline source_collection_ -- --nocapture`：`2 passed / 0 failed / 18 filtered out`，覆盖 happy wire/bridge 输出与 bad input/status/location/enum/identity 拒绝。`git diff --check -- frontend/src-tauri/src/api.rs` exit 0；验证后 `api.rs` SHA-256 `81E0615701130A07C6DE589D1ADDB1D8B3115D926B6D65931F83FB76619065B9`。
- 结论 `COLLECTION_RUN_WIRE_TARGETED_PASS`，本轮新增 P0/P1/P2=`0/0/0`。这是 Rust bridge 定向修复证据，不是重新 build/启动 desktop 或原生复验；Signals native E2E、完整 FE-G2 产品门仍未关闭。未触碰 Docker/PREP-26、backend/schema/OpenAPI、依赖/锁/其他源码，无 commit/push/PR/merge，不批准 G3 或 INT。

### FE-001-G2-GRID-MOTION-30 共享经纬线旋转可见性停点（2026-10-20）

- 在 `feat/fe-001-g2-api@30bd1d3e7555c0bebb029d1bb68ba9711db3f7ea` 上保留既有 `docs/FE-001-G2-ADMISSION.md` 与 `frontend/src-tauri/src/api.rs` dirty；`api.rs` 未改且 SHA-256 仍为 `81E0615701130A07C6DE589D1ADDB1D8B3115D926B6D65931F83FB76619065B9`。本轮产品改动仅将共享 `OriginalBackdrop` 的 `.original-polar-grid svg` 旋转周期从 `230s` 调为 `120s`，保持 `linear infinite`；同一背景组件持续覆盖启动、登录、主星图和工具页，轨道装饰仍为 `280s`，前景、Radar、文字、面板与 `pointer-events: none` 均未改变。未引入 GSAP、新依赖或 JavaScript 帧循环。
- 既有 quiet mode 与系统 `prefers-reduced-motion: reduce` 的全局 `animation: none !important` 继续生效，本轮没有添加覆盖规则。`npm run build` exit 0：Vite `7.3.7`、53 modules transformed、1.25s。
- 唯一 Edge 定向命令 `$env:FLOWTRACER_TEST_EDGE="1"; npx playwright test tests/backdrop-motion.spec.ts --workers=1 --retries=0 --output=test-results/backdrop-motion-30`：`2 passed / 0 failed`（约 9.7s）；独立输出 `.last-run.json` 为 `status=passed`、`failedTests=[]`。测试直接读取 CSSAnimation，确认 `original-turn` 为 `120s / linear / running`，160ms 采样后 `currentTime` 前进超过 80ms 且 computed transform 改变；同一 SVG identity 跨启动、登录、离线 Demo 星图与 Settings 连续，前景/应用壳/工具页自身不运行 `original-turn`，quiet mode 与系统 reduced-motion 均停止该动画。全程无外部请求、页面错误或 console error。
- `frontend/src/styles/original-intro.css` SHA-256 `FE116676D37642A24DB157DCF5C2E8720CC67A57BFED88499D95D29846B4EDFB`；新增 `frontend/tests/backdrop-motion.spec.ts` SHA-256 `BC0F08C03785E7F0B13D629A1862A71E933FF1A968AC7C1582FC7C0D22AE0BBF`；定向 `git diff --check` exit 0。
- 结论 `GRID_MOTION_TARGETED_PASS`，本轮新增 P0/P1/P2=`0/0/0`。这是 Web/CSS 与 Edge 浏览器定向证据；当前原生 exe 是此前构建的旧资产，本轮未重新构建或启动，因此不包含该视觉增量，也没有完成原生窗口视觉复验。未触碰 Docker、认证、PREP-28 资源、backend、契约、素材、依赖/锁、`CURRENT-GATE.md`，无 commit/push/PR/merge，不批准 G3 或 INT。

### FE-001-G2-NATIVE-FLOW-31 真实原生采集与 Signals 停点（2026-10-20）

- 在 `feat/fe-001-g2-api@30bd1d3e7555c0bebb029d1bb68ba9711db3f7ea` 加既有 wire27/motion30 dirty 上，使用 wire-fixed、尚不含 GRID-MOTION30 CSS 的原生 exe（SHA-256 `D48293AC11A140DF43B5935852B9B9F20B88BA4DE3083D09519E7BA148FA7DAB`）继续已由用户完成认证的真实窗口；agent 未读取或写入邮箱、密码、token，也未重复注册。先前 FLOW29 输入保护发生时未创建 Radar，随后在 FLOW31 fresh observation 与显式激活目标窗口后恢复。
- 原生 UI 精确创建并绑定 1 个 active custom Radar `Native Flow 20261020`（UUID `6ae2792d-faad-4def-af23-8ceb227c1493`）与 1 个 RSS Source `Native Offline RSS`（UUID `fa2ce797-e0fd-4799-8ac9-f214c90d5ef0`，URL `https://native-g2-fixture.invalid/feed.xml`，60min）；owner 与 `radar_sources` 绑定均匹配唯一用户。一次有截图证据的 Collect 创建唯一 queued run `0a5a42b8-7716-464a-a195-a8f974f76446`，未触发第二次采集。
- 既有 guarded `/tmp/native-runner28.py` 仅执行一次，以 UID `10001`、固定本地 RSS 字节和既有生产 acquisition/cleaning/intelligence 服务处理 exact PREP28 测试库；使用 FakeAnalysisProvider，无公网或付费 AI。结果为 run `succeeded`、fetched/created/duplicates/failed=`1/1/0/0`，raw/document/completed analysis=`1/1/1`，score `77.60`，并捕获 3 个 recording-only publisher events。原生 panel 自动从 queued 轮询至 succeeded，显示同一计数且 Collect 恢复可用，没有 `invalid_response`，构成 CollectionRun wire mismatch 的真实运行闭环。
- 原生 Signals 显示真实 `Offline RSS intelligence` 列表、COMPLETED/READ、77.6、fixture URL 与 pagination `1/1`；详情显示标题、URL、score、recommendation、category、wordCount、summary、确定性 reason 及正文 `Deterministic local RSS content about resilient backend systems and vector memory.`。返回列表与 Canvas 后仍为 1 个真实 Radar、real connection，无 Demo 混入；最终 users/radars/sources/runs/raw_items/documents/analyses=`1/1/1/1/1/1/1`，ownership 与 run/analysis ID 对齐。
- 结论 `NATIVE_FLOW31_SOURCE_COLLECTION_SIGNALS_PASS`：通过当前原生 Source create/bind、单次 collect queued 事实、guarded 离线生产处理、原生成功轮询、Signals list/detail 与 Canvas 返回。未声明 Worker/Beat/Broker dispatch、Router、embedding、Notification、真实 WS、pause→resume、完整错误/分页/ownership 矩阵或完整 FE-G2 验收；历史 edit/pause 未重跑。验证后按 PID `18128` exact path/start 与 PREP28 完整 ID/lease/owner 精确停止并删除原生进程、四容器和两网络；最终 owned 容器/网络/卷为空、PID 不存在、8000 无监听，临时账号与业务数据随 tmpfs 数据库删除且不可恢复，其他资源未触碰。无需为本停点重新创建账号。无源码修改、fullsuite、commit/push/PR/merge，不批准 G3、INT 或发布。

### FE-001-G2-PACKAGE-32 桌面离线打包停点（2026-10-20）

- 总控独立复核 GRID-MOTION30 的单行 CSS 增量与定向测试后，执行唯一桌面打包 `CARGO_NET_OFFLINE=true npm run build:desktop:debug -- -- --locked --offline` 成功：Vite 53 modules / 1.29s，Rust dev / 12.01s。新 standalone debug exe SHA-256 为 `BB2B948AF880F0DF4C0878CCBE47C4385F4DCEEBDD8EC042628251369B30280D`，包含 wire27 与 GRID-MOTION30 的 120s 经画像旋转；`api.rs` SHA-256 `81E0615701130A07C6DE589D1ADDB1D8B3115D926B6D65931F83FB76619065B9`，`original-intro.css` SHA-256 `FE116676D37642A24DB157DCF5C2E8720CC67A57BFED88499D95D29846B4EDFB`，最终 `git diff --check` 通过。
- 结论 `PACKAGE32_OFFLINE_DESKTOP_BUILD_PASS_NATIVE_VISUAL_NOT_RUN`。本次没有启动新 exe、重新认证或进行原生视觉复验；打包成功与既有浏览器动态证据不能写成 native 120s visual PASS。FLOW31 的真实 Source/collect/Signals 证据来自此前 wire-fixed、pre-motion 二进制并独立保留。无 backend/API/schema/lock/dependency/assets 改动，无 commit/push/PR/merge，不批准 G3、INT 或发布。
