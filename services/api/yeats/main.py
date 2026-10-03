from datetime import timedelta, datetime, timezone
from decimal import Decimal
from pathlib import Path
import hashlib, io, json, secrets
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Header, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func, text as sqltext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DB
from PIL import Image, UnidentifiedImageError
from .config import settings
from .db import database
from .models import *
from .security import parent, issue_session, digest, student_access, class_ids, identity_openid, audit
from .access import category_path, knowledge_for, homework_for, recording_grant, can_file
from .wechat import wechat
from .storage import store
from . import schemas as S

app=FastAPI(title='YEATS · 叶芝英语',version='0.1.0',docs_url='/docs' if settings.environment!='production' else None)
if settings.environment=='development' and settings.enable_development_login:
    from .development import router
    app.include_router(router)

def moderate_text(db,a,text):
    if settings.environment=='development' and settings.enable_development_login and a.is_test:
        audit(db,a,'development_safety_bypass',detail={'scope':'synthetic_text_only'});return
    wechat.check_text(text,identity_openid(db,a))

@app.exception_handler(IntegrityError)
def conflict(request,exc): return JSONResponse(status_code=409,content={'detail':'数据已发生变化，请刷新后重试'})

@app.middleware('http')
async def safe_headers(request,call_next):
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    return response

def public(row, *fields):
    return jsonable_encoder({k:getattr(row,k) for k in ('id','created_at',*fields)}, custom_encoder={datetime:lambda d:d.replace(tzinfo=timezone.utc).isoformat().replace('+00:00','Z')})
def file_meta(db,ids):
    return [public(f,'name','kind','size','mime','safety') for id in ids if (f:=db.get(FileObject,id)) and f.available]
def lesson_view(db,l):
    return {**public(l,'title','starts_at','ends_at','room','units','status','class_id'), 'teacher':db.get(Account,l.teacher_id).name}
def homework_view(db,h,sid):
    s=db.scalar(select(Submission).where(Submission.homework_id==h.id,Submission.student_id==sid).order_by(Submission.revision.desc()))
    return {**public(h,'title','body','due_at','grading_due_at','late_policy'),'teacher':db.get(Account,h.teacher_id).name,'files':file_meta(db,h.attachment_ids),'status':s.status if s else 'todo','grading_overdue':bool(s and s.status=='submitted' and h.grading_due_at and now()>h.grading_due_at),'overdue':bool(h.due_at and now()>h.due_at and (not s or s.status=='returned')),'submission':public(s,'text','status','revision','attachment_ids') if s else None}
def hours_view(db,sid):
    packages=list(db.scalars(select(HourPackage).where(HourPackage.student_id==sid)))
    entries=list(db.scalars(select(HourEntry).where(HourEntry.student_id==sid).order_by(HourEntry.created_at.desc())))
    granted=sum((p.granted for p in packages),Decimal(0)); change=sum((e.amount for e in entries),Decimal(0))
    lessons={e.lesson_id for e in entries if e.lesson_id and sum(x.amount for x in entries if x.lesson_id==e.lesson_id)<0}
    return {'total':float(granted),'consumed':float(-change),'remaining':float(granted+change),'attended_lessons':len(lessons),'packages':[public(p,'name','granted','valid_until') for p in packages],'entries':[{**public(e,'amount','reason','lesson_id','reverses_id'),'lesson':lesson_view(db,db.get(Lesson,e.lesson_id)) if e.lesson_id else None} for e in entries]}

@app.get('/health')
def health(db:DB=Depends(database)):
    db.execute(sqltext('SELECT 1'))
    return {'service':'yeats','status':'ok','environment':settings.environment,'database':db.bind.dialect.name}
@app.post('/v1/auth/wechat')
def login(body:S.Login,db:DB=Depends(database)):
    openid=wechat.identity(body.code)
    identity=db.scalar(select(WechatIdentity).where(WechatIdentity.appid==settings.wechat_appid,WechatIdentity.openid==openid))
    if not identity:
        a=Account(); db.add(a); db.flush()
        identity=WechatIdentity(appid=settings.wechat_appid,openid=openid,account_id=a.id);db.add(identity);db.flush()
    a=db.get(Account,identity.account_id)
    if not a.active: raise HTTPException(403,'账号已停用，请联系机构')
    token=issue_session(db,a,identity.id);audit(db,a,'login');db.commit()
    return {'token':token,'needs_phone':not bool(a.phone)}
