from test_accounts import assigned
from app.db import DB, Session
from test_accounts import start
from test_proctoring import event


def test_validated_tablet_first_warning_second_distinct_event_terminates(client, monkeypatch):
    monkeypatch.setattr('app.main.validation_status',lambda:{'passed':True})
    c,h,_,_=assigned(client);start(client,c,h)
    base='/api/sessions/'+c['id']
    first=event('device','tablet-first',label='tablet computer',score=.85)
    response=client.post(base+'/observations',headers=h,json=first)
    assert response.status_code==200
    assert response.json()['status']!='terminated'
    assert response.json()['security']['device_warning_count']==1
    client.post(base+'/device-warning/acknowledge',headers=h)
    duplicate=client.post(base+'/observations',headers=h,json=first)
    assert duplicate.json()['security']['device_warning_count']==1
    second=client.post(base+'/observations',headers=h,json=event('device','tablet-returned',label='tablet computer',score=.9))
    assert second.json()['status']=='terminated'
    assert second.json()['security']['device_warning_count']==2
    assert second.json()['security']['terminated_reason']=='device_detected_repeat'


def test_hr_without_validated_device_detector(client, monkeypatch):
    monkeypatch.setattr('app.main.validation_status', lambda: {'passed': False, 'reason': 'Not validated'})
    c, h, _, _ = assigned(client)
    base = '/api/sessions/' + c['id']
    config=client.get(base + '/monitoring', headers=h).json()['config']
    assert config['device_detection_enabled'] is True and config['device_warning_only'] is True
    assert client.post(base + '/monitoring/storage-check', headers=h).status_code == 200
    health = dict(camera=True, microphone=True, face_count=1, page_visible=True,
                  fullscreen=True, face_age_ms=1, object_age_ms=1,
                  object_latency_ms=1, evidence_ready=True, face_coverage=1, object_coverage=1)
    assert client.post(base + '/monitoring/heartbeat', headers=h, json=health).json()['healthy']
    assert client.post(base + '/start', headers=h, json={'rules_acknowledged': True}).status_code == 200
    assert client.post(base + '/questions', headers=h).status_code == 200
    for change in [{'camera': False}, {'microphone': False}, {'face_age_ms': 999999},
                   {'fullscreen': False}, {'page_visible': False}, {'evidence_ready': False}]:
        assert not client.post(base + '/monitoring/heartbeat', headers=h, json=health | change).json()['healthy']
    client.post(base + '/monitoring/heartbeat', headers=h, json=health)
    for event_id in ['first-device','second-device','second-device']:
        response=client.post(base + '/observations', headers=h, json={
        'id': event_id, 'type': 'device', 'label': 'mobile phone', 'score': .99, 'timestamp': 1,
        'duration': 1, 'stage': 'answer', 'face_coverage': 1, 'object_coverage': 0
        })
        assert response.status_code==200,response.text
        assert response.json()['status']!='terminated'
    assert client.post(base + '/device-warning', headers=h, json={'event_id': 'forged'}).status_code == 422
    assert client.post(base + '/device-warning', headers=h, json={'event_id': 'second-device'}).status_code == 200
    with DB() as db:
        state=db.get(Session,c['id']).body['security']
        assert state['device_warning_count']==2
        assert not state.get('terminated_reason')
    assert client.post(base+'/device-warning/acknowledge',headers=h).status_code==200


def test_mcq_camera_required_but_microphone_optional(client):
    c,h,_,_=assigned(client)
    base='/api/sessions/'+c['id']
    with DB() as db:
        s=db.get(Session,c['id']);s.body=s.body|{'round_type':'technical'};db.commit()
    assert client.get(base+'/monitoring',headers=h).json()['config']['microphone_required'] is False
    client.post(base+'/monitoring/storage-check',headers=h)
    health=dict(camera=True,microphone=False,face_count=1,page_visible=True,fullscreen=True,
                face_age_ms=1,object_age_ms=1,object_latency_ms=1,evidence_ready=True,face_coverage=1,object_coverage=1)
    assert client.post(base+'/monitoring/heartbeat',headers=h,json=health).json()['healthy']
    assert not client.post(base+'/monitoring/heartbeat',headers=h,json=health|{'camera':False}).json()['healthy']


def test_validated_detector_still_requires_fresh_inference(client, monkeypatch):
    monkeypatch.setattr('app.main.validation_status', lambda: {'passed': True})
    c, h, _, _ = assigned(client)
    base = '/api/sessions/' + c['id']
    assert client.get(base + '/monitoring', headers=h).json()['config']['device_detection_enabled'] is True
    client.post(base + '/monitoring/storage-check', headers=h)
    health = dict(camera=True, microphone=True, face_count=1, page_visible=True,
                  fullscreen=True, face_age_ms=1, object_age_ms=999999,
                  object_latency_ms=1, evidence_ready=True, face_coverage=1, object_coverage=0)
    assert not client.post(base + '/monitoring/heartbeat', headers=h, json=health).json()['healthy']
