"""Applications reuse recruiter-owned positions and examination assignments."""
import time
from typing import Literal
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import PlainTextResponse, Response
from urllib.parse import quote
from pathlib import Path
from .db import CandidateResume, ApplicationResume
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .accounts import organization_scope, organization_recruiters, require_user
from .db import DB, Application, RecruitmentPosition as Position, RecruitmentCandidate as Candidate, User, Assignment, Examination, Session, Answer, uid
from .recruitment import log
from .proctoring import ProctorConfig
from .ai import aggregate
from .scheduling import validate_start
from .candidate_notices import add_notice, interview_notice
from .db import CandidateNotice

router=APIRouter(prefix='/api')

@router.get('/candidate/notifications')
def candidate_notifications(envelope:bool=False):
    user=require_user('candidate')
    with DB() as db:
        items=sorted([{'id':n.id,**n.body} for n in db.scalars(select(CandidateNotice).where(CandidateNotice.candidate_id==user.id))],key=lambda n:n['created_at'],reverse=True)
        return {'items':items,'unread_count':sum(not n.get('read',False) for n in items)} if envelope else items

@router.post('/candidate/notifications/{nid}/read')
@router.patch('/candidate/notifications/{nid}/read')
def read_notification(nid:str):
    user=require_user('candidate')
    with DB() as db:
        n=db.get(CandidateNotice,nid)
        if not n or n.candidate_id!=user.id:raise HTTPException(404,'Notification not found.')
        n.body=n.body|{'read':True};db.commit();return {'saved':True}
STAGES=['applied','under_review','interview_scheduled','interviewed','shortlisted','offer_extended','hired','rejected']
TRANSITIONS={'applied':{'under_review','interview_scheduled','rejected'},'under_review':{'interview_scheduled','shortlisted','rejected'},'interview_scheduled':{'interviewed','rejected'},'interviewed':{'shortlisted','rejected'},'shortlisted':{'interview_scheduled','offer_extended','rejected'},'offer_extended':{'hired','rejected'},'hired':set(),'rejected':set(),'ready_for_offer':{'offer_extended','rejected'}}

def position_view(p):
    b=p.body
    from .db import Organization
    with DB() as db:
        org=db.get(Organization,p.organization_id) if p.organization_id else None
    return {'id':p.id,**b,'company_name':org.name if org else '', 'vacancies_remaining':max(0,b['vacancies_total']-b.get('vacancies_filled',0))}

def owned(db,aid,user):
    a=db.scalar(select(Application).where(Application.id==aid).with_for_update())
    if not a or db.get(Position,a.position_id).organization_id!=organization_scope(user):raise HTTPException(404,'Application not found.')
    return a

def view(db,a,hr=False):
    p=db.get(Position,a.position_id);u=db.get(User,a.candidate_id)
    assignment=db.get(Assignment,a.assignment_id) if a.assignment_id else None
    s=db.get(Session,assignment.session_id) if assignment and assignment.session_id else None
    result={'id':a.id,'position_id':p.id,'position':p.body['title'],'candidate_id':u.id,'candidate':u.name,'status':a.status,'applied_at':a.applied_at,'updated_at':a.updated_at,'assignment_id':a.assignment_id,'session_id':s.id if s else None}
    result['company_name']=position_view(p)['company_name']
    from .rounds import history, current_label
    result.update(rounds=history(db,a,hr),current_round=current_label(db,a))
    if hr:
        evaluations=[x.body.get('evaluation',{}) for x in db.scalars(select(Answer).where(Answer.session_id==s.id))] if s else []
        profile=u.body.get('profile',{})
        result.update(email=u.email,hr_notes=a.hr_notes,resume_url=f'/api/applications/{a.id}/resume' if db.get(ApplicationResume,a.id) or profile.get('resume_profile') else None,scores=aggregate(evaluations) if evaluations else None)
    return result

@router.get('/positions/open')
def open_positions():
    with DB() as db:return [position_view(p) for p in db.scalars(select(Position)) if p.body.get('status')=='open' and not p.body.get('demo') and p.body.get('vacancies_filled',0)<p.body['vacancies_total']]

class ApplyInput(BaseModel):
    position_id:str
    gap_explanation:str=Field(default='',max_length=2000)

@router.post('/candidate/resume')
@router.post('/candidate/profile/resume')
async def upload_resume(file:UploadFile=File(...)):
    user=require_user('candidate')
    from .main import parse_resume
    parsed=await parse_resume(file,user.name)
    await file.seek(0)
    content=await file.read(5*1024*1024+1)
    with DB() as db:
        document=CandidateResume(user_id=user.id,filename=Path((file.filename or 'resume').replace('\\','/')).name,content=content)
        db.add(document);db.flush()
        from .screening import ensure_extraction
        ensure_extraction(db,document)
        account=db.get(User,user.id)
        account.body=account.body|{'profile':account.body.get('profile',{})|{'resume_name':document.filename,'resume_profile':parsed['profile']},'resume_id':document.id}
        from .screening import screen
        for application in db.scalars(select(Application).where(Application.candidate_id==user.id)):
            link=db.get(ApplicationResume,application.id)
            if link:link.resume_id=document.id
            else:db.add(ApplicationResume(application_id=application.id,resume_id=document.id))
            db.flush();screen(db,application)
        db.commit()
        return {'filename':document.filename,'profile':parsed['profile']}

