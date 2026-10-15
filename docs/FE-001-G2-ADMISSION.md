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
