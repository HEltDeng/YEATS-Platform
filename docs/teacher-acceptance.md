# 老师端与家长端联合验收候选 · 2026-10-03

状态：开发并自测，待用户阶段验收。家长端已有初步视觉认可；未新增“用户整端验收通过”记录，未打验收标签。平台管理网页按用户要求在老师阶段验收后继续，最终产品仍是三端。

## A：连接故障的结论与证据

接手路径为原 YEATS 源码目录；初始分支 codex/phase1-parent，HEAD d809e2ece00e4ff4f5aaf9a80dcc90d5e632e32c，工作区干净。旧执行记录有 task_complete，未发现并发写入。机器 HEltDeng，非另行复制的云端源码。

接手时8930和55432均无监听，也无Python/PostgreSQL服务进程；直连 http://127.0.0.1:8930/health 返回连接拒绝。config.ts 与生成 config.js 均为正确本地8930。已证实当前本地服务未运行，无法证明原进程由什么事件退出；原 start-local.ps1 使用前台API，存在终端结束即失去服务的问题。没有证据支持归因Clash，未改代理、TUN、路由、防火墙或证书校验，未重置AppSecret。

随后通过官方CLI打开真实微信模拟器复现同类断服场景，主页 GET /v1/me 与 GET /v1/students 均进入网络失败回调（无HTTP响应）。此为本轮受控复现捕获，不冒称保留了用户最初发生故障时的Network录屏。对应截图与脱敏记录：parent-request-diagnostic.*。恢复后主页真实数据加载、错误清空（parent-final-recovery.*）。拆分后真实 wx.login/code2Session 也取得会话，页面停在手机号授权步骤；real-login-login.json 只记录布尔状态，不含身份/Token。手机号能力与监护绑定仍未验收。

修复：scripts/local.ps1 提供start/status/stop/restart，后台当前用户进程、真实就绪检查、端口与进程归属校验、数据库路径及应用查询验证、幂等启动；不装系统服务或开机任务。验证命令结束后仍可访问；停止后拒绝连接、恢复后原数据保留；用专属临时监听进程模拟端口占用，启动明确拒绝且未杀该进程。

前端区分网络不可达、超时、401登录过期、403无权限、404不可见内容、5xx服务异常；刷新保留未提交作业文字与附件，重复点击由busy和后端幂等控制。脱敏开发诊断仅记录路径/状态，不记录请求体、密码或令牌。

## B：三个私有仓库与可恢复迁移

| 仓库 | 唯一本地目录（均在同一YEATS项目目录下） | 内容 |
|---|---|---|
| HEltDeng/YEATS-Parent | YEATS-Parent | 微信家长／学员端 |
| HEltDeng/YEATS-Teacher | YEATS-Teacher | React老师PC |
| HEltDeng/YEATS-Platform | 01_Source-当前源码 | apps/admin-web下一阶段；services/api唯一后端 |

三仓均Private，互不嵌套。旧YEATS平滑改名，仓库ID与历史保留；没有删除旧仓库重建、覆盖同名仓库或强推。家长以subtree提取历史，来源修复提交 a5a7105ead1084a96d4ece9cbeba32a8d009dc88。原始源码bundle位于 ../03_Archive-历史归档/YEATS-before-teacher-20261003.bundle；旧家长导入目录完整归档在同目录 parent-before-split-20261003。

原数据库 runtime/postgres-data 与私有文件 runtime/private-files 未搬动、未初始化或清空。凭据仍在 %LOCALAPPDATA%/YEATS/secrets。家长和老师各自安装依赖、生成锁文件并独立构建；无旧总仓node_modules依赖。微信只导入新YEATS-Parent根目录。

## C：老师端实际实现与验证

| 原型 | 网页实现 / 共用API | 验证 |
|---|---|---|
| t-dash | 工作台、待办、今日课节、登录/退出；/staff/dashboard /me /auth | Chrome真实密码登录及退出重登 |
| t-class / t-stu | 班级切换、学员详情、本班学情；/classes /lessons | 网页查看、1000px窄窗口无横向溢出 |
| t-hwnew | 多班/定向作业、文字图片音频组合、截止与批改提醒；/homework | 网页发布→家长看到 |
| t-correct | 提交/附件/重交历史、退回、文字/图片/音频批改；/submissions/.../grade | 文字闭环实际完成；老师查看家长历史图片通过；新图片整条闭环待人工选图 |
| t-test | 入门/出门测、图片音频文字、成绩修改/撤回；/tests | 网页图片上传、保存、修改、刷新读回；撤回接口测试 |
| t-sign | 课节看板、人工补签、原因和课时追加更正；/lessons/.../attendance | 网页补签留痕；真实海康未联调 |
| t-kb / t-pick | 共享知识分类/类型搜索、子树勾选、班级引用/移除、变更提示与申请 | 只读资源、引用/移除权限测试；老师不维护平台分类内容 |
| t-qa | 班级/知识筛选、时间排序、未回复筛选、图文音频答复；/questions | 家长提问→网页答复→家长读回→老师重登保留 |
| 在线课程 | 本班录屏、补看申请只读知会；/recordings | 网页查看；没有挪用平台审核权限 |

