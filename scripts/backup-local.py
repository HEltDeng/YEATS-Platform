"""Explicitly invoked local backup; never automatically includes credentials."""
from pathlib import Path
import os,subprocess,datetime,json,zipfile
from sqlalchemy.engine import make_url
from dotenv import dotenv_values
root=Path(__file__).resolve().parents[1]
cfg=dotenv_values(Path(os.environ['LOCALAPPDATA'])/'YEATS/secrets/database.dev.env')
url=make_url(cfg['YEATS_DATABASE_URL'])
if url.host!='127.0.0.1' or url.database!='yeats_development':raise SystemExit('Only independent local YEATS database is allowed')
out=root/'runtime/backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S');out.mkdir(parents=True,exist_ok=False)
env=os.environ.copy();env.update(PGHOST=url.host,PGPORT=str(url.port),PGUSER=url.username,PGPASSWORD=url.password,PGDATABASE=url.database)
r=subprocess.run([str(root/'runtime/postgres-toolchain/pgsql/bin/pg_dump.exe'),'-Fc','--no-owner','-f',str(out/'database.dump')],env=env,capture_output=True)
if r.returncode:raise SystemExit('Database backup failed; private diagnostic output suppressed')
with zipfile.ZipFile(out/'private-files.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in (root/'runtime/private-files').rglob('*'):
        if p.is_file():z.write(p,p.relative_to(root/'runtime/private-files'))
(out/'manifest.json').write_text(json.dumps({'project':'YEATS','database':'yeats_development','includes_credentials':False,'contains_private_business_data':True,'restore_requires_independent_empty_target':True},indent=2),encoding='utf8')
print('Private backup written under YEATS runtime/backups. Never commit or include in ordinary deliverables.')
