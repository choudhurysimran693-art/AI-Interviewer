from app.config import settings
from app.db import DB,ApplicationRound,Assignment
from app.rounds import activate_aptitude_first
from test_accounts import staff
from test_round_templates import setup


def test_shortlisting_opens_five_round_flow_without_resume_approval(client,monkeypatch):
    monkeypatch.setattr(settings,'include_resume_screening_round',False)
    monkeypatch.setattr(settings,'require_sequential_interviews',True)
    hr=staff();pid=hr.post('/api/recruitment/positions',json={'title':'Java Developer'}).json()['id']
    aid=client.post('/api/applications',json={'position_id':pid}).json()['id']
    for status in ('under_review','shortlisted'):
        result=hr.patch('/api/applications/'+aid+'/status',json={'status':status})
        assert result.status_code==200,result.text
    rows=client.get('/api/candidate/applications').json()[0]['rounds']
    assert [r['round_type'] for r in rows]==['aptitude','technical','technical_deep','hr','final_interview']
    assert rows[0]['can_start'] and all(r['status']=='pending' for r in rows[1:])
    notices=client.get('/api/candidate/notifications').json()
    invitation=next(n for n in notices if n.get('type')=='next_round')
    assert 'shortlisted' in invitation['message'] and 'passed Resume' not in invitation['message']


def test_startup_retires_stuck_resume_and_unlocks_aptitude_once(client,monkeypatch):
    hr,pid,aid=setup(client)
    rows=hr.get('/api/hr/applications/'+aid+'/rounds').json()
    with DB() as db:
        first=db.get(ApplicationRound,rows[0]['id']);second=db.get(ApplicationRound,rows[1]['id'])
        first.status='in_progress';first.assignment_id=second.assignment_id
        old_id=first.assignment_id
        second.status='pending';second.assignment_id=None;db.commit()
    monkeypatch.setattr(settings,'include_resume_screening_round',False)
    activate_aptitude_first()
    shown=client.get('/api/candidate/applications').json()[0]['rounds']
    assert len(shown)==5 and shown[0]['round_type']=='aptitude' and shown[0]['can_start']
    assignment=shown[0]['assignment_id'];activate_aptitude_first()
    assert client.get('/api/candidate/applications').json()[0]['rounds'][0]['assignment_id']==assignment
    with DB() as db:
        assert db.get(Assignment,old_id).body['status']=='cancelled'
        assert db.get(ApplicationRound,rows[0]['id']) is not None # Retain historical records.
