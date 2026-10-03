"""Initialize project-local PostgreSQL on loopback; no Windows service changes."""
from pathlib import Path
import os,secrets,subprocess,sys
from urllib.parse import quote
import psycopg
from psycopg import sql
root=Path(__file__).resolve().parents[1]
bin=root/'runtime/postgres-toolchain/pgsql/bin'
data=root/'runtime/postgres-data'
secret=Path(os.environ['LOCALAPPDATA'])/'YEATS/secrets'
secret.mkdir(parents=True,exist_ok=True)
config=secret/'database.dev.env'
if data.exists() or config.exists():raise SystemExit('Existing PostgreSQL data/config found; refusing to overwrite')
admin=secrets.token_urlsafe(32);password=secrets.token_urlsafe(32)
pwfile=secret/'postgres-init-password.tmp';pwfile.write_text(admin,encoding='utf-8')
try:
 subprocess.run([str(bin/'initdb.exe'),'-D',str(data),'-U','yeats_local_admin','--pwfile='+str(pwfile),'--auth=scram-sha-256','--encoding=UTF8','--locale=C'],check=True,capture_output=True)
finally:pwfile.unlink(missing_ok=True)
(secret/'postgres-admin.dev.env').write_text('PGHOST=127.0.0.1\nPGPORT=55432\nPGUSER=yeats_local_admin\nPGPASSWORD='+admin+'\n',encoding='utf-8')
subprocess.run([str(bin/'pg_ctl.exe'),'-D',str(data),'-l',str(root/'runtime/postgres.log'),'-o','-h 127.0.0.1 -p 55432','-w','start'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
with psycopg.connect(host='127.0.0.1',port=55432,user='yeats_local_admin',password=admin,dbname='postgres',autocommit=True) as db:
 db.execute(sql.SQL('CREATE ROLE yeats LOGIN PASSWORD {}').format(sql.Literal(password)))
 for name in ['yeats_development','yeats_test']:db.execute(sql.SQL('CREATE DATABASE {} OWNER yeats').format(sql.Identifier(name)))
config.write_text('YEATS_DATABASE_URL=postgresql+psycopg://yeats:'+quote(password)+'@127.0.0.1:55432/yeats_development\n',encoding='utf-8')
(secret/'postgres-admin.dev.env').write_text('PGHOST=127.0.0.1\nPGPORT=55432\nPGUSER=yeats_local_admin\nPGPASSWORD='+admin+'\n',encoding='utf-8')
print('Project-local PostgreSQL ready on 127.0.0.1:55432; development and test databases isolated. Credentials not printed.')
