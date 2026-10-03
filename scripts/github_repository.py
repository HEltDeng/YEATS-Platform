"""Use existing Git Credential Manager without printing/persisting credentials."""
import subprocess, os, urllib.request, urllib.error, json, sys
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GCM_INTERACTIVE':'never'}
r=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',capture_output=True,text=True,env=env)
if r.returncode: raise SystemExit('GitHub credential unavailable; no secret printed')
cred=dict(line.split('=',1) for line in r.stdout.splitlines() if '=' in line)
def api(path,method='GET',data=None):
    req=urllib.request.Request('https://api.github.com'+path, data=json.dumps(data).encode() if data else None, method=method,headers={'Authorization':'Bearer '+cred['password'],'Accept':'application/vnd.github+json','User-Agent':'YEATS-project-setup'})
    with urllib.request.urlopen(req,timeout=30) as res: return json.load(res)
user=api('/user')['login']
print('Authenticated account:',user)
if user!='HEltDeng': raise SystemExit('Account differs from connected GitHub; stopped')
try:
    repo=api('/repos/'+user+'/YEATS')
    print(json.dumps({k:repo[k] for k in ['full_name','private','html_url','description','size']},ensure_ascii=False))
    if '--create' in sys.argv: raise SystemExit('Existing repository: must inspect ownership before reuse')
except urllib.error.HTTPError as e:
    if e.code!=404: raise
    print('YEATS repository does not exist')
    if '--create' in sys.argv:
        repo=api('/user/repos','POST',{'name':'YEATS','private':True,'description':'YEATS｜叶芝英语定制小程序及三端管理系统','auto_init':False})
        print('Created private repository:',repo['html_url'])
        subprocess.run(['git','remote','add','origin',repo['clone_url']],check=True)
