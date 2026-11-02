from app.db import DB,ApplicationRound,Assignment,Examination
from app.rounds import RoundInput
from test_round_templates import setup


def test_resume_configuration_always_uses_document_screening():
    for mode in ('ai_conducted','ai_scored','auto_evaluated'):
        assert RoundInput(round_type='resume_screening',round_name='Resume',evaluation_mode=mode).evaluation_mode=='auto_evaluated'


def test_legacy_screening_requires_hr_then_opens_aptitude(client):
    hr,pid,aid=setup(client)
    rows=hr.get(f'/api/hr/applications/{aid}/rounds').json()
    # Recreate the older deployment: its first assignment is a spoken resume round.
    with DB() as db:
        first=db.get(ApplicationRound,rows[0]['id']);second=db.get(ApplicationRound,rows[1]['id'])
        old_id=second.assignment_id
        old=db.get(Assignment,old_id);exam=db.get(Examination,old.exam_id)
        old.body=old.body|{'application_round_id':first.id}
        exam.body=exam.body|{'round_type':'resume_screening','application_round_id':first.id}
        first.status='invited';first.assignment_id=old.id
        second.status='pending';second.assignment_id=None
        db.commit()
    request={'assignment_id':old_id,'mode':'hr','name':'Alex Example','role':'Engineer','level':'junior','profile':{},'processing_consent':True,'evidence_consent':True}
    blocked=client.post('/api/sessions',json=request)
    assert blocked.status_code==409 and 'document review' in blocked.text
    endpoint='/api/application-rounds/'+rows[0]['id']+'/approve-resume'
    assert client.post(endpoint).status_code==403
    approved=hr.post(endpoint)
    assert approved.status_code==200,approved.text
    result=approved.json()
    assert result[0]['status']=='passed' and result[1]['status']=='invited'
    assert all(r['status']=='pending' for r in result[2:])
    assert hr.post(endpoint).status_code==200
    with DB() as db:
        assert db.get(Assignment,old_id).body['status']=='cancelled'
        next_assignment=db.get(Assignment,result[1]['assignment_id'])
        assert db.get(Examination,next_assignment.exam_id).body['round_type']=='aptitude'
