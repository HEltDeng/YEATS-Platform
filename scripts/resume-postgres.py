"""Finish the interrupted YEATS-only local cluster setup without rebuilding data.
An offline single-user password recovery is permitted only for this exact local
cluster and only when its initial credential record was never written.
"""
from pathlib import Path
import os,secrets,subprocess,sys,socket
from urllib.parse import quote
import psycopg
from psycopg import sql
from dotenv import dotenv_values
root=Path(__file__).resolve().parents[1]
binary=root/'runtime/postgres-toolchain/pgsql/bin';data=root/'runtime/postgres-data'
secret=Path(os.environ['LOCALAPPDATA'])/'YEATS/secrets';adminfile=secret/'postgres-admin.dev.env';appfile=secret/'database.dev.env'
if not (data/'PG_VERSION').is_file():raise SystemExit('Existing local YEATS cluster required')
if not adminfile.exists():
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1',55432))==0:raise SystemExit('Cluster running without credential record; stop and investigate')
    # No SQL or passwords appear in process arguments or output.
    admin=secrets.token_urlsafe(40)
    command="ALTER ROLE yeats_local_admin PASSWORD '"+admin+"';\n"
    result=subprocess.run([str(binary/'postgres.exe'),'--single','-D',str(data),'postgres'],input=command.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode or b'ERROR:' in result.stderr or b'FATAL:' in result.stderr:raise SystemExit('Offline local role recovery failed; details withheld')
    adminfile.write_text('PGHOST=127.0.0.1\nPGPORT=55432\nPGUSER=yeats_local_admin\nPGPASSWORD='+admin+'\n',encoding='utf-8')
else:admin=dotenv_values(adminfile)['PGPASSWORD']
with socket.socket() as s:running=s.connect_ex(('127.0.0.1',55432))==0
if not running:
    # Do not PIPE child stdio: on Windows the long-lived server inherits handles.
    r=subprocess.run([str(binary/'pg_ctl.exe'),'-D',str(data),'-l',str(root/'runtime/postgres.log'),'-o','-h 127.0.0.1 -p 55432','-w','start'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
    if r.returncode:raise SystemExit('Local PostgreSQL did not start')
with psycopg.connect(host='127.0.0.1',port=55432,user='yeats_local_admin',password=admin,dbname='postgres',autocommit=True) as db:
    exists=db.execute("SELECT 1 FROM pg_roles WHERE rolname='yeats'").fetchone()
    if not exists:
        password=secrets.token_urlsafe(40)
        db.execute(sql.SQL('CREATE ROLE yeats LOGIN PASSWORD {}').format(sql.Literal(password)))
        appfile.write_text('YEATS_DATABASE_URL=postgresql+psycopg://yeats:'+quote(password)+'@127.0.0.1:55432/yeats_development\n',encoding='utf-8')
    elif not appfile.exists():raise SystemExit('Existing application role without credentials; refusing replacement')
    for name in ['yeats_development','yeats_test']:
        if not db.execute('SELECT 1 FROM pg_database WHERE datname=%s',(name,)).fetchone():db.execute(sql.SQL('CREATE DATABASE {} OWNER yeats').format(sql.Identifier(name)))
print('YEATS local PostgreSQL ready; existing cluster preserved; credentials not displayed.')
