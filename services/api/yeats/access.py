"""Re-evaluate resource policy on every ticket use; unpublishing revokes old links."""
from sqlalchemy import select
from fastapi import HTTPException
from .models import *
from .security import student_access, class_ids

def category_path(db, category_id):
    path=[]; seen=set()
    while category_id:
        c=db.get(Category,category_id)
        if not c or not c.active or c.id in seen: return None
        seen.add(c.id); path.insert(0,c); category_id=c.parent_id
    return path if [c.level for c in path]==list(range(1,8)) else None
def knowledge_for(db,student_id,knowledge_id):
    k=db.get(Knowledge,knowledge_id)
    if not k or not k.published or not category_path(db,k.category_id): return None
    ref=db.scalar(select(KnowledgeReference).where(KnowledgeReference.knowledge_id==k.id,KnowledgeReference.class_id.in_(class_ids(db,student_id)),KnowledgeReference.active==True))
    return k if ref else None
def homework_for(db,student_id,homework_id):
    h=db.get(Homework,homework_id)
    t=db.scalar(select(HomeworkTarget).where(HomeworkTarget.homework_id==homework_id,HomeworkTarget.student_id==student_id))
    if not h or not h.published or not t: raise HTTPException(404,'作业不存在或无权访问')
    return h
def recording_grant(db,student_id,recording_id):
    r=db.get(Recording,recording_id)
    if not r or not r.published: return None
    return db.scalar(select(ViewingGrant).where(ViewingGrant.student_id==student_id,ViewingGrant.recording_id==recording_id,ViewingGrant.revoked==False,ViewingGrant.starts_at<=now(),ViewingGrant.expires_at>now()))
def can_file(db,account,f,student_id):
    if not f or not f.available or f.safety!='passed': return False
    if any(f.id in c.attachment_ids for c in db.scalars(select(Content).where(Content.published==True))): return True
    if any(f.id in [p.avatar_file_id,p.demo_file_id] for p in db.scalars(select(TeacherProfile).where(TeacherProfile.published==True))): return True
    if not student_id: return False
    student_access(db,account,student_id)
    if f.owner_id==account.id and f.student_id==student_id: return True
    targets=list(db.scalars(select(HomeworkTarget.homework_id).where(HomeworkTarget.student_id==student_id)))
    if any(f.id in h.attachment_ids for h in db.scalars(select(Homework).where(Homework.id.in_(targets),Homework.published==True))): return True
    for s in db.scalars(select(Submission).where(Submission.student_id==student_id)):
        if f.id in s.attachment_ids: return True
        for fb in db.scalars(select(Feedback).where(Feedback.submission_id==s.id)):
            if f.id in fb.annotation_file_ids or f.id==fb.audio_file_id: return True
    if any(f.id in t.attachment_ids for t in db.scalars(select(TestResult).where(TestResult.student_id==student_id,TestResult.published==True))): return True
    for k in db.scalars(select(Knowledge).where(Knowledge.published==True)):
        if f.id in k.attachment_ids and knowledge_for(db,student_id,k.id): return True
    for q in db.scalars(select(Question).where(Question.parent_id==account.id,Question.student_id==student_id)):
        if f.id in q.reply_files and knowledge_for(db,student_id,q.knowledge_id): return True
    for r in db.scalars(select(Recording).where(Recording.file_id==f.id,Recording.published==True)):
        if recording_grant(db,student_id,r.id): return True
    return False
