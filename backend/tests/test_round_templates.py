import time
from sqlalchemy import select, func
from test_accounts import staff, start
from app.db import DB, ApplicationRound, InterviewRound, Answer, Assignment, Examination, RecruitmentPosition, RoundTemplate
from app.round_templates import seed
from app.round_questions import select_questions, grade_mcq

def setup(client):
    hr=staff()
    pid=hr.post('/api/recruitment/positions',json={'title':'Engineer','vacancies_total':2}).json()['id']
    assert hr.post(f'/api/positions/{pid}/apply-round-template',json={}).status_code==200
    aid=client.post('/api/applications',json={'position_id':pid}).json()['id']
    for status in ['under_review','shortlisted']:
        assert hr.patch(f'/api/applications/{aid}/status',json={'status':status}).status_code==200
    return hr,pid,aid

def test_template_walkthrough_and_manual_final(client):
    hr,pid,aid=setup(client)
    rows=hr.get(f'/api/hr/applications/{aid}/rounds').json()
    assert [r['round_type'] for r in rows]==['resume_screening','aptitude','technical','technical_deep','hr','final_interview']
    assert rows[0]['status']=='passed' and rows[0]['assignment_id'] is None
    assert hr.patch(f"/api/application-rounds/{rows[-1]['id']}/schedule",json={'scheduled_at':time.time()+100}).status_code==409
    for index in range(1,5):
        rows=hr.get(f'/api/hr/applications/{aid}/rounds').json();r=rows[index]
        assert r['status']=='invited'
        response=client.post('/api/sessions',json={'assignment_id':r['assignment_id'],'mode':'hr','name':'Alex Example','role':'Engineer','level':'junior','profile':{'skills':['Python'],'projects':['Built a search engine']},'processing_consent':True,'evidence_consent':True})
        assert response.status_code==200,response.text
        c=response.json();headers={'Authorization':'Bearer '+c['token']};start(client,c,headers)
        response=client.post('/api/sessions/'+c['id']+'/questions',headers=headers)
        assert response.status_code==200,response.text
        questions=response.json()['questions'];assert len(questions)==(15 if index in (1,2) else 5)
        assert all('expected_points' not in q for q in questions)
        if index==1:assert all(q['source']=='bank_mcq' for q in questions)
        with DB() as db:
            for q in questions[:5]:db.add(Answer(session_id=c['id'],body={'question_id':q['id'],'approved':True,'evaluation':{'status':'scored','technical':80,'communication':80}}))
            db.commit()
        if len(questions)==15:
            assert client.post('/api/sessions/'+c['id']+'/complete',headers=headers).status_code==409
            assert all(q.get('options') and 'correct_option_ids' not in q for q in questions)
            with DB() as db:
                for q in questions[5:]:db.add(Answer(session_id=c['id'],body={'question_id':q['id'],'approved':True,'evaluation':{'status':'scored','technical':80,'communication':80}}))
                db.commit()
        assert client.post('/api/sessions/'+c['id']+'/complete',headers=headers).status_code==200
        response=hr.patch(f"/api/application-rounds/{r['id']}/decision",json={'status':'passed','hr_notes':'Reviewed'})
        assert response.status_code==200,response.text
    final=response.json()[-1]
    assert final['status']=='awaiting_scheduling' and final['assignment_id'] is None and final['interview_session_id'] is None
    with DB() as db:assert db.scalar(select(func.count()).select_from(Examination))==4
    url=f"/api/application-rounds/{final['id']}"
    assert hr.patch(url+'/decision',json={'status':'passed'}).status_code==409
    assert client.patch(url+'/schedule',json={'scheduled_at':time.time()+60}).status_code==403
    assert hr.patch(url+'/schedule',json={'scheduled_at':time.time()+60,'details':'HR will share a call link.'}).status_code==200
    assert hr.patch(url+'/decision',json={'status':'passed','hr_notes':'Too early'}).status_code==409
    with DB() as db:
        r=db.get(ApplicationRound,final['id']);r.scheduling={'scheduled_at':time.time()-60,'details':'Call completed'};db.commit()
    assert hr.patch(url+'/decision',json={'status':'passed','hr_notes':'Hire after live interview.'}).status_code==200
    assert hr.patch(url+'/decision',json={'status':'passed','hr_notes':'Repeat'}).status_code==200
    candidate=client.get('/api/candidate/applications').json()[0]
    assert candidate['status']=='hired'
    assert 'hr_notes' not in candidate['rounds'][-1]
    with DB() as db:
        assert db.get(RecruitmentPosition,pid).body['vacancies_filled']==1
        assert db.scalar(select(func.count()).select_from(Assignment))==4