@app.post('/v1/auth/phone')
def phone(body:S.Phone,a:Account=Depends(parent),db:DB=Depends(database)):
    identity_openid(db,a)
    verified=wechat.phone(body.code)
    existing=db.scalar(select(Account).where(Account.phone==verified,Account.id!=a.id))
    if existing: raise HTTPException(409,'该手机号已有账号，请联系机构核验归属')
    if a.phone and a.phone!=verified: raise HTTPException(409,'手机号变更须由机构核验后办理')
    relations=list(db.scalars(select(Guardian).where(Guardian.verified_phone==verified,Guardian.active==True)))
    if any(g.account_id and g.account_id!=a.id for g in relations): raise HTTPException(409,'监护关系存在冲突，请联系机构')
    a.phone=verified
    for g in relations: g.account_id=a.id
    audit(db,a,'verify_phone');db.commit()
    return {'linked_students':len(relations)}
@app.post('/v1/auth/logout')
def logout(authorization:str=Header(),a:Account=Depends(parent),db:DB=Depends(database)):
    s=db.scalar(select(Session).where(Session.token_hash==digest(authorization[7:])))
    s.revoked=True;audit(db,a,'logout');db.commit();return {'saved':True}
@app.get('/v1/me')
def me(a:Account=Depends(parent),db:DB=Depends(database)):
    return {'id':a.id,'name':a.name,'phone':a.phone[:5]+'****'+a.phone[-4:] if a.phone else '', 'needs_phone':not bool(a.phone),'subscription_templates':settings.subscription_templates}
@app.put('/v1/me')
def profile(body:S.Profile,a:Account=Depends(parent),db:DB=Depends(database)):
    moderate_text(db,a,body.name);a.name=body.name.strip();audit(db,a,'profile_update');db.commit();return {'saved':True}
@app.post('/v1/me/subscriptions')
def consent(body:S.Consent,a:Account=Depends(parent),db:DB=Depends(database)):
    if any(k not in settings.subscription_templates or v not in ['accept','reject','ban'] for k,v in body.choices.items()): raise HTTPException(422,'订阅参数无效')
    db.add(SubscriptionConsent(account_id=a.id,choices=body.choices));db.commit();return {'saved':True}
@app.get('/v1/students')
def students(a:Account=Depends(parent),db:DB=Depends(database)):
    ids=list(db.scalars(select(Guardian.student_id).where(Guardian.account_id==a.id,Guardian.verified_phone==a.phone,Guardian.active==True))) if a.phone else []
    return [{**public(s,'name','grade'),'remaining':hours_view(db,s.id)['remaining'],'classes':[public(c,'name','campus','room') for c in db.scalars(select(Classroom).where(Classroom.id.in_(class_ids(db,s.id))))]} for s in db.scalars(select(Student).where(Student.id.in_(ids),Student.active==True).order_by(Student.created_at,Student.id))]
@app.get('/v1/content')
def content(kind:str|None=None,db:DB=Depends(database)):
    q=select(Content).where(Content.published==True).order_by(Content.sort,Content.created_at.desc())
    if kind:q=q.where(Content.kind==kind)
    return [{**public(c,'kind','title','text','target'),'files':file_meta(db,c.attachment_ids)} for c in db.scalars(q)]
@app.get('/v1/teachers')
def teachers(db:DB=Depends(database)):
    return [{**public(p,'name','years','specialties','biography'),'files':file_meta(db,[p.avatar_file_id,p.demo_file_id])} for p in db.scalars(select(TeacherProfile).where(TeacherProfile.published==True))]
