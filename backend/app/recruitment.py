"""Recruiter-owned workflow; existing account and examination security is retained."""
import csv
import io
from .candidate_notices import interview_notice
import time
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from .accounts import organization_scope, organization_recruiters, require_user
from .db import DB, User, Examination, Assignment, Session, Answer, Question, Application, Notification, RecruitmentPosition as Position, RecruitmentCandidate as Candidate, RecruitmentActivity as Activity, uid
from .proctoring import ProctorConfig
from .ai import aggregate, evaluate
from .config import settings
from .scheduling import validate_start

router = APIRouter(prefix='/api/recruitment')
STAGES = ['Source', 'Shortlist', 'Screening', 'Interview', 'Offer', 'Hired', 'Rejected']

def owned(db, model, key, user):
    row = db.get(model, key)
    if not row or (row.organization_id!=organization_scope(user) if model is Position else row.hr_id not in organization_recruiters(user)):
        raise HTTPException(404, 'Record not found in your recruitment workspace.')
    return row

def log(db, user, action):
    db.add(Activity(hr_id=user.id, body={'action':action, 'timestamp':time.time()}))

def sync(db, user):
    """Import existing HR assignments once, without exposing another recruiter's data."""
    existing = {c.user_id:c for c in db.scalars(select(Candidate).where(Candidate.hr_id.in_(organization_recruiters(user)))) if c.user_id}
    positions = {p.body['title']:p for p in db.scalars(select(Position).where(Position.organization_id==organization_scope(user)))}
    for exam in db.scalars(select(Examination).where(Examination.hr_id.in_(organization_recruiters(user)))):
        title = exam.body['role']
        if title not in positions:
            p = Position(hr_id=user.id, organization_id=organization_scope(user), body={'title':title,'department':'Engineering','vacancies_total':1,'status':'open','opened_at':exam.body.get('created_at',time.time()),'difficulty':exam.body.get('level','junior'),'question_set':'Resume-based'})
            db.add(p); db.flush(); positions[title]=p
        for assignment in db.scalars(select(Assignment).where(Assignment.exam_id==exam.id)):
            if assignment.candidate_id not in existing:
                account = db.get(User, assignment.candidate_id)
                c = Candidate(hr_id=user.id,user_id=account.id,body={'name':account.name,'email':account.email,'phone':'','position_id':positions[title].id,'stage':'Source','tags':[],'modified_at':time.time()})
                db.add(c); db.flush(); existing[account.id]=c
    db.commit()

def candidate_data(db, c):
    result = {'id':c.id, **c.body, 'user_id':c.user_id, 'interviews':[]}
    result['application_count']=len(list(db.scalars(select(Application).join(Position).where(Application.candidate_id==c.user_id,Position.organization_id==organization_scope(db.get(User,c.hr_id)))))) if c.user_id else 0
    if c.user_id:
        for a in db.scalars(select(Assignment).where(Assignment.candidate_id==c.user_id)):
            exam = db.get(Examination,a.exam_id)
            if exam.hr_id not in organization_recruiters(db.get(User,c.hr_id)): continue
            s = db.get(Session,a.session_id) if a.session_id else None
            evaluations = [x.body.get('evaluation',{}) for x in db.scalars(select(Answer).where(Answer.session_id==s.id))] if s else []
            summary = aggregate(evaluations)
            technical,communication = summary['technical'],summary['communication']
            result['interviews'].append({'id':a.id,'candidate_id':c.id,'candidate':c.body['name'],'position':exam.body['role'],'scheduled_at':exam.body.get('opens_at',0),'status':s.status if s else 'scheduled','technical':technical,'communication':communication,'overall':summary['overall'],'report_url':'/hr/reports?review='+s.id if s else None})
    if c.body.get('demo_interview'): result['interviews'].append(c.body['demo_interview'] | {'candidate_id':c.id,'candidate':c.body['name']})
    result['interviews'].sort(key=lambda x:x.get('scheduled_at',0),reverse=True)
    latest = next((x for x in result['interviews'] if x.get('overall') is not None),{})
    result.update({k:latest.get(k) for k in ['technical','communication','overall']})
    return result