真实业务写入共享PostgreSQL，不使用SQLite替代，不直接改数据库制造跨端结果。脚本只初始化受控老师密码、执行测试和驱动真实页面控件；老师发布/退回/批改/答复证据来自Chrome DOM操作。家长由官方miniprogram-automator操作真实控件，无wx mock、无注入页面数据。Computer Use所需node_repl未向本执行器提供，因此没有通过Windows UI控制系统原生选图/手机号授权窗口。

29项PostgreSQL测试通过，含角色、班级、学员、私有文件越权、撤销授权后旧票据失效、幂等、测试撤回、签到审计、生产测试身份禁止、音频转换；家长5项回归通过；双连接并发提交仅保存1条。老师构建和真实浏览器冒烟通过。所有自动测试不等同用户验收。

浏览器录音入口已实现，上传后本地转换MP3；仅用合成WebM测试转换链路，未代用户批准麦克风权限，真实设备录制待验收。

## 访问与简明验收路径

在Platform运行 `./scripts/local.ps1 start -WithTestIdentities`，状态/重启/停止分别换status/restart/stop。需重建家长可用start-local.ps1；老师源码改后在Teacher运行npm.cmd run build，再重启后端。

老师： http://127.0.0.1:8930/teacher/ 。本机受保护账号文件 `%LOCALAPPDATA%/YEATS/secrets/teacher-acceptance.json`，自行在本机读取，勿发聊天或截图。家长：微信开发者工具导入YEATS-Parent，受控业务用“测试家长A”，真实登录用微信按钮；手机号本人授权单独验收。

已完成的测试文字作业ID：1c0b796c-f284-4392-bc66-3f52bd854926（测试跨端作业），两次提交，退回原因与最终A评价都可重看。老师作业管理查该条，家长作业列表查同标题。

新图片流程入口：测试图片上传联调（待家长操作），ID 79f39c93-aeb1-4f79-a1c5-cc9047f7f6e4。家长详情点＋，系统窗口选择无真实个人资料的测试图片，填写测试文字并提交；随后老师网页查看附件、退回/批注/批改。原生选图这一环未在本轮自动化完成，不把文字流程写成图片流程通过。

## 证据与未完成项

运行截图和JSON位于 ../02_Deliverables-交付与验收/teacher-phase2。重点：teacher-dashboard-final.png、teacher-graded-history-final.png、parent-graded-history.png、teacher-question-final.png、parent-question-replied.png、teacher-parent-image-preview.png、modules-ui-report.json、qa-ui-report.json。cross-ui-report.json保留了文字流程成功但原问答选择器提前执行失败的原始记录；问答由后续独立qa-ui-report.json完整通过，未覆写失败历史。

未完成/受阻：家长新图片完整跨端链路与图片批注提交验收；真实手机号能力/授权返回及监护绑定；真实麦克风录制；完整大字体/全部窄屏/视觉逐控件人工验收；Office在线转换预览及手机文档兼容；微信订阅模板和真实推送；海康实机；真实企微资料、云服务、生产规则与恢复演练。平台管理网页未开发完成，按用户约定等待老师阶段验收再继续，不取消三端目标。

当前依赖审计：Teacher无已知npm审计漏洞；Parent的官方自动化开发依赖已消除高危/严重项，仍有file-type/Jimp链条中度审计项（仅本地开发工具，非小程序包），不能用不兼容的强制升级冒充消除。未获取正式发布授权。

验收/生产构建输出独立dist目录，剔除测试登录UI/处理方法并扫描残留；后端同时拒绝测试身份和既有测试会话。仅以不可访问的 yeats-review.invalid 测试HTTPS域名验证打包，本地产物不是可发布版本。AppSecret、数据库/老师密码、Token不入Git；推送前扫描三仓候选、历史和第一方产物。

逐项范围以 [teacher-scope-matrix.md](teacher-scope-matrix.md) 为最新细分记录：核心闭环通过不等于全部Demo和老师功能完成。依赖风险详见 [parent-dependency-audit.md](parent-dependency-audit.md)。
