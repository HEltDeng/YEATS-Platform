"""Explicit development credential initialization for an existing synthetic teacher only."""
from pathlib import Path
import os,sys,secrets,json
r=Path(__file__).resolve().parents[1];os.chdir(r);sys.path.insert(0,str(r/'services/api'))
from yeats.config import settings
from yeats.db import SessionLocal
from yeats.models import Account
from yeats.staff import password_hash
from yeats.security import audit
if settings.environment!='development':raise SystemExit('Development only')
destination=Path(os.environ['LOCALAPPDATA'])/'YEATS/secrets/teacher-acceptance.json'
with SessionLocal() as db:
    a=db.get(Account,'test-teacher')
    if not a or not a.is_test or a.role!='teacher':raise SystemExit('Existing synthetic teacher required')
    if destination.exists() and a.password_hash:print('Existing local teacher credentials retained');raise SystemExit(0)
    if destination.exists() or a.password_hash:raise SystemExit('Credential state mismatch; refusing reset')
    password=secrets.token_urlsafe(24)
    with destination.open('x',encoding='utf-8') as f:json.dump({'account':a.id,'password':password,'url':'http://127.0.0.1:8930/teacher/','scope':'local synthetic acceptance only'},f,ensure_ascii=False,indent=2)
    a.password_hash=password_hash(password);audit(db,a,'development_staff_password_initialized');db.commit()
print('Local synthetic teacher credential file created under the existing protected YEATS secrets directory; password withheld.')
