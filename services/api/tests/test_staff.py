import uuid
from sqlalchemy import select
from yeats.models import Account,TeacherClass,Question,Audit
from yeats.security import issue_session
from yeats.staff import password_hash,verify_password
from conftest import auth

def key():return str(uuid.uuid4())
def publish(c,t,**kw):
    body={'title':'测试网页联调作业','body':'明确测试内容','class_ids':['class-1'],'student_ids':['student-1'],'attachment_ids':[],'late_policy':'allow','key':key(),**kw}
    return c.post('/v1/staff/homework',headers=auth(t,'test-teacher'),json=body),body
def test_teacher_role_class_and_file_isolation(setup):
    c,db,t=setup
    assert c.get('/v1/staff/classes').status_code==401
    assert c.get('/v1/staff/classes',headers=auth(t)).status_code==403
    other=Account(id='scope-other',role='teacher',name='测试隔离老师',is_test=True);db.add(other);db.flush();t['other']=issue_session(db,other);db.commit()
    assert c.get('/v1/staff/classes',headers=auth(t,'other')).json()==[]
    assert c.get('/v1/staff/classes/class-1/students',headers=auth(t,'other')).status_code==404
    assert c.get('/v1/staff/homework/homework-2/students/student-1',headers=auth(t,'other')).status_code==404
    # Shared platform knowledge remains available even to a teacher with no student grants.
    assert len(c.get('/v1/staff/knowledge',headers=auth(t,'other')).json()['items'])==1
    r=c.post('/v1/staff/files/file-image/tickets',headers=auth(t,'other'),json={'purpose':'preview'})
    assert r.status_code==200
    assert c.post('/v1/staff/homework',headers=auth(t,'other'),json={'title':'x','body':'x','class_ids':['class-1'],'late_policy':'allow','key':key()}).status_code==404
def test_homework_real_api_cycle_idempotency_and_revocation(setup):
    c,db,t=setup;h,body=publish(c,t);assert h.status_code==200;hid=h.json()['id']
    assert c.post('/v1/staff/homework',headers=auth(t,'test-teacher'),json=body).json()['id']==hid
    body['title']='changed';assert c.post('/v1/staff/homework',headers=auth(t,'test-teacher'),json=body).status_code==409
    path='/v1/students/student-1/homework/'+hid
    assert c.get(path,headers=auth(t)).status_code==200
    assert c.get(path,headers=auth(t,'test-parent-b')).status_code==404
    s=c.post(path+'/submissions',headers=auth(t),json={'text':'第一次测试','attachment_ids':[],'idempotency_key':key()}).json()
    g={'text':'请补充内容','returned':True,'key':key()}
    assert c.post('/v1/staff/submissions/'+s['id']+'/grade',headers=auth(t,'test-teacher'),json=g).status_code==200
    assert c.post('/v1/staff/submissions/'+s['id']+'/grade',headers=auth(t,'test-teacher'),json=g).status_code==200
    s2=c.post(path+'/submissions',headers=auth(t),json={'text':'重交测试','attachment_ids':[],'idempotency_key':key()}).json();assert s2['revision']==2
    assert c.post('/v1/staff/submissions/'+s2['id']+'/grade',headers=auth(t,'test-teacher'),json={'text':'测试反馈已保存','grade':'A','key':key()}).status_code==200
    detail=c.get(path,headers=auth(t)).json();assert detail['history'][0]['status']=='graded';assert len(detail['history'])==2
    assert c.post('/v1/staff/auth/logout',headers=auth(t,'test-teacher')).status_code==200
    assert c.get('/v1/staff/me',headers=auth(t,'test-teacher')).status_code==401