def data(db,user):
    sync(db,user)
    candidates=[candidate_data(db,c) for c in db.scalars(select(Candidate).where(Candidate.hr_id.in_(organization_recruiters(user)))) if settings.enable_demo_data or not c.body.get('demo')]
    positions=[]
    for p in db.scalars(select(Position).where(Position.organization_id==organization_scope(user))):
        if not settings.enable_demo_data and p.body.get('demo'): continue
        people=[c for c in candidates if c.get('position_id')==p.id]
        positions.append({'id':p.id,**p.body,'vacancies_filled':p.body.get('vacancies_filled',sum(c['stage']=='Hired' for c in people)),'days_open':max(0,int((time.time()-p.body['opened_at'])/86400)),'pipeline_count':len(people)})
    return {'candidates':candidates,'positions':positions,'interviews':[i for c in candidates for i in c['interviews']],'stages':STAGES,'activity':sorted([{'id':a.id,**a.body} for a in db.scalars(select(Activity).where(Activity.hr_id.in_(organization_recruiters(user))))],key=lambda a:a['timestamp'],reverse=True)[:10]}

@router.get('/dashboard/overview')
def overview():
    user=require_user('hr','admin')
    with DB() as db:
        result=data(db,user)
        result['demo_enabled']=settings.enable_demo_data
        result['candidates']=[c for c in result['candidates'] if not c.get('demo') and c.get('user_id')]
        result['positions']=[p for p in result['positions'] if not p.get('demo')]
        result['interviews']=[i for c in result['candidates'] for i in c['interviews'] if not i['id'].startswith('demo-')]
        completed_scores=[i['overall'] for i in result['interviews'] if i['status']=='complete' and i['overall'] is not None]
        result['metrics']={'candidates':len(result['candidates']),'interviews':sum(i['report_url'] is not None for i in result['interviews']),'average_score':round(sum(completed_scores)/len(completed_scores),1) if completed_scores else None,'open_vacancies':sum(max(0,p['vacancies_total']-p['vacancies_filled']) for p in result['positions'] if p['status']=='open')}
        apps=list(db.scalars(select(Application).join(Position).where(Position.organization_id==organization_scope(user))))
        result['application_counts']={stage:sum(a.status==stage for a in apps) for stage in ['applied','under_review','interview_scheduled','interviewed','shortlisted','offer_extended','hired','rejected']}
        result['application_total']=len(apps)
        from .rounds import rounds
        from .db import InterviewRound
        round_counts={}
        for application in apps:
            entries=rounds(db,application.id)
            current=next((r for r in entries if r.status!='passed'),None)
            stage=('rejected' if application.status=='rejected' else db.get(InterviewRound,current.round_id).round_type if current else 'ready_for_offer') if entries else application.status
            if application.status in ('hired','offer_extended'):stage=application.status
            round_counts[stage]=round_counts.get(stage,0)+1
        result['round_counts']=round_counts
        result['monitoring_alerts']=[{'id':n.id,**n.body,'session_id':n.session_id,
            'device_warning_count':db.get(Session,n.session_id).body.get('device_warning_count',0),
            'face_warning_count':db.get(Session,n.session_id).body.get('face_warning_count',0),
            'gaze_violation_count':db.get(Session,n.session_id).body.get('security',{}).get('gaze_violation_count',0)}
            for n in db.scalars(select(Notification).where(Notification.hr_id.in_(organization_recruiters(user))))][-30:]
        return result

