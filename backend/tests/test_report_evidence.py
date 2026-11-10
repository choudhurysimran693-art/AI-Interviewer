"""Final reports remain available when supplementary evidence is missing."""
import pytest
from sqlalchemy import select, func
from app.db import DB, Session, Question, Observation, Snapshot, Report
from test_accounts import assigned, start


@pytest.mark.parametrize('pending_snapshot', [False, True])
def test_report_with_missing_device_image(client, pending_snapshot):
    c,h,_,_=assigned(client)
    base='/api/sessions/'+c['id']
    with DB() as db:
        s=db.get(Session,c['id']);s.body=s.body|{'round_type':'aptitude'};db.commit()
    start(client,c,h)
    qs=client.post(base+'/questions',headers=h).json()['questions']
    assert client.post(base+'/complete',headers=h).status_code==409
    for q in qs:
        with DB() as db:key=db.get(Question,q['id']).body['expected_points'][0].split(',')
        assert client.post(base+'/mcq',headers=h,json={'question_id':q['id'],'selected':key}).status_code==200
    with DB() as db:
        db.add(Observation(id='missing-picture',session_id=c['id'],body={'type':'device','timestamp':1,'duration':1,'label':'phone','stage':'answer'}))
        if pending_snapshot:db.add(Snapshot(id='missing-picture',session_id=c['id'],body={'ready':False,'key':'pending.jpg'}))
        s=db.get(Session,c['id']);s.body=s.body|{'monitoring':{'healthy':False,'received':0}};db.commit()
    result=client.post(base+'/complete',headers=h)
    assert result.status_code==200,result.text
    assert client.post(base+'/complete',headers=h).json()==result.json()
    report=client.get('/api/reports/'+result.json()['candidate'].split('/')[-1])
    assert report.status_code==200,report.text
    assert report.json()['summary']['technical']==100
    assert report.json()['proctor_summary']['review_required']
    assert report.json()['observations'][0]['snapshot'] is False
    with DB() as db:
        assert db.get(Session,c['id']).body['missing_evidence']==['missing-picture']
        assert db.scalar(select(func.count()).select_from(Report).where(Report.session_id==c['id']))==2
