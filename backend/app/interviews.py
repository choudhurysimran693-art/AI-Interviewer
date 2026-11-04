"""Bounded interview management with round gating and per-invitation delivery state."""
import time
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, case, literal, union_all, or_
from .db import DB, User, Assignment, Examination, Session, Application, ApplicationRound, InterviewRound, EmailDelivery, RecruitmentCandidate, RecruitmentPosition, uid
from .accounts import require_user, organization_scope, organization_recruiters
from .candidate_notices import add_notice, interview_notice
from .rounds import rounds, definitions, mode, invite, InviteInput
from .scheduling import validate_start
from .proctoring import ProctorConfig

router=APIRouter(prefix='/api/recruitment/interviews')

def position(db,pid,user):
    p=db.get(RecruitmentPosition,pid)
    if not p or p.organization_id!=organization_scope(user):raise HTTPException(404,'Role not found.')
    return p

def candidate(db,cid,user):
    # Accept the older recruiter-directory ID as well as the account ID.
    c=db.get(RecruitmentCandidate,cid)
    if c:
        if c.hr_id not in organization_recruiters(user):raise HTTPException(404,'Candidate not found.')
        cid=c.user_id
    u=db.get(User,cid) if cid else None
    associated=db.scalar(select(Application.id).join(RecruitmentPosition).where(Application.candidate_id==cid,RecruitmentPosition.organization_id==organization_scope(user)).limit(1))
    directory=db.scalar(select(RecruitmentCandidate.id).where(RecruitmentCandidate.user_id==cid,RecruitmentCandidate.hr_id.in_(organization_recruiters(user))).limit(1))
    assigned=db.scalar(select(Assignment.id).join(Examination).where(Assignment.candidate_id==cid,Examination.hr_id.in_(organization_recruiters(user))).limit(1))
    if not u or not (associated or directory or assigned):raise HTTPException(404,'Candidate not found.')
    return u

def context(db,cid,pid,user):
    p=position(db,pid,user);u=candidate(db,cid,user)
    a=db.scalar(select(Application).where(Application.candidate_id==u.id,Application.position_id==pid).with_for_update())
    if not a or not definitions(db,pid):return p,u,a,None,''
    entries=rounds(db,a.id)
    if a.status in ('rejected','hired','offer_extended','ready_for_offer'):return p,u,a,None,'This application is closed to interview scheduling.'
    if not entries:return p,u,a,None,'Shortlist this application to unlock its round pipeline.'
    r=next((r for r in entries if r.status!='passed'),None)
    if not r:return p,u,a,None,'All rounds are complete.'
    d=db.get(InterviewRound,r.round_id)
    if r.status not in ('pending','invited','awaiting_scheduling','scheduled') or mode(d)=='auto_evaluated':return p,u,a,r,'This round requires completion or an HR decision before scheduling.'
    if r.assignment_id:
        assigned=db.get(Assignment,r.assignment_id)
        if assigned.session_id or assigned.body.get('status') in ('cancelled','expired','terminated','attempt_deleted'):return p,u,a,r,'This round already has an attempt or was cancelled. Review the application.'
    return p,u,a,r,''

@router.get('/candidates')
def choices(search:str=Query('',max_length=200)):
    user=require_user('hr','admin')
    with DB() as db:
        app_ids=select(Application.candidate_id).join(RecruitmentPosition).where(RecruitmentPosition.organization_id==organization_scope(user))
        directory=select(RecruitmentCandidate.user_id).where(RecruitmentCandidate.hr_id.in_(organization_recruiters(user)))
        assigned=select(Assignment.candidate_id).join(Examination).where(Examination.hr_id.in_(organization_recruiters(user)))
        q=select(User).where(User.role=='candidate',or_(User.id.in_(app_ids),User.id.in_(directory),User.id.in_(assigned)))
        if search:q=q.where(or_(User.name.icontains(search,autoescape=True),User.email.icontains(search,autoescape=True)))
        return {'items':[{'id':u.id,'name':u.name,'email':u.email} for u in db.scalars(q.order_by(User.name,User.id).limit(50))]}

@router.get('/context')
def scheduling_context(candidate_id:str,position_id:str):
    user=require_user('hr','admin')
    with DB() as db:
        p,u,a,r,reason=context(db,candidate_id,position_id,user)
        d=db.get(InterviewRound,r.round_id) if r else None
        return {'application_id':a.id if a else None,'round_id':r.id if r else None,'round_name':d.round_name if d else None,'evaluation_mode':mode(d) if d else None,'blocked_reason':reason,'pipeline':bool(a and definitions(db,p.id))}

