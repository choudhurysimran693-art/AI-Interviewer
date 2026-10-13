import io
import time
from PIL import Image
from sqlalchemy import select
from fastapi.testclient import TestClient
from app.main import app, report_token
from app.accounts import password_hash
from app.db import DB, User, Session, Observation, Notification, Recovery, Assignment, Organization, Recruiter
from test_application import create
from test_proctoring import event


def staff(role='hr',email='hr@example.test'):
    with DB() as db:
        u=User(email=email,name='Test Reviewer',role=role,password_hash=password_hash('Staff-password-123'),body={})
        db.add(u);db.flush();org=Organization(name='Test organization '+email);db.add(org);db.flush();db.add(Recruiter(user_id=u.id,organization_id=org.id));db.commit()
    client=TestClient(app)
    r=client.post('/api/auth/login',json={'email':email,'password':'Staff-password-123','area':'hr'})
    assert r.status_code==200,r.text
    client.headers['X-CSRF-Token']=client.cookies['interview_csrf']
    return client


def assigned(client,**policy):
    hr=staff()
    exam=hr.post('/api/portal/exams',json={'title':'Software interview','role':'Frontend Engineer','candidate_email':'candidate@example.test','policy':{'auto_terminate':True,'block_account':False,**policy}})
    assert exam.status_code==200,exam.text
    r=client.post('/api/sessions',json={'assignment_id':exam.json()['assignment_id'],'mode':'hr','name':'Alex Example','role':'Ignored role','level':'junior','profile':{'skills':['React'],'projects':['Built dashboard']},'processing_consent':True,'evidence_consent':True})
    assert r.status_code==200,r.text
    c=r.json();h={'Authorization':'Bearer '+c['token']}
    return c,h,hr,exam.json()['assignment_id']


def start(client,c,h):
    base='/api/sessions/'+c['id']
    client.post(base+'/monitoring/storage-check',headers=h)
    health=dict(camera=True,microphone=True,face_count=1,page_visible=True,fullscreen=True,face_age_ms=1,object_age_ms=1,object_latency_ms=1,evidence_ready=True,face_coverage=1,object_coverage=1)
    assert client.post(base+'/monitoring/heartbeat',headers=h,json=health).json()['healthy']
    assert client.post(base+'/start',headers=h,json={'rules_acknowledged':True}).status_code==200


def test_authentication_roles_csrf_and_report_ownership(client):
    c,h=create(client)
    anonymous=TestClient(app)
    assert anonymous.get('/api/portal/dashboard').status_code==401
    assert anonymous.get('/api/sessions/'+c['id'],headers=h).status_code==401
    assert client.get('/api/portal/admin/users').status_code==403
    csrf=client.headers.pop('X-CSRF-Token')
    assert client.post('/api/sessions/'+c['id']+'/questions',headers=h).status_code==403
    client.headers['X-CSRF-Token']=csrf
    assert client.post('/api/sessions/'+c['id']+'/questions',headers=h, json={},).status_code==200
    assert client.post('/api/auth/login',json={'email':'candidate@example.test','password':'Test-passphrase-123','area':'hr'}).status_code==403
    other=TestClient(app)
    other.post('/api/auth/register',json={'name':'Other Person','email':'other@example.test','password':'Test-password-456'})
    other.headers['X-CSRF-Token']=other.cookies['interview_csrf']
    assert other.get('/api/sessions/'+c['id'],headers=h).status_code==404


def test_assignment_and_preexam_requirements(client):
    c,h,hr,aid=assigned(client)
    base='/api/sessions/'+c['id']
    assert client.get(base,headers=h).json()['role']=='Frontend Engineer'
    assert client.post(base+'/start',headers=h,json={'rules_acknowledged':True}).status_code==409
    start(client,c,h)
    assert len(hr.get('/api/portal/dashboard').json()['assignments'])==1
    outsider=staff(email='otherhr@example.test')
    assert outsider.get('/api/portal/reports/'+c['id']).status_code==404
    assert client.get('/api/portal/reports/'+c['id']).status_code==403
    assert hr.get('/api/portal/reports/'+c['id']).status_code==200
    assert client.get('/api/reports/'+report_token(c['id'],'hr')).status_code==403


