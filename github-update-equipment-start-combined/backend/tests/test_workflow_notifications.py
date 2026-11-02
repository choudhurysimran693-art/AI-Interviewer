import time
import pytest
from sqlalchemy import select
from app.db import DB, WorkflowNotification, CandidateNotice, EmailDelivery, ApplicationRound, Application
from app.notifier import notify
from app.config import settings
from app import email_delivery
from test_round_templates import setup


@pytest.mark.parametrize('fail',[False,True],ids=['all-six-selected','round-three-rejected'])
def test_results_and_duplicates(client,fail):
    hr,pid,aid=setup(client)
    with DB() as db:
        rows=list(db.scalars(select(WorkflowNotification).where(WorkflowNotification.application_id==aid,WorkflowNotification.type=='next_round')))
        assert len(rows)==1 and rows[0].round_no==1
        first=rows[0];key=first.id
        inbox=db.get(CandidateNotice,key)
        assert 'Aptitude' in first.title and '?assignment=' in inbox.body['href']
        assert inbox.body['window_end_at']>time.time()
        assert db.get(EmailDelivery,key)
        notify(aid,'next_round',1,db=db);db.commit()
        assert len(list(db.scalars(select(WorkflowNotification).where(WorkflowNotification.id==key))))==1
    assert client.patch('/api/candidate/notifications/'+key+'/read').status_code==200
    with DB() as db:assert db.get(WorkflowNotification,key).is_read
    for number in range(2,7):
        r=hr.get(f'/api/hr/applications/{aid}/rounds').json()[number-1]
        with DB() as db:
            row=db.get(ApplicationRound,r['id']);row.status='scheduled' if number==6 else 'completed';row.score=80
            if number==6:row.scheduling={'scheduled_at':time.time()-60}
            db.commit()
        decision='failed' if fail and number==3 else 'passed'
        endpoint='/api/application-rounds/'+r['id']+'/decision'
        assert hr.patch(endpoint,json={'status':decision,'hr_notes':'Reviewed'}).status_code==200
        assert hr.patch(endpoint,json={'status':decision,'hr_notes':'Reviewed'}).status_code==200
        if decision=='failed':break
    kind='rejected' if fail else 'selected'
    with DB() as db:
        rows=list(db.scalars(select(WorkflowNotification).where(WorkflowNotification.application_id==aid,WorkflowNotification.type==kind)))
        assert len(rows)==1 and rows[0].round_no==(3 if fail else 6)
        assert db.get(CandidateNotice,rows[0].id) and db.get(EmailDelivery,rows[0].id)
        if fail:assert 'Technical Assessment' in rows[0].message


def test_delivery_failure_retry_dry_run_and_access(client,monkeypatch,capsys):
    hr,pid,aid=setup(client)
    with DB() as db:
        app=db.get(Application,aid);candidate=app.candidate_id
        row=db.scalar(select(WorkflowNotification).where(WorkflowNotification.type=='next_round'));key=row.id
        # Deliver only this event; other stage/invitation messages remain queued.
        for email in db.scalars(select(EmailDelivery)):email.next_attempt=0 if email.id==key else time.time()+10000
        db.commit()
    monkeypatch.setattr(settings,'dry_run',True)
    original=email_delivery.send_message
    def failure(message):raise RuntimeError('private-provider-secret')
    monkeypatch.setattr(email_delivery,'send_message',failure)
    assert email_delivery.deliver_once()
    with DB() as db:
        row=db.get(WorkflowNotification,key)
        assert row.email_status.startswith('failed: RuntimeError') and 'secret' not in row.email_status
        assert db.get(CandidateNotice,key)
        assert db.get(Application,aid).status=='shortlisted'
    assert client.get(f'/api/hr/candidates/{candidate}/workflow-notifications').status_code==403
    assert client.post('/api/hr/workflow-notifications/'+key+'/retry').status_code==403
    from test_accounts import staff
    other=staff(email='other-notifications@example.test')
    assert other.get(f'/api/hr/candidates/{candidate}/workflow-notifications').json()==[]
    assert other.post('/api/hr/workflow-notifications/'+key+'/retry').status_code==404
    assert hr.post('/api/hr/workflow-notifications/'+key+'/retry').json()['queued']
    monkeypatch.setattr(email_delivery,'send_message',original)
    assert email_delivery.deliver_once()
    assert '[DRY_RUN EMAIL]' in capsys.readouterr().out
    with DB() as db:assert db.get(WorkflowNotification,key).email_status=='dry_run'
    assert hr.get(f'/api/hr/candidates/{candidate}/workflow-notifications').status_code==200


def test_stage_dropdown_rejection_queues_once(client):
    hr,pid,aid=setup(client)
    for _ in range(2):
        assert hr.patch(f'/api/applications/{aid}/status',json={'status':'rejected'}).status_code==200
    with DB() as db:
        rows=list(db.scalars(select(WorkflowNotification).where(WorkflowNotification.application_id==aid,WorkflowNotification.type=='rejected')))
        assert len(rows)==1


def test_unconfigured_delivery_and_transaction_rollback(client,monkeypatch):
    hr,pid,aid=setup(client)
    monkeypatch.setattr(settings,'dry_run',False)
    monkeypatch.setattr(settings,'email_provider','smtp')
    monkeypatch.setattr(settings,'smtp_host','')
    assert not email_delivery.deliver_once()
    with DB() as db:
        row=db.scalar(select(WorkflowNotification).where(WorkflowNotification.type=='next_round'))
        assert row.email_status=='failed: Email delivery is not configured.'
        assert db.get(CandidateNotice,row.id)
        aborted=notify(aid,'stage_rollback_test',2,db=db).id
        db.rollback()
    with DB() as db:
        assert db.get(WorkflowNotification,aborted) is None
        assert db.get(CandidateNotice,aborted) is None
        assert db.get(EmailDelivery,aborted) is None
