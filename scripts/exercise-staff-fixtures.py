"""Controlled staff actions to verify parent flows, NOT a teacher/admin frontend."""
from pathlib import Path
import sys
from datetime import timedelta
from sqlalchemy import select
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'services/api'))
from yeats.config import settings
from yeats.db import SessionLocal
from yeats.models import Account,Submission,ViewingRequest,now
from yeats.operations import grade_submission,approve_viewing
if settings.environment!='development':raise SystemExit('Only local synthetic development data allowed')
with SessionLocal() as db:
    teacher=db.get(Account,'test-teacher');admin=db.get(Account,'test-admin')
    if not teacher or not teacher.is_test or not admin or not admin.is_test:raise SystemExit('Synthetic staff fixture missing')
    action=sys.argv[1]
    if action in ['return','grade']:
        s=db.scalar(select(Submission).where(Submission.homework_id=='homework-1',Submission.student_id=='student-1',Submission.parent_id=='test-parent-a').order_by(Submission.revision.desc()))
        if not s:raise SystemExit('Synthetic parent submission required')
        grade_submission(db,teacher,s.id,'受控验收：请补充默写图片。' if action=='return' else '受控验收：修改已收到，批改结果已保存。',grade='A' if action=='grade' else '',annotations=['file-image'],audio_id='file-audio',returned=action=='return')
    elif action=='approve':
        r=db.scalar(select(ViewingRequest).where(ViewingRequest.parent_id=='test-parent-a',ViewingRequest.student_id=='student-1',ViewingRequest.lesson_id=='lesson-2',ViewingRequest.status=='pending'))
        if not r:raise SystemExit('Synthetic pending application required')
        approve_viewing(db,admin,r.id,'fixture-recording',now(),now()+timedelta(days=settings.viewing_default_days))
    else:raise SystemExit('Unknown action')
    db.commit()
print('Synthetic staff business operation persisted; no staff UI acceptance implied.')
