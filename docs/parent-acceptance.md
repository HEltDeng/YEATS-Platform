# 家长端本地运行与验收记录

记录日期：2026-10-03（Asia/Singapore）。阶段：phase 1 本地开发候选，尚未经用户整端验收；不进入老师/平台 PC 界面开发。本记录关联其所在 Git 提交，不把后续修改冒充当前截图基线。

## 实际运行环境

- 独立微信项目：YEATS-叶芝英语；导入 apps/parent-miniprogram，projectname/miniprogramRoot 已核对；真实 AppID 由仓库外保护文件注入。
- 原生 TypeScript/WXML/WXSS，20条页面路由；启动页 pages/login/index。不是 HTML web-view。
- Windows 本机 API：127.0.0.1:8930；PostgreSQL：127.0.0.1:55432，独立 yeats_development / yeats_test。私有文件在 runtime/private-files。
- 原 SQLite 数据经行数校验迁入原本为空的独立 PostgreSQL，旧文件未删除。当前迁移版本 20261003_grading_deadline。
- 仅有本机模拟器验收入口；手机真机、验收服务器、客户生产环境未验证。本轮未部署或上传微信版本。

## 已实际运行的业务

| 流程 | 结果 | 边界 |
|---|---|---|
| wx.login → 后端 code2Session → YEATS 随机会话 → GET me/students | PASS：真实微信身份成功，受保护接口200，无学员返回空列表 | 尚未获用户手机号授权；不等于完整绑定验收；没有使用测试身份冒充微信登录 |
| 家长A切换学员1/2 | PASS：姓名、作业和课时随接口切换 | 受控测试资料，不是机构真实学生 |
| 原生选图 → 上传 → 文字/图片作业提交 → 重进 | PASS：服务器保存，原提交图片可恢复查询 | 真实文件、本地私有存储；云文件服务未联调 |
| 老师受控脚本退回 → 原生重交 → 脚本批改 → 家长查看 | PASS：两次提交和反馈保留 | 第2次为文字重交；第1次图片保留在历史。教师脚本不等于老师端完成 |
| 知识树/搜索/详情/提问 | PASS：7级分类加第8层内容，空搜索截图；问题持久化 | 老师答复的实际 PC 操作留待阶段2 |
| 缺课补看申请 → 受控审核 → 原生播放 | PASS：待审记录保存，明确有效期；5秒测试MP4播放至1秒以上 | 本地真实文件，不是腾讯会议或云视频平台联调 |
| 通知全部已读 → 重新进入 | PASS：6条未读变0且保持 | 站内通知；微信订阅消息真实发送未联调 |
| 个人资料修改 | PASS：测试称呼服务器读回一致 | 测试身份跳过真实微信内容安全调用；真实账号内容安全还需验证 |
| API重启后重新查询 | PASS：提交版本[2,1]、状态[graded,returned]、附件数[0,1]、反馈2、提问2、未读0、保存称呼一致 | 持久化复核，不依赖页面内存 |

## 本轮修复和实现

修复课表 wx:else 与循环组合导致整个小程序 WXML 编译失败；修复原生选图器返回触发 onShow 重载、刚上传图片从页面消失的问题；统一服务端 UTC 输出与小程序中国标准时间展示；补充真实图片缩略图和文档类型识别、首页通知徽标、会话失效返回登录；补充分开的学生提交截止时间与老师批改截止时间、私有存储适配接口及订阅消息独立失败处理。

## 自动测试

- npm run build:parent：PASS。
- npm run test:parent：2 passed（日期跨天与原生选图生命周期）。
- scripts/test-postgres.py：19 passed，2 warnings（TestClient httpx 弃用提示、ORM模型 TestResult 被 pytest 发现但不收集），0 failures。
- scripts/check-postgres-concurrency.py：两个并发数据库事务使用相同幂等键，仅生成1条提交并返回相同资源ID。
- 权限覆盖：不同监护人直接改学员/资源 ID、无登录、会话撤销与过期、文件权限及下架撤权、班级引用、手机号冲突、视频播放与下载目的区分。
- 数据覆盖：作业幂等与退回重交、签到事件去重和追加课时更正、文件格式伪造、有效期、提交/批改超时独立、订阅失败不丢站内业务。
- 本机 HTTP 验证：另一家长真实存在的 student-3 返回404；退出后及无会话访问均401。404用于隐藏他人学员是否存在。