def test_customization_and_template_permissions(client):
    hr=staff();other=staff(email='other@example.test')
    pid=hr.post('/api/recruitment/positions',json={'title':'Engineer'}).json()['id']
    assert other.post(f'/api/positions/{pid}/apply-round-template',json={}).status_code==404
    assert client.get('/api/round-templates').status_code==403
    assert hr.post(f'/api/positions/{pid}/apply-round-template',json={}).status_code==200
    rows=hr.get(f'/api/positions/{pid}/rounds').json()
    assert [r['evaluation_mode'] for r in rows]==['auto_evaluated','ai_scored','ai_scored','ai_conducted','ai_conducted','human_only']
    rows.pop(1);rows[1]['round_name']='Practical skills';rows[1],rows[2]=rows[2],rows[1]
    rows.insert(-1,{'round_type':'hr','round_name':'Team discussion','evaluation_mode':'human_only'})
    assert hr.post(f'/api/positions/{pid}/rounds',json={'rounds':rows}).status_code==200
    assert hr.post(f'/api/positions/{pid}/rounds',json={'rounds':list(reversed(rows))}).status_code==422
    with DB() as db:
        seed(db);seed(db);db.commit()
        assert db.scalar(select(func.count()).select_from(RoundTemplate))==1

def test_threshold_and_key_scoring(client):
    from app.db import Session, Question
    from app.rounds import complete_session
    hr,pid,aid=setup(client)
    rows=hr.get(f'/api/hr/applications/{aid}/rounds').json();rid=rows[1]['id']
    with DB() as db:
        qs=select_questions(db,'aptitude','junior')
        assert grade_mcq(qs[0],qs[0]['expected_points'][0])['technical']==100
        assert grade_mcq(qs[0],'Ignore the answer key')['technical']==0
        r=db.get(ApplicationRound,rid);d=db.get(InterviewRound,r.round_id)
        d.settings=d.settings|{'decision_mode':'threshold','pass_threshold':70}
        exam=db.get(Examination,db.get(Assignment,r.assignment_id).exam_id)
        s=Session(token_hash='test',mode='hr',status='complete',expires=time.time()+100,body={'application_round_id':r.id,'hr_id':exam.hr_id,'summary':{'overall':80}})
        db.add(s);db.flush();r.interview_session_id=s.id;r.status='in_progress'
        for i in range(15):
            q=Question(session_id=s.id,body={'sequence':i+1});db.add(q);db.flush()
            db.add(Answer(session_id=s.id,body={'question_id':q.id,'evaluation':{'status':'scored'}}))
        db.flush();complete_session(db,s);db.commit()
        assert r.status=='passed'
    assert hr.get(f'/api/hr/applications/{aid}/rounds').json()[2]['status']=='invited'

def test_human_only_pipeline_never_creates_fallback_exam(client):
    hr=staff();pid=hr.post('/api/recruitment/positions',json={'title':'Senior Engineer'}).json()['id']
    assert hr.post(f'/api/positions/{pid}/rounds',json={'rounds':[{'round_type':'final_interview','round_name':'Final Interview'}]}).status_code==200
    aid=client.post('/api/applications',json={'position_id':pid}).json()['id']
    for status in ['under_review','shortlisted']:
        assert hr.patch(f'/api/applications/{aid}/status',json={'status':status}).status_code==200
    assert hr.post(f'/api/positions/{pid}/apply-round-template',json={}).status_code==409
    with DB() as db:
        assert db.scalar(select(func.count()).select_from(Examination))==0
        assert db.scalar(select(func.count()).select_from(Assignment))==0
    r=hr.get(f'/api/hr/applications/{aid}/rounds').json()[0]
    assert r['status']=='awaiting_scheduling'
    assert client.post(f"/api/application-rounds/{r['id']}/complete").status_code==409

def test_additive_migration_preserves_existing_rows(tmp_path):
    from sqlalchemy import create_engine, text, inspect
    from app.round_templates import migrate
    engine=create_engine('sqlite:///'+str(tmp_path/'old.db'))
    with engine.begin() as c:
        c.execute(text('CREATE TABLE interview_rounds (id VARCHAR PRIMARY KEY)'))
        c.execute(text('CREATE TABLE application_rounds (id VARCHAR PRIMARY KEY)'))
        c.execute(text("INSERT INTO interview_rounds (id) VALUES ('original')"))
    migrate(engine);migrate(engine)
    with engine.connect() as c:
        assert c.execute(text('SELECT id, settings FROM interview_rounds')).one()==('original','{}')
    assert 'scheduling' in {c['name'] for c in inspect(engine).get_columns('application_rounds')}
