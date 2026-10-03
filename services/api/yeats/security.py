import hashlib, secrets
from datetime import timedelta
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DB
from .db import database
from .models import Account, Session, WechatIdentity, Guardian, Student, Enrollment, Audit, now
from .config import settings

def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def issue_session(db,account,identity_id=None):
    token=secrets.token_urlsafe(40)
    db.add(Session(account_id=account.id,identity_id=identity_id,token_hash=digest(token),expires_at=now()+timedelta(hours=settings.session_hours)))
    return token
def principal(authorization: str|None=Header(default=None), db:DB=Depends(database)):
    if not authorization or not authorization.startswith('Bearer '): raise HTTPException(401,'请先登录')
    session=db.scalar(select(Session).where(Session.token_hash==digest(authorization[7:]),Session.revoked==False,Session.expires_at>now()))
    account=db.get(Account,session.account_id) if session else None
    if not account or not account.active: raise HTTPException(401,'登录已过期，请重新登录')
    return account
def parent(account:Account=Depends(principal)):
    if account.role!='parent': raise HTTPException(403,'仅限家长访问')
    return account
def student_access(db,account,student_id):
    student=db.get(Student,student_id)
    relation=db.scalar(select(Guardian).where(Guardian.account_id==account.id,Guardian.student_id==student_id,Guardian.active==True))
    if not student or not student.active or not relation or account.phone!=relation.verified_phone:
        raise HTTPException(404,'学员不存在或无权访问')
    return student
def class_ids(db,student_id):
    return list(db.scalars(select(Enrollment.class_id).where(Enrollment.student_id==student_id,Enrollment.active==True)))
def identity_openid(db,account):
    identity=db.scalar(select(WechatIdentity).where(WechatIdentity.account_id==account.id,WechatIdentity.appid==settings.wechat_appid))
    if not identity: raise HTTPException(403,'微信身份未验证')
    return identity.openid
def audit(db,account,action,resource=None,detail=None):
    db.add(Audit(actor_id=account.id if account else None,action=action,resource_id=resource,detail=detail or {}))