@router.delete('/demo')
def clear_demo():
    user=require_user('hr','admin')
    if not settings.enable_demo_data: raise HTTPException(403,'Demo data is disabled in this environment.')
    with DB() as db:
        for c in list(db.scalars(select(Candidate).where(Candidate.hr_id.in_(organization_recruiters(user))))):
            if c.body.get('demo'): db.delete(c)
        for p in list(db.scalars(select(Position).where(Position.organization_id==organization_scope(user)))):
            if p.body.get('demo'): db.delete(p)
        db.commit()
        return {'cleared':True}

@router.get('/candidates')
def candidates(search:str='',position:str='',stage:str='',minimum:float=0,maximum:float=100,sort:str='modified',page:int=Query(1,ge=1),page_size:int=Query(12,ge=1,le=100)):
    user=require_user('hr','admin')
    with DB() as db:
        rows=data(db,user)['candidates']
        rows=[c for c in rows if search.lower() in (c['name']+' '+c['email']).lower() and (not position or c.get('position_id')==position) and (not stage or c['stage']==stage) and (c['overall'] is None and minimum==0 and maximum==100 or c['overall'] is not None and minimum<=c['overall']<=maximum)]
        rows.sort(key=lambda c:c.get('overall') or -1 if sort=='score' else c.get('modified_at',0),reverse=True)
        return {'items':rows[(page-1)*page_size:page*page_size],'total':len(rows),'page':page,'page_size':page_size}

@router.get('/candidates/{cid}')
def detail(cid:str):
    user=require_user('hr','admin')
    with DB() as db: return candidate_data(db,owned(db,Candidate,cid,user))

class StageInput(BaseModel):
    stage:Literal['Source','Shortlist','Screening','Interview','Offer','Hired','Rejected']

@router.patch('/candidates/{cid}/stage')
def stage(cid:str,body:StageInput):
    user=require_user('hr','admin')
    with DB() as db:
        c=owned(db,Candidate,cid,user); c.body=c.body|{'stage':body.stage,'modified_at':time.time()}
        log(db,user,f"{c.body['name']} moved to {body.stage}");db.commit();return {'saved':True}

class TagInput(BaseModel):
    label:str=Field(min_length=1,max_length=40)

@router.post('/candidates/{cid}/tags')
def tag(cid:str,body:TagInput):
    user=require_user('hr','admin')
    with DB() as db:
        c=owned(db,Candidate,cid,user);tags=c.body.get('tags',[])
        label=body.label.strip()
        if not label: raise HTTPException(422,'Enter a tag.')
        if label not in [t['label'] for t in tags]: tags=tags+[{'id':uid(),'label':label}]
        c.body=c.body|{'tags':tags};db.commit();return {'saved':True}

@router.delete('/candidates/{cid}/tags/{tid}')
def remove_tag(cid:str,tid:str):
    user=require_user('hr','admin')
    with DB() as db:
        c=owned(db,Candidate,cid,user);c.body=c.body|{'tags':[t for t in c.body.get('tags',[]) if t['id']!=tid]};db.commit();return {'saved':True}

class PositionInput(BaseModel):
    description:str=Field(default='',max_length=10000)
    title:str=Field(min_length=2,max_length=150)
    department:str=Field(default='Engineering',max_length=100)
    vacancies_total:int=Field(default=1,ge=1,le=10000)
    status:Literal['open','closed']='open'
    difficulty:Literal['intern','junior','mid-level','senior']='junior'
    question_set:Literal['Resume-based']='Resume-based'

@router.get('/positions')
def positions(status:str='open'):
    user=require_user('hr','admin')
    with DB() as db: return {'items':[p for p in data(db,user)['positions'] if (not status or p['status']==status) and (settings.enable_demo_data or not p.get('demo'))]}

SAMPLE_ROLES=[('Backend Engineer','Engineering'),('Frontend Engineer','Engineering'),('Full Stack Developer','Engineering'),('Data Scientist / ML Engineer','Data Science'),('DevOps Engineer','Infrastructure'),('QA Engineer','Quality Assurance'),('Mobile Developer (Android/iOS)','Engineering'),('UI/UX Designer','Design'),('Product Manager','Product'),('Business Analyst','Business Operations'),('System Administrator','IT'),('Cloud/Solutions Architect','Infrastructure')]

