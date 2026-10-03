import io
from datetime import timedelta
from PIL import Image
import pytest
from fastapi import HTTPException
from sqlalchemy import select,func
from yeats.models import *
from yeats.security import digest
from yeats.operations import record_attendance,ingest_normalized_event,grade_submission,approve_viewing
from yeats.config import settings
from yeats.wechat import wechat
from conftest import auth

def test_role_and_direct_id_access(setup):
 c,db,t=setup
 assert c.get('/v1/students').status_code==401
 assert len(c.get('/v1/students',headers=auth(t)).json())==2
 assert len(c.get('/v1/students',headers=auth(t,'test-parent-b')).json())==1
 assert c.get('/v1/students',headers=auth(t,'test-unlinked')).json()==[]
 for path in ['home','hours','attendance','schedule','tests','homework','knowledge','recordings','notifications']:
  assert c.get('/v1/students/student-1/'+path,headers=auth(t,'test-parent-b')).status_code==404
 assert c.get('/v1/students',headers=auth(t,'test-teacher')).status_code==403

def test_student_switch_all_modules(setup):
 c,db,t=setup
 a=c.get('/v1/students/student-1/homework',headers=auth(t)).json();b=c.get('/v1/students/student-2/homework',headers=auth(t)).json()
 assert {h['id'] for h in a}.isdisjoint({h['id'] for h in b})
 assert c.get('/v1/students/student-2/tests',headers=auth(t)).json()==[]
 assert c.get('/v1/students/student-2/knowledge',headers=auth(t)).json()['items']==[]
 assert c.get('/v1/students/student-2/notifications',headers=auth(t)).json()==[]
 assert c.get('/v1/students/student-2/homework/homework-1',headers=auth(t)).status_code==404

def test_upload_submit_restore_duplicate_and_regrade(setup):
 c,db,t=setup
 im=Image.new('RGB',(10,10),'orange');b=io.BytesIO();im.save(b,'PNG')
 up=c.post('/v1/files',headers=auth(t),data={'student_id':'student-1'},files={'file':('sample.png',b.getvalue(),'image/png')})
 assert up.status_code==200,up.text
 fid=up.json()['id'];payload={'text':'已完成','attachment_ids':[fid],'idempotency_key':'test-submit-once-001'}
 url='/v1/students/student-1/homework/homework-1/submissions'
 first=c.post(url,headers=auth(t),json=payload);assert first.status_code==200,first.text
 assert c.post(url,headers=auth(t),json=payload).json()['id']==first.json()['id']
 assert c.post(url,headers=auth(t),json={**payload,'text':'changed'}).status_code==409
 assert c.post(url,headers=auth(t),json={**payload,'idempotency_key':'test-submit-twice-002'}).status_code==409
 detail=c.get('/v1/students/student-1/homework/homework-1',headers=auth(t)).json()
 assert detail['history'][0]['files'][0]['id']==fid
 grade_submission(db,db.get(Account,'test-teacher'),first.json()['id'],'请重新拍摄',returned=True);db.commit()
 second=c.post(url,headers=auth(t),json={**payload,'idempotency_key':'test-resubmit-once-003'})
 assert second.status_code==200 and second.json()['revision']==2
 assert len(c.get('/v1/students/student-1/homework/homework-1',headers=auth(t)).json()['history'])==2

def test_upload_rejects_spoof_and_cross_student(setup):
 c,db,t=setup
 assert c.post('/v1/files',headers=auth(t),data={'student_id':'student-3'},files={'file':('a.jpg',b'fake','image/jpeg')}).status_code==404
 assert c.post('/v1/files',headers=auth(t),data={'student_id':'student-1'},files={'file':('a.jpg',b'<script>bad</script>','image/jpeg')}).status_code==422
 p={'text':'t','attachment_ids':['file-image'],'idempotency_key':'test-wrong-file-0001'}
 assert c.post('/v1/students/student-1/homework/homework-1/submissions',headers=auth(t),json=p).status_code==422

def test_tickets_recheck_unpublish_category_and_guardian(setup):
 c,db,t=setup
 body={'student_id':'student-1','purpose':'preview'}
 r=c.post('/v1/files/file-audio/tickets',headers=auth(t),json=body);assert r.status_code==200
 url=r.json()['url'].split(':8930')[-1]
 assert c.get(url).status_code==200
 assert c.post('/v1/files/file-audio/tickets',headers=auth(t,'test-parent-b'),json=body).status_code==404
 f=db.get(FileObject,'file-audio');f.available=False;db.commit();assert c.get(url).status_code==403
 f.available=True;db.commit();g=db.scalar(select(Guardian).where(Guardian.account_id=='test-parent-a',Guardian.student_id=='student-1'));g.active=False;db.commit();assert c.get(url).status_code==404

def test_knowledge_tree_private_questions_and_revocation(setup):
 c,db,t=setup
 k=c.get('/v1/students/student-1/knowledge',headers=auth(t)).json()
 assert [x['level'] for x in k['categories']]==list(range(1,8));assert len(k['items'])==1
 assert c.get('/v1/students/student-3/knowledge/knowledge-1',headers=auth(t,'test-parent-b')).json()['questions']==[]
 body={'text':'测试问题','idempotency_key':'test-question-000001'}
 url='/v1/students/student-1/knowledge/knowledge-1/questions'
 r=c.post(url,headers=auth(t),json=body);assert r.status_code==200
 assert c.post(url,headers=auth(t),json=body).json()['id']==r.json()['id']
 db.get(Category,'category-2').active=False;db.commit()
 assert c.get('/v1/students/student-1/knowledge',headers=auth(t)).json()['items']==[]
 assert c.get('/v1/students/student-1/knowledge/knowledge-1',headers=auth(t)).status_code==404