@app.get('/v1/students/{sid}/home')
def home(sid:str,a:Account=Depends(parent),db:DB=Depends(database)):
    student_access(db,a,sid)
    targets=list(db.scalars(select(HomeworkTarget.homework_id).where(HomeworkTarget.student_id==sid)))
    homework=[homework_view(db,h,sid) for h in db.scalars(select(Homework).where(Homework.id.in_(targets),Homework.published==True).order_by(Homework.created_at.desc()).limit(5))]
    unread=db.scalar(select(func.count()).select_from(Notification).where(Notification.account_id==a.id,Notification.student_id==sid,Notification.read==False))
    notices=list(db.scalars(select(Notification).where(Notification.account_id==a.id,Notification.student_id==sid,Notification.read==False)))
    badges={key:sum(n.kind in kinds for n in notices) for key,kinds in {'homework':['homework','feedback'],'tests':['test'],'recordings':['recording','course'],'knowledge':['knowledge']}.items()}
    recent_tests=[{**public(t,'title','kind','score'),'lesson':lesson_view(db,db.get(Lesson,t.lesson_id))} for t in db.scalars(select(TestResult).where(TestResult.student_id==sid,TestResult.published==True).order_by(TestResult.created_at.desc()).limit(2))]
    return {'hours':hours_view(db,sid),'homework':homework,'tests':recent_tests,'badges':badges,'unread':unread,'today':(now()+timedelta(hours=8)).date().isoformat()}
@app.get('/v1/students/{sid}/hours')
def hours(sid:str,a:Account=Depends(parent),db:DB=Depends(database)):
    student_access(db,a,sid);return hours_view(db,sid)
@app.get('/v1/students/{sid}/attendance')
def attendance(sid:str,a:Account=Depends(parent),db:DB=Depends(database)):
    student_access(db,a,sid)
    return [{**public(r,'status','arrived_at','source','reason'),'lesson':lesson_view(db,db.get(Lesson,r.lesson_id))} for r in db.scalars(select(Attendance).where(Attendance.student_id==sid).order_by(Attendance.created_at.desc()))]
@app.get('/v1/students/{sid}/schedule')
def schedule(sid:str,a:Account=Depends(parent),db:DB=Depends(database)):
    student_access(db,a,sid);ids=class_ids(db,sid)
    classes=[]
    for c in db.scalars(select(Classroom).where(Classroom.id.in_(ids))):
        teachers=[]
        for tc in db.scalars(select(TeacherClass).where(TeacherClass.class_id==c.id)):
            p=db.scalar(select(TeacherProfile).where(TeacherProfile.account_id==tc.account_id,TeacherProfile.published==True))
            teachers.append({'name':db.get(Account,tc.account_id).name,'duty':tc.duty,'profile_id':p.id if p else None})
        classes.append({**public(c,'name','campus','room'),'teachers':teachers,'size':db.scalar(select(func.count()).select_from(Enrollment).where(Enrollment.class_id==c.id,Enrollment.active==True))})
    return {'classes':classes,'lessons':[lesson_view(db,l) for l in db.scalars(select(Lesson).where(Lesson.class_id.in_(ids)).order_by(Lesson.starts_at.desc()).limit(200))]}
@app.get('/v1/students/{sid}/tests')
def tests(sid:str,a:Account=Depends(parent),db:DB=Depends(database)):
    student_access(db,a,sid)
    return [{**public(t,'title','kind','text','score'),'lesson':lesson_view(db,db.get(Lesson,t.lesson_id)),'files':file_meta(db,t.attachment_ids)} for t in db.scalars(select(TestResult).where(TestResult.student_id==sid,TestResult.published==True).order_by(TestResult.created_at.desc()))]
@app.get('/v1/students/{sid}/homework')
def homework_list(sid:str,a:Account=Depends(parent),db:DB=Depends(database)):
    student_access(db,a,sid)
    ids=list(db.scalars(select(HomeworkTarget.homework_id).where(HomeworkTarget.student_id==sid)))
    return [homework_view(db,h,sid) for h in db.scalars(select(Homework).where(Homework.id.in_(ids),Homework.published==True).order_by(Homework.created_at.desc()))]
@app.get('/v1/students/{sid}/homework/{hid}')
def homework_detail(sid:str,hid:str,a:Account=Depends(parent),db:DB=Depends(database)):
    student_access(db,a,sid);h=homework_for(db,sid,hid);data=homework_view(db,h,sid)
    history=[]
    for s in db.scalars(select(Submission).where(Submission.student_id==sid,Submission.homework_id==hid).order_by(Submission.revision.desc())):
        feedback=[{**public(f,'text','grade'),'teacher':db.get(Account,f.teacher_id).name,'files':file_meta(db,f.annotation_file_ids+([f.audio_file_id] if f.audio_file_id else []))} for f in db.scalars(select(Feedback).where(Feedback.submission_id==s.id))]
        history.append({**public(s,'text','status','revision'),'files':file_meta(db,s.attachment_ids),'feedback':feedback})
    return {**data,'history':history,'limits':{'image_bytes':settings.upload_image_bytes,'image_count':settings.upload_image_count,'confirmed':settings.policies_confirmed}}
