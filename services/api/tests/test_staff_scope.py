import uuid
from sqlalchemy import select
from conftest import auth
from yeats.models import Account,TeacherClass,Question,Knowledge,Category,Audit
from yeats.security import issue_session

def test_teacher_direct_ids_across_modules_and_shared_library(setup):
    c,db,t=setup
    a=Account(id='test-class2-teacher',name='测试另一班老师',role='teacher',is_test=True)
    db.add(a);db.flush();db.add(TeacherClass(account_id=a.id,class_id='class-2'));t['class2']=issue_session(db,a);db.commit()
    headers=auth(t,'class2')
    for path in ['/classes/class-1/students','/classes/class-1/students/student-1','/classes/class-2/students/student-1','/lessons?class_id=class-1','/tests?lesson_id=lesson-1','/lessons/lesson-1/attendance','/homework?class_id=class-1','/homework/homework-2/students/student-1','/questions?class_id=class-1']:
        assert c.get('/v1/staff'+path,headers=headers).status_code==404,path
    assert c.get('/v1/staff/questions?class_id=class-2',headers=headers).json()==[]
    q=db.scalar(select(Question))
    assert c.post('/v1/staff/questions/'+q.id+'/reply',headers=headers,json={'text':'不得写入','key':str(uuid.uuid4())}).status_code==404
    assert c.post('/v1/staff/submissions/submission-graded/grade',headers=headers,json={'text':'不得写入','key':str(uuid.uuid4())}).status_code==404
    assert c.post('/v1/staff/classes/class-1/references',headers=headers,json={'knowledge_ids':['knowledge-1'],'active':False,'key':str(uuid.uuid4())}).status_code==404
    assert c.post('/v1/staff/lessons/lesson-1/attendance',headers=headers,json={'student_id':'student-1','package_id':'package-1','arrived_at':'2026-10-03T02:00:00Z','reason':'不得写入','key':str(uuid.uuid4())}).status_code==404
    # Shared content is global read-only even for a teacher who does not teach class-1.
    library=c.get('/v1/staff/knowledge',headers=headers).json()
    assert any(k['id']=='knowledge-1' for k in library['items'])
    assert next(k for k in library['items'] if k['id']=='knowledge-1')['references']==[]
    assert c.post('/v1/staff/files/file-image/tickets',headers=headers,json={'purpose':'download'}).status_code==200
    assert db.scalar(select(Audit).where(Audit.actor_id==a.id,Audit.action=='staff_file_download'))

def test_library_changes_unpublish_and_category_disable_in_shared_view(setup):
    c,db,t=setup;headers=auth(t,'test-teacher')
    initial=c.get('/v1/staff/knowledge',headers=headers).json()['items'][0]['version']
    k=db.get(Knowledge,'knowledge-1');k.text='仅隔离测试事务中的变更';db.commit()
    assert c.get('/v1/staff/knowledge',headers=headers).json()['items'][0]['version']!=initial
    k.published=False;db.commit()
    data=c.get('/v1/staff/knowledge',headers=headers).json();assert data['items']==[];assert data['unavailable_references'][0]['id']==k.id
    assert c.post('/v1/staff/classes/class-1/references',headers=headers,json={'knowledge_ids':[k.id],'active':True,'key':str(uuid.uuid4())}).status_code==422
    k.published=True;db.get(Category,'category-1').active=False;db.commit()
    assert c.get('/v1/staff/knowledge',headers=headers).json()['items']==[]
    assert c.get('/v1/students/student-1/knowledge/knowledge-1',headers=auth(t)).status_code==404