def rows_query(user):
    start=func.coalesce(Examination.body['window_start_at'].as_float(),Examination.body['opens_at'].as_float(),0)
    end=func.coalesce(Examination.body['window_end_at'].as_float(),case((start>0,start+7200),else_=0))
    state=case((Assignment.body['status'].as_string()=='cancelled',literal('cancelled')),(Session.id.is_not(None),Session.status),(Assignment.body['status'].as_string().in_(['expired','terminated','attempt_deleted']),Assignment.body['status'].as_string()),((end>0)&(end<time.time()),literal('expired')),else_=literal('scheduled'))
    assignments=select(Assignment.id.label('id'),User.id.label('candidate_id'),User.name.label('candidate'),User.email.label('email'),Examination.body['role'].as_string().label('position'),func.coalesce(Assignment.body['position_id'].as_string(),Examination.body['position_id'].as_string()).label('position_id'),ApplicationRound.application_id.label('application_id'),ApplicationRound.id.label('round_id'),func.coalesce(InterviewRound.round_name,literal('Standalone interview')).label('round_name'),start.label('scheduled_at'),end.label('window_end_at'),state.label('status'),Session.id.label('session_id')).join(Examination,Assignment.exam_id==Examination.id).join(User,Assignment.candidate_id==User.id).outerjoin(Session,Assignment.session_id==Session.id).outerjoin(ApplicationRound,ApplicationRound.assignment_id==Assignment.id).outerjoin(InterviewRound,ApplicationRound.round_id==InterviewRound.id).where(Examination.hr_id.in_(organization_recruiters(user)))
    manual=select((literal('round:')+ApplicationRound.id).label('id'),User.id,User.name,User.email,RecruitmentPosition.body['title'].as_string(),RecruitmentPosition.id,Application.id,ApplicationRound.id,InterviewRound.round_name,ApplicationRound.scheduling['scheduled_at'].as_float(),ApplicationRound.scheduling['window_end_at'].as_float(),ApplicationRound.status,literal(None)).select_from(ApplicationRound).join(InterviewRound,ApplicationRound.round_id==InterviewRound.id).join(Application,ApplicationRound.application_id==Application.id).join(User,Application.candidate_id==User.id).join(RecruitmentPosition,Application.position_id==RecruitmentPosition.id).where(RecruitmentPosition.organization_id==organization_scope(user),ApplicationRound.assignment_id.is_(None),ApplicationRound.scheduling['scheduled_at'].as_float().is_not(None))
    return union_all(assignments,manual).subquery()