自动测试使用专用 yeats_test，外部微信返回使用可控测试替身，不能替代真实微信端到端证据。真实登录证据另见 real-login-results.json；其中早期 crossStudentStatus 使用了不存在的测试 ID，不作为跨家长越权证据。

## 实际截图

截图在项目上级 `02_Deliverables-交付与验收/simulator`；全部来自微信开发者工具实际运行。原型只用于视觉对照。部分截图早于最终时间格式/缩略图调整，最终全面视觉复核尚未完成。

| 证据 | 内容 |
|---|---|
| 01-real-wechat-session-phone-required.png | 真实微信会话后等待用户手机号授权 |
| 02-home-test-parent-a.png、03-student-switch.png、04-home-student-2.png | 首页及学员切换 |
| hours.png、ledger.png、attendance.png、schedule.png、tests.png | 学情各业务页 |
| homework-uploaded.png、homework-submitted.png | 原生上传和提交 |
| homework-returned.png、homework-resubmitted.png、feedback.png | 退回、重交和批改 |
| knowledge-eight-levels.png、knowledge-empty-search.png | 分类和空搜索 |
| knowledge-question-modal.png、knowledge-question-saved.png | 提问输入和保存 |
| viewing-application-modal.png、viewing-application-saved.png、recording-playing.png | 申请和实际视频播放 |
| notifications-read.png、profile-saved.png | 已读及资料保存 |
| teachers.png、teacher-detail.png、me.png、settings.png、content.png | 师资、我的、设置、介绍 |
| persistence-after-restart.json | API重启后持久化与权限复核 |

## 未通过/未完成的门槛

1. 手机号授权需要用户亲自完成。没有授权结果前，真实监护关系绑定和实名账号业务闭环仍未验收；现有业务验收使用明确标识的测试账号。
2. Computer Use 在原生小程序调用 PDF 查看器后，无法可靠判定系统 Edge 当前 URL，触发本轮安全停止。没有继续图形操作或绕过。PDF已下载并调起查看器，但最终渲染未验收；Office/PDF移动端兼容也未验收。
3. 作业列表独立截图、真实账号退出再登录、全部返回路径/网络错误/空状态/弹层逐控件视觉复核尚未完成。不能仅凭20条页面存在就判定全端通过。
4. 最新缩略图、徽标、时间显示等修改已编译及相关逻辑测试，尚缺一轮覆盖所有页面的最终截图对照。尚未达到逐像素还原或用户整端验收通过。
5. 正式客服二维码、客户协议/隐私文案、订阅模板、海康型号及协议、正式存储/视频/文档服务、生产资源及正式业务规则确认未就绪。具体影响见 external-configurations.md；这些项目均未用模拟结果填成成功。
6. 数据库备份/恢复脚本与说明已提供，但未执行正式恢复演练。生产配置校验、部署升级及回滚须在获准资源上实际验证。
7. 老师/平台管理PC端未开发；批改、补看审批等本轮仅以真实业务函数和受控脚本建立前置数据，跨端人工闭环尚未验收。

## 用户开始验收

当前API已运行时无需重复启动。若已退出，在源码根运行 `./scripts/start-local.ps1 -WithTestIdentities`，再打开微信开发者工具中的 YEATS-叶芝英语项目，点击编译，从 pages/login/index 开始。

真实微信流程选择“微信授权登录”，手机号需用户自己操作。测试业务流程选择标识清楚的“测试家长 A”；测试家长 B 和未关联家长用于权限/空状态。测试作业1已有两次提交及批改，勿当作全新作业；新增验收数据需使用受控脚本，不能重置当前数据库。

此版本只请求对本地成果进行检查，尚不申请进入老师端、服务器部署、微信上传、审核或发布。
