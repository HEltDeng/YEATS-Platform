"""Opt-in loopback-only test identity; absent from production route table."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import database
from .models import Account
from .security import issue_session, audit
from .config import settings

router=APIRouter()
@router.post('/v1/auth/development/{persona}')
def dev_login(persona:str,request:Request,db:Session=Depends(database)):
    if settings.environment!='development' or not settings.enable_development_login:
        raise HTTPException(404)
    if request.client.host not in ['127.0.0.1','::1','testclient'] or request.headers.get('x-forwarded-for'):
        raise HTTPException(403,'开发测试身份仅限本机')
    if persona not in ['parent-a','parent-b','unlinked']:
        raise HTTPException(404)
    a=db.scalar(select(Account).where(Account.id=='test-'+persona,Account.is_test==True,Account.role=='parent',Account.active==True))
    if not a:raise HTTPException(404,'尚未初始化隔离测试数据')
    token=issue_session(db,a);audit(db,a,'development_login');db.commit()
    return {'token':token,'needs_phone':False,'environment':'development','test_identity':True}
