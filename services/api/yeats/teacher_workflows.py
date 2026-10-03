"""Atomic teacher batch operations, scoped exports and knowledge-change receipts."""
from datetime import date,datetime,timedelta
import csv,io
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import Response
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DB
from .models import *
from .db import database
from .security import principal,audit
from . import staff as S
from .operations import grade_submission,notify

router=APIRouter(prefix='/v1/staff',tags=['teacher-workflows'])
receipt_router=APIRouter(prefix='/v1/admin/knowledge-change-requests',tags=['knowledge-change-receipts'])
class BatchGrade(S.Input):
    submission_ids:list[str]=Field(min_length=1,max_length=100)
    text:str=Field(min_length=1,max_length=4000)
    grade:str=Field(default='',max_length=40)
    key:str=Field(min_length=16,max_length=80)

@router.post('/submissions/batch-grade')
def batch_grade(body:BatchGrade,a:Account=Depends(S.teacher),db:DB=Depends(database)):
    if not body.text.strip() or len(set(body.submission_ids))!=len(body.submission_ids):raise HTTPException(422,'请填写评语并选择不重复的提交')
    payload={'action':'batch_grade',**body.model_dump()};previous=S.begin(db,a,body.key,payload)
    if previous:return previous
    rows=[]
    for sid in sorted(body.submission_ids):
        row=db.scalar(select(Submission).where(Submission.id==sid).with_for_update())
        if not row or db.get(Homework,row.homework_id).teacher_id!=a.id:raise HTTPException(404,'提交不存在或无权批改')
        S.student_scope(db,a,row.student_id)
        if row.status!='submitted':raise HTTPException(409,'所选提交已被处理，请刷新后重新选择')
        rows.append(row)
    for row in rows:grade_submission(db,a,row.id,body.text.strip(),body.grade)
    audit(db,a,'batch_homework_grade',detail={'submission_ids':body.submission_ids})
    return S.done(db,a,body.key,payload,{'saved':True,'count':len(rows)})

class ScoreRow(S.Input):
    student_id:str
    score:str=Field(min_length=1,max_length=80)
    text:str=Field(default='',max_length=4000)
class BatchTests(S.Input):
    lesson_id:str
    kind:str=Field(pattern='^(entry|exit)$')
    title:str=Field(min_length=1,max_length=200)
    rows:list[ScoreRow]=Field(min_length=1,max_length=200)
    key:str=Field(min_length=16,max_length=80)

@router.post('/tests/batch')
def batch_tests(body:BatchTests,a:Account=Depends(S.teacher),db:DB=Depends(database)):
    lesson=S.lesson_scope(db,a,body.lesson_id)
    ids=[r.student_id for r in body.rows]
    if len(set(ids))!=len(ids):raise HTTPException(422,'同一批次学员不可重复')
    if not body.title.strip() or any(not r.score.strip() for r in body.rows):raise HTTPException(422,'标题或成绩为空')
    for sid in ids:S.student_scope(db,a,sid,lesson.class_id)
    payload={'action':'batch_tests',**body.model_dump()};previous=S.begin(db,a,body.key,payload)
    if previous:return previous
    # Serialize batches and individual results for the same lesson.
    db.scalar(select(Lesson).where(Lesson.id==lesson.id).with_for_update())
    saved=[];created=0;updated=0;by_student={}
    for sid in ids:
        existing=list(db.scalars(select(TestResult).where(TestResult.lesson_id==lesson.id,TestResult.student_id==sid,TestResult.kind==body.kind).with_for_update()))
        if len(existing)>1:raise HTTPException(409,'部分学员存在多条同类型结果，请逐条维护后再导入')
        by_student[sid]=existing
    for item in body.rows:
        existing=by_student[item.student_id]
        row=existing[0] if existing else TestResult(student_id=item.student_id,lesson_id=lesson.id,kind=body.kind,attachment_ids=[])
        before={'title':row.title,'score':row.score,'text':row.text,'published':row.published} if existing else None
        if existing:updated+=1
        else:db.add(row);created+=1
        row.title=body.title.strip();row.score=item.score.strip();row.text=item.text;row.published=True
        db.flush();audit(db,a,'test_batch_upsert',row.id,{'before':before,'attachments_preserved':bool(existing)})
        notify(db,row.student_id,'test','随堂测试已发布',row.id);saved.append(row.id)
    return S.done(db,a,body.key,payload,{'saved':True,'ids':saved,'created':created,'updated':updated})