def test_private_question_and_library_reference(setup):
    c,db,t=setup
    q=c.post('/v1/students/student-1/knowledge/knowledge-1/questions',headers=auth(t),json={'text':'测试新问题','idempotency_key':key()}).json()
    questions=c.get('/v1/staff/questions?class_id=class-1',headers=auth(t,'test-teacher')).json();qid=next(x['id'] for x in questions if x['text']=='测试新问题')
    assert c.post('/v1/staff/questions/'+qid+'/reply',headers=auth(t,'test-teacher'),json={'text':'老师测试答复','key':key()}).status_code==200
    assert any(x['reply']=='老师测试答复' for x in c.get('/v1/students/student-1/knowledge/knowledge-1',headers=auth(t)).json()['questions'])
    assert not any(x['text']=='测试新问题' for x in c.get('/v1/students/student-3/knowledge/knowledge-1',headers=auth(t,'test-parent-b')).json()['questions'])
    assert c.post('/v1/staff/classes/class-1/references',headers=auth(t,'test-teacher'),json={'knowledge_ids':['knowledge-1'],'active':False,'key':key()}).status_code==200
    assert c.get('/v1/students/student-1/knowledge/knowledge-1',headers=auth(t)).status_code==404
def test_tests_attendance_and_audit(setup):
    c,db,t=setup;teacher=auth(t,'test-teacher')
    body={'student_id':'student-1','lesson_id':'lesson-1','kind':'exit','title':'受控测试','text':'测试结果','score':'90','key':key()}
    r=c.post('/v1/staff/tests',headers=teacher,json=body);assert r.status_code==200
    body.update(published=False,key=key());assert c.put('/v1/staff/tests/'+r.json()['id'],headers=teacher,json=body).status_code==200
    assert r.json()['id'] not in [x['id'] for x in c.get('/v1/students/student-1/tests',headers=auth(t)).json()]
    attendance={'student_id':'student-1','package_id':'package-1','arrived_at':'2026-10-03T02:00:00Z','reason':'受控补签测试','key':key()}
    assert c.post('/v1/staff/lessons/lesson-2/attendance',headers=teacher,json=attendance).status_code==200
    assert c.post('/v1/staff/lessons/lesson-2/attendance',headers=teacher,json=attendance).status_code==200
    assert db.scalar(select(Audit).where(Audit.action=='attendance_change'))
def test_password_hash_and_production_test_login_disabled(setup,monkeypatch):
    from yeats.config import settings
    c,db,t=setup;p=password_hash('test-strong-password');assert verify_password('test-strong-password',p);assert not verify_password('wrong',p)
    a=db.get(Account,'test-teacher');a.password_hash=p;db.commit()
    monkeypatch.setattr(settings,'environment','production')
    assert c.post('/v1/staff/auth/login',json={'account':a.id,'password':'test-strong-password'}).status_code==401
    assert c.get('/v1/staff/me',headers=auth(t,'test-teacher')).status_code==403

def test_attachment_only_content_and_required_return_reason(setup):
    import io
    from PIL import Image
    c,db,t=setup;teacher=auth(t,'test-teacher')
    image=io.BytesIO();Image.new('RGB',(16,16),'orange').save(image,'PNG')
    uploaded=c.post('/v1/staff/files',headers=teacher,files={'file':('controlled.png',image.getvalue(),'image/png')})
    assert uploaded.status_code==200;fid=uploaded.json()['id']
    h,_=publish(c,t,body='',attachment_ids=[fid]);assert h.status_code==200
    empty,_=publish(c,t,body='',attachment_ids=[]);assert empty.status_code==422
    sub=c.post('/v1/students/student-1/homework/'+h.json()['id']+'/submissions',headers=auth(t),json={'text':'受控提交','attachment_ids':[],'idempotency_key':key()})
    assert sub.status_code==200;endpoint='/v1/staff/submissions/'+sub.json()['id']+'/grade'
    assert c.post(endpoint,headers=teacher,json={'returned':True,'annotation_ids':[fid],'key':key()}).status_code==422
    assert c.post(endpoint,headers=teacher,json={'annotation_ids':[fid],'key':key()}).status_code==200
    q=c.post('/v1/students/student-1/knowledge/knowledge-1/questions',headers=auth(t),json={'text':'附件答复测试','idempotency_key':key()})
    assert q.status_code==200
    qid=next(x['id'] for x in c.get('/v1/staff/questions?class_id=class-1',headers=teacher).json() if x['text']=='附件答复测试')
    assert c.post('/v1/staff/questions/'+qid+'/reply',headers=teacher,json={'attachment_ids':[fid],'key':key()}).status_code==200
    detail=c.get('/v1/students/student-1/knowledge/knowledge-1',headers=auth(t)).json()
    answer=next(x for x in detail['questions'] if x['id']==qid)
    assert len(answer['files'])==1