@router.post('/positions/seed')
def seed_positions():
    user=require_user('hr','admin')
    if not settings.enable_demo_data:raise HTTPException(403,'Demo data is disabled in this environment.')
    with DB() as db:
        titles={p.body['title'] for p in db.scalars(select(Position).where(Position.organization_id==organization_scope(user)))}
        for title,department in SAMPLE_ROLES:
            if title not in titles:db.add(Position(hr_id=user.id,organization_id=organization_scope(user),body={'title':title,'department':department,'description':f'Join our {department} team as a {title}.','vacancies_total':2,'vacancies_filled':0,'status':'open','opened_at':time.time(),'difficulty':'junior','question_set':'Resume-based','demo':True}))
        log(db,user,'Loaded sample recruitment roles');db.commit();return {'saved':True}

@router.post('/positions')
def create_position(body:PositionInput):
    user=require_user('hr','admin')
    with DB() as db:
        p=Position(hr_id=user.id,organization_id=organization_scope(user),body=body.model_dump()|{'opened_at':time.time()});db.add(p);log(db,user,'Created role: '+body.title);db.commit();return {'id':p.id}

@router.patch('/positions/{pid}')
def edit_position(pid:str,body:PositionInput):
    user=require_user('hr','admin')
    with DB() as db:
        p=owned(db,Position,pid,user);p.body=p.body|body.model_dump();log(db,user,'Updated role: '+body.title);db.commit();return {'saved':True}

@router.get('/positions/{pid}/pipeline')
def pipeline(pid:str):
    user=require_user('hr','admin')
    with DB() as db:
        owned(db,Position,pid,user)
        rows=[c for c in data(db,user)['candidates'] if c.get('position_id')==pid]
        return {'stages':{s:[c for c in rows if c['stage']==s] for s in STAGES}}

class InterviewInput(BaseModel):
    start_now:bool=False
    instructions:str=Field(default="Complete your assigned interview.",max_length=3000)
    interview_type:Literal["resume_based","role_based","mixed"]="role_based"
    candidate_id:str
    position_id:str
    scheduled_at:float=Field(gt=0)
    window_start_at:float|None=None
    window_end_at:float|None=None

@router.post('/interviews')
def schedule(body:InterviewInput):
    user=require_user('hr','admin')
    if body.start_now:body.scheduled_at=body.window_start_at=time.time()
    with DB() as db:
        c=owned(db,Candidate,body.candidate_id,user);p=owned(db,Position,body.position_id,user)
        if not c.user_id: raise HTTPException(409,'Demo candidates cannot receive live interviews. Use a registered candidate.')
        validate_start(body.window_start_at if body.window_start_at is not None else body.scheduled_at)
        if p.body['status']!='open': raise HTTPException(409,'Reopen this role before scheduling.')
        start=body.window_start_at or body.scheduled_at;end=body.window_end_at or start+7200
        if end<=start:raise HTTPException(422,'End time must be after start time.')
        exam=Examination(hr_id=user.id,body={'title':p.body['title']+' interview','role':p.body['title'],'level':p.body['difficulty'],'instructions':body.instructions,'interview_type':body.interview_type,'opens_at':start,'window_start_at':start,'window_end_at':end,'created_at':time.time(),'policy':ProctorConfig().model_dump()})
        db.add(exam);db.flush();a=Assignment(id=uid(),exam_id=exam.id,candidate_id=c.user_id,body={'status':'assigned','position_id':p.id});db.add(a)
        interview_notice(db,a,exam)
        c.body=c.body|{'stage':'Interview','position_id':p.id,'modified_at':time.time()};log(db,user,'Scheduled interview for '+c.body['name']);db.commit();return {'id':a.id}