@router.get('/test-history')
def test_history(class_id:str,student_id:str|None=None,lesson_id:str|None=None,a:Account=Depends(S.teacher),db:DB=Depends(database)):
    S.scope(db,a,class_id)
    if student_id:S.student_scope(db,a,student_id,class_id)
    lessons={l.id:l for l in db.scalars(select(Lesson).where(Lesson.class_id==class_id))}
    if lesson_id and lesson_id not in lessons:raise HTTPException(404)
    query=select(TestResult).where(TestResult.lesson_id.in_(lessons)).order_by(TestResult.created_at.desc())
    if student_id:query=query.where(TestResult.student_id==student_id)
    if lesson_id:query=query.where(TestResult.lesson_id==lesson_id)
    return [{**S.test_view(db,t),'lesson':S.lesson_view(db,lessons[t.lesson_id])} for t in db.scalars(query)]

class Change(S.Input):
    category_id:str|None=None
    knowledge_id:str|None=None
    change_type:str=Field(pattern='^(new|correction|unpublish)$')
    title:str=Field(min_length=1,max_length=200)
    text:str=Field(min_length=1,max_length=4000)
    attachment_ids:list[str]=Field(default_factory=list,max_length=10)
    key:str=Field(min_length=16,max_length=80)
def change_view(db,row):
    cat=db.get(Category,row.category_id) if row.category_id else None
    knowledge=db.get(Knowledge,row.knowledge_id) if row.knowledge_id else None
    return {**S.view(row,'category_id','knowledge_id','change_type','title','text','status','response','processed_at'),'category':cat.name if cat else '', 'knowledge':knowledge.title if knowledge else '', 'files':S.files(db,row.attachment_ids)}

@router.post('/knowledge/change-requests')
def change_request(body:Change,a:Account=Depends(S.teacher),db:DB=Depends(database)):
    if not body.text.strip() or not body.title.strip():raise HTTPException(422,'请填写知识点名称及变更说明')
    if body.category_id and not S.category_path(db,body.category_id):raise HTTPException(422,'分类不可用')
    k=db.get(Knowledge,body.knowledge_id) if body.knowledge_id else None
    if body.knowledge_id and not k:raise HTTPException(422,'所选知识点不存在，请刷新后重选')
    if body.change_type!='new' and not k:raise HTTPException(422,'请选择需要修改或下架的知识点')
    if k and body.category_id and k.category_id!=body.category_id:raise HTTPException(422,'知识点与分类不一致')
    if body.change_type=='new' and not body.category_id:raise HTTPException(422,'请选择所属分类')
    S.attachments(db,a,body.attachment_ids,('image',))
    payload={'action':'knowledge_change',**body.model_dump()};previous=S.begin(db,a,body.key,payload)
    if previous:return previous
    row=KnowledgeChangeRequest(teacher_id=a.id,category_id=body.category_id or (k.category_id if k else None),knowledge_id=body.knowledge_id,change_type=body.change_type,title=body.title.strip(),text=body.text.strip(),attachment_ids=body.attachment_ids,status='pending',response='')
    db.add(row);db.flush();audit(db,a,'knowledge_change_request',row.id,{'change_type':body.change_type})
    return S.done(db,a,body.key,payload,{'saved':True,'id':row.id,'status':row.status})
@router.get('/knowledge/change-requests')
def changes(a:Account=Depends(S.teacher),db:DB=Depends(database)):
    return [change_view(db,r) for r in db.scalars(select(KnowledgeChangeRequest).where(KnowledgeChangeRequest.teacher_id==a.id).order_by(KnowledgeChangeRequest.created_at.desc()))]
@router.get('/knowledge/change-requests/{rid}')
def change_detail(rid:str,a:Account=Depends(S.teacher),db:DB=Depends(database)):
    row=db.get(KnowledgeChangeRequest,rid)
    if not row or row.teacher_id!=a.id:raise HTTPException(404)
    return change_view(db,row)

def admin(a:Account=Depends(principal)):
    if a.role!='admin':raise HTTPException(403,'仅平台管理员可处理内容变更申请')
    return a
class Receipt(S.Input):
    status:str=Field(pattern='^(resolved|rejected)$')
    response:str=Field(min_length=1,max_length=4000)
    key:str=Field(min_length=16,max_length=80)
@receipt_router.get('')
def admin_changes(a:Account=Depends(admin),db:DB=Depends(database)):
    return [{**change_view(db,r),'teacher_id':r.teacher_id} for r in db.scalars(select(KnowledgeChangeRequest).order_by(KnowledgeChangeRequest.created_at.desc()))]
