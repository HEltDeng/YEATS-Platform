# YEATS-Platform｜叶芝英语

唯一共用 FastAPI/PostgreSQL 后端在 `services/api`，平台管理网页入口在 `apps/admin-web`（下一阶段，未开发完成）。原 YEATS 仓库原地改名，历史保留；老师阶段验收后继续平台端。

## 三仓唯一入口

- 本目录 `01_Source-当前源码`：YEATS-Platform（https://github.com/HEltDeng/YEATS-Platform）
- 相邻 `../YEATS-Parent`：微信家长／学员端（https://github.com/HEltDeng/YEATS-Parent）
- 相邻 `../YEATS-Teacher`：老师 React PC（https://github.com/HEltDeng/YEATS-Teacher）

微信开发者工具仅导入 `../YEATS-Parent` 根目录，旧 apps/parent-miniprogram 已归档，不能再导入旧目录。三个 Git 仓库互不嵌套；仅一套后端和数据库。

## 本机启动与恢复

在本仓库 PowerShell 运行：

```powershell
./scripts/local.ps1 start -WithTestIdentities
./scripts/local.ps1 status
./scripts/local.ps1 restart -WithTestIdentities
./scripts/local.ps1 stop
```

启动幂等；核对端口进程、PostgreSQL 数据目录和应用查询后才报告就绪。未知端口进程拒绝操作。不传 WithTestIdentities 时禁止开发登录；若服务已经运行则保留当前模式，切换模式请明确 restart。服务以当前用户后台进程运行，不安装系统服务、不设开机启动；电脑重启后手动 start。

家长端编译并启动后端：`./scripts/start-local.ps1 -WithTestIdentities`。老师需先在其独立仓库 `npm.cmd ci`、`npm.cmd run build`，再 restart 本后端加载 `/teacher/`。开发时可在老师仓库单独 `npm.cmd run dev` 使用8931。

API： http://127.0.0.1:8930/health ；老师： http://127.0.0.1:8930/teacher/ 。仅本机地址，不是云部署或手机真机入口。

## 数据与秘密

原 `runtime/postgres-data`、`runtime/private-files` 原地保留。不会重新初始化、清空或搬动数据库。全部 runtime 被 Git 忽略。原 SQLite 文件仅历史保留，服务配置已禁止静默回退。

凭据目录：`%LOCALAPPDATA%/YEATS/secrets/`，其中 wechat.dev.env、database.dev.env、postgres-admin.dev.env 均只在本机读取。老师测试账号在同目录 `teacher-acceptance.json`，用本机文本查看器读取；不要粘贴聊天、截图、Git。账号仅为受控测试老师，不是真实机构身份。

日志：runtime/api.stdout.log、runtime/api.stderr.log、runtime/postgres.log；不打印密码/Token，日志保留本机不提交。开发图文含明确“测试”标记，数据库也含真实微信会话关联，整个数据库仍视为私有，不能上传。

## 验证与文档

```powershell
.venv/Scripts/python.exe scripts/test-postgres.py
.venv/Scripts/python.exe scripts/security-scan.py
```

Python依赖见 services/api/requirements.lock；新机器使用独立虚拟环境安装，不复制其他项目环境。数据库必须显式配置独立 PostgreSQL 后再执行 `alembic upgrade head`，本机已有数据库不运行 seed/init。

当前验收结果见 docs/teacher-acceptance.md；迁移来源见 docs/repository-migration.md；原需求与原型只读位于 ../00_Reference-需求与原型。docs/parent-acceptance.md 是上一阶段历史记录，本轮状态以 teacher-acceptance.md 为准。

`scripts/backup-local.py` 是显式本机备份工具，备份不进 Git；完整恢复演练尚未验收。不因源码回退随意回退数据库。

开发自测候选，待用户阶段验收。推送源码不等于云部署、微信上传、审核或正式发布获准。
