import time
from sqlalchemy import select
from test_accounts import staff, start
from app.db import DB, ApplicationRound, CandidateNotice, EmailDelivery, Answer, Session, Examination, Assignment

DEFINITIONS=[{'round_type':kind,'round_name':name} for kind,name in [('resume_screening','Resume Screening'),('aptitude','Aptitude Test'),('technical','Technical Round'),('hr','HR Round')]]

def setup_pipeline(client):
    hr=staff()
    pid=hr.post('/api/recruitment/positions',json={'title':'Engineer'}).json()['id']
    response=hr.post(f'/api/positions/{pid}/rounds',json={'rounds':DEFINITIONS})
    assert response.status_code==200,response.text
    aid=client.post('/api/applications',json={'position_id':pid}).json()['id']
    for status in ['under_review','shortlisted']:
        response=hr.patch(f'/api/applications/{aid}/status',json={'status':status})
        assert response.status_code==200,response.text
    return hr,pid,aid

def test_four_rounds_and_notifications(client):
    hr,pid,aid=setup_pipeline(client)
    for index in range(4):
        entries=hr.get(f'/api/hr/applications/{aid}/rounds').json()
        r=entries[index]
        assert r['status']=='invited'
        assert all(x['status']=='passed' for x in entries[:index])
        assert client.post(f"/api/application-rounds/{r['id']}/complete").status_code==409
        created=client.post('/api/sessions',json={'assignment_id':r['assignment_id'],'mode':'hr','name':'Alex Example','role':'Engineer','level':'junior','profile':{'skills':['Python'],'projects':['Built software']},'processing_consent':True,'evidence_consent':True})
        assert created.status_code==200,created.text
        c=created.json();h={'Authorization':'Bearer '+c['token']}
        start(client,c,h)
        questions=client.post('/api/sessions/'+c['id']+'/questions',headers=h)
        assert questions.status_code==200,questions.text
        with DB() as db:
            for q in questions.json()['questions']:
                db.add(Answer(session_id=c['id'],body={'question_id':q['id'],'approved':True,'evaluation':{'status':'scored','technical':80,'communication':70}}))
            db.commit()
        response=client.post('/api/sessions/'+c['id']+'/complete',headers=h)
        assert response.status_code==200,response.text
        completed=hr.get(f'/api/hr/applications/{aid}/rounds').json()[index]
        assert completed['status']=='completed' and completed['score']==78
        decision=hr.patch(f"/api/application-rounds/{r['id']}/decision",json={'status':'passed','hr_notes':'Reviewed'})
        assert decision.status_code==200,decision.text
        assert hr.patch(f"/api/application-rounds/{r['id']}/decision",json={'status':'passed'}).status_code==200
    application=client.get('/api/candidate/applications').json()[0]
    assert application['current_round']=='Ready for offer'
    assert all('hr_notes' not in r and 'score' not in r for r in application['rounds'])
    with DB() as db:
        notices=list(db.scalars(select(CandidateNotice)))
        assert sum(n.body.get('type')=='round_invite' for n in notices)==4
        assert sum(n.body.get('type')=='round_result' for n in notices)==4
        assert len(list(db.scalars(select(EmailDelivery))))==len(notices)
    assert hr.patch(f'/api/applications/{aid}/status',json={'status':'offer_extended'}).status_code==200

def test_round_security_failure_and_configuration(client):
    hr,pid,aid=setup_pipeline(client)
    entries=hr.get(f'/api/hr/applications/{aid}/rounds').json()
    assert hr.post(f'/api/positions/{pid}/rounds',json={'rounds':DEFINITIONS}).status_code==409
    assert hr.post(f"/api/applications/{aid}/rounds/{entries[1]['round_id']}/invite",json={}).status_code==409
    assert hr.patch(f'/api/applications/{aid}/status',json={'status':'offer_extended'}).status_code==409
    other=staff(email='other@example.test')
    assert other.get(f'/api/hr/applications/{aid}/rounds').status_code==404
    assert other.patch(f"/api/application-rounds/{entries[0]['id']}/decision",json={'status':'failed'}).status_code==404
    assert client.patch(f"/api/application-rounds/{entries[0]['id']}/decision",json={'status':'passed'}).status_code==403
    with DB() as db:
        r=db.get(ApplicationRound,entries[0]['id']);r.status='completed';r.score=23;db.commit()
    assert hr.patch(f"/api/application-rounds/{entries[0]['id']}/decision",json={'status':'failed'}).status_code==200
    assert hr.post(f"/api/applications/{aid}/rounds/{entries[1]['round_id']}/invite",json={}).status_code==409
    application=client.get('/api/candidate/applications').json()[0]
    assert application['status']=='rejected'
    with DB() as db:
        result=db.get(CandidateNotice,'round-result:'+entries[0]['id'])
        assert '23' not in result.body['message']
    counts=hr.get('/api/recruitment/dashboard/overview').json()['round_counts']
    assert counts=={'rejected':1}

def test_disabled_rounds_windows_and_unread_count(client):
    hr=staff()
    pid=hr.post('/api/recruitment/positions',json={'title':'Senior Engineer'}).json()['id']
    definitions=[d|{'is_active':d['round_type']!='aptitude'} for d in DEFINITIONS]
    assert hr.post(f'/api/positions/{pid}/rounds',json={'rounds':definitions}).status_code==200
    aid=client.post('/api/applications',json={'position_id':pid}).json()['id']
    for status in ['under_review','shortlisted']:assert hr.patch(f'/api/applications/{aid}/status',json={'status':status}).status_code==200
    entries=hr.get(f'/api/hr/applications/{aid}/rounds').json()
    assert [r['round_type'] for r in entries]==['resume_screening','technical','hr']
    n=client.get('/api/candidate/notifications?envelope=true').json()
    assert n['unread_count']==len(n['items'])
    notice=next(x for x in n['items'] if x.get('type')=='round_invite')
    assert notice['href'].endswith(entries[0]['assignment_id'])
    assert notice['window_end_at']>notice['scheduled_at']
    assert client.patch('/api/candidate/notifications/'+notice['id']+'/read').status_code==200
    assert client.get('/api/candidate/notifications?envelope=true').json()['unread_count']==n['unread_count']-1
    with DB() as db:
        assignment=db.get(Assignment,entries[0]['assignment_id']);exam=db.get(Examination,assignment.exam_id)
        exam.body=exam.body|{'window_end_at':time.time()-1};db.commit()
    response=client.post('/api/sessions',json={'assignment_id':entries[0]['assignment_id'],'mode':'hr','name':'Alex Example','role':'Engineer','level':'senior','profile':{},'processing_consent':True,'evidence_consent':True})
    assert response.status_code==409
    assert 'closed' in response.text
