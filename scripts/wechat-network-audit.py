"""Redacted diagnostics using exactly the backend HTTPX transport defaults.
Never log request URLs, response bodies, tokens, AppID or AppSecret.
"""
from pathlib import Path
import os,sys,json,re,ipaddress,datetime,urllib.request,logging
from urllib.parse import urlsplit
import httpx
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'services/api'))
from yeats.config import settings
for name in ['httpx','httpcore']:logging.getLogger(name).disabled=True
def endpoint(value):
    try:
        p=urlsplit(value if '://' in value else 'http://'+value)
        return {'scheme':p.scheme,'host':p.hostname,'port':p.port,'credentials_present':bool(p.username or p.password)}
    except Exception:return {'configured':True}
report={'detected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'platform':sys.platform,'runtime':'Windows native CPython / HTTPX','proxy_resolution':'HTTPX trust_env=True; urllib.request.getproxies()','proxy_environment':{k:endpoint(v) for k,v in os.environ.items() if k.lower() in ['http_proxy','https_proxy','all_proxy']},'effective_proxies':{k:endpoint(v) for k,v in urllib.request.getproxies().items() if k!='no'},'credentials_loaded':bool(settings.wechat_appid and settings.wechat_secret),'checks':[]}
with httpx.Client(timeout=25) as client:
    for url in ['https://api.ipify.org','https://checkip.amazonaws.com']:
        check={'service':urlsplit(url).hostname}
        try:
            r=client.get(url);r.raise_for_status();address=ipaddress.ip_address(r.text.strip())
            check.update(ip=str(address),public=address.is_global)
        except Exception as e:check['error_type']=type(e).__name__
        report['checks'].append(check)
    if settings.wechat_appid and settings.wechat_secret:
        check={'service':'api.weixin.qq.com','api':'stable_token','force_refresh':False}
        try:
            r=client.post('https://api.weixin.qq.com/cgi-bin/stable_token',json={'grant_type':'client_credential','appid':settings.wechat_appid,'secret':settings.wechat_secret,'force_refresh':False});r.raise_for_status();d=r.json()
            check.update(errcode=d.get('errcode',0),token_received=bool(d.get('access_token')),expires_in=d.get('expires_in'))
            # Extract only explicitly labelled IP from WeChat's whitelist refusal.
            if d.get('errcode') in [40164,45035]:
                m=re.search(r'invalid ip\s+([0-9a-fA-F:.]+)',d.get('errmsg',''))
                if m:
                    address=ipaddress.ip_address(m.group(1));check.update(wechat_observed_ip=str(address),public=address.is_global)
            if d.get('access_token'):
                # Official diagnostic endpoint returns the caller IP as seen by WeChat.
                rr=client.post('https://api.weixin.qq.com/cgi-bin/callback/check',params={'access_token':d['access_token']},json={'action':'get','check_operator':'DEFAULT'})
                dd=rr.json();check['callback_check_errcode']=dd.get('errcode',0)
                try:
                    address=ipaddress.ip_address(dd.get('ip',''));check['wechat_observed_ip']=str(address)
                except ValueError:pass
        except Exception as e:check['error_type']=type(e).__name__
        report['checks'].append(check)
out=root/'runtime/wechat-network-audit.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