def test_screen_lock_survives_resume_and_coalesces_departure(client):
    c,h,hr,aid=assigned(client);start(client,c,h);base='/api/sessions/'+c['id']
    r=client.post(base+'/observations',headers=h,json=event('window_blur','blur')).json()
    assert r['security']['violations']==1
    deadline=r['security']['lock_until']
    assert 118<deadline-time.time()<=120
    client.post(base+'/observations',headers=h,json=event('tab_switch','hidden'))
    client.post(base+'/observations',headers=h,json=event('fullscreen_exit','full'))
    assert client.get(base+'/monitoring',headers=h).json()['security']['violations']==1
    assert client.get('/api/portal/attempts/'+c['id']+'/resume').json()['token']==c['token']
    assert client.get(base+'/monitoring',headers=h).json()['security']['lock_until']==deadline
    assert client.post(base+'/start',headers=h,json={'rules_acknowledged':True}).status_code==423
    client.post(base+'/observations',headers=h,json=event('screen_returned','back'))
    with DB() as db:
        s=db.get(Session,c['id']);s.body=s.body|{'security':s.body['security']|{'lock_until':time.time()-1}};db.commit()
    assert client.get(base+'/monitoring',headers=h).json()['security']['lock_until'] is None
    r=client.post(base+'/observations',headers=h,json=event('window_blur','again')).json()
    assert r['status']=='terminated'
    assert client.post(base+'/complete',headers=h).status_code==409
    assert client.get('/api/portal/attempts/'+c['id']+'/resume').status_code==409
    notes=hr.get('/api/portal/dashboard').json()['notifications']
    assert any('terminated' in n['title'] for n in notes)
    assert hr.patch('/api/portal/notifications/'+notes[0]['id'],json={'status':'reviewed'}).status_code==200
    assert hr.get('/api/portal/reports/'+c['id']).json()['security']['review_required']


def test_repeat_devices_block_login_and_final_evidence_upload_survives(client):
    c,h,hr,aid=assigned(client,block_account=True);start(client,c,h);base='/api/sessions/'+c['id']
    for i in range(2):
        result=client.post(base+'/observations',headers=h,json=event('device',str(i),label='mobile phone',score=.9))
        assert result.status_code==200,result.text
    oid=result.json()['id']
    assert result.json()['status']=='terminated'
    out=io.BytesIO();Image.new('RGB',(10,10)).save(out,'JPEG')
    assert client.post('/api/observations/'+oid+'/snapshot',headers=h,files={'file':('event.jpg',out.getvalue(),'image/jpeg')}).status_code==200
    assert client.get('/api/auth/me').status_code==200
    assert client.post('/api/auth/login',json={'email':'candidate@example.test','password':'Test-passphrase-123'}).status_code==200
    report=hr.get('/api/portal/reports/'+c['id']).json()
    assert any(o.get('snapshot') for o in report['observations'])
    assert client.post(base+'/observations',headers=h,json=event('multiple_faces','later')).status_code in (403,409)


def test_faces_and_devices_have_independent_strikes(client):
    c,h,hr,aid=assigned(client);start(client,c,h);base='/api/sessions/'+c['id']
    def send(kind,identifier,**extra):
        response=client.post(base+'/observations',headers=h,json=event(kind,identifier,**extra))
        assert response.status_code==200,response.text
        return response.json()
    first=send('multiple_faces','faces-1')
    assert first['status']!='terminated'
    assert first['security']['face_warning_count']==1
    assert first['security'].get('device_warning_count',0)==0
    assert first['summary']['counts'].get('device',0)==0
    duplicate=send('multiple_faces','faces-1')
    assert duplicate['security']['face_warning_count']==1
    phone=send('device','phone-1',label='mobile phone',score=.9)
    assert phone['status']!='terminated'
    assert phone['security']['face_warning_count']==phone['security']['device_warning_count']==1
    assert client.post(base+'/face-warning/acknowledge',headers=h).json()['security']['face_warning_acknowledged']==1
    assert client.post(base+'/violation',headers=h,json={'type':'multiple_faces'}).status_code==409
    second=send('multiple_faces','faces-2')
    assert second['status']=='terminated'
    assert second['security']['terminated_reason']=='multiple_faces_repeat'
    assert second['security']['device_warning_count']==1
    assert second['security']['face_warning_count']==2
    notes=hr.get('/api/portal/dashboard').json()['notifications']
    assert {'multiple_faces','device_detected'} <= {n.get('violation_type') for n in notes}


def test_phone_only_does_not_increment_face_strikes(client):
    c,h,hr,aid=assigned(client);start(client,c,h);base='/api/sessions/'+c['id']
    for i in range(2):
        response=client.post(base+'/observations',headers=h,json=event('device',str(i),label='mobile phone',score=.9))
        assert response.status_code==200,response.text
        data=response.json()
        assert data['security'].get('face_warning_count',0)==0
        assert data['summary']['counts'].get('multiple_faces',0)==0
    assert data['status']=='terminated'
    assert data['security']['terminated_reason']=='device_detected_repeat'


