"""Controlled synthetic fixtures; never imported automatically by the API."""
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
import hashlib, io, wave, math, struct
from PIL import Image, ImageDraw
from sqlalchemy import select
from .models import *
from .config import settings

def seed(db):
    if settings.environment not in ['development','test']: raise RuntimeError('Fixtures prohibited in acceptance/production')
    if db.scalar(select(Account).limit(1)):raise RuntimeError('Database is nonempty; refusing to mix test fixtures')
    accounts=[Account(id='test-parent-a',name='测试家长 A',phone='+8600000000001',is_test=True),Account(id='test-parent-b',name='测试家长 B',phone='+8600000000002',is_test=True),Account(id='test-unlinked',name='测试未关联家长',phone='+8600000000003',is_test=True),Account(id='test-teacher',name='测试老师',role='teacher',is_test=True),Account(id='test-admin',name='测试管理员',role='admin',is_test=True)]
    db.add_all(accounts);db.flush()
    for i in range(1,4):db.add(Student(id='student-'+str(i),name='测试学员 '+str(i),grade='三年级' if i!=2 else '初一'))
    db.add_all([Classroom(id='class-1',name='测试三年级提高班 A',campus='测试校区',room='A203',grade='三年级'),Classroom(id='class-2',name='测试初一班 B',campus='测试校区',room='B101',grade='初一')]);db.flush()
    for i in range(1,4):
        sid='student-'+str(i);pid='test-parent-a' if i<3 else 'test-parent-b';phone='+8600000000001' if i<3 else '+8600000000002'
        db.add(Guardian(student_id=sid,verified_phone=phone,account_id=pid,registered_by='test-admin'))
        db.add(Enrollment(student_id=sid,class_id='class-2' if i==2 else 'class-1'))
        db.add(HourPackage(id='package-'+str(i),student_id=sid,name='测试课时包 '+str(i),granted=96 if i!=2 else 48,valid_until=now()+timedelta(days=180)))
    for cid in ['class-1','class-2']:db.add(TeacherClass(account_id='test-teacher',class_id=cid))
    db.add(TeacherProfile(id='teacher-profile-1',account_id='test-teacher',name='测试老师',years=0,specialties='受控验收数据',biography='仅用于验证师资资料展示。此资料不代表叶芝真实老师、资历或教学成果。',published=True))
    today=now().replace(hour=10,minute=0,second=0,microsecond=0)
    for i in range(1,5):
        db.add(Lesson(id='lesson-'+str(i),class_id='class-2' if i==4 else 'class-1',teacher_id='test-teacher',title='测试 Unit '+str(i)+' 阅读课',starts_at=today+timedelta(days=i-3),ends_at=today+timedelta(days=i-3,hours=1.5),room='A203',units=2,status='completed' if i<3 else 'scheduled'))
    db.flush()
    db.add_all([Attendance(student_id='student-1',lesson_id='lesson-1',status='present',arrived_at=today-timedelta(days=2,minutes=8),source='fixture'),Attendance(student_id='student-1',lesson_id='lesson-2',status='absent',source='fixture'),Attendance(student_id='student-2',lesson_id='lesson-4',status='makeup',arrived_at=today,source='manual',reason='受控补签测试')])
    db.add(HourEntry(package_id='package-1',student_id='student-1',lesson_id='lesson-1',amount=-2,reason='受控出勤测试',event_key='fixture-attendance-1'))
    settings.file_root.mkdir(parents=True,exist_ok=True)
    img=Image.new('RGB',(1000,700),'#fff8f0');draw=ImageDraw.Draw(img);draw.rounded_rectangle((60,60,940,640),radius=30,fill='white',outline='#ff7a00',width=3);draw.text((110,120),'YEATS - SYNTHETIC TEST FILE',fill='#3b2a17');draw.text((110,200),'Unit 1: season / weather / autumn',fill='#f26a00');b=io.BytesIO();img.save(b,'JPEG');data=b.getvalue();key='fixture-image.jpg';(settings.file_root/key).write_bytes(data)
    db.add(FileObject(id='file-image',owner_id='test-admin',kind='image',name='受控教学图片.jpg',storage_key=key,mime='image/jpeg',size=len(data),sha256=hashlib.sha256(data).hexdigest(),safety='passed'))
    audio=io.BytesIO()
    with wave.open(audio,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(b''.join(struct.pack('<h',int(1000*math.sin(2*math.pi*440*i/16000))) for i in range(16000)))
    data=audio.getvalue();(settings.file_root/'fixture-tone.wav').write_bytes(data)
    db.add(FileObject(id='file-audio',owner_id='test-admin',kind='audio',name='受控音频测试.wav',storage_key='fixture-tone.wav',mime='audio/wav',size=len(data),sha256=hashlib.sha256(data).hexdigest(),safety='passed'))
    for i in range(1,4):
        h=Homework(id='homework-'+str(i),teacher_id='test-teacher',title='测试 Unit '+str(i)+' 单词与阅读作业',body='1. 阅读词表并完成默写。\n2. 提交图片，可附文字说明。\n本条为受控测试数据。',due_at=now()+timedelta(days=2),late_policy='allow',attachment_ids=['file-image','file-audio'])
        db.add(h);db.flush();db.add(HomeworkTarget(homework_id=h.id,student_id='student-2' if i==3 else 'student-1'))
    db.add(Submission(id='submission-graded',homework_id='homework-2',student_id='student-1',parent_id='test-parent-a',revision=1,text='受控历史提交',status='graded',attachment_ids=['file-image'],idempotency_key='fixture-graded-0001',request_hash='fixture'))
    db.flush();db.add(Feedback(submission_id='submission-graded',teacher_id='test-teacher',text='受控批改反馈：请注意单词拼写。',grade='A',annotation_file_ids=['file-image'],audio_file_id='file-audio'))
    for kind in ['entry','exit']:db.add(TestResult(student_id='student-1',lesson_id='lesson-1',kind=kind,title='测试 '+('入门测' if kind=='entry' else '出门测'),text='仅用于验证图片、文字及音频展示。',score='受控示例 85 分',attachment_ids=['file-image','file-audio']))
    names=['测试小学','三年级','测试学期','Unit 1','词汇与拼写','单元核心词','词表与发音']
    for i,n in enumerate(names,1):db.add(Category(id='category-'+str(i),parent_id='category-'+str(i-1) if i>1 else None,name=n,level=i));db.flush()
    db.add(Knowledge(id='knowledge-1',category_id='category-7',owner_id='test-admin',title='测试季节与天气词表',text='season / weather / autumn。受控知识内容。',attachment_ids=['file-image','file-audio']));db.flush()
    db.add(KnowledgeReference(knowledge_id='knowledge-1',class_id='class-1'))
    db.add(Question(parent_id='test-parent-a',student_id='student-1',knowledge_id='knowledge-1',text='测试：autumn 和 fall 可以互换吗？',reply='受控答复：两者均可表示秋季。',replied_by='test-teacher',idempotency_key='fixture-question-1'))
    for kind,title,body in [('banner','YEATS 学习记录 · 内部验收','受控测试数据，不是机构真实业务'),('announcement','内部验收环境使用说明','请勿上传真实学生、家长或作业资料。'),('introduction','关于叶芝英语','机构正式介绍待提供；此为测试内容。'),('courses','年级课程介绍','正式课程设置由机构维护。'),('services','教学服务','查看课时、签到、随堂测试、作业及反馈。'),('enrollment','报名须知','报名缴费线下办理；真实收费、退费与课时有效期说明待机构提供。'),('privacy','开发验收隐私说明','当前为隔离测试环境，仅限虚构数据。正式版使用微信身份、授权手机号、监护关系及学习记录提供服务。上传图片移除 EXIF 位置信息；附件通过访问权限校验。正式主体、联系方式、保存期限及注销流程须在上线前确认。'),('agreement','开发验收用户说明','当前仅用于内部业务流程验证，不代表真实微信认证或正式上线服务。请勿录入真实学生资料。')]:
        db.add(Content(kind=kind,title=title,text=body))
    for kind,title,rid in [('homework','新作业：测试 Unit 1','homework-1'),('feedback','作业已批改：测试 Unit 2','homework-2'),('test','随堂测试已发布',None)]:db.add(Notification(account_id='test-parent-a',student_id='student-1',kind=kind,title=title,text='受控站内通知',resource_id=rid))
    db.commit()
