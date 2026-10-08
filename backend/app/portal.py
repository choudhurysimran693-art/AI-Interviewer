from .candidate_notices import interview_notice
import time
import secrets
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from .accounts import organization_scope, organization_recruiters, require_user,public,password_hash,hashed
from .db import DB,User,Examination,Assignment,Session,Notification,Recovery,Report,Observation,Recruiter
from .proctoring import ProctorConfig

router=APIRouter(prefix='/api/portal')
def window_status(exam, assignment, session, now=None):
    now=now or time.time(); b=exam.body; start=b.get('window_start_at',b.get('opens_at',0)); end=b.get('window_end_at',start+7200 if start else 0)
    if assignment.body.get('status') in ('attempt_deleted','terminated','completed'):
        return assignment.body['status']
    if session:
        if session.status=='complete': return 'completed'
        if session.status=='terminated': return 'terminated'
        if session.body.get('exam_started_at'): return session.status

    if end and now>end:
        if not assignment.body.get('attempt_used'):
            assignment.body=assignment.body|{'attempt_used':True,'status':'expired','expired_at':now}
        return 'expired'
    return 'open_now' if start<=now<=end else 'scheduled'
class ExamInput(BaseModel):
    title:str=Field(min_length=3,max_length=180)
    role:str=Field(min_length=2,max_length=150)
    level:str='junior'
    interview_type:Literal['resume_based','role_based','mixed']='resume_based'
    instructions:str=Field(default='Remain alone, keep your face visible, and stay in fullscreen. Do not use additional devices or copy/paste.',max_length=3000)
    candidate_email:str=Field(max_length=200)
    opens_at:float=0
    policy:ProctorConfig=Field(default_factory=lambda:ProctorConfig(auto_terminate=True,block_account=True))
class StatusInput(BaseModel):
    status:str
class StaffInput(BaseModel):
    name:str=Field(min_length=2,max_length=150)
    email:str=Field(max_length=200)
    password:str=Field(min_length=8,max_length=200)
    @field_validator('password')
    @classmethod
    def strong_password(cls,value):
        if not any(c.islower() for c in value) or not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError('Password must include uppercase, lowercase, and a number.')
        return value
    role:str='hr'
class RestrictionInput(BaseModel):
    blocked:bool
    reason:str=Field(min_length=5,max_length=1000)

@router.get('/dashboard')
def dashboard():
    user=require_user()
    with DB() as db:
        assignments=[]
        for a in db.scalars(select(Assignment)):
            exam=db.get(Examination,a.exam_id)
            if user.role=='candidate' and a.candidate_id!=user.id:continue
            if user.role in ('hr','admin') and exam.hr_id not in organization_recruiters(user):continue
            candidate=db.get(User,a.candidate_id);session=db.get(Session,a.session_id) if a.session_id else None
            start=exam.body.get('window_start_at',exam.body.get('opens_at',0));end=exam.body.get('window_end_at',start+7200 if start else 0)
            assignments.append({'id':a.id,'exam_id':exam.id,'title':exam.body['title'],'role':exam.body['role'],'level':exam.body['level'],'instructions':exam.body.get('instructions','Complete your assigned interview.'),'interview_type':exam.body.get('interview_type','resume_based'),'opens_at':start,'window_start_at':start,'window_end_at':end,'candidate':public(candidate),'session_id':a.session_id,'status':window_status(exam,a,session),'security':session.body.get('security',{}) if session else {},'started_at':session.body.get('exam_started_at') if session else None,'ended_at':session.body.get('ended_at') if session else None,'policy':exam.body['policy']})
        db.commit()
        history=[{'id':s.id,'role':s.body['role'],'status':s.status,'created':s.created} for s in db.scalars(select(Session)) if s.body.get('user_id')==user.id and s.mode=='practice']
        notifications=[{'id':n.id,'session_id':n.session_id,**n.body} for n in db.scalars(select(Notification)) if user.role in ('hr','admin') and n.hr_id in organization_recruiters(user)]
        return {'user':public(user),'assignments':assignments,'practice_history':history,'notifications':sorted(notifications,key=lambda n:n['timestamp'],reverse=True)}

