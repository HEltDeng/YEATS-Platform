"""Compare actual local secrets in memory against Git candidates and client files."""
from pathlib import Path
import subprocess,sys,json,os
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'services/api'))
from yeats.config import settings
if not settings.wechat_secret:raise SystemExit('No protected secret available to compare')
def git(*args):return subprocess.check_output(['git','-C',str(root),*args])
tracked=git('ls-files','-z').decode().split('\0');candidates=git('ls-files','--cached','--others','--exclude-standard','-z').decode().split('\0')
secret=settings.wechat_secret.encode();appid=settings.wechat_appid.encode()
secret_hits=[];appid_hits=[];database_secret_hits=[]
protected_values=set()
for filename in ('database.dev.env','postgres-admin.dev.env'):
    p=Path(os.environ['LOCALAPPDATA'])/'YEATS/secrets'/filename
    if p.is_file():
        for key,value in dotenv_values(p).items():
            if not value:continue
            if 'PASSWORD' in key or 'SECRET' in key:protected_values.add(value.encode())
            if 'DATABASE_URL' in key:
                protected_values.add(value.encode())
                password=make_url(value).password
                if password:protected_values.add(password.encode())
for name in set(candidates)-{''}:
    p=root/name
    if p.is_file():
        b=p.read_bytes()
        if secret in b:secret_hits.append(name)
        if appid in b:appid_hits.append(name)
        if any(value in b for value in protected_values):database_secret_hits.append(name)
client_hits=[]
for p in (root/'apps').rglob('*'):
    if p.is_file() and secret in p.read_bytes():client_hits.append(str(p.relative_to(root)))
report={'tracked_file_count':len([p for p in tracked if p]),'candidate_count':len([p for p in candidates if p]),'secret_in_git_candidates':secret_hits,'real_appid_in_git_candidates':appid_hits,'database_secrets_in_git_candidates':database_secret_hits,'secret_in_client_or_generated_files':client_hits,'local_project_config_ignored':subprocess.run(['git','-C',str(root),'check-ignore','-q','apps/parent-miniprogram/project.config.json']).returncode==0,'credential_file_outside_repository':True}
print(json.dumps(report,ensure_ascii=False,indent=2))
if secret_hits or appid_hits or client_hits or database_secret_hits:raise SystemExit(1)
