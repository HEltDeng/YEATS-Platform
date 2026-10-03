import io,uuid,csv
from PIL import Image
import pytest
from sqlalchemy import select,func
from conftest import auth
from yeats.models import Account,TeacherClass,TestResult,KnowledgeChangeRequest,Feedback,Submission,Audit
from yeats.security import issue_session
from test_staff import publish,key

def parent_image(c,t,persona='test-parent-a',student='student-1'):
    b=io.BytesIO();Image.new('RGB',(24,24),'orange').save(b,'PNG')
    r=c.post('/v1/files',headers=auth(t,persona),data={'student_id':student},files={'file':('controlled.png',b.getvalue(),'image/png')});assert r.status_code==200;return r.json()['id']

@pytest.mark.parametrize('rule,bad_text,bad_images,good_text,good_images',[('images','文字不能替代图片',False,'',True),('images_text','',True,'图片说明',True),('text','说明',True,'只有文字',False),('image_or_text','',False,'旧作业兼容',False)])
def test_submission_policy_parent_contract_and_server_enforcement(setup,rule,bad_text,bad_images,good_text,good_images):
    c,db,t=setup;fid=parent_image(c,t)
    h,_=publish(c,t,submission_requirement=rule,submission_instructions='受控提交说明');assert h.status_code==200
    path='/v1/students/student-1/homework/'+h.json()['id']
    detail=c.get(path,headers=auth(t)).json();assert detail['submission_requirement']==rule;assert detail['submission_instructions']=='受控提交说明'
    assert c.post(path+'/submissions',headers=auth(t),json={'text':bad_text,'attachment_ids':[fid] if bad_images else [],'idempotency_key':key()}).status_code==422
    assert c.post(path+'/submissions',headers=auth(t),json={'text':good_text,'attachment_ids':[fid] if good_images else [],'idempotency_key':key()}).status_code==200

def test_batch_grade_atomic_permissions_and_idempotency(setup):
    c,db,t=setup;h,_=publish(c,t,student_ids=['student-1','student-3']);assert h.status_code==200
    ids=[]
    for student,persona in [('student-1','test-parent-a'),('student-3','test-parent-b')]:
        s=c.post('/v1/students/'+student+'/homework/'+h.json()['id']+'/submissions',headers=auth(t,persona),json={'text':'受控批量提交','idempotency_key':key()});assert s.status_code==200;ids.append(s.json()['id'])
    body={'submission_ids':[ids[0],'unknown-id'],'text':'统一评语','grade':'B','key':key()}
    assert c.post('/v1/staff/submissions/batch-grade',headers=auth(t,'test-teacher'),json=body).status_code==404
    db.expire_all();assert db.get(Submission,ids[0]).status=='submitted'
    body.update(submission_ids=ids,key=key());r=c.post('/v1/staff/submissions/batch-grade',headers=auth(t,'test-teacher'),json=body);assert r.status_code==200;assert r.json()['count']==2
    assert c.post('/v1/staff/submissions/batch-grade',headers=auth(t,'test-teacher'),json=body).status_code==200
    assert db.scalar(select(func.count()).select_from(Feedback).where(Feedback.submission_id.in_(ids)))==2

def test_batch_scores_preserve_media_and_reject_foreign_student(setup):
    c,db,t=setup;teacher=auth(t,'test-teacher');before=db.scalar(select(TestResult).where(TestResult.student_id=='student-1',TestResult.kind=='entry'));old=before.score
    body={'lesson_id':'lesson-1','kind':'entry','title':'批量测试','rows':[{'student_id':'student-1','score':'91','text':'完整句子'},{'student_id':'student-2','score':'92'}],'key':key()}
    assert c.post('/v1/staff/tests/batch',headers=teacher,json=body).status_code==404;db.expire_all();assert db.get(TestResult,before.id).score==old
    body['rows'][1]['student_id']='student-3';body['key']=key();r=c.post('/v1/staff/tests/batch',headers=teacher,json=body);assert r.status_code==200;assert r.json()['created']==1 and r.json()['updated']==1
    assert c.post('/v1/staff/tests/batch',headers=teacher,json=body).json()['ids']==r.json()['ids']
    db.expire_all();assert db.get(TestResult,before.id).attachment_ids==['file-image','file-audio']
    history=c.get('/v1/staff/test-history?class_id=class-1&student_id=student-3',headers=teacher);assert history.status_code==200;assert len(history.json())==1
    assert c.get('/v1/staff/test-history?class_id=class-2&student_id=student-1',headers=teacher).status_code==404

def test_private_change_request_receipt_role_and_persistence(setup):
    c,db,t=setup;teacher=auth(t,'test-teacher');body={'category_id':'category-7','knowledge_id':'knowledge-1','change_type':'correction','title':'测试申请','text':'请核对词表','attachment_ids':[],'key':key()}
    invalid={**body,'change_type':'new','knowledge_id':'unknown-id','key':key()}
    assert c.post('/v1/staff/knowledge/change-requests',headers=teacher,json=invalid).status_code==422
    r=c.post('/v1/staff/knowledge/change-requests',headers=teacher,json=body);assert r.status_code==200;rid=r.json()['id']
    assert c.post('/v1/staff/knowledge/change-requests',headers=teacher,json=body).json()['id']==rid
    a=Account(id='test-request-other',name='测试老师乙',role='teacher',is_test=True);db.add(a);db.flush();t['other']=issue_session(db,a);db.commit()
    assert c.get('/v1/staff/knowledge/change-requests',headers=auth(t,'other')).json()==[]
    assert c.get('/v1/staff/knowledge/change-requests/'+rid,headers=auth(t,'other')).status_code==404
    receipt={'status':'resolved','response':'测试平台回执：已核对，无需修改。','key':key()}
    route='/v1/admin/knowledge-change-requests/'+rid+'/receipt'
    assert c.post(route,headers=teacher,json=receipt).status_code==403
    assert c.post(route,headers=auth(t,'test-admin'),json=receipt).status_code==200
    assert c.post(route,headers=auth(t,'test-admin'),json=receipt).status_code==200
    detail=c.get('/v1/staff/knowledge/change-requests/'+rid,headers=teacher).json();assert detail['status']=='resolved';assert detail['response']==receipt['response'];assert detail['processed_at']

def test_exports_scope_csv_injection_and_audit(setup):
    c,db,t=setup;teacher=auth(t,'test-teacher')
    from yeats.models import Question
    q=db.scalar(select(Question));q.text='=HYPERLINK("invalid")';db.commit()
    for kind in ['students','tests','questions','weekly','student-detail']:
        response=c.get('/v1/staff/exports/'+kind+'?class_id=class-1&student_id=student-1',headers=teacher);assert response.status_code==200;assert 'text/csv' in response.headers['content-type'];assert 'no-store'==response.headers['cache-control']
    exported=c.get('/v1/staff/exports/questions?class_id=class-1',headers=teacher).text
    assert next(csv.reader(io.StringIO(exported.lstrip('\ufeff'))))[0]=='学员'
    assert "'=HYPERLINK" in exported
    assert db.scalar(select(Audit).where(Audit.action=='teacher_export'))
    assert c.get('/v1/staff/exports/student-detail?class_id=class-2&student_id=student-1',headers=teacher).status_code==404
    assert c.get('/v1/staff/exports/students?class_id=class-1',headers=auth(t)).status_code==403
