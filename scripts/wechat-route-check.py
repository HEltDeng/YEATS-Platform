"""Read only local Clash configuration and only YEATS WeChat connection metadata."""
from pathlib import Path
import os,re,json,sys,time,threading,logging
import httpx
for n in ['httpx','httpcore']:logging.getLogger(n).disabled=True
folder=Path(os.environ['APPDATA'])/'io.github.clash-verge-rev.clash-verge-rev'
controller=None;key=''
for name in ['clash-verge.yaml','config.yaml']:
    p=folder/name
    if not p.exists():continue
    t=p.read_text(encoding='utf-8')
    c=re.search(r'^external-controller:\s*[\'\"]?([^\s\'\"]+)',t,re.M)
    s=re.search(r'^secret:\s*(.*)$',t,re.M)
    if c:controller=c.group(1);key=s.group(1).strip().strip('\'\"') if s else '';break
if not controller or not controller.startswith(('127.0.0.1:','localhost:')):raise SystemExit('Loopback controller unavailable; route cannot be confirmed')
headers={'Authorization':'Bearer '+key} if key else {}
observed=[]
def poll():
    with httpx.Client(trust_env=False,timeout=3) as local:
        for i in range(16):
            try:
                data=local.get('http://'+controller+'/connections',headers=headers).json()
                for c in data.get('connections',[]):
                    m=c.get('metadata',{})
                    if m.get('host')=='api.weixin.qq.com':
                        item={'host':m.get('host'),'network':m.get('network'),'sourceIP':m.get('sourceIP'),'destinationIP':m.get('destinationIP'),'chains':c.get('chains'),'rule':c.get('rule'),'rulePayload':c.get('rulePayload')}
                        if item not in observed:observed.append(item)
            except Exception:pass
            time.sleep(.15)
th=threading.Thread(target=poll);th.start()
try:
    with httpx.Client(timeout=15) as client:
        # Keep the same WeChat destination connection observable, with no credential payload.
        for i in range(3):client.get('https://api.weixin.qq.com/');time.sleep(.15)
except Exception:pass
th.join()
result={'controller_read_only':True,'wechat_connections':observed}
out=Path(__file__).resolve().parents[1]/'runtime/wechat-route-audit.json'
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
