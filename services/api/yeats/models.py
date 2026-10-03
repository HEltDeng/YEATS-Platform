"""Relational identity, learning records and access grants. UTC timestamps."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Text, ForeignKey, UniqueConstraint, JSON, DateTime, Numeric, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def uid(): return str(uuid4())
def now(): return datetime.now(timezone.utc).replace(tzinfo=None)
class Row:
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime,default=now)

class Account(Row,Base):
    __tablename__='accounts'
    role: Mapped[str] = mapped_column(String(16),default='parent')
    name: Mapped[str] = mapped_column(String(80),default='家长')
    active: Mapped[bool] = mapped_column(default=True)
    is_test: Mapped[bool] = mapped_column(default=False)
    phone: Mapped[str|None] = mapped_column(String(32),unique=True)
    password_hash: Mapped[str|None] = mapped_column(String(255))
class WechatIdentity(Row,Base):
    __tablename__='wechat_identities'
    __table_args__=(UniqueConstraint('appid','openid'),)
    appid: Mapped[str] = mapped_column(String(40))
    openid: Mapped[str] = mapped_column(String(128))
    account_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
class Session(Row,Base):
    __tablename__='sessions'
    token_hash: Mapped[str] = mapped_column(String(64),unique=True)
    account_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    identity_id: Mapped[str|None] = mapped_column(ForeignKey('wechat_identities.id'))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(default=False)
class Student(Row,Base):
    __tablename__='students'
    name: Mapped[str] = mapped_column(String(80))
    grade: Mapped[str] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(default=True)
class Guardian(Row,Base):
    __tablename__='guardians'
    __table_args__=(UniqueConstraint('student_id','verified_phone'),)
    student_id: Mapped[str] = mapped_column(ForeignKey('students.id'))
    verified_phone: Mapped[str] = mapped_column(String(32))
    account_id: Mapped[str|None] = mapped_column(ForeignKey('accounts.id'))
    relation: Mapped[str] = mapped_column(String(20),default='监护人')
    active: Mapped[bool] = mapped_column(default=True)
    registered_by: Mapped[str] = mapped_column(String(36))
class Classroom(Row,Base):
    __tablename__='classrooms'
    name: Mapped[str] = mapped_column(String(120))
    campus: Mapped[str] = mapped_column(String(80))
    room: Mapped[str] = mapped_column(String(80),default='')
    grade: Mapped[str] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(default=True)
class Enrollment(Row,Base):
    __tablename__='enrollments'
    __table_args__=(UniqueConstraint('student_id','class_id'),)
    student_id: Mapped[str] = mapped_column(ForeignKey('students.id'))
    class_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id'))
    active: Mapped[bool] = mapped_column(default=True)
class TeacherClass(Row,Base):
    __tablename__='teacher_classes'
    __table_args__=(UniqueConstraint('account_id','class_id'),)
    account_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    class_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id'))
    duty: Mapped[str] = mapped_column(String(30),default='主课老师')
class TeacherProfile(Row,Base):
    __tablename__='teacher_profiles'
    account_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'),unique=True)
    name: Mapped[str] = mapped_column(String(80))
    years: Mapped[int] = mapped_column(Integer,default=0)
    specialties: Mapped[str] = mapped_column(String(200),default='')
    biography: Mapped[str] = mapped_column(Text,default='')
    avatar_file_id: Mapped[str|None] = mapped_column(String(36))
    demo_file_id: Mapped[str|None] = mapped_column(String(36))
    published: Mapped[bool] = mapped_column(default=False)
class Lesson(Row,Base):
    __tablename__='lessons'
    class_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id'))
    teacher_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    title: Mapped[str] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    room: Mapped[str] = mapped_column(String(80))
    units: Mapped[float] = mapped_column(Numeric(10,2),default=1)
    status: Mapped[str] = mapped_column(String(20),default='scheduled')
class HourPackage(Row,Base):
    __tablename__='hour_packages'
    student_id: Mapped[str] = mapped_column(ForeignKey('students.id'))
    name: Mapped[str] = mapped_column(String(120))
    granted: Mapped[float] = mapped_column(Numeric(10,2))
    valid_until: Mapped[datetime|None] = mapped_column(DateTime)
class HourEntry(Row,Base):
    __tablename__='hour_entries'
    package_id: Mapped[str] = mapped_column(ForeignKey('hour_packages.id'))
    student_id: Mapped[str] = mapped_column(ForeignKey('students.id'))
    lesson_id: Mapped[str|None] = mapped_column(ForeignKey('lessons.id'))
    amount: Mapped[float] = mapped_column(Numeric(10,2))
    reason: Mapped[str] = mapped_column(String(200))
    event_key: Mapped[str] = mapped_column(String(160),unique=True)
    reverses_id: Mapped[str|None] = mapped_column(ForeignKey('hour_entries.id'),unique=True)
class Attendance(Row,Base):
    __tablename__='attendance'
    __table_args__=(UniqueConstraint('student_id','lesson_id'),)
    student_id: Mapped[str] = mapped_column(ForeignKey('students.id'))
    lesson_id: Mapped[str] = mapped_column(ForeignKey('lessons.id'))
    status: Mapped[str] = mapped_column(String(20))
    arrived_at: Mapped[datetime|None] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(String(200),default='')
class DeviceEvent(Row,Base):
    __tablename__='device_events'
    external_id: Mapped[str] = mapped_column(String(160),unique=True)
    state: Mapped[str] = mapped_column(String(20),default='unmatched')
    detail: Mapped[dict] = mapped_column(JSON,default=dict)
class Homework(Row,Base):
    __tablename__='homework'
    teacher_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    due_at: Mapped[datetime|None] = mapped_column(DateTime)
    grading_due_at: Mapped[datetime|None] = mapped_column(DateTime)
    late_policy: Mapped[str] = mapped_column(String(20),default='unconfirmed')
    attachment_ids: Mapped[list] = mapped_column(JSON,default=list)
    published: Mapped[bool] = mapped_column(default=True)
class HomeworkTarget(Row,Base):
    __tablename__='homework_targets'
    __table_args__=(UniqueConstraint('homework_id','student_id'),)
    homework_id: Mapped[str] = mapped_column(ForeignKey('homework.id'))
    student_id: Mapped[str] = mapped_column(ForeignKey('students.id'))
class Submission(Row,Base):
    __tablename__='submissions'
    __table_args__=(UniqueConstraint('homework_id','student_id','revision'),UniqueConstraint('parent_id','idempotency_key'))
    homework_id: Mapped[str] = mapped_column(ForeignKey('homework.id'))
    student_id: Mapped[str] = mapped_column(ForeignKey('students.id'))
    parent_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    revision: Mapped[int] = mapped_column(Integer,default=1)
    text: Mapped[str] = mapped_column(Text,default='')
    attachment_ids: Mapped[list] = mapped_column(JSON,default=list)
    status: Mapped[str] = mapped_column(String(20),default='submitted')
    idempotency_key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))
class Feedback(Row,Base):
    __tablename__='feedback'
    submission_id: Mapped[str] = mapped_column(ForeignKey('submissions.id'))
    teacher_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    text: Mapped[str] = mapped_column(Text,default='')
    grade: Mapped[str] = mapped_column(String(40),default='')
    annotation_file_ids: Mapped[list] = mapped_column(JSON,default=list)
    audio_file_id: Mapped[str|None] = mapped_column(String(36))
class TestResult(Row,Base):
    __tablename__='test_results'
    student_id: Mapped[str] = mapped_column(ForeignKey('students.id'))
    lesson_id: Mapped[str] = mapped_column(ForeignKey('lessons.id'))
    kind: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text,default='')
    score: Mapped[str] = mapped_column(String(80),default='')
    attachment_ids: Mapped[list] = mapped_column(JSON,default=list)
    published: Mapped[bool] = mapped_column(default=True)
class Category(Row,Base):
    __tablename__='categories'
    parent_id: Mapped[str|None] = mapped_column(ForeignKey('categories.id'))
    name: Mapped[str] = mapped_column(String(120))
    level: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(default=True)
    sort: Mapped[int] = mapped_column(Integer,default=0)
class Knowledge(Row,Base):
    __tablename__='knowledge'
    category_id: Mapped[str] = mapped_column(ForeignKey('categories.id'))
    owner_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    title: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text,default='')
    attachment_ids: Mapped[list] = mapped_column(JSON,default=list)
    published: Mapped[bool] = mapped_column(default=True)
class KnowledgeReference(Row,Base):
    __tablename__='knowledge_references'
    __table_args__=(UniqueConstraint('knowledge_id','class_id'),)
    knowledge_id: Mapped[str] = mapped_column(ForeignKey('knowledge.id'))
    class_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id'))
    active: Mapped[bool] = mapped_column(default=True)
class Question(Row,Base):
    __tablename__='questions'
    __table_args__=(UniqueConstraint('parent_id','idempotency_key'),)
    parent_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    student_id: Mapped[str] = mapped_column(ForeignKey('students.id'))
    knowledge_id: Mapped[str] = mapped_column(ForeignKey('knowledge.id'))
    text: Mapped[str] = mapped_column(Text)
    reply: Mapped[str] = mapped_column(Text,default='')
    reply_files: Mapped[list] = mapped_column(JSON,default=list)
    replied_by: Mapped[str|None] = mapped_column(ForeignKey('accounts.id'))
    idempotency_key: Mapped[str] = mapped_column(String(80))
class Recording(Row,Base):
    __tablename__='recordings'
    lesson_id: Mapped[str] = mapped_column(ForeignKey('lessons.id'))
    title: Mapped[str] = mapped_column(String(200))
    file_id: Mapped[str] = mapped_column(String(36))
    published: Mapped[bool] = mapped_column(default=True)
class ViewingRequest(Row,Base):
    __tablename__='viewing_requests'
    __table_args__=(UniqueConstraint('parent_id','idempotency_key'),)
    parent_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    student_id: Mapped[str] = mapped_column(ForeignKey('students.id'))
    lesson_id: Mapped[str] = mapped_column(ForeignKey('lessons.id'))
    status: Mapped[str] = mapped_column(String(20),default='pending')
    reason: Mapped[str] = mapped_column(Text,default='')
    decision_reason: Mapped[str] = mapped_column(Text,default='')
    idempotency_key: Mapped[str] = mapped_column(String(80))
class ViewingGrant(Row,Base):
    __tablename__='viewing_grants'
    student_id: Mapped[str] = mapped_column(ForeignKey('students.id'))
    recording_id: Mapped[str] = mapped_column(ForeignKey('recordings.id'))
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(default=False)
class FileObject(Row,Base):
    __tablename__='files'
    owner_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    student_id: Mapped[str|None] = mapped_column(ForeignKey('students.id'))
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    storage_key: Mapped[str] = mapped_column(String(120))
    mime: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    safety: Mapped[str] = mapped_column(String(20),default='pending')
    available: Mapped[bool] = mapped_column(default=True)
class FileTicket(Row,Base):
    __tablename__='file_tickets'
    token_hash: Mapped[str] = mapped_column(String(64),unique=True)
    file_id: Mapped[str] = mapped_column(ForeignKey('files.id'))
    account_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    student_id: Mapped[str|None] = mapped_column(ForeignKey('students.id'))
    purpose: Mapped[str] = mapped_column(String(20))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
class Content(Row,Base):
    __tablename__='content'
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text,default='')
    attachment_ids: Mapped[list] = mapped_column(JSON,default=list)
    target: Mapped[str] = mapped_column(String(80),default='')
    published: Mapped[bool] = mapped_column(default=True)
    sort: Mapped[int] = mapped_column(Integer,default=0)
class Notification(Row,Base):
    __tablename__='notifications'
    account_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    student_id: Mapped[str] = mapped_column(ForeignKey('students.id'))
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text,default='')
    resource_id: Mapped[str|None] = mapped_column(String(36))
    read: Mapped[bool] = mapped_column(default=False)
class SubscriptionConsent(Row,Base):
    __tablename__='subscription_consents'
    account_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    choices: Mapped[dict] = mapped_column(JSON)
class Outbox(Row,Base):
    __tablename__='outbox'
    notification_id: Mapped[str] = mapped_column(ForeignKey('notifications.id'))
    state: Mapped[str] = mapped_column(String(30),default='pending_configuration')
    attempts: Mapped[int] = mapped_column(default=0)
class Audit(Row,Base):
    __tablename__='audit'
    actor_id: Mapped[str|None] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str|None] = mapped_column(String(36))
    detail: Mapped[dict] = mapped_column(JSON,default=dict)
