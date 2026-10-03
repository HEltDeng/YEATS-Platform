# 页面、接口、实体及验收映射

API 前缀 `/v1`；表中 `{sid}` 必须由服务端校验当前账号的有效监护关系及经过验证的手机号。前端选中 ID 不构成权限。源码共20个家长原生路由；记录状态不是用户验收签字。

| 原型/页面 | 正式路由 pages/.../index | 操作与接口 | 实体/权限 | 当前实现及证据 |
|---|---|---|---|---|
| p-login 微信登录 | login | wx.login → POST auth/wechat；POST auth/phone | Account/WechatIdentity/Session/Guardian；手机号官方验证 | 真实微信会话成功；手机号待用户授权；01-real-wechat-session-phone-required.png |
| p-home 首页 | home | GET students/{sid}/home、content | 作业/测试/课时/当前学员通知 | 模拟器已运行；02-home-test-parent-a.png；最新徽标与时区改动待完整视觉复核 |
| p-switch 切换弹层 | 各业务页公共弹层 | GET students；重新请求所选学员接口 | Guardian/Enrollment | 实际从学员1切2，作业清单变化；03-student-switch.png、04-home-student-2.png |
| p-hours 课时总览 | hours | GET students/{sid}/hours | HourPackage/HourEntry | 数据库实时统计；hours.png |
| p-detail 消耗明细 | ledger | 同上，日期筛选 | 追加流水、课节关联 | ledger.png；更正/去重接口测试 |
| p-sign 签到 | attendance | GET students/{sid}/attendance；状态Tab | Attendance/Lesson | attendance.png；设备来源仍是受控数据 |
| p-schedule 班级课表 | schedule | GET students/{sid}/schedule；周切换/列表/老师详情 | Enrollment/TeacherClass/Lesson | schedule.png；修复原生编译错误及窄列时间显示 |
| p-test 随堂测试 | tests | GET students/{sid}/tests；入门/出门Tab；媒体预览 | TestResult/私有资源 | tests.png；图文/音频记录来自服务器 |
| p-hw 作业列表 | homework | GET students/{sid}/homework；状态Tab、进入详情 | HomeworkTarget/Submission | 已实现、构建通过；本轮尚缺该列表独立截图及逐入口复核 |
| p-hw 作业详情/上传 | homework-detail | GET详情、POST files、POST submissions | 文件归属、大小/格式、安全、幂等、目标行锁 | 原生选图上传/提交/重进成功；homework-uploaded/submitted.png |
| p-correct 批改 | feedback | GET作业详情及提交历史 | Feedback/图片批注文件/语音 | 退回→重交→批改；两次历史保留；homework-returned/resubmitted.png、feedback.png |
| p-makeup 缺课补看 | recordings | GET recordings、POST viewing-requests、文件播放票据、watch | Attendance/ViewingRequest/ViewingGrant | 页面申请→受控审核→真实本地视频播放；viewing-application-saved.png、recording-playing.png |
| p-kb 知识树 | knowledge | GET knowledge?q=；1–7层分类→第8层内容 | Category/KnowledgeReference/当前班级 | 模拟器展开8层/搜索无结果；knowledge-eight-levels.png、knowledge-empty-search.png |
| p-kb 内容及提问 | knowledge-detail | GET详情、POST questions、文件票据 | 仅当前班级内容；问答仅该提问家长可读 | 问题真实保存；knowledge-question-modal/saved.png；文件预览最终兼容待核验 |
| p-teacher 师资列表 | teachers | GET teachers | 已发布展示资料 | teachers.png；纯受控展示资料 |
| p-teacher 师资详情/约课 | teacher-detail | GET teachers；demo播放；GET content?kind=support | 公开示范课独立资源；受控二维码 | teacher-detail.png；真实二维码未配置，空状态保留 |
| p-notify 通知 | notifications | GET notifications、POST read单条/全部 | account_id与student_id双重过滤 | 6条未读→0，重进仍0；notifications-read.png |
| 原型“我的”入口补齐 | me | GET me/students；个人资料/设置/机构介绍 | 当前账号 | me.png |
| 个人资料 | profile | GET/PUT me | 仅当前账号，文字安全检查 | 实际修改测试称呼并读回；profile-saved.png |
| 设置/退出 | settings | POST auth/logout、me/subscriptions | 服务端撤销会话，订阅不阻塞基础业务 | settings.png；过期/撤销接口测试；真实账号退出再登录的模拟器复测未完成 |
| 机构/年级课程/服务/报名/协议 | content?kind=... | GET content 分类 | 已发布图文；媒体仍需权限票据 | introduction/courses实际运行；其他分类已有实现，内容为开发说明；content.png |

## 二级状态与弹层

| 元素 | 行为 | 证据/状态 |
|---|---|---|
| 学员弹层 | 展开、选中、关闭；详情切换返回 | 已实操切换；关闭/返回路径还需最终统一复核 |
| 客服浮层 | 拉取配置、显示二维码或明确未配置、关闭 | 实现；真实素材暂缺 |
| 图片选择器 | 原生选图、真实上传、预览、移除 | 原生选择/上传成功；修复返回后误刷新；生命周期回归测试 |
| 提问弹层 | 输入、取消、提交、显示服务器记录 | 已实操提交；不生成假成功 |
| 补看弹层 | 输入、提交、待审/通过/拒绝 | 提交/通过及播放实操；拒绝/到期接口验证 |
| 空状态 | 无学员/无业务/搜索无结果/未配置 | 搜索空状态有截图；其他状态代码/接口测试，尚需逐状态截图 |
| 网络/会话错误 | 真实失败、重试、401清理会话并回登录 | 代码已实现；401/权限/错误脱敏测试；图形停止后未完成全部错误页实操 |

## 后续端的原型清点（未开发 UI）

老师端：t-dash、t-kb、t-pick、t-class、t-stu、t-hwnew、t-correct、t-test、t-sign、t-qa。

平台端：a-dash、a-grade、a-class、a-teacher、a-stu、a-content、a-kb、a-course、a-stat、a-sys。

上述20屏已进入原型清点范围，正式路由与界面实现留待前一端验收后确定。本轮只保留独立工程入口说明，没有交付两个PC展示壳。

完整截图位于项目 `02_Deliverables-交付与验收/simulator`。截图取自实际微信开发者工具；原型截图不参与运行验收计数。

## 本轮老师端更新

上一节“老师UI未开发”是家长阶段历史状态。2026-10-03已新增独立YEATS-Teacher；本轮实现、实际操作证据、未通过项和权限对应见 [teacher-acceptance.md](teacher-acceptance.md)。平台管理网页仍按老师阶段验收后推进。
