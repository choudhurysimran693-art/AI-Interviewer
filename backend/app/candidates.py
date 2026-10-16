"""Application cards with shared pipeline stages and organization authorization."""
import time
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, case
from .accounts import require_user, organization_scope
from .db import DB, Application, RecruitmentPosition as Position, User, Session, ApplicationRound, InterviewRound, ApplicationResume
from .role_cards import pipeline_stage_expression
from .applications import transition

router=APIRouter(prefix='/api')
STAGES=('source','shortlisted','screening','interview','offer','hired','rejected')
Stage=Literal['source','shortlisted','screening','interview','offer','hired','rejected']

def filters(search:str=Query('',max_length=200),position_id:str|None=None,min_score:float=Query(0,ge=0,le=100)):
    user=require_user('hr','admin')
    return {'user':user,'search':search.strip(),'position_id':position_id or None,'min_score':min_score}

def base(db,f):
    org=organization_scope(f['user'])
    if f['position_id']:
        p=db.get(Position,f['position_id'])
        if not p or p.organization_id!=org:raise HTTPException(404,'Position not found.')
    # One most recently completed interview per application, never another role's score.
    ranked=select(Session.body['application_id'].as_string().label('aid'),Session.body['summary']['overall'].as_float().label('score'),
        func.row_number().over(partition_by=Session.body['application_id'].as_string(),order_by=[Session.body['ended_at'].as_float().desc(),Session.id]).label('rank')).where(Session.status=='complete',Session.body['ended_at'].as_float().is_not(None),Session.body['application_id'].as_string().in_(select(Application.id).join(Position).where(Position.organization_id==org))).subquery()
    recent=select(ranked.c.aid,ranked.c.score).where(ranked.c.rank==1).subquery()
    stage=pipeline_stage_expression()
    active=select(Session.id).where(Session.body['application_id'].as_string()==Application.id,Session.status.in_(['active','processing'])).exists()
    round_active=select(ApplicationRound.id).where(ApplicationRound.application_id==Application.id,ApplicationRound.status.in_(['invited','active','in_progress','completed','scheduled','awaiting_scheduling'])).exists()
    score=case((recent.c.score.between(0,100),recent.c.score),else_=None)
    query=select(Application.id.label('id'),Application.id.label('application_id'),User.id.label('candidate_id'),User.name.label('full_name'),User.email,
        Application.position_id,Position.body['title'].as_string().label('position_title'),
        case((stage=='shortlist','shortlisted'),else_=stage).label('pipeline_stage'),
        score.label('overall_score'),case((score.is_not(None),'assessed'),(active|round_active,'in_progress'),else_='not_assessed').label('assessment_status'),Application.updated_at)
    query=query.select_from(Application).join(Position,Application.position_id==Position.id).join(User,Application.candidate_id==User.id).outerjoin(recent,recent.c.aid==Application.id).where(Position.organization_id==org)
    if f['position_id']:query=query.where(Position.id==f['position_id'])
    if f['search']:
        value=f['search'].lower().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        query=query.where(func.lower(User.name).like('%'+value+'%',escape='\\')|func.lower(User.email).like('%'+value+'%',escape='\\'))
    if f['min_score']>0:query=query.where(score>=f['min_score'])
    return query.subquery()

@router.get('/candidates/filter-counts')
def filter_counts(f=Depends(filters)):
    with DB() as db:
        s=base(db,f)
        counts=dict(db.execute(select(s.c.pipeline_stage,func.count()).group_by(s.c.pipeline_stage)).all())
        return {stage:counts.get(stage,0) for stage in STAGES}