def test_attendance_idempotency_and_compensation(setup):
 c,db,t=setup;a=db.get(Account,'test-admin')
 args=(db,a,'student-1','lesson-3','present','evt-001','package-1')
 assert record_attendance(*args,source='device')=='recorded'
 assert record_attendance(*args,source='device')=='duplicate'
 record_attendance(db,a,'student-1','lesson-3','leave','evt-correction','package-1',reason='已核实请假')
 db.commit();entries=list(db.scalars(select(HourEntry).where(HourEntry.lesson_id=='lesson-3')))
 assert len(entries)==2 and sum(x.amount for x in entries)==0
 assert ingest_normalized_event(db,a,'unmatched-1',None,None,None,None)=='unmatched'
 assert ingest_normalized_event(db,a,'unmatched-1',None,None,None,None)=='duplicate'
 with pytest.raises(HTTPException):record_attendance(db,db.get(Account,'test-parent-a'),'student-1','lesson-3','present','evt-bad','package-1',reason='bad')

def test_application_expiry_and_video_download(setup):
 c,db,t=setup
 url='/v1/students/student-1/lessons/lesson-2/viewing-requests';p={'reason':'申请补看','idempotency_key':'test-viewing-00001'}
 r=c.post(url,headers=auth(t),json=p);assert r.status_code==200
 assert c.post(url,headers=auth(t),json=p).json()['id']==r.json()['id']
 assert c.post(url,headers=auth(t),json={**p,'idempotency_key':'test-viewing-00002'}).status_code==409
 db.add(FileObject(id='video-test',owner_id='test-admin',kind='video',name='test.mp4',storage_key='test.mp4',mime='video/mp4',size=0,sha256='test',safety='passed'));db.flush()
 db.add(Recording(id='recording-test',lesson_id='lesson-2',title='受控录屏',file_id='video-test'));db.flush()
 approve_viewing(db,db.get(Account,'test-admin'),r.json()['id'],'recording-test',now(),now()+timedelta(days=7));db.commit()
 assert c.post('/v1/files/video-test/tickets',headers=auth(t),json={'student_id':'student-1','purpose':'download'}).status_code==403
 assert c.post('/v1/files/video-test/tickets',headers=auth(t),json={'student_id':'student-1','purpose':'play'}).status_code==200
 grant=db.scalar(select(ViewingGrant).where(ViewingGrant.recording_id=='recording-test'));grant.expires_at=now()-timedelta(seconds=1);db.commit()
 assert c.post('/v1/files/video-test/tickets',headers=auth(t),json={'student_id':'student-1','purpose':'play'}).status_code==404
 assert c.post('/v1/students/student-1/recordings/recording-test/watch',headers=auth(t),json={'seconds':30}).status_code==403

def test_notifications_persist_and_logout_revokes(setup):
 c,db,t=setup
 assert c.post('/v1/students/student-1/notifications/read',headers=auth(t)).status_code==200
 assert all(x['read'] for x in c.get('/v1/students/student-1/notifications',headers=auth(t)).json())
 assert c.post('/v1/auth/logout',headers=auth(t)).status_code==200
 assert c.get('/v1/me',headers=auth(t)).status_code==401

def test_phone_never_trusts_self_input_and_conflict(setup,monkeypatch):
 c,db,t=setup
 assert c.post('/v1/auth/phone',headers=auth(t),json={'phone':'+8600000000002'}).status_code==422
 monkeypatch.setattr(wechat,'phone',lambda code:'+8600000000002')
 assert c.post('/v1/auth/phone',headers=auth(t),json={'code':'wechat-code'}).status_code==409
 assert {s['id'] for s in c.get('/v1/students',headers=auth(t)).json()}=={'student-1','student-2'}

def test_late_submission_no_punishment(setup):
 c,db,t=setup
 h=db.get(Homework,'homework-1');h.due_at=now()-timedelta(days=1);h.late_policy='unconfirmed';db.commit()
 p={'text':'补交','attachment_ids':[],'idempotency_key':'test-late-submit-0001'}
 before=c.get('/v1/students/student-1/hours',headers=auth(t)).json()['remaining']
 assert c.post('/v1/students/student-1/homework/homework-1/submissions',headers=auth(t),json=p).status_code==409
 assert c.get('/v1/students/student-1/hours',headers=auth(t)).json()['remaining']==before
 h.late_policy='allow';db.commit();assert c.post('/v1/students/student-1/homework/homework-1/submissions',headers=auth(t),json=p).status_code==200

def test_no_development_route_in_test_or_production(setup):
 c,db,t=setup;assert c.post('/v1/auth/development/parent-a').status_code==404

def test_wechat_missing_config_fails_closed(setup,monkeypatch):
 c,db,t=setup;monkeypatch.setattr(settings,'wechat_secret','')
 assert c.post('/v1/auth/wechat',json={'code':'not-real'}).status_code==503
