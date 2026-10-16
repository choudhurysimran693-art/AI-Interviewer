import time
from test_accounts import staff
from app.db import DB,User,Application,Session,RecruitmentPosition,InterviewRound,ApplicationRound

def seed(client):
    hr=staff();other=staff(email='candidate-outsider@example.test')
    pids=[hr.post('/api/positions',json={'title':title,'vacancies_total':1}).json()['id'] for title in ['Data Analyst','Developer']]
    foreign=other.post('/api/positions',json={'title':'Other organization'}).json()['id']
    ids=[];uids=[]
    with DB() as db:
        for idx,(pid,status,score) in enumerate([(pids[0],'applied',None),(pids[0],'shortlisted',85),(pids[1],'under_review',0),(pids[1],'offer_extended',60),(foreign,'applied',99)]):
            u=User(email=f'person{idx}@example.test',name=f'Person {idx}',role='candidate',password_hash='test',body={});db.add(u);db.flush();uids.append(u.id)
            a=Application(candidate_id=u.id,position_id=pid,status=status,updated_at=100+idx);db.add(a);db.flush();ids.append(a.id)
            if score is not None:db.add(Session(mode='hr',token_hash='candidate-test-'+str(idx),status='complete',expires=9999999999,body={'application_id':a.id,'position_id':pid,'summary':{'overall':score},'ended_at':time.time()}))
        # Same person applying for another role must receive a separate card and score.
        second=Application(candidate_id=uids[1],position_id=pids[1],status='applied',updated_at=200);db.add(second);db.flush();ids.append(second.id)
        # A missing score on the latest completed attempt must not reuse an older score.
        db.add(Session(mode='hr',token_hash='missing-latest',status='complete',expires=9999999999,body={'application_id':ids[3],'position_id':pids[1],'summary':{'overall':None},'ended_at':time.time()+1}))
        db.commit()
    return hr,other,pids,foreign,ids,uids

def test_candidate_filters_counts_pagination_and_profile(client):
    hr,other,p,foreign,ids,uids=seed(client)
    result=hr.get('/api/candidates?page_size=2').json()
    assert result['total_count']==5 and result['organization_total']==5
    assert [r['id'] for r in result['items']]==[ids[5],ids[3]]
    rows=hr.get('/api/candidates').json()['items'];assert next(r for r in rows if r['id']==ids[5])['overall_score'] is None
    assert next(r for r in rows if r['id']==ids[3])['overall_score'] is None
    assert hr.get('/api/candidates?min_score=1').json()['total_count']==1
    assert hr.get('/api/candidates?min_score=0').json()['total_count']==5
    q='?search=PERSON%201&position_id='+p[0]+'&min_score=80&stages=shortlisted'
    filtered=hr.get('/api/candidates'+q).json();assert [r['id'] for r in filtered['items']]==[ids[1]]
    counts=hr.get('/api/candidates/filter-counts?search=person&min_score=1').json()
    assert counts=={'source':0,'shortlisted':1,'screening':0,'interview':0,'offer':0,'hired':0,'rejected':0}
    assert hr.get('/api/candidates?search=%25').json()['total_count']==0
    assert hr.get('/api/candidates?stages=source,screening').json()['total_count']==3
    assert hr.get('/api/candidates?stages=unknown').status_code==422
    assert hr.get('/api/candidates?min_score=101').status_code==422
    assert hr.get('/api/candidates?sort=invalid').status_code==422
    profile=hr.get('/api/candidates/'+uids[1]).json();assert len(profile['applications'])==2
    assert len(profile['interviews'])==1
    assert other.get('/api/candidates/'+uids[1]).status_code==404
    assert hr.get('/api/candidates?position_id='+foreign).status_code==404
    assert hr.get('/api/candidates/filter-counts?position_id='+foreign).status_code==404
    assert client.get('/api/candidates').status_code==403
    assert client.get('/api/candidates/filter-counts').status_code==403
    assert client.get('/api/candidates/'+uids[1]).status_code==403

def test_bulk_move_partial_scope_workflow_and_hire_capacity(client):
    hr,other,p,foreign,ids,uids=seed(client)
    response=hr.patch('/api/applications/bulk-move',json={'application_ids':[ids[0],ids[4]],'target_stage':'shortlisted'})
    assert response.status_code==200,response.text
    assert response.json()['success_count']==1 and response.json()['failure_count']==1
    with DB() as db:
        assert db.get(Application,ids[0]).status=='shortlisted'
        assert db.get(Application,ids[4]).status=='applied'
        assert db.get(Application,ids[0]).updated_at>200
    assert hr.patch('/api/applications/bulk-move',json={'application_ids':[ids[5]],'target_stage':'interview'}).json()['failure_count']==1
    with DB() as db:
        for aid in [ids[0],ids[1]]:
            a=db.get(Application,aid);a.status='offer_extended'
        db.commit()
    result=hr.patch('/api/applications/bulk-move',json={'application_ids':[ids[0],ids[1]],'target_stage':'hired'}).json()
    assert result['success_count']==result['failure_count']==1
    with DB() as db:
        position=db.get(RecruitmentPosition,p[0]);assert position.body['vacancies_filled']==1 and position.body['status']=='closed'
    hired=next(r['id'] for r in result['results'] if r['success'])
    assert hr.patch('/api/applications/bulk-move',json={'application_ids':[hired,hired],'target_stage':'hired'}).json()['success_count']==1
    with DB() as db:assert db.get(RecruitmentPosition,p[0]).body['vacancies_filled']==1
    assert client.patch('/api/applications/bulk-move',json={'application_ids':[hired],'target_stage':'hired'}).status_code==403

def test_round_stage_consistency_and_in_progress(client):
    hr,other,p,foreign,ids,uids=seed(client)
    with DB() as db:
        r=InterviewRound(position_id=p[0],round_order=1,round_type='technical',round_name='Technical');db.add(r);db.flush();db.add(ApplicationRound(application_id=ids[0],round_id=r.id,status='invited'));db.commit()
    row=next(r for r in hr.get('/api/candidates').json()['items'] if r['id']==ids[0])
    assert row['pipeline_stage']=='interview' and row['assessment_status']=='in_progress'
    assert hr.get('/api/candidates/filter-counts').json()['interview']==1
    assert hr.get('/api/positions/'+p[0]+'/pipeline-summary').json()['interview']==1