@router.post('/candidate/applications/{aid}/resume')
def attach_resume(aid:str):
    user=require_user('candidate')
    with DB() as db:
        application=db.get(Application,aid)
        if not application or application.candidate_id!=user.id:raise HTTPException(404,'Application not found.')
        document=db.get(CandidateResume,user.body.get('resume_id')) if user.body.get('resume_id') else None
        if not document or document.user_id!=user.id:raise HTTPException(422,'Upload your resume first.')
        link=db.get(ApplicationResume,aid)
        if link:link.resume_id=document.id
        else:db.add(ApplicationResume(application_id=aid,resume_id=document.id))
        db.flush()
        from .screening import screen
        screen(db,application)
        db.commit();return {'saved':True}

@router.get('/applications/{aid}/resume')
def resume(aid:str):
    user=require_user('hr','admin')
    with DB() as db:
        a=owned(db,aid,user);u=db.get(User,a.candidate_id);profile=u.body.get('profile',{})
        link=db.get(ApplicationResume,a.id)
        if link:
            document=db.get(CandidateResume,link.resume_id)
            return Response(document.content,media_type='application/pdf' if document.filename.lower().endswith('.pdf') else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(document.filename,safe=''),'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
        parsed=profile.get('resume_profile',{})
        if not parsed:raise HTTPException(404,'No resume is available in this profile.')
        return PlainTextResponse(u.name+'\n'+profile.get('resume_name','Resume profile')+'\n\n'+'\n'.join(f'{key}: '+(', '.join(map(str,value)) if isinstance(value,list) else str(value)) for key,value in parsed.items()))

@router.post('/applications')
def apply(body:ApplyInput):
    user=require_user('candidate')
    with DB() as db:
        p=db.scalar(select(Position).where(Position.id==body.position_id).with_for_update())
        if not p or p.body.get('demo') or p.body['status']!='open' or p.body.get('vacancies_filled',0)>=p.body['vacancies_total']:raise HTTPException(409,'This role is no longer accepting applications.')
        a=Application(candidate_id=user.id,position_id=p.id);db.add(a)
        try:db.flush()
        except IntegrityError:db.rollback();raise HTTPException(409,'You have already applied to this role.')
        if user.body.get('resume_id'):
            document=db.get(CandidateResume,user.body['resume_id'])
            if document and document.user_id==user.id:db.add(ApplicationResume(application_id=a.id,resume_id=document.id))
        db.flush()
        from .screening import screen
        from .db import ScreeningSummary
        screen(db,a);db.flush()
        summary=db.get(ScreeningSummary,a.id)
        summary.body=summary.body|{'gap_explanation':body.gap_explanation}
        hr=db.get(User,p.hr_id);log(db,hr,f'{user.name} applied for {p.body["title"]}')
        if not db.scalar(select(Candidate).where(Candidate.hr_id.in_(organization_recruiters(hr)),Candidate.user_id==user.id)):
            db.add(Candidate(hr_id=p.hr_id,user_id=user.id,body={'name':user.name,'email':user.email,'phone':'','position_id':p.id,'stage':'Source','tags':[],'modified_at':time.time()}))
        try:db.commit()
        except IntegrityError:db.rollback();raise HTTPException(409,'You have already applied to this role.')
        return view(db,a)

@router.get('/candidate/applications')
def my_applications():
    user=require_user('candidate')
    with DB() as db:return [view(db,a) for a in db.scalars(select(Application).where(Application.candidate_id==user.id).order_by(Application.applied_at.desc()))]

@router.get('/hr/applications')
def applications(position:str='',status:str='',start:float=0,end:float=1e20,candidate:str=''):
    user=require_user('hr','admin')
    with DB() as db:
        rows=db.scalars(select(Application).join(Position).where(Position.organization_id==organization_scope(user),Application.applied_at>=start,Application.applied_at<=end).order_by(Application.applied_at.desc()))
        return {'items':[view(db,a,True) for a in rows if (not position or a.position_id==position) and (not status or a.status==status) and (not candidate or a.candidate_id==candidate)]}

class StatusInput(BaseModel):
    status:Literal['under_review','interview_scheduled','interviewed','shortlisted','offer_extended','hired','rejected']
    hr_notes:str|None=Field(default=None,max_length=10000)

def transition(db,a,status,user,notes=None):
    from .rounds import rounds, initialize
    if status in ('offer_extended','hired') and any(r.status!='passed' for r in rounds(db,a.id)):
        raise HTTPException(409,'Pass all interview rounds before making an offer.')
    if status!=a.status and status not in TRANSITIONS[a.status]:raise HTTPException(409,'This stage transition is not available.')
    p=db.scalar(select(Position).where(Position.id==a.position_id).with_for_update())
    if status=='hired' and a.status!='hired':
        filled=p.body.get('vacancies_filled',0)
        if filled>=p.body['vacancies_total']:raise HTTPException(409,'All vacancies for this role have been filled.')
        p.body=p.body|{'vacancies_filled':filled+1,'status':'closed' if filled+1>=p.body['vacancies_total'] else p.body['status']}
    if status!=a.status:log(db,user,f'{db.get(User,a.candidate_id).name}: {a.status} → {status} ({p.body["title"]})')
    newly_shortlisted=status=='shortlisted' and a.status!=status
    a.status=status;a.updated_at=time.time()
    if status=='shortlisted':
        initialize(db,a,user)
        if not a.assignment_id and not rounds(db,a.id):
            from .proctoring import ProctorConfig
            now=time.time()
            exam=Examination(hr_id=user.id,body={'title':p.body['title']+' interview','role':p.body['title'],'level':p.body.get('difficulty','junior'),'position_id':p.id,'application_id':a.id,'instructions':'Complete your assigned interview.','interview_type':'role_based','opens_at':now,'window_start_at':now,'window_end_at':now+7*86400,'created_at':now,'policy':ProctorConfig().model_dump()})
            db.add(exam);db.flush()
            assignment=Assignment(id=uid(),exam_id=exam.id,candidate_id=a.candidate_id,body={'status':'assigned','application_id':a.id,'position_id':p.id})
            db.add(assignment);db.flush();a.assignment_id=assignment.id
        if newly_shortlisted and a.assignment_id:
            assignment=db.get(Assignment,a.assignment_id)
            exam=db.get(Examination,assignment.exam_id)
            add_notice(db,a.candidate_id,'shortlisted:'+a.id,'You have been shortlisted',
                       'You have been shortlisted for '+p.body['title']+'. Open your interview invitation using the link below.',
                       '/candidate/interview?assignment='+a.assignment_id,user.id,
                       scheduled_at=exam.body.get('window_start_at',exam.body.get('opens_at')),
                       window_end_at=exam.body.get('window_end_at'))
    if notes is not None:a.hr_notes=notes

@router.patch('/applications/{aid}/status')
def change_status(aid:str,body:StatusInput):
    user=require_user('hr','admin')
    with DB() as db:
        a=owned(db,aid,user)
        if body.status=='interview_scheduled' and not a.assignment_id:raise HTTPException(409,'Use Schedule interview to assign a time first.')
        transition(db,a,body.status,user,body.hr_notes);db.commit();return view(db,a,True)

class NotesInput(BaseModel):
    hr_notes:str=Field(max_length=10000)

@router.patch('/applications/{aid}/notes')
def notes(aid:str,body:NotesInput):
    user=require_user('hr','admin')
    with DB() as db:
        a=owned(db,aid,user);a.hr_notes=body.hr_notes;a.updated_at=time.time();log(db,user,'Updated application notes');db.commit();return view(db,a,True)

class ScheduleInput(BaseModel):
    start_now:bool=False
    scheduled_at:float
    instructions:str=Field(default='Complete your assigned interview.',max_length=3000)
    interview_type:Literal['resume_based','role_based','mixed']='role_based'

@router.post('/applications/{aid}/schedule-interview')
def schedule(aid:str,body:ScheduleInput):
    user=require_user('hr','admin')
    if body.start_now:body.scheduled_at=time.time()
    with DB() as db:
        a=owned(db,aid,user);p=db.get(Position,a.position_id)
        if a.assignment_id:raise HTTPException(409,'An interview is already linked to this application.')
        validate_start(body.scheduled_at)
        if p.body['status']!='open':raise HTTPException(409,'This role is closed.')
        transition(db,a,'interview_scheduled',user)
        exam=Examination(hr_id=user.id,body={'title':p.body['title']+' interview','role':p.body['title'],'level':p.body.get('difficulty','junior'),'position_id':p.id,'application_id':a.id,'instructions':body.instructions,'interview_type':body.interview_type,'opens_at':body.scheduled_at,'created_at':time.time(),'policy':ProctorConfig().model_dump()})
        db.add(exam);db.flush();assignment=Assignment(id=uid(),exam_id=exam.id,candidate_id=a.candidate_id,body={'status':'assigned','application_id':a.id,'position_id':p.id});db.add(assignment);db.flush();a.assignment_id=assignment.id;interview_notice(db,assignment,exam);db.commit();return view(db,a,True)


