from sqlalchemy import select
from app.config import settings
from app.db import DB,Question,WorkflowNotification
from test_accounts import staff,assigned


def test_generic_session_cannot_resume_or_load_questions_in_strict_mode(client,monkeypatch):
    credentials,headers,hr,assignment=assigned(client)
    monkeypatch.setattr(settings,'require_sequential_interviews',True)
    base='/api/sessions/'+credentials['id']
    assert client.get(base,headers=headers).status_code==409
    assert client.post(base+'/questions',headers=headers).status_code==409
    assert client.get('/api/portal/attempts/'+credentials['id']+'/resume').status_code==409
    invitation=hr.post('/api/portal/exams',json={'title':'Old generic route','role':'Engineer','candidate_email':'candidate@example.test'}).json()['assignment_id']
    response=client.post('/api/sessions',json={'assignment_id':invitation,'mode':'hr','name':'Alex Example','role':'Engineer','level':'junior','profile':{},'processing_consent':True,'evidence_consent':True})
    assert response.status_code==409 and 'not linked' in response.text


def test_default_shortlist_starts_aptitude_bank_and_queues_invitation(client,monkeypatch):
    monkeypatch.setattr(settings,'require_sequential_interviews',True)
    hr=staff()
    pid=hr.post('/api/recruitment/positions',json={'title':'Java Developer'}).json()['id']
    aid=client.post('/api/applications',json={'position_id':pid}).json()['id']
    for stage in ('under_review','shortlisted'):
        response=hr.patch('/api/applications/'+aid+'/status',json={'status':stage})
        assert response.status_code==200,response.text
    rows=client.get('/api/candidate/applications').json()[0]['rounds']
    assert [r['round_type'] for r in rows]==['resume_screening','aptitude','technical','technical_deep','hr','final_interview']
    assert rows[0]['status']=='passed' and rows[1]['can_start']
    c=client.post('/api/sessions',json={'assignment_id':rows[1]['assignment_id'],'mode':'hr','name':'Alex Example','role':'Java Developer','level':'junior','profile':{'skills':['FastAPI']},'processing_consent':True,'evidence_consent':True}).json()
    result=client.post('/api/sessions/'+c['id']+'/questions',headers={'Authorization':'Bearer '+c['token']})
    assert result.status_code==200,result.text
    assert result.json()['round_type']=='aptitude'
    assert len(result.json()['questions'])==15 and all(q['options'] for q in result.json()['questions'])
    with DB() as db:
        assert db.scalar(select(WorkflowNotification).where(WorkflowNotification.application_id==aid,WorkflowNotification.type=='next_round'))


def test_hr_can_enable_rounds_for_legacy_shortlisted_application(client,monkeypatch):
    hr=staff();pid=hr.post('/api/recruitment/positions',json={'title':'Engineer'}).json()['id']
    aid=client.post('/api/applications',json={'position_id':pid}).json()['id']
    for stage in ('under_review','shortlisted'):assert hr.patch('/api/applications/'+aid+'/status',json={'status':stage}).status_code==200
    monkeypatch.setattr(settings,'require_sequential_interviews',True)
    url='/api/applications/'+aid+'/enable-standard-rounds'
    assert client.post(url).status_code==403
    response=hr.post(url)
    assert response.status_code==200,response.text
    assert response.json()[1]['round_type']=='aptitude' and response.json()[1]['can_start']
    assert hr.post(url).status_code==409
