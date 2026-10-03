# YEATS 微信配置接入与 AppSecret IP 白名单核查

核查时间：2026-10-03，Asia/Singapore。范围仅本地配置、必要官方接口、出口核查；未部署、上传、提交审核或发布。

## 配置与保护

- 从实际桌面唯一明确标注 YEATS 的 AppSecret 文本导入；未读取 VaSports 凭据，未改动或删除桌面原件。
- 后端私密配置：`%LOCALAPPDATA%\YEATS\secrets\wechat.dev.env`。仅当前用户与 SYSTEM 访问，父目录关闭 ACL 继承。
- AppID 注入本地 `apps/parent-miniprogram/project.config.json`，该文件忽略；仓库候选仅保留 `project.config.template.json` 的占位配置。
- AppSecret 仅后端加载。传输日志 httpx/httpcore 禁用，异常不输出原始请求地址及微信响应。
- 当前仓库无提交、无已跟踪文件；146 个待提交候选按真实密钥值扫描均未命中，真实 AppID 也未出现在候选中。前端源码和已生成 JS 文件未命中 AppSecret。
- 此次未创建源码交付压缩包，未向 GitHub 或服务器传送私密配置。以后打包仍须运行检查，不把本次结果视为永久保证。

## 实测

| 项目 | 结果 | 边界 |
|---|---|---|
| 真实 stable_token | PASS，errcode=0 | 使用 force_refresh=false，Token 仅内存使用，不保存、不输出 |
| 运行服务内凭据校验 | PASS | 重启 YEATS 自身进程后再次验证，未重启其他业务 |
| API 健康 | HTTP 200 | Windows 本机 127.0.0.1:8930，开发环境仍为 SQLite，不代表 PostgreSQL 阶段完成 |
| TS 编译 | PASS | 不代表真机或真实微信登录验收 |
| 后端回归 | 15 passed | 本地测试含两项日志/异常脱敏验证；两条既有测试依赖警告 |
| 微信实际源 IP | 未确认 | 网络诊断接口返回 40202，未提供源 IP；不据此推断账号能力原因 |
| wx.login → code2Session → 本项目会话 | 未验收 | 需要真实登录 code，不能用 Token 成功替代 |
| 手机号/内容安全/订阅发送 | 未联调 | Token 可用不等于各能力权限、模板及授权通过 |

## 网络路径与结论

运行于 Windows 原生 CPython + HTTPX，不在 WSL、Docker 或腾讯云。HTTPX 默认 trust_env=True；当前未配置 HTTP_PROXY/HTTPS_PROXY/ALL_PROXY 环境变量，但 Windows 系统代理被解析为 127.0.0.1:7897，监听进程为 verge-mihomo。

两个公网地址查询服务通过相同 HTTPX 设置返回一致结果，完整脱敏取证位于忽略目录 `runtime/wechat-network-audit.json`。该结果仅证明两个查询域名的出口。Clash 可能按域名分流，未获得 api.weixin.qq.com 对应的具体代理链。只读访问本机管理接口失败；没有修改代理、虚拟网卡、路由或全局网络设置。

**暂缓开启 AppSecret IP 白名单；当前没有可直接复制的已核实微信出口 IP 清单。** 不填写查 IP 服务的代理出口，也不填写微信目标地址、回环、局域网、候选腾讯云地址或全网网段。本次成功获取 Token 仅说明此调用当前可通过，不能反推公众平台开关状态或固定出口。

待本地微信调用链路有可重复核实且可保持的公网出口，或客户后端部署环境稳定后，重新核实实际调用进程及出口，每个独立 IP 一行填入 AppSecret 对应白名单，并复测 Token、真实登录和相关能力。网络、代理节点或域名规则变更后须重新验证，不将一次检测作为固定 IP 承诺。若开关已开启且当前调用成功，保留现状，不建议先关闭。

## 功能影响与官方依据

- stable_token 直接使用 AppID/AppSecret；官方错误码包含 40164，白名单拒绝会妨碍凭据获取。此次使用普通模式，未强制刷新。
- code2Session 也使用 AppSecret；wx.login 本身在客户端获取 code，后续校验才由本后端发起。开关启用后的实际约束应通过真实 code 流程验证，不因为某接口错误表未列出白名单码就认定豁免。
- 手机号、内容安全、订阅消息使用 access_token；凭据不能取得或更新会影响后续业务。站内数据、编译及隔离测试无需调用 AppSecret 接口。
- 代码上传使用独立上传私钥及对应配置，本次未创建该私钥，也未配置上传白名单。AppSecret 不能替代上传私钥。

官方文档已通过本地 HTTP 客户端读取（原旧文档地址会显示迁移后的目录）：

- https://developers.weixin.qq.com/miniprogram/dev/server/API/mp-access-token/api_getstableaccesstoken.html
- https://developers.weixin.qq.com/miniprogram/dev/server/API/user-login/api_code2session.html
- https://developers.weixin.qq.com/miniprogram/dev/devtools/ci.html
- https://developers.weixin.qq.com/miniprogram/dev/framework/security.html

## 可复现检查

从唯一源码根目录运行 `.venv\Scripts\python scripts\configure-wechat-local.py` 注入 AppID；运行 `.venv\Scripts\python scripts\check-wechat-secrets.py` 扫描真实值；运行 `.venv\Scripts\python scripts\wechat-network-audit.py` 重新实测。脚本只输出允许的状态与网络元数据，不打印秘密值。网络核查报告含时间，仅保留本地，不进入源码归档。

后端启动可以使用 `.venv\Scripts\python scripts\run-api.py --verify-wechat`。该选项在同一进程内验证微信凭据后启动本地服务；失败时停止，不降级为测试微信身份。
