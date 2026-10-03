"""Durable in-app notifications are independent from optional WeChat delivery."""
from sqlalchemy import select
from .models import Outbox,Notification,SubscriptionConsent,WechatIdentity,Account,Guardian
from .config import settings
from .wechat import wechat
from .security import audit

def deliver_one(db,row):
    notice=db.get(Notification,row.notification_id);account=db.get(Account,notice.account_id)
    rule=settings.subscription_rules.get(notice.kind,{})
    template=rule.get('template_id')
    if not template or template not in settings.subscription_templates:
        row.state='pending_configuration';return
    relation=db.scalar(select(Guardian).where(Guardian.account_id==account.id,Guardian.student_id==notice.student_id,Guardian.active==True,Guardian.verified_phone==account.phone))
    if not account.active or not relation:row.state='access_revoked';return
    identity=db.scalar(select(WechatIdentity).where(WechatIdentity.account_id==account.id,WechatIdentity.appid==settings.wechat_appid))
    if not identity or account.is_test:row.state='identity_unavailable';return
    consent=db.scalar(select(SubscriptionConsent).where(SubscriptionConsent.account_id==account.id).order_by(SubscriptionConsent.created_at.desc()))
    if not consent or consent.choices.get(template)!='accept':row.state='not_subscribed';return
    # Only approved template field names are configured. No names or phone numbers
    # are implicitly inserted into a third-party message.
    allowed={'title':notice.title,'text':notice.text}
    mapping=rule.get('fields',{})
    if not mapping or any(v not in allowed for v in mapping.values()):row.state='pending_configuration';return
    data={key:{'value':allowed[field][:20]} for key,field in mapping.items()}
    row.attempts+=1
    try:
        wechat.call('POST','/cgi-bin/message/subscribe/send',params={'access_token':wechat.token()},json={'touser':identity.openid,'template_id':template,'page':'pages/notifications/index','data':data,'miniprogram_state':'formal' if settings.environment=='production' else 'developer'})
        row.state='sent'
    except Exception:
        row.state='failed'
    audit(db,account,'subscription_delivery',row.id,{'state':row.state,'attempt':row.attempts})

def drain(db,limit=20,retry_failed=False):
    states=['pending_configuration']+(['failed'] if retry_failed else [])
    rows=list(db.scalars(select(Outbox).where(Outbox.state.in_(states)).order_by(Outbox.created_at).limit(limit).with_for_update(skip_locked=True)))
    for row in rows:deliver_one(db,row)
    db.commit();return {state:sum(r.state==state for r in rows) for state in {r.state for r in rows}}
