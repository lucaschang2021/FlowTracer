# FE-001-G2 真实接口接入准入

更新时间：2026-10-15。控制纪元：`GOV-2.1`。

## 身份与状态

- 已合并 Backend 基线及 `origin/main`：`fc180a1d2eba32935fba6ee6c128f9b2d7015574`。
- 本地 Frontend 候选：`24e2ebd14ac559ae9251424f30a4295f3006e0a0`，父提交为上述 Backend 基线，tree 为 `e867861769f29d3a88c27b6dd45b9d2163fe95fd`；该候选未 push、未 merge。
- G1 骨架已独立验收。总控在 2026-10-13 对 `24e2...` 完成 source/scope、typecheck、13 unit、web build 与 13 UI E2E 检查；后续 G2 原生链路证据不回填为 G1 基线的独立原生复跑，浏览器测试也不能替代原生证据。
- 本文件冻结 G2 范围与安全边界。`FE-001-G2-AUTH-01` 仍是 branch-local 实现候选，已取得下述定向证据；这不等于 FE-G2/FE-001 产品验收，也不准入 INT-001 或 REL-001。

## 当前候选证据快照（2026-10-15；不提供执行许可）

- `AUTH-UI-REGISTER-11` 在隔离 `_test` 库取得原生 UI 注册→`users/me`→真实空 Radar 的请求和界面证据；`AUTH-API-SEED-09` 在另一隔离 `_test` 库取得原生登录、退出与进程重开后需重新登录的证据。两轮临时账号/无卷容器及专名网络均已清理。具体请求与停点见下方各轮记录，不将不同测试轮次冒充同一次完整操作。
- 后续视觉候选的 typecheck、Web build、15 unit、7 targeted UI E2E、Windows debug build 已通过；新版视觉尚无原生截图验收，浏览器 mock 不作 native 视觉证明。
- `AUTH-SESSION-FENCE-01` 对 `users/me` 会话代次写回 P1 作最小修复：旧响应写回时在同一锁内复核代次，不匹配即拒绝；开发侧 Rust `api::tests` 7/7 通过，总控独立源码复核关闭此路径。当前候选未发现未关闭 P0/P1 产品缺陷；旧 npm audit 提示冲突与来源未明本机 404 探测是两项历史 P2 待解释观察，不当作已证实产品缺陷或已消除风险。
- AUTH-01 仍未 commit/push/PR/merge；Radar CRUD、Source、collect、Signals 与 G3 未实现。FE-G2 产品验收、INT-001 和 REL-001 均未准入，下一操作须总控另签。

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
