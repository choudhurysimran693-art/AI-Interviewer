"""Organization-scoped, ordered interview rounds using the transactional mail outbox."""
import time
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, delete, update
from .accounts import require_user, organization_scope
from .db import DB, InterviewRound, ApplicationRound, Application, RecruitmentPosition, Examination, Assignment, Session, User, uid
from .candidate_notices import add_notice
from .proctoring import ProctorConfig

router=APIRouter(prefix='/api')
RoundType=Literal['resume_screening','aptitude','technical','technical_deep','hr','final_interview']

class RoundInput(BaseModel):
    round_type:RoundType
    round_name:str=Field(min_length=1,max_length=120)
    is_active:bool=True
    evaluation_mode:Literal['auto_evaluated','ai_scored','ai_conducted','human_only']='ai_conducted'
    default_instructions:str=Field(default='',max_length=3000)
    decision_mode:Literal['hr_review','threshold']='hr_review'
    pass_threshold:float=Field(default=70,ge=0,le=100)

    @model_validator(mode='after')
    def valid_mode(self):
        if self.round_type=='final_interview':self.evaluation_mode='human_only'
        if self.evaluation_mode=='auto_evaluated' and self.round_type!='resume_screening':
            raise ValueError('Automatic resume evaluation is only available for resume screening.')
        if self.decision_mode=='threshold' and (self.round_type!='aptitude' or self.evaluation_mode!='ai_scored'):
            raise ValueError('Automatic thresholds are available only for scored aptitude rounds.')
        return self

class SequenceInput(BaseModel):
    rounds:list[RoundInput]=Field(min_length=1,max_length=12)

    @model_validator(mode='after')
    def order(self):
        active=[r for r in self.rounds if r.is_active]
        if not active:raise ValueError('Enable at least one round.')
        finals=[i for i,r in enumerate(active) if r.round_type=='final_interview']
        if finals and finals != [len(active)-1]:raise ValueError('Final Interview must be the last enabled round and appear only once.')
        resumes=[i for i,r in enumerate(active) if r.evaluation_mode=='auto_evaluated']
        if resumes and resumes != [0]:raise ValueError('Automatic resume screening must be the first enabled round.')
        return self

class InviteInput(BaseModel):
    window_start_at:float|None=None
    window_end_at:float|None=None

class DecisionInput(BaseModel):
    status:Literal['passed','failed']
    hr_notes:str=Field(default='',max_length=10000)

class ScheduleInput(BaseModel):
    scheduled_at:float
    details:str=Field(default='',max_length=3000)

def mode(d):
    return 'human_only' if d.round_type=='final_interview' else (d.settings or {}).get('evaluation_mode','ai_conducted')

def definition(d):
    return {'round_type':d.round_type,'round_name':d.round_name,'is_active':d.is_active, **(d.settings or {}), 'evaluation_mode':mode(d)}

def definitions(db,pid):
    return list(db.scalars(select(InterviewRound).where(InterviewRound.position_id==pid).order_by(InterviewRound.round_order)))

def rounds(db,aid):
    return list(db.scalars(select(ApplicationRound).join(InterviewRound).where(ApplicationRound.application_id==aid).order_by(InterviewRound.round_order)))

def history(db,a,hr=False):
    result=[]
    for r in rounds(db,a.id):
        d=db.get(InterviewRound,r.round_id)
        item={'id':r.id,'round_id':d.id,'round_name':d.round_name,'round_type':d.round_type,'round_order':d.round_order,'status':r.status,'invited_at':r.invited_at,'completed_at':r.completed_at,'assignment_id':r.assignment_id}
        item.update(evaluation_mode=mode(d), scheduled_at=(r.scheduling or {}).get('scheduled_at'), scheduling_details=(r.scheduling or {}).get('details',''))
        if hr:item.update(score=r.score,hr_notes=r.hr_notes,interview_session_id=r.interview_session_id)
        result.append(item)
    return result

def current_label(db,a):
    entries=rounds(db,a.id)
    if not entries:return None
    if a.status=='rejected':return 'Not selected'
    if a.status=='hired':return 'Hired'
    for r in entries:
        if r.status!='passed':
            name=db.get(InterviewRound,r.round_id).round_name
            return name+' — '+('awaiting HR decision' if r.status=='completed' else r.status.replace('_',' '))
    return 'Ready for offer'

