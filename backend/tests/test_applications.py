import time
from test_accounts import staff,assigned
from test_proctoring import event
from app.db import DB,Application,Assignment

def test_open_positions_empty_multiple_and_capacity_filter(client):
    from app.db import RecruitmentPosition
    response=client.get('/api/positions/open')
    assert response.status_code==200 and response.json()==[]
    hr=staff()
    ids=[hr.post('/api/recruitment/positions',json={'title':title,'vacancies_total':2}).json()['id'] for title in ['Backend','Frontend','Closed','Filled']]
    with DB() as db:
        closed=db.get(RecruitmentPosition,ids[2]);closed.body=closed.body|{'status':'closed'}
        filled=db.get(RecruitmentPosition,ids[3]);filled.body=filled.body|{'vacancies_filled':2}
        partial=db.get(RecruitmentPosition,ids[0]);partial.body=partial.body|{'vacancies_filled':1}
        db.commit()
    rows=client.get('/api/positions/open').json()
    assert {p['id'] for p in rows}==set(ids[:2])
    assert next(p for p in rows if p['id']==ids[0])['vacancies_remaining']==1
    for pid in ids[2:]:assert client.post('/api/applications',json={'position_id':pid}).status_code==409
    assert client.post('/api/applications',json={'position_id':ids[0]}).status_code==200
    assert client.get('/api/candidate/applications').json()[0]['position_id']==ids[0]
    assert client.post('/api/applications',json={'position_id':ids[0]}).status_code==409

def test_apply_schedule_hire_and_vacancy_closure(client):
    hr=staff()
    pid=hr.post('/api/recruitment/positions',json={'title':'Frontend Engineer','vacancies_total':1}).json()['id']
    a=client.post('/api/applications',json={'position_id':pid});assert a.status_code==200,a.text
    aid=a.json()['id']
    assert client.post('/api/applications',json={'position_id':pid}).status_code==409
    assert client.get('/api/hr/applications').status_code==403
    other=staff(email='other@example.test')
    assert other.patch(f'/api/applications/{aid}/status',json={'status':'under_review'}).status_code==404
    r=hr.post(f'/api/applications/{aid}/schedule-interview',json={'scheduled_at':time.time()+3600});assert r.status_code==200,r.text
    with DB() as db:
        a=db.get(Application,aid);assert db.get(Assignment,a.assignment_id).body['application_id']==aid
    assert hr.post(f'/api/applications/{aid}/schedule-interview',json={'scheduled_at':time.time()+3600}).status_code==409
    for stage in ['interviewed','shortlisted','offer_extended','hired']:
        r=hr.patch(f'/api/applications/{aid}/status',json={'status':stage,'hr_notes':'Reviewed'});assert r.status_code==200,r.text
    assert hr.patch(f'/api/applications/{aid}/status',json={'status':'hired'}).status_code==200
    assert not client.get('/api/positions/open').json()
    p=hr.get('/api/recruitment/dashboard/overview').json()
    assert p['positions'][0]['vacancies_filled']==1
    assert p['application_counts']['hired']==1
    assert client.get('/api/candidate/applications').json()[0]['status']=='hired'
    assert 'hr_notes' not in client.get('/api/candidate/applications').json()[0]

def test_candidate_applications_zero_one_multiple_and_ownership(client):
    from fastapi.testclient import TestClient
    from app.main import app
    response=client.get('/api/candidate/applications')
    assert response.status_code==200 and response.json()==[]
    hr=staff()
    ids=[]
    for title in ['Backend Engineer','QA Engineer']:
        pid=hr.post('/api/recruitment/positions',json={'title':title}).json()['id']
        assert pid in [p['id'] for p in client.get('/api/positions/open').json()]
        created=client.post('/api/applications',json={'position_id':pid})
        assert created.status_code==200,created.text
        ids.append(created.json()['id'])
        listed=client.get('/api/candidate/applications')
        assert listed.status_code==200
        assert {a['id'] for a in listed.json()}==set(ids)
        assert all(a['status']=='applied' for a in listed.json())
    other=TestClient(app)
    assert other.post('/api/auth/register',json={'email':'other-candidate@example.test','name':'Other Candidate','password':'Test-passphrase-456'}).status_code==200
    assert other.get('/api/candidate/applications').json()==[]
    assert TestClient(app).get('/api/candidate/applications').status_code==401

def test_precheck_detections_do_not_consume_strikes(client):
    c,h,hr,aid=assigned(client,auto_terminate=False);base='/api/sessions/'+c['id']
    for kind,label in [('device','mobile phone'),('multiple_faces',None)]:
        for i in range(2):
            payload=event(kind,kind.replace('_','-')+str(i),label=label,score=.72)|{'stage':'equipment'}
            r=client.post(base+'/observations',headers=h,json=payload)
            assert r.status_code==200,r.text
            assert r.json()['security'].get('device_warning_count',0)==0
            assert r.json()['security'].get('face_warning_count',0)==0
            assert r.json()['status']!='terminated'


def test_role_seed_is_idempotent_and_open_only(client):
    hr=staff()
    for _ in range(2):assert hr.post('/api/recruitment/positions/seed').status_code==200
    rows=hr.get('/api/recruitment/positions').json()['items'];assert len(rows)==12
    p=rows[0]
    assert hr.patch('/api/recruitment/positions/'+p['id'],json={'title':p['title'],'status':'closed'}).status_code==200
    assert len(hr.get('/api/recruitment/positions').json()['items'])==11



def test_shortlist_and_schedule_notify_candidate_without_duplicates(client):
    hr=staff()
    pid=hr.post('/api/recruitment/positions',json={'title':'Engineer','vacancies_total':2}).json()['id']
    aid=client.post('/api/applications',json={'position_id':pid}).json()['id']
    assert client.get('/api/candidate/notifications').json()==[]
    for stage in ['under_review','shortlisted','shortlisted']:
        assert hr.patch(f'/api/applications/{aid}/status',json={'status':stage}).status_code==200
    notes=client.get('/api/candidate/notifications').json()
    assert len(notes)==2
    assert notes[0]['type']=='next_round'
    assert notes[0]['read'] is False
    assignments=client.get('/api/portal/dashboard').json()['assignments']
    assert len(assignments)==1
    assert notes[0]['href']=='/candidate/interview?assignment='+assignments[0]['id']
    assert time.time()<notes[0]['window_end_at']
    from backend.app.db import DB, EmailDelivery
    with DB() as db:
        mail=db.get(EmailDelivery,notes[0]['id'])
        assert mail.body['href']==notes[0]['href']
    assert hr.get('/api/candidate/notifications').status_code==403
    assert client.post('/api/candidate/notifications/'+notes[0]['id']+'/read').status_code==200
    assert client.get('/api/candidate/notifications').json()[0]['read'] is True
    assert client.post('/api/candidate/notifications/missing/read').status_code==404
    r=hr.post(f'/api/applications/{aid}/schedule-interview',json={'scheduled_at':time.time()+3600})
    assert r.status_code==409,r.text
    notes=client.get('/api/candidate/notifications').json()
    assert len(notes)==2
