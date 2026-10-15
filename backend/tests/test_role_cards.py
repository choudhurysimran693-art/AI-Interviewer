import time
from sqlalchemy import event
from test_accounts import staff
from app.db import DB, Application, RecruitmentPosition, User, InterviewRound, ApplicationRound, engine
from app.role_cards import pipeline_summaries


def test_role_cards_real_stages_batch_scope_and_days(client):
    hr=staff()
    pids=[hr.post('/api/positions',json={'title':title,'vacancies_total':n,'screening_type':'aptitude_first','level':'mid'}).json()['id'] for title,n in [('Analyst',10),('Developer',2)]]
    fresh=hr.get('/api/positions?include=pipeline_summary').json()['items']
    assert len(fresh)==2
    assert all(p['days_open']==0 and p['vacancies_filled']==0 and sum(p['pipeline_summary'].values())==0 for p in fresh)
    with DB() as db:
        p=db.get(RecruitmentPosition,pids[0]);p.body=p.body|{'opened_at':time.time()-5*86400}
        for idx,(status,kind,rstatus) in enumerate([('applied',None,None),('shortlisted',None,None),('under_review','resume_screening','completed'),('interview_scheduled','technical','invited'),('interviewed','hr','passed'),('hired',None,None),('rejected','technical','invited')]):
            user=User(email=f'role{idx}@example.test',name='Candidate',role='candidate',password_hash='unused',body={});db.add(user);db.flush()
            a=Application(candidate_id=user.id,position_id=pids[0],status=status);db.add(a);db.flush()
            if kind:
                r=InterviewRound(position_id=pids[0],round_order=idx,round_type=kind,round_name=kind);db.add(r);db.flush()
                db.add(ApplicationRound(application_id=a.id,round_id=r.id,status=rstatus))
        db.commit()
        statements=[]
        def capture(conn,cursor,statement,parameters,context,many):statements.append(statement)
        event.listen(engine,'before_cursor_execute',capture)
        try:summary=pipeline_summaries(db,pids)
        finally:event.remove(engine,'before_cursor_execute',capture)
        assert len(statements)==1
        assert all(n==1 for n in summary[pids[0]].values())
        assert sum(summary[pids[1]].values())==0
    rows=hr.get('/api/positions?include=pipeline_summary').json()['items']
    first=next(p for p in rows if p['id']==pids[0])
    assert first['days_open']==5 and first['level']=='mid'
    assert first['pipeline_summary']==hr.get('/api/positions/'+pids[0]+'/pipeline-summary').json()
    other=staff(email='outsider@example.test')
    assert other.get('/api/positions/'+pids[0]+'/pipeline-summary').status_code==404
    assert client.get('/api/positions').status_code==403


def test_pause_and_capacity_edit(client):
    hr=staff();pid=hr.post('/api/positions',json={'title':'Paused job','status':'paused'}).json()['id']
    assert not client.get('/api/positions/open').json()
    with DB() as db:
        p=db.get(RecruitmentPosition,pid);p.body=p.body|{'vacancies_filled':2,'vacancies_total':2};db.commit()
    assert hr.patch('/api/positions/'+pid,json={'title':'Paused job','vacancies_total':1}).status_code==409
    assert hr.patch('/api/positions/'+pid,json={'title':'Paused job','vacancies_total':2,'status':'open'}).status_code==200
    assert hr.get('/api/positions?status=').json()['items'][0]['status']=='closed'