def test_device_events_reject_people_and_low_confidence(client):
    c,h,hr,aid=assigned(client);start(client,c,h);base='/api/sessions/'+c['id']
    for label,score in [('person',.99),('unclassified',.99),('mobile phone',.1)]:
        assert client.post(base+'/observations',headers=h,json=event('device',label,label=label,score=score)).status_code==422
    with DB() as db:
        assert db.get(Session,c['id']).body.get('security',{}).get('device_warning_count',0)==0


def test_deleting_attempt_cannot_enable_reentry(client):
    c,h,hr,aid=assigned(client)
    assert client.delete('/api/sessions/'+c['id'],headers=h).status_code==403
    with DB() as db:
        assert db.get(Session,c['id']) is not None
    outsider=staff(email='other-hr@example.test')
    assert outsider.delete('/api/sessions/'+c['id']).status_code==404
    assert hr.delete('/api/sessions/'+c['id']).status_code==200
    dashboard=client.get('/api/portal/dashboard').json()
    assert dashboard['assignments'][0]['status']=='attempt_deleted'
    r=client.post('/api/sessions',json={'mode':'hr','assignment_id':aid,'name':'Alex Example','role':'Engineer','level':'junior','profile':{},'processing_consent':True,'evidence_consent':True})
    assert r.status_code==409


def test_report_deletion_requires_owning_hr_team(client):
    c,h,hr,aid=assigned(client)
    assert hr.get('/api/portal/reports/'+c['id']).status_code==200
    token=report_token(c['id'],'hr')
    assert client.delete('/api/reports/'+token,headers=h).status_code==403
    outsider=staff(email='outsider@example.test')
    assert outsider.delete('/api/reports/'+token).status_code==403
    with DB() as db:
        assert db.get(Session,c['id']) is not None
    assert hr.delete('/api/reports/'+token).json()=={'deleted':True}
    with DB() as db:
        assert db.get(Session,c['id']) is None


def test_recovery_single_use_and_admin_unblock(client):
    admin=staff('admin')
    client.post('/api/auth/forgot-password',json={'email':'candidate@example.test'})
    assert admin.get('/api/portal/admin/recovery').json()==[]
    uid=client.get('/api/auth/me').json()['id']
    assert admin.patch('/api/portal/admin/users/'+uid+'/restriction',json={'blocked':True,'reason':'Company cannot block shared candidate'}).status_code==404
    admin.post('/api/portal/admin/users',json={'email':'teammate@example.test','name':'Teammate','password':'Test-passphrase-123','role':'hr'})
    client.post('/api/auth/forgot-password',json={'email':'teammate@example.test'})
    request=admin.get('/api/portal/admin/recovery').json()[0]
    issued=admin.post('/api/portal/admin/recovery/'+request['id']+'/issue').json()
    uid=request['user']['id']
    admin.patch('/api/portal/admin/users/'+uid+'/restriction',json={'blocked':True,'reason':'Test review restriction'})
    payload={'token':issued['reset_path'].split('=')[1],'password':'Updated-password-123'}
    assert client.post('/api/auth/reset-password',json=payload).status_code==200
    assert client.post('/api/auth/reset-password',json=payload).status_code==400
    assert client.post('/api/auth/login',json={'email':'teammate@example.test','password':payload['password'],'area':'hr'}).status_code==403
    assert admin.patch('/api/portal/admin/users/'+uid+'/restriction',json={'blocked':False,'reason':'Identity verified and reviewed'}).status_code==200
    assert client.post('/api/auth/login',json={'email':'teammate@example.test','password':payload['password'],'area':'hr'}).status_code==200


def test_face_cannot_be_submitted_as_device(client):
    c,h,hr,aid=assigned(client);start(client,c,h)
    url='/api/sessions/'+c['id']
    assert client.post(url+'/observations',headers=h,json=event('device','person',label='person',score=.99)).status_code==422
    result=client.get(url+'/monitoring',headers=h).json()
    assert result['status']!='terminated'
    assert result['security'].get('device_warning_count',0)==0


def test_practice_multiple_faces_does_not_terminate(client):
    c,h=create(client)
    result=client.post('/api/sessions/'+c['id']+'/observations',headers=h,json=event('multiple_faces','faces')).json()
    assert result['status']!='terminated'
    assert result['security'].get('device_warning_count',0)==0
