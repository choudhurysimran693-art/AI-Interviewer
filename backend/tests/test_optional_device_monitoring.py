from test_accounts import assigned
from app.db import DB, Session


def test_hr_without_validated_device_detector(client, monkeypatch):
    monkeypatch.setattr('app.main.validation_status', lambda: {'passed': False, 'reason': 'Not validated'})
    c, h, _, _ = assigned(client)
    base = '/api/sessions/' + c['id']
    assert client.get(base + '/monitoring', headers=h).json()['config']['device_detection_enabled'] is False
    assert client.post(base + '/monitoring/storage-check', headers=h).status_code == 200
    health = dict(camera=True, microphone=True, face_count=1, page_visible=True,
                  fullscreen=True, face_age_ms=1, object_age_ms=999999,
                  object_latency_ms=999999, evidence_ready=True, face_coverage=1, object_coverage=0)
    assert client.post(base + '/monitoring/heartbeat', headers=h, json=health).json()['healthy']
    assert client.post(base + '/start', headers=h, json={'rules_acknowledged': True}).status_code == 200
    assert client.post(base + '/questions', headers=h).status_code == 200
    for change in [{'camera': False}, {'microphone': False}, {'face_age_ms': 999999},
                   {'fullscreen': False}, {'page_visible': False}, {'evidence_ready': False}]:
        assert not client.post(base + '/monitoring/heartbeat', headers=h, json=health | change).json()['healthy']
    assert client.post(base + '/observations', headers=h, json={
        'id': 'unvalidated-device', 'type': 'device', 'label': 'mobile phone', 'score': .99, 'timestamp': 1,
        'duration': 1, 'stage': 'answer', 'face_coverage': 1, 'object_coverage': 0
    }).status_code == 409
    assert client.post(base + '/device-warning', headers=h, json={'event_id': 'forged'}).status_code == 409
    with DB() as db:
        assert not db.get(Session, c['id']).body.get('security', {}).get('device_warning_count')


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