@router.get('/interviews')
def interviews(status:str='',position:str='',date:str=''):
    user=require_user('hr','admin')
    with DB() as db:
        rows=data(db,user)['interviews']
        return {'items':[i for i in rows if (not status or i['status']==status) and (not position or i['position']==position) and (not date or datetime.fromtimestamp(i['scheduled_at'],timezone.utc).strftime('%Y-%m-%d')==date)]}

class RescheduleInput(BaseModel):
    scheduled_at:float=Field(gt=0)
    window_start_at:float|None=None
    window_end_at:float|None=None

@router.patch('/interviews/{iid}')
def reschedule(iid:str,body:RescheduleInput):
    user=require_user('hr','admin')
    with DB() as db:
        a=db.get(Assignment,iid)
        if not a: raise HTTPException(404,'Interview not found.')
        exam=db.get(Examination,a.exam_id)
        if exam.hr_id not in organization_recruiters(user): raise HTTPException(404,'Interview not found.')
        if a.session_id: raise HTTPException(409,'An interview that has started cannot be rescheduled.')
        validate_start(body.window_start_at if body.window_start_at is not None else body.scheduled_at)
        start=body.window_start_at or body.scheduled_at;end=body.window_end_at or start+7200
        if end<=start:raise HTTPException(422,'End time must be after start time.')
        exam.body=exam.body|{'opens_at':start,'window_start_at':start,'window_end_at':end};log(db,user,'Rescheduled '+exam.body['title']);db.commit();return {'saved':True}

@router.get('/interviews/{iid}/status')
def interview_status(iid:str):
    user=require_user('hr','admin')
    with DB() as db:
        row=next((i for i in data(db,user)['interviews'] if i['id']==iid),None)
        if not row: raise HTTPException(404,'Interview not found.')
        return row

@router.post('/interviews/{iid}/resend')
def resend(iid:str):
    user=require_user('hr','admin')
    with DB() as db:
        a=db.get(Assignment,iid)
        if not a: raise HTTPException(404,'Interview not found.')
        exam=db.get(Examination,a.exam_id)
        if exam.hr_id not in organization_recruiters(user): raise HTTPException(404,'Interview not found.')
        if not settings.smtp_host or not settings.smtp_from: raise HTTPException(503,'Email delivery is not configured. The candidate can sign in to view their assigned interview.')
        account=db.get(User,a.candidate_id)
        message=EmailMessage();message['Subject']='Your assigned interview';message['From']=settings.smtp_from;message['To']=account.email
        message.set_content(f"Hello {account.name},\nYour {exam.body['title']} interview is available in your candidate account. Sign in at {settings.public_url.rstrip('/')}/login.")
        try:
            with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=10) as smtp:
                if settings.smtp_use_tls:smtp.starttls()
                if settings.smtp_user:smtp.login(settings.smtp_user,settings.smtp_password)
                smtp.send_message(message)
        except (OSError,smtplib.SMTPException): raise HTTPException(503,'Email could not be delivered. Try again later.')
        log(db,user,'Sent interview reminder to '+account.name);db.commit();return {'saved':True}

@router.post('/interviews/{iid}/reanalyze')
async def reanalyze(iid:str):
    user=require_user('hr','admin')
    with DB() as db:
        a=db.get(Assignment,iid)
        if not a or db.get(Examination,a.exam_id).hr_id not in organization_recruiters(user):raise HTTPException(404,'Interview not found.')
        session=db.get(Session,a.session_id) if a.session_id else None
        if not session or session.status!='complete':raise HTTPException(409,'Only a completed interview can be re-analyzed.')
        answers=[(x.id,x.body.get('version',0),db.get(Question,x.body['question_id']).body,x.body['transcript']) for x in db.scalars(select(Answer).where(Answer.session_id==session.id)) if x.body.get('approved')]
        if not answers:raise HTTPException(409,'There are no approved answers to analyze.')
    results=[(aid,version,await evaluate(question,transcript)) for aid,version,question,transcript in answers]
    with DB() as db:
        for aid,version,result in results:
            answer=db.get(Answer,aid)
            if not answer or answer.body.get('version',0)!=version:raise HTTPException(409,'An answer changed. Retry analysis.')
            answer.body=answer.body|{'evaluation':result}
        log(db,user,'Re-analyzed completed interview');db.commit();return {'saved':True}