@router.get('/candidates')
def candidates():
    require_user('hr','admin')
    with DB() as db:
        return [{'id':u.id,'name':u.name,'email':u.email,'role':u.role} for u in db.scalars(select(User)).all() if u.role=='candidate']

@router.get('/overview')
def overview():
    """Recruiter summary backed by the same assignments used by the HR workspace."""
    user=require_user('hr','admin')
    with DB() as db:
        rows=[]
        for a in db.scalars(select(Assignment)):
            exam=db.get(Examination,a.exam_id)
            if not exam or (user.role in ('hr','admin') and exam.hr_id not in organization_recruiters(user)): continue
            session=db.get(Session,a.session_id) if a.session_id else None
            candidate=db.get(User,a.candidate_id)
            status=session.status if session else a.body.get('status','assigned')
            rows.append({'id':a.id,'role':exam.body.get('role',''), 'title':exam.body.get('title',''), 'candidate':public(candidate), 'status':status, 'opens_at':exam.body.get('opens_at',0), 'review_required':bool(session and session.body.get('security',{}).get('review_required'))})
        roles={}
        for row in rows:
            item=roles.setdefault(row['role'],{'role':row['role'],'assigned':0,'active':0,'completed':0,'flagged':0})
            item['assigned']+=1
            if row['status'] in ['active','ready','paused']: item['active']+=1
            if row['status']=='complete': item['completed']+=1
            if row['review_required']: item['flagged']+=1
        return {'metrics':{'applicants':len(rows),'shortlisted':sum(r['status'] in ['ready','active','complete'] for r in rows),'completed':sum(r['status']=='complete' for r in rows),'flagged':sum(r['review_required'] for r in rows)},'roles':list(roles.values()),'interviews':rows}

@router.get('/malpractice-alerts')
def malpractice_alerts():
    user=require_user('hr','admin')
    with DB() as db:
        alerts=[]
        for s in db.scalars(select(Session)):
            if s.status!='terminated' and not s.body.get('security',{}).get('gaze_review_required'):continue
            if not s.body.get('exam_id') or (user.role in ('hr','admin') and s.body.get('hr_id') not in organization_recruiters(user)):continue
            candidate=db.get(User,s.body.get('user_id'))
            reason='gaze_review' if s.status!='terminated' else s.body.get('terminated_reason') or s.body.get('security',{}).get('terminated_reason') or 'policy threshold'
            alerts.append({'session_id':s.id,'candidate':public(candidate) if candidate else None,'position':s.body.get('role',''),
                'violation_type':reason,'detected_at':s.body.get('ended_at') or s.created,'status':'review_required' if reason=='gaze_review' else 'terminated','attempt_used':bool(s.body.get('attempt_used')),
                'report_path':'/portal/reports/'+s.id})
        return {'items':sorted(alerts,key=lambda x:x['detected_at'] or 0,reverse=True)}

@router.post('/exams')
def create_exam(data:ExamInput):
    user=require_user('hr','admin')
    if data.level not in ['intern','junior','mid-level','senior']:raise HTTPException(422,'Invalid level.')
    with DB() as db:
        candidate=db.scalar(select(User).where(User.email==data.candidate_email.strip().lower(),User.role=='candidate'))
        if not candidate:raise HTTPException(404,'Candidate must create an account before assignment.')
        exam=Examination(hr_id=user.id,body=data.model_dump(exclude={'candidate_email'})|{'created_at':time.time()});db.add(exam);db.flush()
        a=Assignment(id=f'{exam.id}:{candidate.id}',exam_id=exam.id,candidate_id=candidate.id,body={'status':'assigned'});db.add(a);interview_notice(db,a,exam);db.commit()
        return {'id':exam.id,'assignment_id':a.id}

@router.patch('/exams/{eid}/policy')
def policy(eid:str,data:ProctorConfig):
    user=require_user('admin')
    with DB() as db:
        exam=db.get(Examination,eid)
        if not exam or exam.hr_id not in organization_recruiters(user):raise HTTPException(404)
        if any(a.session_id for a in db.scalars(select(Assignment).where(Assignment.exam_id==eid))):raise HTTPException(409,'Policy is frozen once an attempt exists. Create a new examination for changed rules.')
        exam.body=exam.body|{'policy':data.model_dump(),'policy_updated_by':user.id};db.commit();return {'saved':True}

