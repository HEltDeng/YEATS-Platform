from sqlalchemy import select
from yeats.models import Outbox,Notification,WechatIdentity,SubscriptionConsent,Account
from yeats.operations import notify
from yeats.messages import deliver_one
from yeats.config import settings
from yeats.wechat import wechat

def test_missing_template_preserves_in_app_message(setup):
    c,db,t=setup
    notify(db,'student-1','feedback','受控消息')
    row=db.scalar(select(Outbox));deliver_one(db,row);db.flush()
    assert row.state=='pending_configuration' and row.attempts==0
    assert db.get(Notification,row.notification_id).title=='受控消息'

def test_send_failure_and_retry_do_not_lose_result(setup,monkeypatch):
    c,db,t=setup;a=db.get(Account,'test-parent-a');a.is_test=False
    db.add(WechatIdentity(appid=settings.wechat_appid,openid='synthetic-unit-test',account_id=a.id))
    db.add(SubscriptionConsent(account_id=a.id,choices={'test-template':'accept'}));db.flush()
    monkeypatch.setattr(settings,'subscription_templates',['test-template'])
    monkeypatch.setattr(settings,'subscription_rules',{'feedback':{'template_id':'test-template','fields':{'thing1':'title'}}})
    monkeypatch.setattr(wechat,'token',lambda:'synthetic-token-only')
    def fail(*args,**kwargs):raise RuntimeError('synthetic transport failure')
    monkeypatch.setattr(wechat,'call',fail)
    notify(db,'student-1','feedback','受控消息');row=db.scalar(select(Outbox))
    deliver_one(db,row);assert row.state=='failed' and row.attempts==1
    assert db.get(Notification,row.notification_id) is not None
    monkeypatch.setattr(wechat,'call',lambda *args,**kwargs:{'errcode':0})
    deliver_one(db,row);assert row.state=='sent' and row.attempts==2