def invite(db,a,r,user,window=None):
    if a.status in ('rejected','hired','offer_extended'):raise HTTPException(409,'This application is closed to round invitations.')
    entries=rounds(db,a.id)
    for previous in entries:
        if previous.id==r.id:break
        if previous.status!='passed':raise HTTPException(409,'The previous rounds must be passed first.')
    if r.status!='pending':return r
    d=db.get(InterviewRound,r.round_id)
    if mode(d)=='human_only':
        r.status='awaiting_scheduling'
        a.updated_at=time.time()
        add_notice(db,a.candidate_id,'round-invite:'+r.id,d.round_name+' — awaiting scheduling','Details will be shared separately.','/candidate/applications',user.id,type='round_invite',related_application_round_id=r.id)
        return r
    if mode(d)=='auto_evaluated':
        from .screening import screen
        screen(db,a)
        r.status='completed';r.completed_at=time.time()
        return r
    now=time.time();window=window or InviteInput()
    start=window.window_start_at if window.window_start_at is not None else now
    end=window.window_end_at if window.window_end_at is not None else start+7*86400
    if end<=max(start,now):raise HTTPException(422,'The invitation must have a future end after its start.')
    claimed=db.execute(update(ApplicationRound).where(ApplicationRound.id==r.id,ApplicationRound.status=='pending').values(status='invited'))
    if claimed.rowcount!=1:raise HTTPException(409,'This round was already invited. Refresh its status.')
    p=db.get(RecruitmentPosition,a.position_id);d=db.get(InterviewRound,r.round_id)
    exam=Examination(hr_id=user.id,body={'title':p.body['title']+' · '+d.round_name,'role':p.body['title'],'level':p.body.get('difficulty','junior'),'position_id':p.id,'application_id':a.id,'application_round_id':r.id,'round_type':d.round_type,'instructions':'Complete '+d.round_name+'. One attempt is allowed.','interview_type':'resume_based' if d.round_type=='resume_screening' else 'role_based','opens_at':start,'window_start_at':start,'window_end_at':end,'created_at':now,'policy':ProctorConfig().model_dump()})
    db.add(exam);db.flush()
    exam.body=exam.body|{'evaluation_mode':mode(d),'instructions':(d.settings or {}).get('default_instructions') or exam.body['instructions']}
    assignment=Assignment(id=uid(),exam_id=exam.id,candidate_id=a.candidate_id,body={'status':'assigned','application_id':a.id,'position_id':p.id,'application_round_id':r.id})
    db.add(assignment);db.flush()
    r.status='invited';r.invited_at=now;r.assignment_id=assignment.id
    a.assignment_id=assignment.id;a.updated_at=now
    add_notice(db,a.candidate_id,'round-invite:'+r.id,d.round_name+' invitation',p.body['title']+': You are invited to '+d.round_name+'. This assessment allows one attempt.', '/candidate/interview?assignment='+assignment.id,user.id,type='round_invite',related_application_round_id=r.id,scheduled_at=start,window_end_at=end)
    return r

def initialize(db,a,user):
    if rounds(db,a.id):return
    for d in definitions(db,a.position_id):
        if d.is_active:db.add(ApplicationRound(application_id=a.id,round_id=d.id))
    db.flush();entries=rounds(db,a.id)
    if entries:
        first=entries[0];d=db.get(InterviewRound,first.round_id)
        if mode(d)=='auto_evaluated':
            from .screening import screen
            screen(db,a)
            first.status='passed';first.completed_at=time.time();first.hr_notes='Passed by HR shortlisting this application.'
            if len(entries)>1:invite(db,a,entries[1],user)
        else:invite(db,a,first,user)

