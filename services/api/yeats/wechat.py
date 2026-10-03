"""Server-only WeChat integration. Fail closed; never synthesize an OpenID."""
import time, io, logging
import httpx
from fastapi import HTTPException
from PIL import Image
from .config import settings

# HTTPX INFO includes the complete URL; code2Session carries AppSecret in its
# query string. These transport loggers must never expose URLs or token queries.
for _logger in ('httpx', 'httpcore'):
    logging.getLogger(_logger).disabled = True

class Wechat:
    _token = ''
    _expires = 0
    def configured(self):
        if not settings.wechat_appid or not settings.wechat_secret:
            raise HTTPException(503, '微信服务尚未配置，请联系机构')
    def call(self, method, path, **kw):
        self.configured()
        try:
            with httpx.Client(timeout=15) as client:
                r=client.request(method,'https://api.weixin.qq.com'+path,**kw)
                r.raise_for_status()
                data=r.json()
        except (httpx.HTTPError, ValueError):
            raise HTTPException(502,'微信服务暂时不可用，请重试') from None
        if data.get('errcode',0):
            raise HTTPException(422,'微信授权失效或服务拒绝，请重新授权')
        return data
    def token(self):
        if time.time()>=self._expires:
            data=self.call('POST','/cgi-bin/stable_token',json={'grant_type':'client_credential','appid':settings.wechat_appid,'secret':settings.wechat_secret})
            self._token=data['access_token']; self._expires=time.time()+int(data['expires_in'])-300
        return self._token
    def identity(self, code):
        data=self.call('GET','/sns/jscode2session',params={'appid':settings.wechat_appid,'secret':settings.wechat_secret,'js_code':code,'grant_type':'authorization_code'})
        if not data.get('openid'): raise HTTPException(422,'微信身份验证失败')
        return data['openid']
    def phone(self, code):
        data=self.call('POST','/wxa/business/getuserphonenumber',params={'access_token':self.token()},json={'code':code})
        info=data.get('phone_info',{})
        if info.get('watermark',{}).get('appid')!=settings.wechat_appid:
            raise HTTPException(422,'手机号授权来源不匹配')
        if not info.get('purePhoneNumber'): raise HTTPException(422,'未获得手机号授权')
        return '+'+info['countryCode']+info['purePhoneNumber']
    def check_text(self, text, openid):
        if not text.strip(): return
        data=self.call('POST','/wxa/msg_sec_check',params={'access_token':self.token()},json={'version':2,'scene':2,'openid':openid,'content':text})
        if data.get('result',{}).get('suggest')!='pass': raise HTTPException(422,'内容未通过安全检查，请修改后重试')
    def check_image(self, data):
        # Existing synchronous image safety API; real account capability must be verified.
        with Image.open(io.BytesIO(data)) as img:
            img=img.convert('RGB'); img.thumbnail((750,750)); buf=io.BytesIO(); img.save(buf,'JPEG',quality=80)
        self.call('POST','/wxa/img_sec_check',params={'access_token':self.token()},files={'media':('check.jpg',buf.getvalue(),'image/jpeg')})

wechat=Wechat()
