"""Extend only the original synthetic fixtures. Never create a playback grant."""
from pathlib import Path
import sys,hashlib
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'services/api'))
from yeats.config import settings
from yeats.db import SessionLocal
from yeats.models import Account,FileObject,Knowledge,Recording,TeacherProfile
if settings.environment!='development':raise SystemExit('Development only')
with SessionLocal() as db:
 a=db.get(Account,'test-admin');k=db.get(Knowledge,'knowledge-1')
 if not a or not a.is_test or not k:raise SystemExit('Original controlled fixture required')
 ids=list(k.attachment_ids)
 for ext,kind,mime in [('mp4','video','video/mp4'),('docx','word','application/vnd.openxmlformats-officedocument.wordprocessingml.document'),('xlsx','excel','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),('pptx','ppt','application/vnd.openxmlformats-officedocument.presentationml.presentation'),('pdf','pdf','application/pdf')]:
  fid='fixture-'+ext;name='fixture-video.mp4' if ext=='mp4' else 'fixture.'+ext;p=settings.file_root/name
  if not p.is_file():raise SystemExit('Fixture file missing')
  if not db.get(FileObject,fid):
   data=p.read_bytes();db.add(FileObject(id=fid,owner_id=a.id,kind=kind,name='受控测试文件.'+ext,storage_key=name,mime=mime,size=len(data),sha256=hashlib.sha256(data).hexdigest(),safety='passed'))
  if fid not in ids:ids.append(fid)
 k.attachment_ids=ids
 # Separate resource IDs for public demo, class-only knowledge and private replay.
 # Reusing the same public file ID for a restricted replay would defeat its gate.
 for fid in ['fixture-demo-mp4','fixture-recording-mp4']:
  if not db.get(FileObject,fid):
   p=settings.file_root/'fixture-video.mp4';data=p.read_bytes();db.add(FileObject(id=fid,owner_id=a.id,kind='video',name='受控测试视频.mp4',storage_key=p.name,mime='video/mp4',size=len(data),sha256=hashlib.sha256(data).hexdigest(),safety='passed'))
 if not db.get(Recording,'fixture-recording'):db.add(Recording(id='fixture-recording',lesson_id='lesson-2',file_id='fixture-recording-mp4',title='受控补看视频（色块与测试音）',published=True))
 else:db.get(Recording,'fixture-recording').file_id='fixture-recording-mp4'
 db.get(TeacherProfile,'teacher-profile-1').demo_file_id='fixture-demo-mp4'
 db.commit()
print('Seven file types registered to synthetic knowledge; recording registered without viewing grant.')
