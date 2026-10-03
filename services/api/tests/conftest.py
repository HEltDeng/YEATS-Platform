import os,sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['YEATS_ENVIRONMENT']='test'
os.environ['YEATS_ENABLE_DEVELOPMENT_LOGIN']='false'
from yeats.db import Base,database
from yeats.main import app
from yeats.models import Account
from yeats.fixtures import seed
from yeats.security import issue_session
from yeats.config import settings
from yeats.wechat import wechat

@pytest.fixture
def setup(tmp_path,monkeypatch):
    url=os.environ.get('YEATS_TEST_DATABASE_URL','sqlite:///'+str(tmp_path/'test.db'))
    if not (url.endswith('/yeats_test') or url.startswith('sqlite:')):raise RuntimeError('Refusing tests on non-test database')
    engine=create_engine(url,connect_args={'check_same_thread':False} if url.startswith('sqlite:') else {})
    Base.metadata.create_all(engine)
    connection=engine.connect();outer=connection.begin()
    db=Session(bind=connection,join_transaction_mode='create_savepoint',expire_on_commit=False)
    monkeypatch.setattr(settings,'file_root',tmp_path/'files');monkeypatch.setattr(settings,'wechat_appid','wx-test-contract')
    monkeypatch.setattr(wechat,'check_text',lambda *args:None);monkeypatch.setattr(wechat,'check_image',lambda *args:None)
    seed(db)
    # Fake WeChat boundary only in tests, never in application login code.
    import yeats.main as main
    monkeypatch.setattr(main,'identity_openid',lambda db,a:'test-openid')
    tokens={}
    for id in ['test-parent-a','test-parent-b','test-unlinked','test-teacher','test-admin']:
        tokens[id]=issue_session(db,db.get(Account,id))
    db.commit()
    def override():yield db
    app.dependency_overrides[database]=override
    with TestClient(app) as client:yield client,db,tokens
    app.dependency_overrides.clear();db.close();outer.rollback();connection.close();engine.dispose()
def auth(tokens,name='test-parent-a'):return {'Authorization':'Bearer '+tokens[name]}