@router.get('/analytics/export')
def export(position:str='',start:float=0,end:float=1e20):
    user=require_user('hr','admin')
    with DB() as db:
        rows=data(db,user)['interviews'];out=io.StringIO();writer=csv.writer(out)
        writer.writerow(['Candidate','Position','Scheduled','Status','Technical','Communication','Overall'])
        for i in rows:
            if (not position or i['position']==position) and start<=i['scheduled_at']<=end:
                values=[i.get(k,'') for k in ['candidate','position','scheduled_at','status','technical','communication','overall']]
                writer.writerow(["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v for v in values])
        return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="recruitment-report.csv"'})

@router.post('/demo')
def seed():
    user=require_user('hr','admin')
    if not settings.enable_demo_data: raise HTTPException(403,'Demo data is disabled in this environment.')
    with DB() as db:
        if any(c.body.get('demo') for c in db.scalars(select(Candidate).where(Candidate.hr_id.in_(organization_recruiters(user))))): return {'saved':True}
        roles=[]
        for title in ['Frontend Engineer','Backend Engineer','Data Analyst','Product Designer','QA Engineer']:
            p=Position(hr_id=user.id,organization_id=organization_scope(user),body={'title':title,'department':'Product & Engineering','vacancies_total':3,'opened_at':time.time()-86400*20,'status':'open','difficulty':'junior','question_set':'Resume-based','demo':True});db.add(p);db.flush();roles.append(p)
        for n in range(30):
            name=['Aarav','Maya','Rohan','Priya','Sam','Anika'][n%6]+' '+['Shah','Patel','Rao','Das','Roy'][n//6]
            score=40+(n*7)%57;p=roles[n%5]
            c=Candidate(hr_id=user.id,body={'name':name,'email':f'demo{n+1}@example.test','phone':'','position_id':p.id,'stage':STAGES[n%7],'tags':[],'modified_at':time.time()-n*3600,'demo':True,'demo_interview':{'id':'demo-'+uid(),'position':p.body['title'],'scheduled_at':time.time()-n*86400*3,'status':['complete','scheduled','active','complete','failed'][n%5],'technical':score,'communication':min(100,score+4),'overall':score+2,'report_url':None}});db.add(c)
        log(db,user,'Loaded 30 clearly labeled demo candidates');db.commit();return {'saved':True}

@router.get('/analytics/{kind}')
def analytics(kind:str):
    user=require_user('hr','admin')
    with DB() as db:
        rows=[i for i in data(db,user)['interviews'] if i.get('overall') is not None]
        if kind=='score-distribution':
            return {'items':[{'label':f'{n}–{n+20}','count':sum(n<=i['overall']<n+20 or n==80 and i['overall']==100 for i in rows)} for n in range(0,100,20)]}
        if kind=='correlation':
            return {'items':[{'technical':i['technical'],'communication':i['communication']} for i in rows],'basis':'Assessed answer content'}
        if kind in ['trends','by-position']:
            buckets={}
            for i in rows:
                key=i['position'] if kind=='by-position' else datetime.fromtimestamp(i['scheduled_at'],timezone.utc).strftime('%Y-%m')
                buckets.setdefault(key,[]).append(i['overall'])
            return {'items':[{'label':k,'average':round(sum(v)/len(v),1),'count':len(v)} for k,v in sorted(buckets.items())]}
        raise HTTPException(404,'Analytics view not found.')