@app.post('/v1/students/{sid}/homework/{hid}/submissions')
def submit(sid:str,hid:str,body:S.Submit,a:Account=Depends(parent),db:DB=Depends(database)):
    student_access(db,a,sid);h=homework_for(db,sid,hid)
    # Lock target row so concurrent devices cannot create two current submissions.
    db.scalar(select(HomeworkTarget).where(HomeworkTarget.homework_id==hid,HomeworkTarget.student_id==sid).with_for_update())
    request_hash=digest(json.dumps({'sid':sid,'hid':hid,'text':body.text,'files':body.attachment_ids},sort_keys=True))
    previous=db.scalar(select(Submission).where(Submission.parent_id==a.id,Submission.idempotency_key==body.idempotency_key))
    if previous:
        if previous.request_hash!=request_hash: raise HTTPException(409,'重复请求参数不一致')
        return public(previous,'status','revision')
    latest=db.scalar(select(Submission).where(Submission.student_id==sid,Submission.homework_id==hid).order_by(Submission.revision.desc()))
    if latest and latest.status!='returned': raise HTTPException(409,'作业已提交，老师退回后可重新提交')
    if h.due_at and now()>h.due_at and h.late_policy!='allow': raise HTTPException(409,'已超过截止时间，请联系老师确认补交')
    if not body.text.strip() and not body.attachment_ids: raise HTTPException(422,'请填写文字或上传图片')
    if len(body.attachment_ids)>settings.upload_image_count or len(set(body.attachment_ids))!=len(body.attachment_ids): raise HTTPException(422,'图片数量超出限制或存在重复')
    for fid in body.attachment_ids:
        f=db.get(FileObject,fid)
        if not f or f.owner_id!=a.id or f.student_id!=sid or f.kind!='image' or f.safety!='passed' or not f.available: raise HTTPException(422,'附件尚未通过检查或无权使用')
    moderate_text(db,a,body.text)
    s=Submission(homework_id=hid,student_id=sid,parent_id=a.id,text=body.text.strip(),attachment_ids=body.attachment_ids,revision=latest.revision+1 if latest else 1,idempotency_key=body.idempotency_key,request_hash=request_hash)
    db.add(s);db.flush();audit(db,a,'homework_submit',s.id);db.commit();return public(s,'status','revision')
@app.post('/v1/files')
async def upload(student_id:str=Form(),file:UploadFile=File(),a:Account=Depends(parent),db:DB=Depends(database)):
    student_access(db,a,student_id)
    data=await file.read(settings.upload_image_bytes+1)
    if len(data)>settings.upload_image_bytes: raise HTTPException(413,'图片超过大小上限')
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in ['JPEG','PNG','WEBP'] or img.width*img.height>40_000_000: raise ValueError()
            img.verify()
        with Image.open(io.BytesIO(data)) as img:
            # Strip EXIF/geolocation and polyglot trailers; retain actual pixels.
            buf=io.BytesIO();img.convert('RGB').save(buf,'JPEG',quality=95);clean=buf.getvalue()
    except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError): raise HTTPException(422,'仅支持有效 JPG、PNG 或 WebP 图片') from None
    if settings.environment=='development' and settings.enable_development_login and a.is_test:
        audit(db,a,'development_safety_bypass',detail={'scope':'synthetic_image_only'})
    else:
        identity_openid(db,a);wechat.check_image(clean)
    fid=uid();key=fid+'.jpg';settings.file_root.mkdir(parents=True,exist_ok=True)
    f=FileObject(id=fid,owner_id=a.id,student_id=student_id,kind='image',name='作业图片.jpg',storage_key=key,mime='image/jpeg',size=len(clean),sha256=hashlib.sha256(clean).hexdigest(),safety='passed')
    path=settings.file_root/key
    try:
        store.put(key,clean);db.add(f);audit(db,a,'file_upload',fid);db.commit()
    except Exception:
        store.delete(key);raise
    return public(f,'name','kind','size','safety')