def complete_session(db,s):
    rid=s.body.get('application_round_id')
    if not rid:return
    r=db.get(ApplicationRound,rid)
    if not r or r.interview_session_id!=s.id:raise HTTPException(409,'Round session does not match.')
    if r.status in ('completed','passed','failed'):return
    if s.status!='complete':raise HTTPException(409,'Finish the assigned assessment first.')
    r.status='completed';r.completed_at=time.time()
    summary=s.body.get('summary',{});value=summary.get('overall',summary.get('overall_score'))
    r.score=float(value) if isinstance(value,(int,float)) else None
    a=db.get(Application,r.application_id);a.updated_at=time.time()
    d=db.get(InterviewRound,r.round_id)
    if (d.settings or {}).get('decision_mode')=='threshold' and r.score is not None:
        from .db import Answer, Question
        answers=list(db.scalars(select(Answer).where(Answer.session_id==s.id)))
        # Missing/unavailable scores always require review, never automatic rejection.
        question_ids=set(db.scalars(select(Question.id).where(Question.session_id==s.id)))
        if question_ids and len(answers)==len(question_ids) and {x.body.get('question_id') for x in answers}==question_ids and all(x.body.get('evaluation',{}).get('status')=='scored' for x in answers):
            user=db.get(User,s.body['hr_id'])
            status='passed' if r.score>=d.settings.get('pass_threshold',70) else 'failed'
            apply_decision(db,r,a,user,DecisionInput(status=status,hr_notes='Configured aptitude threshold applied.'))

def owned_round(db,rid,user):
    from .applications import owned
    r=db.get(ApplicationRound,rid,with_for_update=True)
    if not r:raise HTTPException(404,'Round not found.')
    return r,owned(db,r.application_id,user)

@router.get('/positions/{pid}/rounds')
def get_rounds(pid:str):
    user=require_user('hr','admin')
    with DB() as db:
        p=db.get(RecruitmentPosition,pid)
        if not p or p.organization_id!=organization_scope(user):raise HTTPException(404,'Position not found.')
        return [definition(d) for d in definitions(db,pid)]

@router.post('/positions/{pid}/rounds')
def define_rounds(pid:str,body:SequenceInput):
    user=require_user('hr','admin')
    with DB() as db:
        p=db.get(RecruitmentPosition,pid,with_for_update=True)
        if not p or p.organization_id!=organization_scope(user):raise HTTPException(404,'Position not found.')
        if db.scalar(select(ApplicationRound).join(InterviewRound).where(InterviewRound.position_id==pid)):raise HTTPException(409,'Rounds cannot be changed after candidates enter this pipeline.')
        if not any(r.is_active for r in body.rounds):raise HTTPException(422,'Enable at least one round.')
        db.execute(delete(InterviewRound).where(InterviewRound.position_id==pid))
        for order,r in enumerate(body.rounds,1):
            values=r.model_dump();settings={k:values.pop(k) for k in ['evaluation_mode','default_instructions','decision_mode','pass_threshold']}
            db.add(InterviewRound(position_id=pid,round_order=order,settings=settings,**values))
        db.commit();return {'saved':True}

@router.get('/round-templates')
def templates():
    require_user('hr','admin')
    from .round_templates import seed, items
    from .db import RoundTemplate
    with DB() as db:
        seed(db);db.commit()
        return [{'id':t.id,'name':t.name,'description':t.description,'is_default':t.is_default,'items':[{'round_type':i.round_type,'round_name':i.round_name,'evaluation_mode':i.evaluation_mode,'default_instructions':i.default_instructions} for i in items(db,t.id)]} for t in db.scalars(select(RoundTemplate))]

class TemplateInput(BaseModel):
    template_id:str='standard-technical-v1'

@router.post('/positions/{pid}/apply-round-template')
def apply_template(pid:str,body:TemplateInput):
    require_user('hr','admin')
    from .round_templates import seed, items
    with DB() as db:
        seed(db);db.commit();rows=items(db,body.template_id)
        if not rows:raise HTTPException(404,'Template not found.')
        sequence=SequenceInput(rounds=[RoundInput(round_type=r.round_type,round_name=r.round_name,evaluation_mode=r.evaluation_mode,default_instructions=r.default_instructions) for r in rows])
    return define_rounds(pid,sequence)

@router.patch('/application-rounds/{rid}/schedule')
def schedule_manual(rid:str,body:ScheduleInput):
    user=require_user('hr','admin')
    with DB() as db:
        r,a=owned_round(db,rid,user);d=db.get(InterviewRound,r.round_id)
        if mode(d)!='human_only' or r.status not in ('awaiting_scheduling','scheduled') or a.status=='rejected':
            raise HTTPException(409,'Only an unlocked human interview can be scheduled.')
        if body.scheduled_at<=time.time():raise HTTPException(422,'Choose a future date and time.')
        r.scheduling=body.model_dump();r.status='scheduled';a.updated_at=time.time()
        add_notice(db,a.candidate_id,'round-schedule:'+uid(),d.round_name+' scheduled',body.details or 'Details will be shared separately.','/candidate/applications',user.id,scheduled_at=body.scheduled_at)
        db.commit();return history(db,a,True)

