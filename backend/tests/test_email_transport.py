from types import SimpleNamespace
from sqlalchemy import select
import httpx
from app.config import settings
from app.db import DB,EmailDelivery,Question,Answer,Session
from app import email_delivery
from app.accounts import send_recovery_email
from test_accounts import assigned,start


def brevo(monkeypatch):
    monkeypatch.setattr(settings,'email_provider','brevo')
    monkeypatch.setattr(settings,'brevo_api_key','fake-test-key')
    monkeypatch.setattr(settings,'email_from','AI Interviewer <sender@example.test>')
    monkeypatch.setattr(settings,'public_url','https://interview.example.test')


def test_recovery_uses_https_and_production_link(monkeypatch):
    brevo(monkeypatch);calls=[]
    def post(url,**kwargs):
        calls.append((url,kwargs));return httpx.Response(201,request=httpx.Request('POST',url),json={'messageId':'test'})
    monkeypatch.setattr(email_delivery.httpx,'post',post)
    assert send_recovery_email(SimpleNamespace(name='Candidate',email='candidate@example.test'),'test-token')
    url,args=calls[0]
    assert url=='https://api.brevo.com/v3/smtp/email'
    assert args['headers']['api-key']=='fake-test-key'
    assert args['json']['to']==[{'email':'candidate@example.test'}]
    assert 'https://interview.example.test/?reset=test-token' in args['json']['textContent']
    assert args['json']['sender']['email']=='sender@example.test'


def test_delivery_retries_and_marks_sent(client,monkeypatch):
    brevo(monkeypatch)
    with DB() as db:
        db.add(EmailDelivery(id='mail-test',body={'name':'Alex','recipient':'candidate@example.test','title':'Invitation','message':'Interview ready','company':'Company','href':'/candidate/interview'}));db.commit()
    def fail(*args,**kwargs):raise httpx.ConnectError('network failure')
    monkeypatch.setattr(email_delivery.httpx,'post',fail)
    assert email_delivery.deliver_once()
    with DB() as db:
        row=db.get(EmailDelivery,'mail-test');assert row.status=='pending' and row.attempts==1
        row.next_attempt=0;db.commit()
    monkeypatch.setattr(email_delivery.httpx,'post',lambda url,**kwargs:httpx.Response(201,request=httpx.Request('POST',url)))
    assert email_delivery.deliver_once()
    with DB() as db:assert db.get(EmailDelivery,'mail-test').status=='sent'


def test_results_email_is_queued_once_after_completion(client):
    c,h,hr,aid=assigned(client);start(client,c,h);base='/api/sessions/'+c['id']
    qs=client.post(base+'/questions',headers=h).json()['questions']
    with DB() as db:
        for q in qs:db.add(Answer(session_id=c['id'],body={'question_id':q['id'],'approved':True,'evaluation':{'status':'scored','technical':80,'communication':80},'transcript':'test','duration':1,'metrics':{}}))
        db.commit()
    r=client.post(base+'/complete',headers=h);assert r.status_code==200,r.text
    assert client.post(base+'/complete',headers=h).status_code==200
    with DB() as db:
        row=db.get(EmailDelivery,'interview-results:'+c['id'])
        assert row and '80.0/100' in row.body['message']
        assert row.body['recipient']=='candidate@example.test'
    assert client.get('/api/recruitment/email-status').status_code==403
    assert hr.get('/api/recruitment/email-status').status_code==200


def test_resend_queues_without_network_io(client,monkeypatch):
    brevo(monkeypatch);c,h,hr,aid=assigned(client)
    monkeypatch.setattr(email_delivery.httpx,'post',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('Request must not send synchronously')))
    r=hr.post('/api/recruitment/interviews/'+aid+'/resend')
    assert r.status_code==200,r.text
    assert r.json()['delivery']=='queued'
    rows=hr.get('/api/recruitment/email-status').json()
    assert rows['configured'] and any(x['title']=='Your assigned interview' and x['status']=='pending' for x in rows['items'])


def test_email_status_does_not_expose_another_organization(client,monkeypatch):
    from test_accounts import staff
    brevo(monkeypatch);c,h,hr,aid=assigned(client)
    assert hr.post('/api/recruitment/interviews/'+aid+'/resend').status_code==200
    other=staff(email='email-outsider@example.test')
    assert other.get('/api/recruitment/email-status').json()['items']==[]


def test_background_job_polling_does_not_block_requests(client,monkeypatch):
    import asyncio,time
    from app import jobs
    async def slow_poll():
        time.sleep(.2)
        return False
    monkeypatch.setattr(jobs,'work_once',slow_poll)
    async def check():
        stop=asyncio.Event();task=asyncio.create_task(jobs.worker(stop))
        before=time.monotonic();await asyncio.sleep(.02)
        elapsed=time.monotonic()-before;stop.set();await task
        assert elapsed<.15
    asyncio.run(check())