@receipt_router.post('/{rid}/receipt')
def receipt(rid:str,body:Receipt,a:Account=Depends(admin),db:DB=Depends(database)):
    if not body.response.strip():raise HTTPException(422,'请填写处理回执')
    payload={'action':'change_receipt','id':rid,**body.model_dump()};previous=S.begin(db,a,body.key,payload)
    if previous:return previous
    row=db.scalar(select(KnowledgeChangeRequest).where(KnowledgeChangeRequest.id==rid).with_for_update())
    if not row:raise HTTPException(404)
    if row.status!='pending':raise HTTPException(409,'申请已经处理')
    row.status=body.status;row.response=body.response.strip();row.processed_by=a.id;row.processed_at=now()
    audit(db,a,'knowledge_change_receipt',rid,{'status':row.status,'response':row.response})
    # Receipt never edits or publishes shared content implicitly.
    return S.done(db,a,body.key,payload,{'saved':True,'id':row.id})

def cell(value):
    text='' if value is None else str(value)
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')) else text
@router.get('/exports/{kind}')
def export(kind:str,class_id:str|None=None,student_id:str|None=None,lesson_id:str|None=None,from_date:date|None=None,to_date:date|None=None,a:Account=Depends(S.teacher),db:DB=Depends(database)):
    if class_id:S.scope(db,a,class_id)
    if kind!='weekly' and not class_id:raise HTTPException(422,'请选择班级')
    rows=[]
    if kind=='students':
        header=['学员ID','姓名','年级','剩余课时','监护联系方式（脱敏）']
        rows=[[s['id'],s['name'],s['grade'],s['remaining'],' / '.join(s['contacts'])] for s in S.students(class_id,a,db)]
    elif kind=='tests':
        header=['课节','上课时间','学员','类型','标题','成绩','说明','发布状态']
        rows=[[t['lesson']['title'],t['lesson']['starts_at'],t['student'],t['kind'],t['title'],t['score'],t['text'],'已发布' if t['published'] else '已撤回'] for t in test_history(class_id,student_id,lesson_id,a,db)]
    elif kind=='questions':
        header=['学员','知识内容','提问时间','问题','答复','答复附件数']
        rows=[[q['student'],q['knowledge'],q['created_at'],q['text'],q['reply'],len(q['files'])] for q in S.questions(class_id,False,a,db)]
    elif kind=='student-detail':
        if not student_id:raise HTTPException(422,'请选择学员')
        d=S.student_detail(class_id,student_id,a,db);header=['学员','记录类型','日期','内容','结果']
        for x in d['hours']:rows.append([d['student']['name'],'课时',x['created_at'],x['reason'],x['amount']])
        for x in d['attendance']:rows.append([d['student']['name'],'签到',x['arrived_at'] or x['created_at'],x['reason'],x['status']])
        for x in d['tests']:rows.append([d['student']['name'],'测试',x['created_at'],x['title'],x['score']])
        for h in d['homework']:
            ss=list(db.scalars(select(Submission).where(Submission.homework_id==h['id'],Submission.student_id==student_id).order_by(Submission.revision)))
            if not ss:rows.append([d['student']['name'],'作业','',h['title'],'未提交'])
            for x in ss:
                fb=list(db.scalars(select(Feedback).where(Feedback.submission_id==x.id)))
                rows.append([d['student']['name'],'作业第'+str(x.revision)+'次',x.created_at,h['title']+' / '+x.text,x.status+' / '+'; '.join(f.grade+' '+f.text for f in fb)])
    elif kind=='weekly':
        today=(now()+timedelta(hours=8)).date();start=from_date or today-timedelta(days=today.weekday());end=to_date or start+timedelta(days=6)
        if end<start or (end-start).days>366:raise HTTPException(422,'导出日期范围无效')
        header=['日期','班级','课节','教室','应到','已签到','补签','缺勤','未签到','入门测已上传','出门测已上传']
        for l in S.lessons(class_id,a,db):
            if not start<=(datetime.fromisoformat(l['starts_at'])+timedelta(hours=8)).date()<=end:continue
            att=S.attendance(l['id'],a,db);ts=S.tests(l['id'],a,db)
            rows.append([l['starts_at'],l['class_name'],l['title'],l['room'],len(att),sum(x['attendance'] and x['attendance']['status']=='present' or False for x in att),sum(x['attendance'] and x['attendance']['status']=='makeup' or False for x in att),sum(x['attendance'] and x['attendance']['status']=='absent' or False for x in att),sum(not x['attendance'] for x in att),len({x['student_id'] for x in ts if x['published'] and x['kind']=='entry'}),len({x['student_id'] for x in ts if x['published'] and x['kind']=='exit'})])
    else:raise HTTPException(404)
    out=io.StringIO();writer=csv.writer(out);writer.writerow(header);writer.writerows([[cell(v) for v in row] for row in rows])
    audit(db,a,'teacher_export',detail={'kind':kind,'class_id':class_id,'student_id':student_id,'row_count':len(rows)});db.commit()
    return Response('\ufeff'+out.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="yeats-'+kind+'.csv"','Cache-Control':'no-store'})
