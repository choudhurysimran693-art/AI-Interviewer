from sqlalchemy import select,func,event
from app.db import DB,Session,Question,Answer,Job,engine
from app.question_bank import seed_bank
from test_accounts import assigned,start


def test_mcq_submission_immediate_and_idempotent(client):
    c,h,_,_=assigned(client)
    with DB() as db:
        s=db.get(Session,c['id']);s.body=s.body|{'round_type':'aptitude'};db.commit()
    start(client,c,h);base='/api/sessions/'+c['id']
    qs=client.post(base+'/questions',headers=h).json()['questions']
    assert len(qs)==15
    assert client.post(base+'/mcq',headers=h,json={'question_id':qs[1]['id'],'selected':[qs[1]['options'][0]['id']]}).status_code==409
    assert client.post(base+'/mcq',headers=h,json={'question_id':qs[0]['id'],'selected':['invalid']}).status_code==422
    for q in qs[:2]:
        with DB() as db:key=db.get(Question,q['id']).body['expected_points'][0].split(',')
        response=client.post(base+'/mcq',headers=h,json={'question_id':q['id'],'selected':key})
        assert response.status_code==200,response.text
        assert response.json()['approved'] and response.json()['evaluation']['technical']==100
        assert 'expected_points' not in response.json()
        retry=client.post(base+'/mcq',headers=h,json={'question_id':q['id'],'selected':key})
        assert retry.json()==response.json()
    with DB() as db:
        assert db.scalar(select(func.count()).select_from(Job).where(Job.session_id==c['id']))==0
        assert db.scalar(select(func.count()).select_from(Answer).where(Answer.session_id==c['id']))==2
    client.post(base+'/monitoring/heartbeat',headers=h,json={'camera':False,'microphone':False,'face_age_ms':1,'object_age_ms':1,'evidence_ready':True,'face_coverage':1,'object_coverage':1})
    assert client.post(base+'/mcq',headers=h,json={'question_id':qs[2]['id'],'selected':[qs[2]['options'][0]['id']]}).status_code==409


def test_repeated_bank_seed_is_one_read_without_updates(client):
    with DB() as db:seed_bank(db)
    statements=[]
    def record(conn,cursor,statement,parameters,context,executemany):statements.append(statement)
    event.listen(engine,'before_cursor_execute',record)
    try:
        with DB() as db:seed_bank(db)
    finally:event.remove(engine,'before_cursor_execute',record)
    assert len([s for s in statements if s.lstrip().upper().startswith('SELECT')])==1
    assert not any(s.lstrip().upper().startswith(('INSERT','UPDATE','DELETE')) for s in statements)
