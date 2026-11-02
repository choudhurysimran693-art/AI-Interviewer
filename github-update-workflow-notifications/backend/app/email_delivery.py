"""Transactional email outbox: schedule commits first, delivery retries independently."""
import asyncio
import hashlib
import smtplib
import ssl
import time
import httpx
from datetime import datetime, timezone
from email.message import EmailMessage
from sqlalchemy import select, update
from .config import settings
from .db import DB, EmailDelivery, WorkflowNotification

def configured():
    if settings.dry_run:return True
    if settings.email_provider == 'brevo':
        return bool(settings.brevo_api_key and settings.email_from)
    return bool(settings.smtp_host and settings.smtp_from)

def send_message(message):
    """One transport for invitations, results, and password recovery."""
    if settings.dry_run:
        print('[DRY_RUN EMAIL] '+message.as_string())
        return
    if not configured():raise RuntimeError('Email delivery is not configured.')
    if settings.email_provider == 'brevo':
        from email.utils import parseaddr
        name,address=parseaddr(settings.email_from)
        content=message.get_body(preferencelist=('plain',))
        response=httpx.post('https://api.brevo.com/v3/smtp/email',
            headers={'api-key':settings.brevo_api_key,'accept':'application/json'},
            json={'sender':{'email':address,'name':name or 'AI Interviewer'},
                  'to':[{'email':str(message['To'])}], 'subject':str(message['Subject']),
                  'textContent':content.get_content(), 'htmlContent':message.get_body(preferencelist=('html',)).get_content() if message.get_body(preferencelist=('html',)) else content.get_content()},timeout=15)
        response.raise_for_status()
        return
    transport=smtplib.SMTP_SSL if settings.smtp_port==465 else smtplib.SMTP
    kwargs={'context':ssl.create_default_context()} if settings.smtp_port==465 else {}
    with transport(settings.smtp_host,settings.smtp_port,timeout=15,**kwargs) as smtp:
        if settings.smtp_use_tls and settings.smtp_port!=465:smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_user:smtp.login(settings.smtp_user,settings.smtp_password)
        smtp.send_message(message)

def send(key,body):
    message=EmailMessage()
    message['Subject']=body['title']+' — '+body['company']
    message['From']=settings.email_from if settings.email_provider=='brevo' else settings.smtp_from;message['To']=body['recipient']
    message['Message-ID']='<'+hashlib.sha256(key.encode()).hexdigest()+'@interview-notifications>'
    text=f"Hello {body['name']},\n\n{body['company']}\n{body['message']}\n"
    if body.get('scheduled_at'):
        text+='\nInterview starts: '+datetime.fromtimestamp(body['scheduled_at'],timezone.utc).strftime('%d %B %Y, %H:%M UTC')+'\nYour workspace shows this time in your local timezone.\n'
    if body.get('window_end_at'):
        text+='\nInterview window ends: '+datetime.fromtimestamp(body['window_end_at'],timezone.utc).strftime('%d %B %Y, %H:%M UTC')+'\n'
    text+='\nView details: '+settings.public_url.rstrip('/')+body['href']+'\n\nSign in with your candidate account. Please contact the company’s HR team if you need help.'
    text=body.get('plain_text') or text
    message.set_content(text)
    from html import escape
    message.add_alternative(body.get('html') or '<html><body>'+''.join('<p>'+escape(part).replace('\n','<br>')+'</p>' for part in text.split('\n\n'))+'</body></html>',subtype='html')
    send_message(message)

def deliver_once():
    if not configured():
        with DB() as db:
            for notice in db.scalars(select(WorkflowNotification).where(WorkflowNotification.email_status=='pending')):
                notice.email_status='failed: Email delivery is not configured.'
            db.commit()
        return False # Keep outbox pending until an operator configures SMTP.
    now=time.time()
    with DB() as db:
        row=db.scalar(select(EmailDelivery).where(EmailDelivery.status.in_(['pending','sending']),EmailDelivery.next_attempt<=now).order_by(EmailDelivery.next_attempt).limit(1))
        if not row:return False
        key,body,attempts=row.id,row.body,row.attempts
        claimed=db.execute(update(EmailDelivery).where(EmailDelivery.id==key,EmailDelivery.status==row.status,EmailDelivery.next_attempt==row.next_attempt,EmailDelivery.attempts==attempts).values(status='sending',attempts=attempts+1,next_attempt=now+180))
        db.commit()
        if not claimed.rowcount:return False
    try:
        from .notifier import send_email
        send_email(key,body)
    except Exception as exc:
        with DB() as db:
            row=db.get(EmailDelivery,key)
            row.status='failed' if attempts+1>=5 else 'pending'
            notice=db.get(WorkflowNotification,key)
            if notice:notice.email_status='failed: '+type(exc).__name__+'; check provider configuration or recipient.'
            row.next_attempt=time.time()+min(3600,30*2**attempts)
            row.body=row.body|{'delivery_error':'Email delivery failed. Check email provider credentials, verified sender, and recipient address.'}
            db.commit()
    else:
        with DB() as db:
            row=db.get(EmailDelivery,key);row.status='sent'
            row.body=row.body|{'sent_at':time.time(),'delivery_error':None}
            notice=db.get(WorkflowNotification,key)
            if notice:notice.email_status='dry_run' if settings.dry_run else 'sent'
            db.commit()
    return True

async def email_worker(stop):
    while not stop.is_set():
        try:await asyncio.to_thread(deliver_once)
        except Exception:pass # Preserve the outbox; try again on the next loop.
        try:await asyncio.wait_for(stop.wait(),timeout=5)
        except asyncio.TimeoutError:pass
