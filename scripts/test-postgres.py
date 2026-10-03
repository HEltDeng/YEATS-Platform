"""Run integration tests against the independent PostgreSQL test database."""
from pathlib import Path
import os,sys,subprocess
from dotenv import dotenv_values
root=Path(__file__).resolve().parents[1]
secret=Path(os.environ['LOCALAPPDATA'])/'YEATS/secrets/database.dev.env'
url=dotenv_values(secret).get('YEATS_DATABASE_URL','')
if not url.endswith('/yeats_development') or '@127.0.0.1:55432/' not in url:raise SystemExit('Unexpected database target')
env=os.environ.copy();env['YEATS_TEST_DATABASE_URL']=url.rsplit('/',1)[0]+'/yeats_test'
env['YEATS_ENVIRONMENT']='test';env['YEATS_ENABLE_DEVELOPMENT_LOGIN']='false'
env['YEATS_DATABASE_URL']=env['YEATS_TEST_DATABASE_URL']
from sqlalchemy import create_engine,inspect,text
engine=create_engine(env['YEATS_TEST_DATABASE_URL'])
inspection=inspect(engine)
if inspection.has_table('accounts') and not inspection.has_table('alembic_version'):
    # Previous test runs used create_all. Adopt migrations only on an empty,
    # dedicated test schema; never stamp an occupied business database.
    with engine.connect() as db:
        if any(db.scalar(text('SELECT count(*) FROM "'+t+'"')) for t in inspection.get_table_names()):raise SystemExit('Occupied test schema cannot be adopted')
    version='20261003_grading_deadline' if 'grading_due_at' in {c['name'] for c in inspection.get_columns('homework')} else 'fed048e339a9'
    if subprocess.run([sys.executable,'-m','alembic','stamp',version],cwd=root,env=env).returncode:raise SystemExit('Test migration stamp failed')
if subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root,env=env).returncode:raise SystemExit('Test migration failed')
engine.dispose()
raise SystemExit(subprocess.run([sys.executable,'-m','pytest','services/api/tests','-q'],cwd=root,env=env).returncode)
