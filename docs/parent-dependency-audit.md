# Parent 开发依赖审计分析（2026-10-03）

当前 npm audit：5 moderate、0 high、0 critical。这5项是同一根因沿 file-type → @jimp/core → @jimp/custom → jimp → miniprogram-automator 传播，不是5个独立漏洞。file-type 本地16.5.4；官方修复21.3.1。官方说明是畸形ASF子头size=0造成文件探测无限循环，属于可用性风险，不是凭据泄露证据。

上游原始说明：https://github.com/sindresorhus/file-type/security/advisories/GHSA-5v7r-6r5c-r473

实际调用已检：官方 miniprogram-automator/out/util.js 的 decodeQrCode 将 Base64 图像交给 Jimp.read；@jimp/core/dist/utils/image-bitmap.js 调用 require('file-type').fromBuffer。该链仅存在本地开发工具，独立验收/生产小程序包不包含 node_modules；FastAPI和老师网页不加载它。当前代码没有把家长作业文件送进这一Node解码链。影响主要是开发工具处理攻击者可控的伪装二维码图像时卡住；不能因未在生产包中就写“漏洞已修复”。

兼容性结论：npm元数据确认21.3.1为ES module，要求Node>=20；其公开方法改为fileTypeFromBuffer，现有Jimp期待fromBuffer。直接强制override版本不是可验证的兼容修复。升级Jimp主版本也涉及官方automator期望的默认导出/read接口。未使用 npm audit fix --force，未回退官方automator，未手改node_modules来制造审计通过。

后续可控方案：在独立工具分支验证新的Jimp/检测适配层，或按上游补丁回移ASF边界检查并用畸形输入在worker timeout下回归，再完整验证官方CLI连接/预览/二维码解码。前者是工具兼容迁移；后者须维护补丁且npm审计版本仍会报项。当前保留风险记录，不加载未知来源二维码/图像，不把开发工具暴露为公共上传服务。没有更改现用依赖或正在运行的微信工程。
