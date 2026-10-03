"""Shared business operations for controlled fixtures and future staff UI.
No staff HTTP routes are exposed during parent phase.
"""
from decimal import Decimal
from sqlalchemy import select
from fastapi import HTTPException
from .models import *
from .security import audit

def teacher_scope(db,actor,lesson):
    if actor.role=='admin':return
    if actor.role!='teacher' or not db.scalar(select(TeacherClass).where(TeacherClass.account_id==actor.id,TeacherClass.class_id==lesson.class_id)):
        raise HTTPException(403,'无权操作此班级')
def record_attendance(db,actor,student_id,lesson_id,status,event_key,package_id,arrived_at=None,reason='',source='manual'):
    lesson=db.get(Lesson,lesson_id)
    if not lesson:raise HTTPException(404)
    teacher_scope(db,actor,lesson)
    if status not in ['present','makeup','absent','leave','cancelled']:raise HTTPException(422,'无效签到状态')
    if source=='manual' and not reason:raise HTTPException(422,'人工更正必须填写原因')
    if not db.scalar(select(Enrollment).where(Enrollment.student_id==student_id,Enrollment.class_id==lesson.class_id)):raise HTTPException(404,'学员不属于本课节班级')
    package=db.scalar(select(HourPackage).where(HourPackage.id==package_id,HourPackage.student_id==student_id).with_for_update())
    if not package:raise HTTPException(404,'课时包归属不匹配')
    if db.scalar(select(HourEntry).where(HourEntry.event_key==event_key)):return 'duplicate'
    current=sum((e.amount for e in db.scalars(select(HourEntry).where(HourEntry.student_id==student_id,HourEntry.lesson_id==lesson_id))),Decimal(0))
    desired=-lesson.units if status in ['present','makeup'] else Decimal(0)
    # Append compensating delta; never overwrite financial/lesson history.
    entry=HourEntry(package_id=package_id,student_id=student_id,lesson_id=lesson_id,amount=desired-current,reason=reason or '设备签到',event_key=event_key)
    db.add(entry)
    attendance=db.scalar(select(Attendance).where(Attendance.student_id==student_id,Attendance.lesson_id==lesson_id))
    if attendance is None:attendance=Attendance(student_id=student_id,lesson_id=lesson_id,status=status,source=source);db.add(attendance)
    before=attendance.status;attendance.status=status;attendance.source=source;attendance.arrived_at=arrived_at;attendance.reason=reason
    audit(db,actor,'attendance_change',lesson_id,{'student_id':student_id,'before':before,'after':status,'delta':str(desired-current),'event_key':event_key})
    db.flush();return 'recorded'
def ingest_normalized_event(db,actor,external_id,student_id,lesson_id,package_id,arrived_at):
    if actor.role!='admin':raise HTTPException(403)
    if db.scalar(select(DeviceEvent).where(DeviceEvent.external_id==external_id)):return 'duplicate'
    event=DeviceEvent(external_id=external_id,detail={'student_id':student_id,'lesson_id':lesson_id});db.add(event)
    if not student_id or not lesson_id or not package_id:
        event.state='unmatched';db.flush();return 'unmatched'
    record_attendance(db,actor,student_id,lesson_id,'present','device:'+external_id,package_id,arrived_at,source='device')
    event.state='matched';db.flush();return 'matched'
def notify(db,student_id,kind,title,resource_id=None,text=''):
    for g in db.scalars(select(Guardian).where(Guardian.student_id==student_id,Guardian.active==True,Guardian.account_id!=None)):
        n=Notification(account_id=g.account_id,student_id=student_id,kind=kind,title=title,text=text,resource_id=resource_id);db.add(n);db.flush();db.add(Outbox(notification_id=n.id))
def grade_submission(db,actor,submission_id,text,grade='',annotations=None,audio_id=None,returned=False):
    s=db.get(Submission,submission_id)
    if not s:raise HTTPException(404)
    h=db.get(Homework,s.homework_id)
    if actor.role!='admin' and (actor.role!='teacher' or h.teacher_id!=actor.id):raise HTTPException(403)
    if s.status!='submitted':raise HTTPException(409,'当前提交已处理')
    s.status='returned' if returned else 'graded'
    db.add(Feedback(submission_id=s.id,teacher_id=actor.id,text=text,grade=grade,annotation_file_ids=annotations or [],audio_file_id=audio_id))
    notify(db,s.student_id,'feedback','作业已退回' if returned else '作业已批改',s.homework_id)
    audit(db,actor,'homework_grade',s.id);db.flush()
def approve_viewing(db,actor,request_id,recording_id,starts_at,expires_at,reject_reason=None):
    if actor.role!='admin':raise HTTPException(403)
    r=db.scalar(select(ViewingRequest).where(ViewingRequest.id==request_id).with_for_update())
    if not r:raise HTTPException(404)
    if r.status!='pending':raise HTTPException(409,'申请已处理')
    if reject_reason:r.status='rejected';r.decision_reason=reject_reason
    else:
        rec=db.get(Recording,recording_id)
        if not rec or rec.lesson_id!=r.lesson_id or not rec.published or starts_at>=expires_at:raise HTTPException(422,'资源或有效期不匹配')
        r.status='approved';db.add(ViewingGrant(student_id=r.student_id,recording_id=rec.id,starts_at=starts_at,expires_at=expires_at))
    notify(db,r.student_id,'recording','在线课程申请已处理',text=r.decision_reason);audit(db,actor,'viewing_decision',r.id);db.flush()
