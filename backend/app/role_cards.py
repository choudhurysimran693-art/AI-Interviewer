"""Application-derived role cards; one grouped query for all visible roles."""
import time
from sqlalchemy import select, case, func
from .db import Application, ApplicationRound, InterviewRound

STAGES=('source','shortlist','screening','interview','offer','hired','rejected')

def pipeline_stage_expression():
    def has_round(types, statuses):
        return select(ApplicationRound.id).join(InterviewRound).where(
            ApplicationRound.application_id==Application.id,
            InterviewRound.round_type.in_(types),ApplicationRound.status.in_(statuses)).exists()
    active=['invited','in_progress','active','completed','scheduled','awaiting_scheduling']
    stage=case(
        (Application.status=='hired','hired'),
        (Application.status=='rejected','rejected'),
        (Application.status.in_(['offer_extended','ready_for_offer']),'offer'),
        (has_round(['hr'],['passed']),'offer'),
        (has_round(['resume_screening'],active),'screening'),
        (has_round(['aptitude','technical','technical_deep','hr','final_interview'],active),'interview'),
        (Application.status=='shortlisted','shortlist'),
        (Application.status=='under_review','screening'),
        (Application.status.in_(['interview_scheduled','interviewed']),'interview'),
        else_='source')
    return stage

def pipeline_summaries(db, position_ids):
    result={pid:dict.fromkeys(STAGES,0) for pid in position_ids}
    if not result:return result
    stage=pipeline_stage_expression()
    query=select(Application.position_id,stage.label('stage'),func.count()).where(Application.position_id.in_(position_ids)).group_by(Application.position_id,stage)
    for pid,name,count in db.execute(query):result[pid][name]=count
    return result

def card(position, summary=None):
    b=position.body
    level=b.get('level') or {'mid-level':'mid'}.get(b.get('difficulty'),b.get('difficulty','junior'))
    result={'id':position.id,**b,'level':level,'screening_type':b.get('screening_type','resume_based'),
            'vacancies_filled':b.get('vacancies_filled',0),
            'days_open':max(0,int((time.time()-b.get('opened_at',time.time()))/86400))}
    if summary is not None:result.update(pipeline_summary=summary,pipeline_count=sum(summary.values()))
    return result