@router.get('/hr/applications/{aid}/rounds')
def round_history(aid:str):
    user=require_user('hr','admin')
    from .applications import owned
    with DB() as db:return history(db,owned(db,aid,user),True)

@router.post('/applications/{aid}/rounds/{rid}/invite')
def invite_round(aid:str,rid:str,body:InviteInput):
    user=require_user('hr','admin')
    from .applications import owned
    with DB() as db:
        a=owned(db,aid,user)
        r=db.scalar(select(ApplicationRound).where(ApplicationRound.application_id==aid,ApplicationRound.round_id==rid))
        if not r:raise HTTPException(404,'Round not found. Shortlist this application first.')
        invite(db,a,r,user,body);db.commit();return history(db,a,True)

@router.post('/application-rounds/{rid}/complete')
def finish_round(rid:str):
    user=require_user('candidate')
    with DB() as db:
        r=db.get(ApplicationRound,rid,with_for_update=True)
        a=db.get(Application,r.application_id) if r else None
        if not a or a.candidate_id!=user.id:raise HTTPException(404,'Round not found.')
        s=db.get(Session,r.interview_session_id) if r.interview_session_id else None
        if not s:raise HTTPException(409,'Start and finish the assigned assessment first.')
        complete_session(db,s);db.commit();return {'status':r.status}

@router.patch('/application-rounds/{rid}/decision')
def decide(rid:str,body:DecisionInput):
    user=require_user('hr','admin')
    with DB() as db:
        r,a=owned_round(db,rid,user)
        result=apply_decision(db,r,a,user,body);db.commit();return result

def apply_decision(db,r,a,user,body):
    if r.status==body.status:return history(db,a,True)
    d=db.get(InterviewRound,r.round_id)
    manual=mode(d)=='human_only' and r.status=='scheduled'
    if manual and (r.scheduling or {}).get('scheduled_at',float('inf'))>time.time():raise HTTPException(409,'Record the outcome after the scheduled interview.')
    if manual and not body.hr_notes.strip():raise HTTPException(422,'Record notes for the human interview decision.')
    if a.status=='rejected' or (r.status!='completed' and not manual):raise HTTPException(409,'Only a completed, undecided round can receive a decision.')
    claimed=db.execute(update(ApplicationRound).where(ApplicationRound.id==r.id,ApplicationRound.status==r.status).values(status=body.status))
    if claimed.rowcount!=1:raise HTTPException(409,'A decision was already recorded. Refresh this application.')
    r.completed_at=r.completed_at or time.time()
    r.status=body.status;r.hr_notes=body.hr_notes;a.updated_at=time.time()
    d=db.get(InterviewRound,r.round_id);p=db.get(RecruitmentPosition,a.position_id)
    entries=rounds(db,a.id);following=next((x for x in entries if x.status=='pending'),None)
    if body.status=='failed':
        a.status='rejected';message='Thank you for your time and interest in '+p.body['title']+'. We will not be moving forward with your application.'
    else:
        message='You passed '+d.round_name+' for '+p.body['title']+'. '
        if following:
            invite(db,a,following,user);message+='Your next round is '+db.get(InterviewRound,following.round_id).round_name+'. '+('Details will be shared separately.' if following.status=='awaiting_scheduling' else 'See the invitation for your assessment window.')
        else:
            if d.round_type=='final_interview':
                from .applications import transition
                a.status='ready_for_offer'
                transition(db,a,'offer_extended',user)
                transition(db,a,'hired',user)
            else:a.status='ready_for_offer'
            message+=('HR has recorded a hire decision and will contact you with next steps.' if a.status=='hired' else 'All rounds are complete. HR will contact you about the final decision.')
    add_notice(db,a.candidate_id,'round-result:'+r.id,d.round_name+' result',message,'/candidate/applications',user.id,type='round_result',related_application_round_id=r.id)
    return history(db,a,True)
