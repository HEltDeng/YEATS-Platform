# 家长开发工具依赖兼容修复 · 2026-10-03

历史审计中5个中度节点来自同一 file-type 16.5.4 / Jimp 链。官方 miniprogram-automator 0.12.1 的远程调试二维码解码实际调用 Jimp.read，再调用 file-type.fromBuffer；直接换成 ESM 新版会破坏旧接口，因此没有使用强制升级或忽略审计。

本次保留 Jimp 0.22.12，项目内 tools/file-type-buffer-compat 用9行 CommonJS 适配器异步加载 file-type 21.3.4，保留 fromBuffer 接口。npm overrides 使用显式本地依赖引用，锁文件已通过 npm ci --ignore-scripts 干净安装。适配层仅开发工具使用，不进入微信验收/生产包。

验证：11项家长测试通过，其中官方自动化工具对合成二维码的真实解码、PNG/JPEG读取，以及恶意零长度ASF头在独立worker超时保护下正常结束。兼容实验工程安装/审计0漏洞。实际家长仓库在线audit在08:39 UTC两次遇到官方registry TLS连接中断；08:44后的最终重试成功：100个依赖、0个漏洞。保留失败事实，不将网络失败当成通过。

依据：上游安全公告 https://github.com/sindresorhus/file-type/security/advisories/GHSA-5v7r-6r5c-r473 及 npm 官方 overrides 文档 https://docs.npmjs.com/cli/v11/configuring-npm/package-json/#overrides 。21.3.1的试验版本仍有另一ZIP条目，最终使用21.3.4。没有关闭证书校验、修改全局npm配置或网络设置。