@app.get('/v1/students/{sid}/knowledge')
def knowledge(sid:str,q:str=Query(default='',max_length=100),a:Account=Depends(parent),db:DB=Depends(database)):
    student_access(db,a,sid);items=[];cats={}
    for k in db.scalars(select(Knowledge).where(Knowledge.published==True).order_by(Knowledge.title)):
        if (q.casefold() in (k.title+' '+k.text).casefold()) and knowledge_for(db,sid,k.id):
            path=category_path(db,k.category_id)
            for c in path:cats[c.id]=public(c,'name','level','parent_id','sort')
            items.append({**public(k,'title','text','category_id'),'path':[c.name for c in path],'files':file_meta(db,k.attachment_ids)})
    return {'categories':list(cats.values()),'items':items}
@app.get('/v1/students/{sid}/knowledge/{kid}')
def knowledge_detail(sid:str,kid:str,a:Account=Depends(parent),db:DB=Depends(database)):
    student_access(db,a,sid);k=knowledge_for(db,sid,kid)
    if not k:raise HTTPException(404,'知识内容已下架或无权访问')
    questions=[{**public(q,'text','reply'),'files':file_meta(db,q.reply_files),'teacher':db.get(Account,q.replied_by).name if q.replied_by else ''} for q in db.scalars(select(Question).where(Question.parent_id==a.id,Question.student_id==sid,Question.knowledge_id==kid).order_by(Question.created_at.desc()))]
    return {**public(k,'title','text'),'path':[c.name for c in category_path(db,k.category_id)],'files':file_meta(db,k.attachment_ids),'questions':questions}
@app.post('/v1/students/{sid}/knowledge/{kid}/questions')
def ask(sid:str,kid:str,body:S.Ask,a:Account=Depends(parent),db:DB=Depends(database)):
    student_access(db,a,sid)
    if not knowledge_for(db,sid,kid):raise HTTPException(404,'知识内容已下架或无权访问')
    old=db.scalar(select(Question).where(Question.parent_id==a.id,Question.idempotency_key==body.idempotency_key))
    if old:
        if (old.student_id,old.knowledge_id,old.text)!=(sid,kid,body.text.strip()):raise HTTPException(409,'重复请求参数不一致')
        return {'id':old.id,'saved':True}
    if not body.text.strip():raise HTTPException(422,'请填写问题')
    moderate_text(db,a,body.text)
    q=Question(parent_id=a.id,student_id=sid,knowledge_id=kid,text=body.text.strip(),idempotency_key=body.idempotency_key);db.add(q);db.flush();audit(db,a,'question_create',q.id);db.commit();return {'id':q.id,'saved':True}
@app.get('/v1/students/{sid}/recordings')
def recordings(sid:str,a:Account=Depends(parent),db:DB=Depends(database)):
    student_access(db,a,sid)
    absent=[lesson_view(db,db.get(Lesson,x.lesson_id)) for x in db.scalars(select(Attendance).where(Attendance.student_id==sid,Attendance.status.in_(['absent','leave'])))]
    reqs=[public(r,'lesson_id','status','reason','decision_reason') for r in db.scalars(select(ViewingRequest).where(ViewingRequest.student_id==sid,ViewingRequest.parent_id==a.id).order_by(ViewingRequest.created_at.desc()))]
    grants=[]
    for g in db.scalars(select(ViewingGrant).where(ViewingGrant.student_id==sid).order_by(ViewingGrant.created_at.desc())):
        r=db.get(Recording,g.recording_id)
        grants.append({**public(g,'starts_at','expires_at','revoked','recording_id'),'title':r.title,'available':bool(recording_grant(db,sid,r.id)),'file_id':r.file_id})
    return {'absences':absent,'requests':reqs,'grants':grants}
