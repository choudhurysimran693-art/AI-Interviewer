"""Transactional workflow notifications. Transport runs after the transaction commits."""
import hashlib
from datetime import datetime, timezone
from html import escape
from sqlalchemy import select
from .db import DB, Application, User, RecruitmentPosition, InterviewRound, Assignment, Examination, WorkflowNotification, EmailDelivery
from .candidate_notices import add_notice
from .config import settings


def build_message(kind: str, candidate, application, round_no: int, *, db) -> dict:
    """Build a plain text and escaped HTML snapshot using the actual next assignment."""
    from .rounds import rounds
    position=db.get(RecruitmentPosition,application.position_id)
    entries=rounds(db,application.id)
    definitions={r.id:db.get(InterviewRound,r.round_id) for r in entries}
    current=next((r for r in entries if definitions[r.id].round_order==round_no),None)
    name=definitions[current.id].round_name if current else 'Resume Screening' if round_no==1 else 'application review'
    href='/candidate/applications';deadline=None
    if kind=='next_round':
        upcoming=next((r for r in entries if definitions[r.id].round_order>round_no and r.status!='pending'),None)
        if upcoming:
            next_name=definitions[upcoming.id].round_name
            assignment=db.get(Assignment,upcoming.assignment_id) if upcoming.assignment_id else None
        else:
            next_name='interview'
            assignment=db.get(Assignment,application.assignment_id) if application.assignment_id and not entries else None
        title='Next round: '+next_name
        message=(f'You have been shortlisted for {position.body["title"]}. Start {next_name}.' if round_no==0 else f'You passed {name} for {position.body["title"]}. Your next round is {next_name}.')
        if assignment:
            exam=db.get(Examination,assignment.exam_id)
            href='/candidate/interview?assignment='+assignment.id
            deadline=exam.body.get('window_end_at')
        message+=(' Complete it by '+datetime.fromtimestamp(deadline,timezone.utc).strftime('%d %B %Y, %H:%M UTC')+'.') if deadline else ' HR will share the schedule and deadline separately.'
    elif kind=='rejected':
        title='Application update: '+position.body['title']
        message=f'Thank you for taking part in {name}. After reviewing your application for {position.body["title"]}, we will not be moving forward. We appreciate your time and interest.'
    elif kind=='selected':
        title='You have been selected'
        message=f'Congratulations! You have been selected for {position.body["title"]}. HR will contact you with the next steps.'
    elif kind=='rounds_completed':
        title='All assessment rounds completed'
        message=f'You passed {name} for {position.body["title"]}. All assessment rounds are complete. HR will contact you with the next steps.'
    else:
        title='Application stage updated'
        message=f'Your application for {position.body["title"]} is now {application.status.replace("_", " ")}. View your application for details.'
    text=f'Hello {candidate.name},\n\n{message}\n\n{settings.public_url.rstrip("/")+href}'
    html='<html><body>'+''.join('<p>'+escape(part).replace('\n','<br>')+'</p>' for part in text.split('\n\n'))+'<p><a href="'+escape(settings.public_url.rstrip('/')+href,quote=True)+'">View next steps</a></p></body></html>'
    return dict(title=title,message=message,href=href,window_end_at=deadline,plain_text=text,html=html)


def notify(app_id: str, kind: str, round_no: int, *, db=None):
    """Queue one inbox item and email per application/round/type, never send inline."""
    if db is None:
        with DB() as session:
            result=notify(app_id,kind,round_no,db=session)
            session.commit()
            return result
    application=db.scalar(select(Application).where(Application.id==app_id).with_for_update())
    if not application:raise ValueError('Application not found')
    key='workflow:'+hashlib.sha256(f'{app_id}:{round_no}:{kind}'.encode()).hexdigest()
    existing=db.get(WorkflowNotification,key)
    if existing:return existing
    candidate=db.get(User,application.candidate_id)
    position=db.get(RecruitmentPosition,application.position_id)
    body=build_message(kind,candidate,application,round_no,db=db)
    row=WorkflowNotification(id=key,candidate_id=candidate.id,application_id=app_id,round_no=round_no,type=kind,title=body['title'],message=body['message'])
    db.add(row)
    add_notice(db,candidate.id,key,body['title'],body['message'],body['href'],position.hr_id,
               application_id=app_id,round_no=round_no,type=kind,window_end_at=body['window_end_at'],plain_text=body['plain_text'],html=body['html'])
    db.flush()
    return row


def send_email(key: str, body: dict) -> None:
    """Provider-swappable transport; SMTP/Brevo and DRY_RUN use shared settings."""
    from .email_delivery import send
    send(key,body)


def retry_failed(db, key: str) -> bool:
    """Requeue a failed delivery without creating another notification."""
    row=db.get(WorkflowNotification,key);email=db.get(EmailDelivery,key)
    if not row or not email or not row.email_status.startswith('failed:'):return False
    if email.status=='sending':return False
    email.status='pending';email.attempts=0;email.next_attempt=0
    row.email_status='pending'
    return True
