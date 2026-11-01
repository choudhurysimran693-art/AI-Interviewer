"""Transactional progression shared by all round handlers; database access stays in db.py."""
import math
import time
from fastapi import HTTPException
from sqlalchemy import update
from .accounts import organization_scope
from .db import Application,ApplicationRound,InterviewRound,RecruitmentPosition
from .candidate_notices import add_notice

# Scores use the app's established 0–100 scale. These are review recommendations.
HANDLERS = {
    'resume_screening': {'threshold':60, 'screen':'resume'},
    'aptitude': {'threshold':50, 'screen':'mcq'},
    'technical': {'threshold':60, 'screen':'technical'},
    'technical_deep': {'threshold':60, 'screen':'interview'},
    'hr': {'threshold':55, 'screen':'interview'},
    'final_interview': {'threshold':None, 'screen':'manual'},
}

def recommendation(kind: str, score: float | None) -> str:
    """Return a score-based recommendation without making a hiring decision."""
    threshold=HANDLERS.get(kind,{}).get('threshold')
    if threshold is None or score is None or not math.isfinite(score):return 'review_required'
    return 'passed' if score>=threshold else 'failed'

def complete_round(db, app_id: str, round_no: int, score: float | None, *, user, decision, notes: str = ''):
    """Record a reviewed outcome and unlock one successor in the caller's transaction."""
    from .rounds import rounds, history, mode, invite, DecisionInput
    a=db.get(Application,app_id,with_for_update=True)
    if not a:raise HTTPException(404,'Application not found.')
    p=db.get(RecruitmentPosition,a.position_id)
    if user.role not in ('hr','admin') or p.organization_id!=organization_scope(user):raise HTTPException(403,'An authorized recruiter must record the decision.')
    entries=rounds(db,a.id)
    r=next((entry for entry in entries if db.get(InterviewRound,entry.round_id).round_order==round_no),None)
    if not r:raise HTTPException(404,'Round not found.')
    if decision not in ('passed','failed'):raise HTTPException(422,'Choose passed or failed.')
    if score is not None and (not math.isfinite(score) or not 0<=score<=100):raise HTTPException(422,'Score must be between 0 and 100.')
    for previous in entries:
        if previous.id==r.id:break
        if previous.status!='passed':raise HTTPException(409,'The previous rounds must be passed first.')
    body=DecisionInput(status=decision,hr_notes=notes)
    if r.status==body.status:return history(db,a,True)
    d=db.get(InterviewRound,r.round_id)
    manual=mode(d)=='human_only' and r.status=='scheduled'
    if manual and (r.scheduling or {}).get('scheduled_at',float('inf'))>time.time():raise HTTPException(409,'Record the outcome after the scheduled interview.')
    if manual and not body.hr_notes.strip():raise HTTPException(422,'Record notes for the human interview decision.')
    if a.status=='rejected' or (r.status!='completed' and not manual):raise HTTPException(409,'Only a completed, undecided round can receive a decision.')
    claimed=db.execute(update(ApplicationRound).where(ApplicationRound.id==r.id,ApplicationRound.status==r.status).values(status=body.status))
    if claimed.rowcount!=1:raise HTTPException(409,'A decision was already recorded. Refresh this application.')
    if score is not None:r.score=score
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