@app.post('/v1/students/{sid}/lessons/{lid}/viewing-requests')
def apply(sid:str,lid:str,body:S.Apply,a:Account=Depends(parent),db:DB=Depends(database)):
    student_access(db,a,sid)
    att=db.scalar(select(Attendance).where(Attendance.student_id==sid,Attendance.lesson_id==lid,Attendance.status.in_(['absent','leave'])).with_for_update())
    if not att:raise HTTPException(404,'无对应缺课记录')
    old=db.scalar(select(ViewingRequest).where(ViewingRequest.parent_id==a.id,ViewingRequest.idempotency_key==body.idempotency_key))
    if old:
        if (old.student_id,old.lesson_id,old.reason)!=(sid,lid,body.reason):raise HTTPException(409,'重复请求参数不一致')
        return public(old,'status')
    pending=db.scalar(select(ViewingRequest).where(ViewingRequest.student_id==sid,ViewingRequest.lesson_id==lid,ViewingRequest.status=='pending'))
    if pending:raise HTTPException(409,'该课节已有待审核申请')
    moderate_text(db,a,body.reason)
    r=ViewingRequest(parent_id=a.id,student_id=sid,lesson_id=lid,reason=body.reason,idempotency_key=body.idempotency_key);db.add(r);db.flush();audit(db,a,'viewing_request',r.id);db.commit();return public(r,'status')
@app.post('/v1/students/{sid}/recordings/{rid}/watch')
def watch(sid:str,rid:str,body:S.Watch,a:Account=Depends(parent),db:DB=Depends(database)):
    student_access(db,a,sid)
    if not recording_grant(db,sid,rid):raise HTTPException(403,'观看权限已到期或未开通')
    audit(db,a,'recording_watch',rid,{'student_id':sid,'reported_seconds':body.seconds});db.commit();return {'saved':True}
@app.get('/v1/students/{sid}/notifications')
def notifications(sid:str,a:Account=Depends(parent),db:DB=Depends(database)):
    student_access(db,a,sid)
    return [public(n,'kind','title','text','read','resource_id') for n in db.scalars(select(Notification).where(Notification.account_id==a.id,Notification.student_id==sid).order_by(Notification.created_at.desc()))]
@app.post('/v1/students/{sid}/notifications/read')
def read_all(sid:str,a:Account=Depends(parent),db:DB=Depends(database)):
    student_access(db,a,sid)
    for n in db.scalars(select(Notification).where(Notification.account_id==a.id,Notification.student_id==sid)):n.read=True
    db.commit();return {'saved':True}
@app.post('/v1/students/{sid}/notifications/{nid}/read')
def read_one(sid:str,nid:str,a:Account=Depends(parent),db:DB=Depends(database)):
    student_access(db,a,sid);n=db.get(Notification,nid)
    if not n or n.account_id!=a.id or n.student_id!=sid:raise HTTPException(404,'通知不存在')
    n.read=True;db.commit();return {'saved':True}
@app.post('/v1/files/{fid}/tickets')
def ticket(fid:str,body:S.Ticket,a:Account=Depends(parent),db:DB=Depends(database)):
    f=db.get(FileObject,fid)
    if not can_file(db,a,f,body.student_id):raise HTTPException(404,'文件不可访问')
    if f.kind=='video' and body.purpose!='play':raise HTTPException(403,'视频仅可在线播放')
    token=secrets.token_urlsafe(32)
    t=FileTicket(token_hash=digest(token),file_id=f.id,account_id=a.id,student_id=body.student_id,purpose=body.purpose,expires_at=now()+timedelta(minutes=5));db.add(t);audit(db,a,'file_'+body.purpose,f.id);db.commit()
    return {'url':settings.public_base_url+'/v1/media/'+token,'expires_in':300,'kind':f.kind,'name':f.name}
@app.get('/v1/media/{token}')
def media(token:str,db:DB=Depends(database)):
    t=db.scalar(select(FileTicket).where(FileTicket.token_hash==digest(token),FileTicket.expires_at>now()))
    if not t:raise HTTPException(403,'链接已失效，请重新打开')
    a=db.get(Account,t.account_id);f=db.get(FileObject,t.file_id)
    if not a or not a.active or not can_file(db,a,f,t.student_id):raise HTTPException(403,'资源权限已变更')
    try:path=store.path(f.storage_key)
    except ValueError:raise HTTPException(404,'文件暂不可用') from None
    if not path.is_file():raise HTTPException(404,'文件暂不可用')
    return FileResponse(path,media_type=f.mime,filename=f.name,content_disposition_type='attachment' if t.purpose=='download' else 'inline')
