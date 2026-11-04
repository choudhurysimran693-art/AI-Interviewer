"""Short persisted simulations: score production is stubbed, progression is real."""
import time
import pytest
from app.db import DB,ApplicationRound
from test_round_templates import setup


@pytest.mark.parametrize('fail_round',[None,3],ids=['pass-all-six','fail-at-round-three'])
def test_six_round_progression(client,fail_round):
    hr,pid,aid=setup(client)
    # Round 1 is reviewed by HR during shortlisting in this application's workflow.
    rows=hr.get(f'/api/hr/applications/{aid}/rounds').json()
    assert len(rows)==6 and rows[0]['status']=='passed'
    for number in range(2,7):
        rows=hr.get(f'/api/hr/applications/{aid}/rounds').json()
        row=rows[number-1]
        assert row['is_current'] and all(x['status']=='passed' for x in rows[:number-1])
        assert all(x['status']=='pending' for x in rows[number:])
        with DB() as db:
            stored=db.get(ApplicationRound,row['id'])
            stored.score=30 if number==fail_round else 80
            stored.status='scheduled' if number==6 else 'completed'
            if number==6:stored.scheduling={'scheduled_at':time.time()-60}
            db.commit()
        outcome='failed' if number==fail_round else 'passed'
        result=hr.patch('/api/application-rounds/'+row['id']+'/decision',json={'status':outcome,'hr_notes':'Reviewed simulation outcome.'})
        assert result.status_code==200,result.text
        if outcome=='failed':break
    application=client.get('/api/candidate/applications').json()[0]
    if fail_round:
        assert application['status']=='rejected'
        assert application['rounds'][2]['status']=='failed'
        assert all(r['status']=='pending' and not r['can_start'] for r in application['rounds'][3:])
    else:
        assert application['status']=='hired' # Existing production name for selected.
        assert all(r['status']=='passed' for r in application['rounds'])


def test_later_round_cannot_be_decided_even_with_stale_completed_state(client):
    hr,pid,aid=setup(client)
    rows=hr.get(f'/api/hr/applications/{aid}/rounds').json()
    with DB() as db:
        r=db.get(ApplicationRound,rows[3]['id']);r.status='completed';r.score=90;db.commit()
    response=hr.patch('/api/application-rounds/'+rows[3]['id']+'/decision',json={'status':'passed','hr_notes':'Out of order'})
    assert response.status_code==409
    assert 'previous rounds' in response.text


def test_current_round_exposes_resume_action(client):
    hr,pid,aid=setup(client)
    rows=hr.get(f'/api/hr/applications/{aid}/rounds').json();r=rows[1]
    created=client.post('/api/sessions',json={'assignment_id':r['assignment_id'],'mode':'hr','name':'Alex Example','role':'Engineer','level':'junior','profile':{},'processing_consent':True,'evidence_consent':True})
    assert created.status_code==200,created.text
    refreshed=client.get('/api/candidate/applications').json()[0]['rounds']
    assert refreshed[1]['can_resume'] and refreshed[1]['resume_session_id']==created.json()['id']
    assert not refreshed[1]['can_start']
    assert all(not row['can_start'] and not row['can_resume'] for row in refreshed[2:])