@router.get('/candidates')
def candidates(f=Depends(filters),stages:str='',sort:Literal['modified_date']='modified_date',page:int=Query(1,ge=1),page_size:int=Query(12,ge=1,le=100)):
    selected=[s for s in stages.split(',') if s]
    if any(s not in STAGES for s in selected):raise HTTPException(422,'Unknown pipeline stage.')
    with DB() as db:
        s=base(db,f);where=s.c.pipeline_stage.in_(selected) if selected else True
        total=db.scalar(select(func.count()).select_from(s).where(where))
        rows=db.execute(select(s).where(where).order_by(s.c.updated_at.desc(),s.c.id).offset((page-1)*page_size).limit(page_size)).mappings().all()
        org_total=db.scalar(select(func.count()).select_from(Application).join(Position).where(Position.organization_id==organization_scope(f['user'])))
        return {'items':[dict(r) for r in rows],'total_count':total,'organization_total':org_total,'page':page,'page_size':page_size}

class BulkMove(BaseModel):
    application_ids:list[str]=Field(min_length=1,max_length=100)
    target_stage:Stage

@router.patch('/applications/bulk-move')
def bulk_move(body:BulkMove):
    user=require_user('hr','admin');ids=list(dict.fromkeys(body.application_ids));results=[]
    with DB() as db:
        # Resolve every ID through organization ownership before any mutation.
        allowed=set(db.scalars(select(Application.id).join(Position).where(Application.id.in_(ids),Position.organization_id==organization_scope(user))))
        for aid in ids:
            if aid not in allowed:results.append({'id':aid,'success':False,'error':'Application not found.'})
        targets={'source':'applied','shortlisted':'shortlisted','screening':'under_review','interview':'interview_scheduled','offer':'offer_extended','hired':'hired','rejected':'rejected'}
        for aid in sorted(allowed):
            try:
                with db.begin_nested():
                    a=db.scalar(select(Application).where(Application.id==aid).with_for_update())
                    status=targets[body.target_stage]
                    if status=='interview_scheduled' and not a.assignment_id:raise HTTPException(409,'Schedule an interview or invite a round first.')
                    if status=='shortlisted' and a.status=='applied':transition(db,a,'under_review',user)
                    transition(db,a,status,user)
                    actual=db.scalar(select(pipeline_stage_expression()).where(Application.id==aid))
                    if actual=='shortlist':actual='shortlisted'
                    if actual!=body.target_stage:raise HTTPException(409,'Round progress prevents this move. Update the round decision or invitation first.')
                results.append({'id':aid,'success':True})
            except HTTPException as exc:results.append({'id':aid,'success':False,'error':str(exc.detail)})
        db.commit()
    return {'results':results,'success_count':sum(r['success'] for r in results),'failure_count':sum(not r['success'] for r in results)}

@router.get('/candidates/{cid}')
def profile(cid:str):
    user=require_user('hr','admin');f={'user':user,'search':'','position_id':None,'min_score':0}
    with DB() as db:
        s=base(db,f);apps=[dict(r) for r in db.execute(select(s).where(s.c.candidate_id==cid)).mappings()]
        if not apps:raise HTTPException(404,'Candidate not found.')
        account=db.get(User,cid);ids=[a['id'] for a in apps]
        rounds=[{'application_id':r.application_id,'id':r.id,'round_type':d.round_type,'round_name':d.round_name,'round_order':d.round_order,'status':r.status,'score':r.score} for r,d in db.execute(select(ApplicationRound,InterviewRound).join(InterviewRound).where(ApplicationRound.application_id.in_(ids)).order_by(InterviewRound.round_order))]
        sessions=[{'id':s.id,'application_id':s.body.get('application_id'),'status':s.status,'completed_at':s.body.get('ended_at'),'scores':s.body.get('summary'),'report_url':'/hr/reports?review='+s.id} for s in db.scalars(select(Session).where(Session.body['application_id'].as_string().in_(ids)).order_by(Session.created.desc()))]
        resumes=set(db.scalars(select(ApplicationResume.application_id).where(ApplicationResume.application_id.in_(ids))))
        for a in apps:
            a['rounds']=[r for r in rounds if r['application_id']==a['id']]
            a['resume_url']='/api/applications/'+a['id']+'/resume' if a['id'] in resumes else None
        return {'id':cid,'full_name':account.name,'email':account.email,'phone':account.body.get('profile',{}).get('phone',''),'parsed_profile':account.body.get('profile',{}).get('resume_profile',{}),'applications':apps,'interviews':sessions}
