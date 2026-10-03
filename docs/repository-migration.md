# 三仓迁移记录

基线 `a5a7105ead1084a96d4ece9cbeba32a8d009dc88`；拆分前完整历史 bundle：`../03_Archive-历史归档/YEATS-before-teacher-20261003.bundle`。
家长端历史由 git subtree split 提取，旧微信导入目录已归档至同级 Archive，后续仅导入 `../YEATS-Parent`。
平台与共用后端保留本仓库完整历史，原 PostgreSQL `runtime/postgres-data`、上传 `runtime/private-files`、本机凭据路径均未移动。

唯一开发入口：家长 `../YEATS-Parent`；老师 `../YEATS-Teacher`；平台及唯一后端 `01_Source-当前源码`（本仓库）。三个独立仓库，互不嵌套。
老师阶段验收后再完成 `apps/admin-web`。不把旧阶段的说明或历史验收记录当作当前完成证明。
