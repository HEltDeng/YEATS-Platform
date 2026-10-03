import io,uuid
from PIL import Image
from sqlalchemy import select,delete
from yeats.models import Account,TeacherClass
from yeats.security import issue_session
from conftest import auth

def test_private_parent_attachment_checks_teacher_scope_on_every_use(setup):
    c,db,t=setup;image=io.BytesIO();Image.new('RGB',(20,20),'orange').save(image,'PNG')
    r=c.post('/v1/files',headers=auth(t),data={'student_id':'student-1'},files={'file':('test-private.png',image.getvalue(),'image/png')});assert r.status_code==200;fid=r.json()['id']
    s=c.post('/v1/students/student-1/homework/homework-1/submissions',headers=auth(t),json={'text':'私有图片权限测试','attachment_ids':[fid],'idempotency_key':str(uuid.uuid4())});assert s.status_code==200
    other=Account(id='test-other-teacher',name='测试隔离老师',role='teacher',is_test=True);db.add(other);db.flush();t['other']=issue_session(db,other);db.commit()
    endpoint='/v1/staff/files/'+fid+'/tickets'
    assert c.post(endpoint,headers=auth(t,'other'),json={'purpose':'preview'}).status_code==404
    assert c.post('/v1/files/'+fid+'/tickets',headers=auth(t,'test-parent-b'),json={'purpose':'preview','student_id':'student-3'}).status_code==404
    allowed=c.post(endpoint,headers=auth(t,'test-teacher'),json={'purpose':'preview'});assert allowed.status_code==200
    media='/v1/media/'+allowed.json()['url'].rsplit('/',1)[-1];assert c.get(media).status_code==200
    db.execute(delete(TeacherClass).where(TeacherClass.account_id=='test-teacher',TeacherClass.class_id=='class-1'));db.commit()
    assert c.get(media).status_code==403