@router.get('/attempts/{sid}/resume')
def resume(sid:str):
    user=require_user('candidate')
    from .main import session_token,report_token
    with DB() as db:
        s=db.get(Session,sid)
        if not s or s.body.get('user_id')!=user.id:raise HTTPException(404)
        if s.status in ['terminated','deleting'] or s.expires<=time.time():raise HTTPException(409,'This attempt cannot be resumed.')
        if s.status=='complete':return {'report':f'/report/{report_token(s.id,"candidate")}'}
        return {'id':sid,'token':session_token(sid)}

@router.get('/reports/{sid}')
def hr_report(sid:str):
    user=require_user('hr','admin')
    from .main import report,report_token
    with DB() as db:
        s=db.get(Session,sid)
        if not s or (s.body.get('hr_id') not in organization_recruiters(user)):raise HTTPException(404)
        result=report(report_token(sid,'hr'),db)
        return result|{'status':s.status,'started_at':s.body.get('exam_started_at'),'ended_at':s.body.get('ended_at'),'security':s.body.get('security',{}),'report_url':f'/report/{report_token(sid,"hr")}'}

@router.patch('/notifications/{nid}')
def notification(nid:str,data:StatusInput):
    user=require_user('hr','admin')
    if data.status not in ['unread','read','reviewed']:raise HTTPException(422)
    with DB() as db:
        n=db.get(Notification,nid)
        if not n or n.hr_id not in organization_recruiters(user):raise HTTPException(404)
        now=time.time()
        changes={'status':data.status,'updated_by':user.id,'updated_at':now}
        if data.status=='reviewed':
            changes.update({'reviewed_by':user.id,'reviewed_at':now})
        n.body=n.body|changes;db.commit();return {'saved':True,'reviewed_by':n.body.get('reviewed_by'),'reviewed_at':n.body.get('reviewed_at')}

@router.get('/admin/users')
def users():
    admin=require_user('admin')
    with DB() as db:return [public(u) for u in db.scalars(select(User).where(User.id.in_(organization_recruiters(admin))))]

@router.post('/admin/users')
def create_staff(data:StaffInput):
    admin=require_user('admin')
    if data.role not in ['hr','admin'] or '@' not in data.email:raise HTTPException(422)
    with DB() as db:
        if db.scalar(select(User).where(User.email==data.email.strip().lower())):raise HTTPException(409,'Email already exists.')
        user=User(name=data.name,email=data.email.strip().lower(),password_hash=password_hash(data.password),role=data.role,body={});db.add(user);db.flush();db.add(Recruiter(user_id=user.id,organization_id=organization_scope(admin)));db.commit();return public(user)

@router.patch('/admin/users/{uid}/restriction')
def restriction(uid:str,data:RestrictionInput):
    admin=require_user('admin')
    with DB() as db:
        user=db.get(User,uid)
        if not user or user.id not in organization_recruiters(admin):raise HTTPException(404)
        if user.id==admin.id:raise HTTPException(409,'Cannot restrict your own administrator account.')
        user.body=user.body|{'blocked':data.blocked,'blocked_until':None,'block_reason':data.reason,'restriction_updated_by':admin.id,'restriction_updated_at':time.time()};db.commit();return {'saved':True}

@router.get('/admin/recovery')
def recoveries():
    admin=require_user('admin')
    with DB() as db:return [{'id':r.id,'user':public(db.get(User,r.user_id)),**{k:v for k,v in r.body.items() if k!='token_hash'}} for r in db.scalars(select(Recovery).where(Recovery.user_id.in_(organization_recruiters(admin))))]

@router.post('/admin/recovery/{rid}/issue')
def issue_recovery(rid:str):
    admin=require_user('admin')
    with DB() as db:
        row=db.get(Recovery,rid)
        if not row or row.user_id not in organization_recruiters(admin):raise HTTPException(404)
        token=secrets.token_urlsafe(40);row.body=row.body|{'status':'issued','issued_by':admin.id,'token_hash':hashed(token),'expires':time.time()+1800};db.commit()
        return {'reset_path':f'/?reset={token}','message':'Deliver this one-use link to the verified account owner through your approved secure channel.'}

