"""Real concurrent PostgreSQL transactions in the dedicated test database only."""
from pathlib import Path
import os,sys,json,threading
from concurrent.futures import ThreadPoolExecutor
from dotenv import dotenv_values
root=Path(__file__).resolve().parents[1]
url=dotenv_values(Path(os.environ['LOCALAPPDATA'])/'YEATS/secrets/database.dev.env')['YEATS_DATABASE_URL']
url=url.rsplit('/',1)[0]+'/yeats_test'
if '@127.0.0.1:55432/yeats_test' not in url:raise SystemExit('Unexpected test database')
os.environ['YEATS_DATABASE_URL']=url;os.environ['YEATS_ENVIRONMENT']='test';os.environ['YEATS_ENABLE_DEVELOPMENT_LOGIN']='false'
sys.path.insert(0,str(root/'services/api'))
from sqlalchemy import select,func
from yeats.db import engine,SessionLocal,Base
from yeats.models import Account,Submission
from yeats.fixtures import seed
from yeats import main,schemas
from yeats.config import settings
settings.file_root=root/'runtime/concurrency-files'
Base.metadata.create_all(engine)
with SessionLocal() as db:
    if db.scalar(select(func.count()).select_from(Account)):raise SystemExit('Test database not empty; refusing destructive reset')
    seed(db)
main.moderate_text=lambda *args:None  # test process only; never changes running API
barrier=threading.Barrier(2)
def worker(_):
    with SessionLocal() as db:
        account=db.get(Account,'test-parent-a');barrier.wait()
        result=main.submit('student-1','homework-1',schemas.Submit(text='Concurrent isolated test',attachment_ids=[],idempotency_key='concurrent-identical-key'),account,db)
        return result['id']
try:
    with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(worker,range(2)))
    with SessionLocal() as db:count=db.scalar(select(func.count()).select_from(Submission).where(Submission.homework_id=='homework-1'))
    assert len(set(ids))==1 and count==1
    print(json.dumps({'engine':'PostgreSQL','concurrent_identical_submissions':2,'persisted_submissions':count,'same_result_id':True}))
finally:
    # Remove only this named test database's synthetic fixture rows, not tables.
    with engine.begin() as db:
        for table in reversed(Base.metadata.sorted_tables):db.execute(table.delete())
