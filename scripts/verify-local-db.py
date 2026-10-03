"""Read-only identity check. Never creates roles, resets passwords or seeds data."""
from pathlib import Path
import os,sys
from dotenv import dotenv_values
import psycopg
root=Path(__file__).resolve().parents[1]
secret=Path(os.environ['LOCALAPPDATA'])/'YEATS/secrets'
try:
    values=dotenv_values(secret/'postgres-admin.dev.env')
    with psycopg.connect(host='127.0.0.1',port=55432,user=values['PGUSER'],password=values['PGPASSWORD'],dbname='postgres',connect_timeout=4) as db:
        actual=Path(db.execute('SHOW data_directory').fetchone()[0]).resolve()
        if actual != (root/'runtime/postgres-data').resolve():
            raise ValueError('directory')
    url=dotenv_values(secret/'database.dev.env')['YEATS_DATABASE_URL'].replace('postgresql+psycopg://','postgresql://',1)
    with psycopg.connect(url,connect_timeout=4) as db:
        if db.execute('select current_database()').fetchone()[0]!='yeats_development':raise ValueError('database')
        revision=db.execute('select version_num from alembic_version').fetchone()[0]
    print('YEATS PostgreSQL identity and application query verified; migration='+revision)
except Exception:
    print('YEATS PostgreSQL verification failed; details withheld to protect credentials',file=sys.stderr)
    raise SystemExit(1)
