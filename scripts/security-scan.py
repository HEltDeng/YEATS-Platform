"""Compare actual protected values in memory; output paths/counts only, never values."""
from pathlib import Path
import subprocess,os,sys,json,re
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
root=Path(__file__).resolve().parents[1];secret_dir=Path(os.environ['LOCALAPPDATA'])/'YEATS/secrets'
secrets=set();appid=None
for name in ['wechat.dev.env','database.dev.env','postgres-admin.dev.env']:
    for key,value in dotenv_values(secret_dir/name).items():
        if not value:continue
        if 'APPID' in key:appid=value.encode()
        if any(k in key for k in ['PASSWORD','SECRET']):secrets.add(value.encode())
        if 'DATABASE_URL' in key:
            secrets.add(value.encode());password=make_url(value).password
            if password:secrets.add(password.encode())
staff=secret_dir/'teacher-acceptance.json'
if staff.exists():secrets.add(json.loads(staff.read_text(encoding='utf-8'))['password'].encode())
repos=[root,root.parent/'YEATS-Parent',root.parent/'YEATS-Teacher'];hits=[];report=[]
for repo in repos:
    candidates=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=repo).decode().split('\0')
    count=0
    for rel in set(candidates)-{''}:
        p=repo/rel
        if not p.is_file():continue
        count+=1;data=p.read_bytes()
        if any(v in data for v in secrets) or (appid and appid in data):hits.append(repo.name+'/'+rel)
        if p.suffix.lower() in ['.pem','.key','.jks','.db','.sqlite'] or any(x in p.parts for x in ['runtime','node_modules','.venv']):hits.append(repo.name+'/'+rel+' forbidden artifact')
    # Check all committed history blobs as well as current candidates.
    objects=subprocess.check_output(['git','rev-list','--objects','--all'],cwd=repo).decode().splitlines()
    checked=0
    for line in objects:
        oid=line.split(' ',1)[0]
        if subprocess.check_output(['git','cat-file','-t',oid],cwd=repo).strip()!=b'blob':continue
        data=subprocess.check_output(['git','cat-file','blob',oid],cwd=repo);checked+=1
        if any(v in data for v in secrets) or (appid and appid in data):hits.append(repo.name+'/history/'+oid)
    # Generated first-party frontend artifacts, including acceptance bundles, exclude dependencies.
    targets=[repo/'dist']
    if repo.name=='YEATS-Parent':targets += [repo/'services',repo/'pages',repo/'components',repo/'config.js',repo/'app.js']
    for target in targets:
        for p in ([target] if target.is_file() else target.rglob('*') if target.exists() else []):
            if p.is_file() and any(v in p.read_bytes() for v in secrets):hits.append(str(p.relative_to(repo)))
    report.append({'repository':repo.name,'candidate_files':count,'history_blobs':checked})
print(json.dumps({'repositories':report,'secret_or_private_file_hits':hits,'result':'PASS' if not hits else 'FAIL'},ensure_ascii=False,indent=2))
if hits:raise SystemExit(1)
