"""Read persisted local acceptance state without printing identities or tokens."""
from pathlib import Path
import json, sys
from datetime import datetime, timezone
import httpx

root = Path(__file__).resolve().parents[1]
report = {'checked_at': datetime.now(timezone.utc).isoformat()}
with httpx.Client(base_url='http://127.0.0.1:8930', trust_env=False, timeout=15) as client:
    report['health'] = client.get('/health').json()
    response = client.post('/v1/auth/development/parent-a')
    response.raise_for_status()
    client.headers['Authorization'] = 'Bearer ' + response.json()['token']
    def read(path):
        response = client.get(path)
        response.raise_for_status()
        return response.json()
    students = read('/v1/students')
    homework = read('/v1/students/student-1/homework/homework-1')
    knowledge = read('/v1/students/student-1/knowledge/knowledge-1')
    notices = read('/v1/students/student-1/notifications')
    recordings = read('/v1/students/student-1/recordings')
    me = read('/v1/me')
    report.update({
        'student_ids': [s['id'] for s in students],
        'submission_revisions': [s['revision'] for s in homework['history']],
        'submission_statuses': [s['status'] for s in homework['history']],
        'submission_file_counts': [len(s['files']) for s in homework['history']],
        'feedback_count': sum(len(s['feedback']) for s in homework['history']),
        'question_count': len(knowledge['questions']),
        'notification_unread_count': sum(not n['read'] for n in notices),
        'saved_test_profile_matches': me['name'] == '测试家长 A（验收保存）',
        'other_parent_student_status': client.get('/v1/students/student-3/home').status_code,
    })
    client.post('/v1/auth/logout').raise_for_status()
    report['revoked_session_status'] = client.get('/v1/me').status_code
    del client.headers['Authorization']
    report['unauthenticated_status'] = client.get('/v1/me').status_code
    contract = client.get('/openapi.json')
    contract.raise_for_status()
    destination = root / 'packages/api-contracts/openapi.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(contract.json(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report['api_path_count'] = len(contract.json()['paths'])

assert report['student_ids'] == ['student-1', 'student-2']
assert report['submission_revisions'] == [2, 1]
assert report['submission_statuses'][0] == 'graded'
assert report['submission_file_counts'] == [0, 1]  # revision 2 is text-only; original image remains in history
assert report['feedback_count'] > 0 and report['question_count'] >= 2
assert report['notification_unread_count'] == 0 and report['saved_test_profile_matches']
assert report['other_parent_student_status'] == 404  # conceal the existence of another parent's child
assert report['revoked_session_status'] == report['unauthenticated_status'] == 401
destination = root.parent / '02_Deliverables-交付与验收/simulator/persistence-after-restart.json'
destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
