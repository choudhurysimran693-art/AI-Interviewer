from app.db import DB, Session
from app.proctoring import ProctorConfig
from test_application import create

def event(kind, id='event', **extra):
    return dict(id=id,type=kind,timestamp=1,duration=0,stage='answer',face_coverage=1,object_coverage=1,**extra)

def test_event_ownership_idempotency_duration_and_summary(client):
    c,h=create(client); other,oh=create(client)
    url=f'/api/sessions/{c["id"]}/observations'
    assert client.post(url,headers=oh,json=event('tab_switch')).status_code==404
    first=client.post(url,headers=h,json=event('tab_switch')).json()
    second=client.post(url,headers=h,json=event('tab_switch')|{'duration':4}).json()
    assert first['id']==second['id']
    result=client.get(f'/api/sessions/{c["id"]}/monitoring',headers=h).json()
    assert result['summary']['counts']=={'tab_switch':1}
    assert result['summary']['activity_score']==3
    assert result['events'][0]['duration']==4
    assert result['events'][0]['event_type']=='TAB_SWITCH'
    assert result['events'][0]['severity']=='medium'
    assert client.get(f'/api/sessions/{c["id"]}/monitoring',headers=oh).status_code==404

def test_review_does_not_terminate_by_default(client):
    c,h=create(client,'hr')
    for i in range(3):
        out=client.post(f'/api/sessions/{c["id"]}/observations',headers=h,json=event('fullscreen_exit',str(i)))
        assert out.status_code==200
    result=client.get(f'/api/sessions/{c["id"]}/monitoring',headers=h).json()
    assert result['summary']['review_required']
    assert not result['summary']['terminate']
    assert result['status']!='terminated'

def test_optional_termination_is_enforced_on_server(client):
    from test_accounts import start
    c,h=create(client,'hr')
    start(client,c,h)
    with DB() as db:
        s=db.get(Session,c['id']);s.body=s.body|{'proctor_config':ProctorConfig(auto_terminate=True,max_violations=2).model_dump()};db.commit()
    client.post(f'/api/sessions/{c["id"]}/observations',headers=h,json=event('fullscreen_exit'))
    client.post(f'/api/sessions/{c["id"]}/observations',headers=h,json=event('screen_returned','return'))
    client.post(f'/api/sessions/{c["id"]}/observations',headers=h,json=event('fullscreen_exit','second'))
    result=client.get(f'/api/sessions/{c["id"]}/monitoring',headers=h).json()
    assert result['status']=='terminated'
    assert client.post(f'/api/sessions/{c["id"]}/questions',headers=h).status_code==409

def test_low_confidence_device_is_rejected(client):
    c,h=create(client,'hr');url=f'/api/sessions/{c["id"]}/observations'
    assert client.post(url,headers=h,json=event('device',label='mobile phone',score=.2)).status_code==422
    assert client.post(url,headers=h,json=event('device',label='mobile phone',score=.8)).status_code==200
    result=client.get(f'/api/sessions/{c["id"]}/monitoring',headers=h).json()
    assert result['events'][0]['event_type']=='PHONE_DETECTED'
    assert result['events'][0]['confidence']==.8

def test_omitted_or_disabled_microphone_blocks_health(client):
    c,h=create(client,'hr')
    client.post(f'/api/sessions/{c["id"]}/monitoring/storage-check',headers=h)
    health=dict(camera=True,page_visible=True,fullscreen=True,face_age_ms=1,object_age_ms=1,object_latency_ms=1,evidence_ready=True,face_coverage=1,object_coverage=1)
    url=f'/api/sessions/{c["id"]}/monitoring/heartbeat'
    assert not client.post(url,headers=h,json=health).json()['healthy']
    assert not client.post(url,headers=h,json=health|{'microphone':False}).json()['healthy']
    assert client.post(url,headers=h,json=health|{'microphone':True}).json()['healthy']
