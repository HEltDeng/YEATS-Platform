from datetime import timedelta
from sqlalchemy import select
from yeats.models import Homework,Submission,Session,now
from yeats.main import homework_view
from conftest import auth

def test_grading_and_submission_deadlines_are_independent(setup):
    c,db,t=setup;h=db.get(Homework,'homework-2');s=db.get(Submission,'submission-graded')
    h.due_at=now()-timedelta(days=3);h.grading_due_at=now()-timedelta(days=1);s.status='submitted';db.flush()
    view=homework_view(db,h,'student-1')
    assert view['grading_overdue'] is True and view['overdue'] is False
    h.grading_due_at=None
    assert homework_view(db,h,'student-1')['grading_overdue'] is False

def test_expired_session_cannot_access_protected_data(setup):
    c,db,t=setup
    for s in db.scalars(select(Session).where(Session.account_id=='test-parent-a')):s.expires_at=now()-timedelta(seconds=1)
    db.flush()
    assert c.get('/v1/me',headers=auth(t)).status_code==401
    assert c.get('/v1/students/student-1/home',headers=auth(t)).status_code==401
