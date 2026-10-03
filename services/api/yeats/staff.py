"""Teacher HTTP application. All mutations use the existing shared PostgreSQL."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import hashlib,hmac,secrets,io,json,time,tempfile,subprocess
from fastapi import APIRouter,Depends,HTTPException,Request,Header,UploadFile,File
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import select,or_,text as sqltext
from sqlalchemy.orm import Session as DB
from PIL import Image,UnidentifiedImageError
from .db import database
from .models import *
from .security import principal,issue_session,digest,audit
from .config import settings
from .access import category_path
from .operations import grade_submission,record_attendance,notify
from .storage import store

router=APIRouter(prefix='/v1/staff',tags=['teacher'])
class Input(BaseModel):model_config=ConfigDict(extra='forbid')
class Login(Input):
    account:str=Field(min_length=1,max_length=80)
    password:str=Field(min_length=1,max_length=256)
class Publish(Input):
    title:str=Field(min_length=1,max_length=200)
    body:str=Field(default='',max_length=8000)
    class_ids:list[str]=Field(min_length=1,max_length=30)
    student_ids:list[str]=Field(default_factory=list,max_length=300)
    attachment_ids:list[str]=Field(default_factory=list,max_length=30)
    due_at:datetime|None=None
    grading_due_at:datetime|None=None
    late_policy:str=Field(pattern='^(allow|deny|unconfirmed)$')
    submission_requirement:str=Field(default='image_or_text',pattern='^(image_or_text|images|images_text|text)$')
    submission_instructions:str=Field(default='',max_length=2000)
    key:str=Field(min_length=16,max_length=80)
class Grade(Input):
    text:str=Field(default='',max_length=4000)
    grade:str=Field(default='',max_length=40)
    annotation_ids:list[str]=Field(default_factory=list,max_length=20)
    audio_id:str|None=None
    returned:bool=False
    key:str=Field(min_length=16,max_length=80)
class Test(Input):
    student_id:str
    lesson_id:str
    kind:str=Field(pattern='^(entry|exit)$')
    title:str=Field(min_length=1,max_length=200)
    text:str=Field(default='',max_length=4000)
    score:str=Field(default='',max_length=80)
    attachment_ids:list[str]=Field(default_factory=list,max_length=30)
    published:bool=True
    key:str=Field(min_length=16,max_length=80)
class AttendanceInput(Input):
    student_id:str
    package_id:str
    arrived_at:datetime
    reason:str=Field(min_length=1,max_length=200)
    key:str=Field(min_length=16,max_length=80)
class Reply(Input):
    text:str=Field(default='',max_length=4000)
    attachment_ids:list[str]=Field(default_factory=list,max_length=20)
    key:str=Field(min_length=16,max_length=80)
class References(Input):
    knowledge_ids:list[str]=Field(min_length=1,max_length=500)
    active:bool=True
    key:str=Field(min_length=16,max_length=80)
class Ticket(Input):purpose:str=Field(pattern='^(preview|download|play)$')
class ChangeRequest(Input):
    text:str=Field(min_length=1,max_length=4000)
    knowledge_id:str|None=None
    key:str=Field(min_length=16,max_length=80)

def password_hash(value,salt=None):
    salt=salt or secrets.token_hex(16)
    return 'pbkdf2_sha256$600000$'+salt+'$'+hashlib.pbkdf2_hmac('sha256',value.encode(),salt.encode(),600000).hex()
def verify_password(value,encoded):
    try:
        scheme,iterations,salt,expected=encoded.split('$')
        if scheme!='pbkdf2_sha256' or iterations!='600000':return False
        return hmac.compare_digest(password_hash(value,salt),encoded)
    except (ValueError,AttributeError):return False
def teacher(a:Account=Depends(principal)):
    if a.role!='teacher':raise HTTPException(403,'仅限老师使用')
    if a.is_test and not (settings.environment=='test' or (settings.environment=='development' and settings.enable_development_login)):raise HTTPException(403,'测试身份不可用于体验或生产')
    return a
def classes(db,a):return list(db.scalars(select(TeacherClass.class_id).join(Classroom,Classroom.id==TeacherClass.class_id).where(TeacherClass.account_id==a.id,Classroom.active==True)))
def scope(db,a,cid):
    if cid not in classes(db,a):raise HTTPException(404,'班级不存在或无权访问')
def members(db,cids):return list(db.scalars(select(Enrollment.student_id).join(Student,Student.id==Enrollment.student_id).where(Enrollment.class_id.in_(cids),Enrollment.active==True,Student.active==True).distinct()))
def student_scope(db,a,sid,cid=None):
    cs=classes(db,a)
    if cid:scope(db,a,cid);cs=[cid]
    if sid not in members(db,cs):raise HTTPException(404,'学员不存在或无权访问')
def lesson_scope(db,a,lid):
    l=db.get(Lesson,lid)
    if not l:raise HTTPException(404,'课节不存在')
    scope(db,a,l.class_id);return l
def utc(value):return value.astimezone(timezone.utc).replace(tzinfo=None) if value and value.tzinfo else value
def view(row,*keys):
    out={k:getattr(row,k) for k in ('id','created_at',*keys)}
    for k,v in out.items():
        if isinstance(v,datetime):out[k]=v.replace(tzinfo=timezone.utc).isoformat()
    return out
def files(db,ids):return [view(f,'name','kind','mime','size') for fid in ids if (f:=db.get(FileObject,fid)) and f.available and f.safety=='passed']
def attachments(db,a,ids,kinds=('image','audio'),existing=()):
    if len(set(ids))!=len(ids):raise HTTPException(422,'附件重复')
    for fid in ids:
        f=db.get(FileObject,fid)
        if not f or not f.available or f.safety!='passed' or (f.owner_id!=a.id and fid not in existing) or f.kind not in kinds:raise HTTPException(422,'附件归属或类型无效')
def begin(db,a,key,payload):
    # Lock per actor/request across processes, not just within one Python worker.
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
    if db.bind.dialect.name=='postgresql':
        lock=int.from_bytes(hashlib.sha256((a.id+key).encode()).digest()[:8],'big',signed=True)
        db.execute(sqltext('SELECT pg_advisory_xact_lock(:key)'),{'key':lock})
    previous=db.scalar(select(Audit).where(Audit.actor_id==a.id,Audit.action=='staff_command',Audit.detail['key'].as_string()==key))
    if previous:
        if previous.detail['fingerprint']!=fingerprint:raise HTTPException(409,'该请求已保存，内容不同请重新操作')
        return previous.detail['result']
    return None
def done(db,a,key,payload,result):
    audit(db,a,'staff_command',detail={'key':key,'fingerprint':hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest(),'result':result});db.commit();return result
def allowed_question(db,a,q):
    if not q or q.student_id not in members(db,classes(db,a)):return False
    enrolled=list(db.scalars(select(Enrollment.class_id).where(Enrollment.student_id==q.student_id,Enrollment.active==True,Enrollment.class_id.in_(classes(db,a)))))
    return bool(db.scalar(select(KnowledgeReference).where(KnowledgeReference.class_id.in_(enrolled),KnowledgeReference.knowledge_id==q.knowledge_id,KnowledgeReference.active==True)))
def file_allowed(db,a,f):
    if not f or not a.active or a.role!='teacher' or not f.available or f.safety!='passed':return False
    if a.is_test and not (settings.environment=='test' or (settings.environment=='development' and settings.enable_development_login)):return False
    if f.owner_id==a.id:return True
    # Platform library is shared across teachers; student material is scoped separately.
    if any(f.id in k.attachment_ids and category_path(db,k.category_id) for k in db.scalars(select(Knowledge).where(Knowledge.published==True))):return True
    sids=members(db,classes(db,a))
    owned=list(db.scalars(select(Homework.id).where(Homework.teacher_id==a.id)))
    for h in db.scalars(select(Homework).where(Homework.id.in_(owned))):
        if f.id in h.attachment_ids:return True
    for s in db.scalars(select(Submission).where(Submission.student_id.in_(sids),Submission.homework_id.in_(owned))):
        if f.id in s.attachment_ids:return True
        for fb in db.scalars(select(Feedback).where(Feedback.submission_id==s.id)):
            if f.id in fb.annotation_file_ids or f.id==fb.audio_file_id:return True
    lids=list(db.scalars(select(Lesson.id).where(Lesson.class_id.in_(classes(db,a)))))
    if any(f.id in t.attachment_ids for t in db.scalars(select(TestResult).where(TestResult.student_id.in_(sids),TestResult.lesson_id.in_(lids)))):return True
    if any(f.id==r.file_id for r in db.scalars(select(Recording).where(Recording.lesson_id.in_(lids),Recording.published==True))):return True
    return any(f.id in q.reply_files and allowed_question(db,a,q) for q in db.scalars(select(Question).where(Question.student_id.in_(sids))))

@router.post('/auth/login')
def login(body:Login,request:Request,db:DB=Depends(database)):
    # Persist failed attempts without storing the account input or password.
    key=digest((request.client.host or '')+'|'+body.account)[:32]
    attempts=list(db.scalars(select(Audit).where(Audit.action=='staff_login_failed',Audit.resource_id==key,Audit.created_at>now()-timedelta(minutes=10))))
    if len(attempts)>=10:raise HTTPException(429,'尝试次数过多，请稍后重试')
    a=db.scalar(select(Account).where(or_(Account.id==body.account,Account.phone==body.account),Account.role=='teacher',Account.active==True))
    valid=verify_password(body.password,a.password_hash if a and a.password_hash else password_hash('unavailable',salt='0'*32))
    if not a or not valid or (a.is_test and (settings.environment!='development' or not settings.enable_development_login or request.client.host not in ['127.0.0.1','::1','testclient'] or request.headers.get('x-forwarded-for'))):
        audit(db,None,'staff_login_failed',key);db.commit();raise HTTPException(401,'账号或密码错误，或当前环境不允许该账号')
    token=issue_session(db,a);audit(db,a,'staff_login');db.commit();return {'token':token,'name':a.name,'test_identity':a.is_test}
@router.post('/auth/logout')
def logout(authorization:str=Header(),a:Account=Depends(teacher),db:DB=Depends(database)):
    s=db.scalar(select(Session).where(Session.token_hash==digest(authorization[7:])))
    s.revoked=True;audit(db,a,'staff_logout');db.commit();return {'saved':True}
@router.get('/me')
def me(a:Account=Depends(teacher)):return {'id':a.id,'name':a.name,'role':a.role,'test_identity':a.is_test}
@router.get('/classes')
def class_list(a:Account=Depends(teacher),db:DB=Depends(database)):
    return [{**view(c,'name','campus','room','grade'),'size':len(members(db,[c.id]))} for c in db.scalars(select(Classroom).where(Classroom.id.in_(classes(db,a))))]
def lesson_view(db,l):return {**view(l,'class_id','title','starts_at','ends_at','room','units','status'),'class_name':db.get(Classroom,l.class_id).name}
@router.get('/classes/{cid}/students')
def students(cid:str,a:Account=Depends(teacher),db:DB=Depends(database)):
    scope(db,a,cid);out=[]
    for s in db.scalars(select(Student).where(Student.id.in_(members(db,[cid])))):
        packages=list(db.scalars(select(HourPackage).where(HourPackage.student_id==s.id)))
        remaining=sum(float(p.granted) for p in packages)+sum(float(e.amount) for e in db.scalars(select(HourEntry).where(HourEntry.student_id==s.id)))
        contacts=[g.verified_phone[:5]+'****'+g.verified_phone[-4:] for g in db.scalars(select(Guardian).where(Guardian.student_id==s.id,Guardian.active==True))]
        out.append({**view(s,'name','grade'),'remaining':remaining,'contacts':contacts,'packages':[view(p,'name','granted') for p in packages]})
    return out
@router.get('/lessons')
def lessons(class_id:str|None=None,a:Account=Depends(teacher),db:DB=Depends(database)):
    cs=classes(db,a)
    if class_id:scope(db,a,class_id);cs=[class_id]
    return [lesson_view(db,l) for l in db.scalars(select(Lesson).where(Lesson.class_id.in_(cs)).order_by(Lesson.starts_at.desc()))]
@router.get('/classes/{cid}/students/{sid}')
def student_detail(cid:str,sid:str,a:Account=Depends(teacher),db:DB=Depends(database)):
    student_scope(db,a,sid,cid);ls=list(db.scalars(select(Lesson.id).where(Lesson.class_id==cid)))
    return {'student':next(s for s in students(cid,a,db) if s['id']==sid),'attendance':[view(x,'lesson_id','status','arrived_at','reason','source') for x in db.scalars(select(Attendance).where(Attendance.student_id==sid,Attendance.lesson_id.in_(ls)))],'hours':[view(x,'lesson_id','amount','reason') for x in db.scalars(select(HourEntry).where(HourEntry.student_id==sid,HourEntry.lesson_id.in_(ls)))],'tests':[test_view(db,x) for x in db.scalars(select(TestResult).where(TestResult.student_id==sid,TestResult.lesson_id.in_(ls)))],'homework':[h for h in homework_list(cid,a,db) if sid in h['student_ids']]}
def homework_view(db,h,sids):
    targets=[sid for sid in db.scalars(select(HomeworkTarget.student_id).where(HomeworkTarget.homework_id==h.id)) if sid in sids]
    latest=[]
    for sid in targets:
        s=db.scalar(select(Submission).where(Submission.homework_id==h.id,Submission.student_id==sid).order_by(Submission.revision.desc()))
        latest.append({'student_id':sid,'name':db.get(Student,sid).name,'status':s.status if s else 'todo','submission_id':s.id if s else None})
    return {**view(h,'title','body','due_at','grading_due_at','late_policy','submission_requirement','submission_instructions'),'files':files(db,h.attachment_ids),'student_ids':targets,'targets':latest}
@router.get('/homework')
def homework_list(class_id:str|None=None,a:Account=Depends(teacher),db:DB=Depends(database)):
    cs=classes(db,a)
    if class_id:scope(db,a,class_id);cs=[class_id]
    sids=members(db,cs);out=[]
    for h in db.scalars(select(Homework).where(Homework.teacher_id==a.id).order_by(Homework.created_at.desc())):
        publication=db.scalar(select(Audit).where(Audit.action=='homework_publish',Audit.resource_id==h.id)) if class_id else None
        if publication and class_id not in publication.detail.get('class_ids',[]):continue
        item=homework_view(db,h,sids)
        if item['student_ids']:out.append(item)
    return out
@router.post('/homework')
def publish(body:Publish,a:Account=Depends(teacher),db:DB=Depends(database)):
    if not body.title.strip() or not (body.body.strip() or body.attachment_ids):raise HTTPException(422,'请填写标题及文字或附件内容')
    for cid in body.class_ids:scope(db,a,cid)
    sids=members(db,body.class_ids)
    if body.student_ids:
        if not set(body.student_ids)<=set(sids):raise HTTPException(404,'定向学员不属于所选班级')
        sids=list(set(body.student_ids))
    if not sids:raise HTTPException(422,'所选班级暂无学员')
    attachments(db,a,body.attachment_ids)
    payload={'action':'publish',**body.model_dump()};previous=begin(db,a,body.key,payload)
    if previous:return previous
    h=Homework(teacher_id=a.id,title=body.title.strip(),body=body.body.strip(),due_at=utc(body.due_at),grading_due_at=utc(body.grading_due_at),late_policy=body.late_policy,submission_requirement=body.submission_requirement,submission_instructions=body.submission_instructions,attachment_ids=body.attachment_ids);db.add(h);db.flush()
    for sid in sids:db.add(HomeworkTarget(homework_id=h.id,student_id=sid));notify(db,sid,'homework','新作业：'+h.title,h.id)
    audit(db,a,'homework_publish',h.id,{'class_ids':body.class_ids,'student_count':len(sids)})
    return done(db,a,body.key,payload,{'id':h.id,'saved':True})
@router.get('/homework/{hid}/students/{sid}')
def submissions(hid:str,sid:str,a:Account=Depends(teacher),db:DB=Depends(database)):
    student_scope(db,a,sid);h=db.get(Homework,hid)
    if not h or h.teacher_id!=a.id or not db.scalar(select(HomeworkTarget).where(HomeworkTarget.homework_id==hid,HomeworkTarget.student_id==sid)):raise HTTPException(404)
    out=[]
    for s in db.scalars(select(Submission).where(Submission.homework_id==hid,Submission.student_id==sid).order_by(Submission.revision.desc())):
        out.append({**view(s,'text','status','revision'),'files':files(db,s.attachment_ids),'feedback':[{**view(f,'text','grade'),'files':files(db,f.annotation_file_ids+([f.audio_file_id] if f.audio_file_id else []))} for f in db.scalars(select(Feedback).where(Feedback.submission_id==s.id))]})
    return {'homework':homework_view(db,h,[sid]),'history':out,'student':view(db.get(Student,sid),'name','grade')}
@router.post('/submissions/{sid}/grade')
def grade(sid:str,body:Grade,a:Account=Depends(teacher),db:DB=Depends(database)):
    if body.returned and not body.text.strip():raise HTTPException(422,'退回必须填写原因')
    if not (body.text.strip() or body.annotation_ids or body.audio_id):raise HTTPException(422,'请填写评语或添加批改附件')
    s=db.scalar(select(Submission).where(Submission.id==sid).with_for_update())
    if not s:raise HTTPException(404)
    student_scope(db,a,s.student_id)
    h=db.get(Homework,s.homework_id)
    if h.teacher_id!=a.id:raise HTTPException(404)
    attachments(db,a,body.annotation_ids,('image',));attachments(db,a,[body.audio_id] if body.audio_id else [],('audio',))
    payload={'action':'grade','submission':sid,**body.model_dump()};previous=begin(db,a,body.key,payload)
    if previous:return previous
    grade_submission(db,a,sid,body.text,body.grade,body.annotation_ids,body.audio_id,body.returned)
    return done(db,a,body.key,payload,{'saved':True,'status':s.status})
def test_view(db,t):return {**view(t,'student_id','lesson_id','kind','title','text','score','published'),'student':db.get(Student,t.student_id).name,'files':files(db,t.attachment_ids)}
@router.get('/tests')
def tests(lesson_id:str,a:Account=Depends(teacher),db:DB=Depends(database)):
    lesson_scope(db,a,lesson_id);return [test_view(db,t) for t in db.scalars(select(TestResult).where(TestResult.lesson_id==lesson_id))]
def save_test(body,a,db,tid=None):
    l=lesson_scope(db,a,body.lesson_id);student_scope(db,a,body.student_id,l.class_id)
    payload={'action':'test','id':tid,**body.model_dump()};previous=begin(db,a,body.key,payload)
    if previous:return previous
    # Match the batch writer's lock order; read existing media only after locking.
    db.scalar(select(Lesson).where(Lesson.id==l.id).with_for_update())
    row=db.scalar(select(TestResult).where(TestResult.id==tid).with_for_update()) if tid else None
    if tid and (not row or row.lesson_id!=body.lesson_id or row.student_id!=body.student_id):raise HTTPException(404)
    attachments(db,a,body.attachment_ids,existing=row.attachment_ids if row else ())
    if not row:row=TestResult(student_id=body.student_id,lesson_id=body.lesson_id);db.add(row)
    before={'published':row.published,'text':row.text,'score':row.score,'attachment_ids':row.attachment_ids} if tid else None
    for k in ['kind','title','text','score','attachment_ids','published']:setattr(row,k,getattr(body,k))
    db.flush();audit(db,a,'test_update',row.id,{'before':before,'published':row.published})
    if row.published:notify(db,row.student_id,'test','随堂测试已发布',row.id)
    return done(db,a,body.key,payload,{'saved':True,'id':row.id})
@router.post('/tests')
def create_test(body:Test,a:Account=Depends(teacher),db:DB=Depends(database)):return save_test(body,a,db)
@router.put('/tests/{tid}')
def edit_test(tid:str,body:Test,a:Account=Depends(teacher),db:DB=Depends(database)):return save_test(body,a,db,tid)
@router.get('/lessons/{lid}/attendance')
def attendance(lid:str,a:Account=Depends(teacher),db:DB=Depends(database)):
    l=lesson_scope(db,a,lid);out=[]
    for s in students(l.class_id,a,db):
        row=db.scalar(select(Attendance).where(Attendance.lesson_id==lid,Attendance.student_id==s['id']))
        out.append({**s,'attendance':view(row,'status','arrived_at','reason','source') if row else None})
    return out
@router.post('/lessons/{lid}/attendance')
def makeup(lid:str,body:AttendanceInput,a:Account=Depends(teacher),db:DB=Depends(database)):
    l=lesson_scope(db,a,lid);student_scope(db,a,body.student_id,l.class_id)
    payload={'action':'attendance','lesson':lid,**body.model_dump()};previous=begin(db,a,body.key,payload)
    if previous:return previous
    record_attendance(db,a,body.student_id,lid,'makeup','staff:'+a.id+':'+body.key,body.package_id,utc(body.arrived_at),body.reason)
    return done(db,a,body.key,payload,{'saved':True})
@router.get('/knowledge')
def knowledge(q:str='',kind:str='',a:Account=Depends(teacher),db:DB=Depends(database)):
    out=[];cs=classes(db,a)
    for k in db.scalars(select(Knowledge).where(Knowledge.published==True)):
        path=category_path(db,k.category_id)
        if not path or q.casefold() not in (k.title+k.text).casefold():continue
        ff=files(db,k.attachment_ids)
        if kind and not any(f['kind']==kind for f in ff):continue
        item={**view(k,'title','text','category_id'),'files':ff,'path':[c.name for c in path],'category_ids':[c.id for c in path],'references':list(db.scalars(select(KnowledgeReference.class_id).where(KnowledgeReference.knowledge_id==k.id,KnowledgeReference.class_id.in_(cs),KnowledgeReference.active==True)))}
        item['version']=digest(json.dumps({'title':k.title,'text':k.text,'files':[(f.id,f.sha256) for f in db.scalars(select(FileObject).where(FileObject.id.in_(k.attachment_ids)))]},sort_keys=True))[:16];out.append(item)
    unavailable=[]
    for ref in db.scalars(select(KnowledgeReference).where(KnowledgeReference.class_id.in_(cs),KnowledgeReference.active==True)):
        k=db.get(Knowledge,ref.knowledge_id)
        if not k or not k.published or not category_path(db,k.category_id):unavailable.append({'id':ref.knowledge_id,'title':k.title if k else '已移除内容','class_id':ref.class_id})
    return {'items':out,'unavailable_references':unavailable,'categories':[view(c,'parent_id','name','level','sort') for c in db.scalars(select(Category).where(Category.active==True).order_by(Category.sort))]}
@router.post('/classes/{cid}/references')
def references(cid:str,body:References,a:Account=Depends(teacher),db:DB=Depends(database)):
    scope(db,a,cid);payload={'action':'references','class':cid,**body.model_dump()};previous=begin(db,a,body.key,payload)
    if previous:return previous
    for kid in set(body.knowledge_ids):
        k=db.get(Knowledge,kid)
        if body.active and (not k or not k.published or not category_path(db,k.category_id)):raise HTTPException(422,'包含已下架知识内容')
        ref=db.scalar(select(KnowledgeReference).where(KnowledgeReference.class_id==cid,KnowledgeReference.knowledge_id==kid).with_for_update())
        if not ref and body.active:db.add(KnowledgeReference(class_id=cid,knowledge_id=kid,active=True))
        elif ref:ref.active=body.active
    audit(db,a,'knowledge_references',cid,{'knowledge_ids':body.knowledge_ids,'active':body.active})
    return done(db,a,body.key,payload,{'saved':True})
@router.get('/questions')
def questions(class_id:str|None=None,unanswered:bool=False,a:Account=Depends(teacher),db:DB=Depends(database)):
    cs=classes(db,a)
    if class_id:scope(db,a,class_id);cs=[class_id]
    out=[]
    for q in db.scalars(select(Question).where(Question.student_id.in_(members(db,cs))).order_by(Question.created_at.desc())):
        if not allowed_question(db,a,q) or (unanswered and (q.reply or q.reply_files)):continue
        out.append({**view(q,'student_id','knowledge_id','text','reply'),'student':db.get(Student,q.student_id).name,'knowledge':db.get(Knowledge,q.knowledge_id).title,'files':files(db,q.reply_files)})
    return out
@router.post('/questions/{qid}/reply')
def reply(qid:str,body:Reply,a:Account=Depends(teacher),db:DB=Depends(database)):
    if not (body.text.strip() or body.attachment_ids):raise HTTPException(422,'请填写回复或添加附件')
    q=db.scalar(select(Question).where(Question.id==qid).with_for_update())
    if not allowed_question(db,a,q):raise HTTPException(404)
    attachments(db,a,body.attachment_ids,existing=q.reply_files);payload={'action':'reply','question':qid,**body.model_dump()};previous=begin(db,a,body.key,payload)
    if previous:return previous
    audit(db,a,'question_reply',qid,{'previous_reply':q.reply,'previous_files':q.reply_files});q.reply=body.text;q.reply_files=body.attachment_ids;q.replied_by=a.id
    # Private question notifications go only to the asking parent.
    n=Notification(account_id=q.parent_id,student_id=q.student_id,kind='knowledge',title='老师已答复你的提问',resource_id=q.knowledge_id);db.add(n);db.flush();db.add(Outbox(notification_id=n.id))
    return done(db,a,body.key,payload,{'saved':True})
@router.get('/recordings')
def recordings(a:Account=Depends(teacher),db:DB=Depends(database)):
    lids=list(db.scalars(select(Lesson.id).where(Lesson.class_id.in_(classes(db,a)))))
    return {'recordings':[{**view(r,'lesson_id','title'),'files':files(db,[r.file_id])} for r in db.scalars(select(Recording).where(Recording.lesson_id.in_(lids),Recording.published==True))],'requests':[{**view(r,'lesson_id','student_id','status','reason','decision_reason'),'student':db.get(Student,r.student_id).name} for r in db.scalars(select(ViewingRequest).where(ViewingRequest.lesson_id.in_(lids),ViewingRequest.student_id.in_(members(db,classes(db,a)))))]}
@router.get('/dashboard')
def dashboard(a:Account=Depends(teacher),db:DB=Depends(database)):
    hw=homework_list(None,a,db);qs=questions(None,True,a,db)
    today=(now()+timedelta(hours=8)).date()
    ls=[l for l in lessons(None,a,db) if (datetime.fromisoformat(l['starts_at'])+timedelta(hours=8)).date()==today]
    return {'pending_homework':sum(t['status']=='submitted' for h in hw for t in h['targets']),'unanswered':len(qs),'today_lessons':ls,'course_requests':len([r for r in recordings(a,db)['requests'] if r['status']=='pending'])}
@router.post('/files')
async def upload(file:UploadFile=File(),a:Account=Depends(teacher),db:DB=Depends(database)):
    data=await file.read(20*1024*1024+1)
    if not data or len(data)>20*1024*1024:raise HTTPException(413,'附件为空或超过20MB本地验收上限')
    suffix=Path(file.filename or '').suffix.lower();kind='';mime=''
    if suffix in ['.jpg','.jpeg','.png']:
        try:
            im=Image.open(io.BytesIO(data));im.load();out=io.BytesIO();im.convert('RGB').save(out,'JPEG');data=out.getvalue();suffix='.jpg';kind='image';mime='image/jpeg'
        except (UnidentifiedImageError,OSError,Image.DecompressionBombError):raise HTTPException(422,'图片格式无效')
    elif suffix=='.wav' and data[:4]==b'RIFF' and data[8:12]==b'WAVE':kind='audio';mime='audio/wav'
    elif suffix=='.mp3' and (data[:3]==b'ID3' or (len(data)>2 and data[0]==255 and data[1]&224==224)):kind='audio';mime='audio/mpeg'
    elif suffix in ['.webm','.ogg'] and (data[:4]==b'\x1a\x45\xdf\xa3' or data[:4]==b'OggS'):
        # Browser microphone recordings are normalized for WeChat audio playback.
        try:
            import imageio_ffmpeg
            with tempfile.TemporaryDirectory(prefix='yeats-audio-') as directory:
                source=Path(directory)/('recording'+suffix);target=Path(directory)/'recording.mp3';source.write_bytes(data)
                result=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-nostdin','-hide_banner','-loglevel','error','-i',str(source),'-vn','-ac','1','-ar','44100','-codec:a','libmp3lame','-b:a','96k',str(target)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
                if result.returncode or not target.is_file():raise ValueError('conversion')
                if target.stat().st_size>20*1024*1024:raise ValueError('size')
                data=target.read_bytes();suffix='.mp3';kind='audio';mime='audio/mpeg'
        except Exception:raise HTTPException(422,'录音无法转换，请重试或上传 MP3/WAV 文件') from None
    else:raise HTTPException(422,'仅支持图片、MP3/WAV音频或浏览器录音；知识库内容由平台维护')
    fid=uid();name=(Path(file.filename or '教学附件').stem+suffix)[:180];key='staff/'+fid+suffix
    store.put(key,data);f=FileObject(id=fid,owner_id=a.id,kind=kind,name=name,storage_key=key,mime=mime,size=len(data),sha256=hashlib.sha256(data).hexdigest(),safety='passed');db.add(f);audit(db,a,'staff_upload',fid,{'validation':'format_checked','kind':kind});db.commit();return view(f,'name','kind','mime','size')
@router.post('/files/{fid}/tickets')
def ticket(fid:str,body:Ticket,a:Account=Depends(teacher),db:DB=Depends(database)):
    f=db.get(FileObject,fid)
    if not file_allowed(db,a,f):raise HTTPException(404,'文件不存在或无权访问')
    if f.kind=='video' and body.purpose!='play':raise HTTPException(403,'视频仅可在线播放')
    token=secrets.token_urlsafe(32);db.add(FileTicket(token_hash=digest(token),file_id=f.id,account_id=a.id,purpose=body.purpose,expires_at=now()+timedelta(minutes=5)));audit(db,a,'staff_file_'+body.purpose,f.id);db.commit()
    return {'url':settings.public_base_url+'/v1/media/'+token,'kind':f.kind,'name':f.name,'expires_in':300}
