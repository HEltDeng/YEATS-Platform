# YEATS｜叶芝英语

独立正式工程的家长端开发分支。微信原生 TypeScript/WXML/WXSS + FastAPI + PostgreSQL 17；老师和平台管理 PC 界面尚未进入开发阶段。当前提供本地联调版本，不能视为生产上线或用户验收通过。

## 唯一入口

`D:\Codex\02_MiniProgram-小程序开发\002_YEATS-叶芝英语小程序\01_Source-当前源码`

微信开发者工具项目：`YEATS-叶芝英语`；导入 `apps/parent-miniprogram`；启动页 `pages/login/index`；小程序根 `./`，TypeScript 原位编译为生成的 JavaScript，生成文件不进 Git。不得导入其他项目或使用其他项目 AppID。

## 本机运行

当前电脑已配置独立本地 PostgreSQL 数据目录和仓库外凭据。首次恢复本次开发环境可在源码根运行：

```powershell
./scripts/start-local.ps1 -WithTestIdentities
```

该脚本启动现有 PostgreSQL、应用迁移、注入本地 AppID、编译家长端并前台启动 API。已运行时会拒绝占用端口，不会杀掉未知服务。测试身份参数只供本地验收；不传参数则禁用开发身份 API。关闭终端会结束 API，不会删除数据库。PostgreSQL 可使用项目自带 `pg_ctl` 对本项目数据目录正常停止。

后端 `http://127.0.0.1:8930`；健康检查 `/health` 应显示 `postgresql`。本地地址只适用于这台电脑的模拟器，不是手机或线上入口。原 SQLite 已原样保留在忽略的 runtime 中，当前 API 使用 PostgreSQL。

```powershell
npm.cmd ci
npm.cmd run build:parent
npm.cmd run test:parent
.venv/Scripts/python scripts/test-postgres.py
.venv/Scripts/python scripts/check-postgres-concurrency.py
.venv/Scripts/python scripts/check-wechat-secrets.py
```

Python 运行依赖锁定在 `services/api/requirements.lock`。`imageio-ffmpeg==0.6.0` 仅用于受控视频测试素材生成，非服务运行依赖。文档测试素材通过本机 Codex 随附文档运行库生成。

## 数据和账号

真实微信登录调用微信 code2Session，并建立 YEATS 随机会话。不会降级为测试登录。手机号须通过微信授权验证，匹配机构预登记的监护关系；没有绑定时显示受控空状态，不会开放其他学员数据。

本地数据库中的业务资料为带“测试”标记的受控数据。真实开发者微信登录身份和会话也存放在本地私有数据库，不能把整个数据库当成可上传的测试样例。Token 只存哈希；不存 session_key。测试家长 A 有学员 1/2，测试家长 B 只有学员 3，另有未关联家长。不会复制客户或其他项目真实业务资料。

## 凭据与配置

`%LOCALAPPDATA%\YEATS\secrets\wechat.dev.env`：AppID/AppSecret，仅后端读取。

同一私密目录中 `database.dev.env` 为独立本地数据库连接；`postgres-admin.dev.env` 为本地集群维护配置。当前用户/SYSTEM 限制访问。不得打印、提交或打包这些文件。

`project.config.template.json` 保留占位 AppID；真实 AppID 注入忽略的 `project.config.json`。AppSecret 不进入任何前端文件。`services/api/.env.example` 是无秘密模板。验收和生产应显式指定环境；缺少 PostgreSQL/HTTPS/正式微信配置及规则确认时，启动检查失败，不退回测试环境。

## 验收资料

- `docs/parent-acceptance.md`：当前操作结果、截图索引和限制。
- `docs/page-function-map.md`：页面、接口、实体与权限对应。
- `docs/business-flows.md`：跨端创建/处理/查看和状态变化。
- `docs/external-configurations.md`：配置负责人、缺口、影响与验证办法。
- `packages/api-contracts/openapi.json`：当前接口契约。

原始文件保存在项目上一级 `00_Reference-需求与原型`，哈希见 `docs/reference-manifest.json`，未改写原件。模拟器截图位于上一级 `02_Deliverables-交付与验收/simulator`。Demo 截图不是小程序运行证据。

## 备份与后续部署

显式执行 `scripts/backup-local.py` 可在忽略的 runtime/backups 创建本地数据库和私有文件备份，不包含凭据。恢复时必须选独立空数据库，先验证备份、迁移版本和文件清单，再使用项目版本匹配的 pg_restore；禁止覆盖运行中数据库。源码回退使用已记录提交，数据库采用经验证的恢复点或前向修复，不盲目执行破坏性降级。

本轮未部署腾讯云或客户服务器；未上传微信开发版本、体验版、审核或发布。正式恢复演练、客户云适配及生产域名/文件/消息/隐私配置留待对应阶段实际执行，不能把本地运行称为线上交付。