@router.get('')
def listing(search:str=Query('',max_length=200),position_id:str='',status:str='',date:str='',page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=50)):
    user=require_user('hr','admin')
    with DB() as db:
        source=rows_query(user);q=select(source)
        total_org=db.scalar(select(func.count()).select_from(source))
        if search:q=q.where(or_(source.c.candidate.icontains(search,autoescape=True),source.c.email.icontains(search,autoescape=True)))
        if position_id:position(db,position_id,user);q=q.where(source.c.position_id==position_id)
        if status:q=q.where(source.c.status==status)
        if date:
            try:start=datetime.strptime(date,'%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp()
            except ValueError:raise HTTPException(422,'Use YYYY-MM-DD for the date.')
            q=q.where(source.c.scheduled_at>=start,source.c.scheduled_at<start+86400)
        total=db.scalar(select(func.count()).select_from(q.subquery()))
        items=[dict(r) for r in db.execute(q.order_by(source.c.scheduled_at.desc(),source.c.id).offset((page-1)*page_size).limit(page_size)).mappings()]
        # Only delivery records belonging to these rows, never marks/shortlisting mail.
        hrefs=['/candidate/interview?assignment='+i['id'] for i in items if not i['id'].startswith('round:')]
        rids=[i['round_id'] for i in items if i['round_id']]
        mails=list(db.scalars(select(EmailDelivery).where(EmailDelivery.body['hr_id'].as_string().in_(organization_recruiters(user)),or_(EmailDelivery.body['href'].as_string().in_(hrefs),EmailDelivery.body['related_application_round_id'].as_string().in_(rids))))) if items else []
        for i in items:
            relevant=[m for m in mails if m.body.get('email_kind')!='cancellation' and (m.body.get('href')=='/candidate/interview?assignment='+i['id'] or i['id'].startswith('round:') and m.body.get('related_application_round_id')==i['round_id'])]
            relevant.sort(key=lambda m:(m.body.get('created_at',m.body.get('sent_at',0)),m.id),reverse=True)
            m=relevant[0] if relevant else None
            i['invitation_status']='sent' if m and m.status=='sent' else 'failed' if m and (m.status=='failed' or m.body.get('delivery_error')) else 'pending'
            i['report_url']='/hr/reports?review='+i['session_id'] if i['session_id'] else None
            i['details_url']='/hr/applications#application-'+i['application_id'] if i['application_id'] else '/hr/candidates?candidate='+i['candidate_id']
        return {'items':items,'total_count':total,'organization_total':total_org,'page':page,'page_size':page_size}

class Schedule(BaseModel):
    candidate_id:str
    position_id:str
    scheduled_at:float=Field(gt=0,allow_inf_nan=False)
    window_end_at:float|None=Field(default=None,gt=0,allow_inf_nan=False)
    start_now:bool=False
    window_start_at:float|None=Field(default=None,allow_inf_nan=False)
    instructions:str=Field(default='Complete your assigned interview.',max_length=3000)
    interview_type:Literal['role_based','resume_based','mixed']='role_based'
    round_id:str|None=None

def private_exam(db,assignment,exam):
    # Legacy examinations may be assigned to several candidates. Copy before editing.
    other=db.scalar(select(Assignment.id).where(Assignment.exam_id==exam.id,Assignment.id!=assignment.id).limit(1))
    if other:
        exam=Examination(hr_id=exam.hr_id,body=dict(exam.body));db.add(exam);db.flush();assignment.exam_id=exam.id
    return exam

def notify(db,assignment,exam,title='Your interview is scheduled'):
    add_notice(db,assignment.candidate_id,'interview-update:'+uid(),title,exam.body['title'],'/candidate/interview?assignment='+assignment.id,exam.hr_id,scheduled_at=exam.body.get('window_start_at',exam.body.get('opens_at',0)),window_end_at=exam.body.get('window_end_at',0),created_at=time.time(),email_kind='invitation')

@router.post('')
def schedule(body:Schedule):
    user=require_user('hr','admin');start=validate_start(time.time() if body.start_now else (body.window_start_at if body.window_start_at is not None else body.scheduled_at))
    if body.window_end_at is None:body.window_end_at=start+7200
    if body.window_end_at<=start:raise HTTPException(422,'End time must be after start time.')
    with DB() as db:
        p,u,a,r,reason=context(db,body.candidate_id,body.position_id,user)
        if p.body.get('status')!='open':raise HTTPException(409,'Reopen this role before scheduling.')
        if reason:raise HTTPException(409,reason)
        if r:
            if body.round_id!=r.id:raise HTTPException(409,'Select the current accessible round. Refresh the form.')
            d=db.get(InterviewRound,r.round_id)
            if mode(d)=='human_only':
                r.status='scheduled';r.scheduling={'scheduled_at':start,'window_end_at':body.window_end_at,'details':body.instructions};a.updated_at=time.time()
                add_notice(db,u.id,'round-schedule:'+uid(),d.round_name+' scheduled',body.instructions,'/candidate/applications',user.id,scheduled_at=start,window_end_at=body.window_end_at,related_application_round_id=r.id,created_at=time.time(),email_kind='invitation')
                db.commit();return {'id':'round:'+r.id}
            if r.assignment_id:
                assignment=db.get(Assignment,r.assignment_id,with_for_update=True)
                if assignment.session_id or assignment.body.get('status')=='cancelled':raise HTTPException(409,'This interview is no longer schedulable.')
                exam=private_exam(db,assignment,db.get(Examination,assignment.exam_id));exam.body=exam.body|{'opens_at':start,'window_start_at':start,'window_end_at':body.window_end_at,'instructions':body.instructions};notify(db,assignment,exam)
            else:
                invite(db,a,r,user,InviteInput(window_start_at=start,window_end_at=body.window_end_at));assignment=db.get(Assignment,r.assignment_id)
            a.updated_at=time.time();db.commit();return {'id':assignment.id}
        if body.round_id:raise HTTPException(409,'This round is not accessible.')
        exam=Examination(hr_id=user.id,body={'title':p.body['title']+' interview','role':p.body['title'],'position_id':p.id,'level':p.body.get('difficulty','junior'),'instructions':body.instructions,'interview_type':body.interview_type,'opens_at':start,'window_start_at':start,'window_end_at':body.window_end_at,'created_at':time.time(),'policy':ProctorConfig().model_dump()})
        db.add(exam);db.flush();assignment=Assignment(id=uid(),exam_id=exam.id,candidate_id=u.id,body={'status':'assigned','position_id':p.id});db.add(assignment);db.flush();notify(db,assignment,exam);db.commit();return {'id':assignment.id}

class Reschedule(BaseModel):
    scheduled_at:float=Field(gt=0,allow_inf_nan=False)

def editable(db,iid,user):
    if iid.startswith('round:'):
        r=db.get(ApplicationRound,iid[6:],with_for_update=True)
        a=db.get(Application,r.application_id) if r else None
        if not a:raise HTTPException(404,'Interview not found.')
        position(db,a.position_id,user)
        if r.assignment_id or r.status!='scheduled':raise HTTPException(409,'Only scheduled interviews can be changed.')
        return r,a,None
    a=db.get(Assignment,iid,with_for_update=True);exam=db.get(Examination,a.exam_id) if a else None
    if not exam or exam.hr_id not in organization_recruiters(user):raise HTTPException(404,'Interview not found.')
    if a.session_id or a.body.get('status') in ('cancelled','terminated','attempt_deleted','completed'):raise HTTPException(409,'Only interviews that have not started can be changed.')
    linked=db.scalar(select(ApplicationRound).where(ApplicationRound.assignment_id==a.id))
    if linked and linked.status not in ('pending','invited','scheduled','awaiting_scheduling'):raise HTTPException(409,'This round is no longer open for scheduling.')
    return a,exam,True

@router.patch('/{iid}')
def reschedule(iid:str,body:Reschedule):
    user=require_user('hr','admin');start=validate_start(body.scheduled_at)
    with DB() as db:
        a,exam,online=editable(db,iid,user)
        if online:
            exam=private_exam(db,a,exam)
            old=exam.body.get('window_start_at',exam.body.get('opens_at',0));duration=max(60,exam.body.get('window_end_at',old+7200)-old)
            exam.body=exam.body|{'opens_at':start,'window_start_at':start,'window_end_at':start+duration};notify(db,a,exam,'Your interview was rescheduled')
        else:
            old=a.scheduling.get('scheduled_at',0);duration=max(60,a.scheduling.get('window_end_at',old+7200)-old);a.scheduling=a.scheduling|{'scheduled_at':start,'window_end_at':start+duration};exam.updated_at=time.time()
            add_notice(db,exam.candidate_id,'round-reschedule:'+uid(),'Your interview was rescheduled',a.scheduling.get('details',''),'/candidate/applications',user.id,scheduled_at=start,window_end_at=start+duration,related_application_round_id=a.id,created_at=time.time(),email_kind='invitation')
        db.commit();return {'saved':True}

@router.post('/{iid}/resend')
def resend(iid:str):
    user=require_user('hr','admin')
    with DB() as db:
        a,exam,online=editable(db,iid,user)
        if online:
            start=exam.body.get('window_start_at',exam.body.get('opens_at',0));end=exam.body.get('window_end_at',start+7200 if start else 0)
            if end and end<time.time():raise HTTPException(409,'Reschedule the expired interview before resending.')
            notify(db,a,exam,'Your assigned interview')
        else:add_notice(db,exam.candidate_id,'round-reminder:'+uid(),'Your scheduled interview',a.scheduling.get('details',''),'/candidate/applications',user.id,scheduled_at=a.scheduling['scheduled_at'],related_application_round_id=a.id,created_at=time.time(),email_kind='invitation')
        db.commit();return {'saved':True,'delivery':'queued','message':'Invitation queued.'}

@router.post('/{iid}/cancel')
def cancel(iid:str):
    user=require_user('hr','admin')
    with DB() as db:
        a,exam,online=editable(db,iid,user)
        if online:
            a.body=a.body|{'status':'cancelled','cancelled_at':time.time(),'cancelled_by':user.id}
            r=db.scalar(select(ApplicationRound).where(ApplicationRound.assignment_id==a.id))
            if r:r.status='cancelled'
            cid=a.candidate_id;href='/candidate/interview?assignment='+a.id;rid=r.id if r else None
        else:a.status='cancelled';exam.updated_at=time.time();cid=exam.candidate_id;href='/candidate/applications';rid=a.id
        # Prevent queued reminders from advertising the cancelled interview.
        for mail in db.scalars(select(EmailDelivery).where(EmailDelivery.status=='pending',or_(EmailDelivery.body['href'].as_string()==href if online else literal(False),EmailDelivery.body['related_application_round_id'].as_string()==rid if rid else literal(False)))):mail.status='cancelled'
        add_notice(db,cid,'interview-cancelled:'+uid(),'Interview cancelled','HR has cancelled this interview. Contact the company for further details.','/candidate/applications',user.id,email_kind='cancellation',created_at=time.time())
        db.commit();return {'saved':True}

@router.get('/{iid}/status')
def status_detail(iid:str):
    user=require_user('hr','admin')
    with DB() as db:
        source=rows_query(user)
        row=db.execute(select(source).where(source.c.id==iid)).mappings().first()
        if not row:raise HTTPException(404,'Interview not found.')
        return dict(row)
