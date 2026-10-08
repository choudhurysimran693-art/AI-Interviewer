import asyncio
import hmac
import random
import time
from typing import Literal
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from .accounts import require_user, hashed, blocked
from .db import DB, User, LoginSession, PracticeAttempt, PracticeQuestion
from .question_bank import seed_bank
from .ai import evaluate
from .code_runner import grade, RuntimeUnavailable

router=APIRouter(prefix='/api/candidate')

def own(db,sid,user):
    row=db.get(PracticeAttempt,sid)
    if not row or row.user_id!=user.id:raise HTTPException(404,'Practice session not found.')
    return row

def public_question(q, option_order=None):
    body={k:v for k,v in q.body.items() if k not in ['key','expected_points','correct_option_ids','option_explanations_json','hidden_tests']}
    if option_order:
        by_id={o['id']:o for o in body.get('options_json',[])}
        body['options_json']=[by_id[i] for i in option_order if i in by_id]
    return {'id':q.id,**body}

def view(db,row):
    b=row.body
    questions=[public_question(db.get(PracticeQuestion,q),b.get('option_orders',{}).get(q)) for q in b['question_ids']]
    return {'id':row.id,**{k:v for k,v in b.items() if k!='question_ids'},'questions':questions}

class ProfileInput(BaseModel):
    name:str=Field(min_length=2,max_length=150)
    phone:str=Field(default='',max_length=30)
    target_position:str=Field(default='',max_length=150)
    skill_tags:list[str]=Field(default_factory=list,max_length=30)
    notifications:bool=True
    resume_name:str=Field(default='',max_length=250)
    resume_profile:dict=Field(default_factory=dict)
    country:str=Field(default='',max_length=100)
    profile_image_url:str=Field(default='',max_length=500)
    id_card_url:str=Field(default='',max_length=500)

@router.get('/profile')
def profile():
    u=require_user('candidate')
    saved=dict(u.body.get('profile',{}))
    # Older saved profiles may have parsed skills only inside resume_profile.
    # Normalize them into the editable field so they survive reloads.
    if not saved.get('skill_tags') and isinstance(saved.get('resume_profile'),dict):
        saved['skill_tags']=[str(skill) for skill in (saved['resume_profile'].get('skills') or [])]
    required=[u.name,u.email,saved.get('phone'),saved.get('target_position'),saved.get('resume_name')]
    optional=[saved.get('skill_tags')]
    completion_percent=round((sum(bool(x) for x in required)*100/5)*.8+(sum(bool(x) for x in optional)*100)*.2)
    return {'name':u.name,'email':u.email,'completion_percent':completion_percent,**saved}

@router.patch('/profile')
def save_profile(body:ProfileInput):
    u=require_user('candidate')
    if any(len(s)>80 for s in body.skill_tags):raise HTTPException(422,'Each skill must be under 80 characters.')
    with DB() as db:
        row=db.get(User,u.id);row.name=body.name
        saved=row.body.get('profile',{})|body.model_dump(exclude={'name'},exclude_unset=True)
        if not saved.get('skill_tags') and isinstance(saved.get('resume_profile'),dict):saved['skill_tags']=saved['resume_profile'].get('skills',[])
        row.body=row.body|{'profile':saved};db.commit()
    return {'saved':True}

@router.get('/question-bank')
def bank(category:str='',subcategory:str='',difficulty:str='',chapter:str='',type:str=''):
    require_user('candidate')
    with DB() as db:
        seed_bank(db)
        return {'items':[public_question(q) for q in db.scalars(select(PracticeQuestion)) if (not category or q.body['category']==category) and (not subcategory or q.body['subcategory']==subcategory) and (not difficulty or q.body['difficulty']==difficulty) and (not chapter or q.body.get('chapter')==chapter) and (not type or q.body.get('question_type')==type)]}

@router.get('/question-bank/chapters')
def chapters(coding_only:bool=False):
    require_user('candidate')
    with DB() as db:
        seed_bank(db);items=[q.body for q in db.scalars(select(PracticeQuestion)) if q.body.get('category')=='technical' and q.body.get('chapter')]
        if coding_only:items=[q for q in items if str(q.get('id','')).startswith('coding-v1-')]
        result=[]
        for name in sorted({x['chapter'] for x in items}):
            rows=[x for x in items if x['chapter']==name]
            result.append({'chapter':name,'counts':{d:sum(x['difficulty']==d for x in rows) for d in ['easy','medium','hard']},'total':len(rows)})
        return {'items':result}

class StartInput(BaseModel):
    track:Literal['technical','aptitude','reasoning','mixed']='mixed'
    difficulty:Literal['easy','medium','hard']='easy'
    topic:str=Field(default='',max_length=80)
    chapter_focus:str|None=Field(default=None,max_length=100)

def progression(db,user_id,track):
    completed=[r for r in db.scalars(select(PracticeAttempt).where(PracticeAttempt.user_id==user_id)) if r.body.get('status')=='completed' and r.body.get('track')==track]
    cleared={r.body['difficulty'] for r in completed if len(r.body.get('answers',[]))>=10}
    return {'unlocked':['easy']+(['medium'] if 'easy' in cleared else [])+(['hard'] if {'easy','medium'}<=cleared else []),'completed_questions':sum(len(r.body.get('answers',[])) for r in completed)}

@router.get('/practice-progress')
def practice_progress():
    u=require_user('candidate')
    with DB() as db:return {track:progression(db,u.id,track) for track in ['technical','aptitude','reasoning','mixed']}

@router.post('/interview-sessions')
def start(body:StartInput):
    u=require_user('candidate')
    with DB() as db:
        seed_bank(db)
        if body.difficulty not in progression(db,u.id,body.track)['unlocked']:
            raise HTTPException(409,'Complete 10 questions at the previous difficulty in this track to unlock this level.')
        completed=[r for r in db.scalars(select(PracticeAttempt).where(PracticeAttempt.user_id==u.id)) if r.body.get('status')=='completed' and r.body.get('track')==body.track]
        used={qid for r in completed for qid in r.body.get('question_ids',[])}
        questions=[q for q in db.scalars(select(PracticeQuestion)) if q.body['difficulty']==body.difficulty and (body.track=='mixed' or q.body['category']==body.track) and (not body.topic or q.body['subcategory']==body.topic) and (not body.chapter_focus or q.body.get('chapter')==body.chapter_focus)]
        fresh=[q for q in questions if q.id not in used]
        questions=fresh
        if body.track=='technical':
            questions=[q for q in questions if q.id.startswith('coding-v1-')]
        if not questions:raise HTTPException(422,'No questions match this selection. Choose another topic.')
        if not body.chapter_focus and not body.topic and len(questions)<10:raise HTTPException(409,'Fewer than 10 new questions remain at this level. Choose the next unlocked difficulty or a focused chapter.')
        random.SystemRandom().shuffle(questions)
        if body.track=='technical' and body.chapter_focus:
            balanced=[]
            for kind in ['mcq_single','mcq_multi','true_false','pseudocode','coding','code']:
                balanced.extend(q for q in questions if q.body.get('question_type')==kind and q not in balanced)
            questions=balanced+[q for q in questions if q not in balanced]
        if body.track=='mixed':
            first=[next(q for q in questions if q.body['category']==c) for c in ['technical','aptitude','reasoning'] if any(q.body['category']==c for q in questions)]
            questions=first+[q for q in questions if q not in first]
        chosen=questions[:10];orders={}
        for q in chosen:
            ids=[o['id'] for o in q.body.get('options_json',[])]
            if q.body.get('shuffle_options'):random.SystemRandom().shuffle(ids)
            orders[q.id]=ids
        row=PracticeAttempt(user_id=u.id,body={'track':body.track,'difficulty':body.difficulty,'chapter_focus':body.chapter_focus,'mode':'practice','status':'in_progress','started_at':time.time(),'completed_at':None,'question_started_at':time.time(),'question_ids':[q.id for q in chosen],'option_orders':orders,'answers':[],'overall_score':None,'scores':{},'events':[]})
        db.add(row);db.commit();return view(db,row)

@router.get('/interview-sessions')
def sessions(status:str='',track:str='',date:str=''):
    u=require_user('candidate')
    from datetime import datetime,timezone
    with DB() as db:
        rows=[{'id':r.id,**r.body} for r in db.scalars(select(PracticeAttempt).where(PracticeAttempt.user_id==u.id))]
        return {'items':sorted([r for r in rows if (not status or r['status']==status) and (not track or r['track']==track) and (not date or datetime.fromtimestamp(r['started_at'],timezone.utc).strftime('%Y-%m-%d')==date)],key=lambda r:r['started_at'],reverse=True)}

@router.get('/overview')
def overview():
    u=require_user('candidate')
    from .portal import dashboard
    with DB() as db:
        rows=[{'id':r.id,**r.body} for r in db.scalars(select(PracticeAttempt).where(PracticeAttempt.user_id==u.id))]
    completed=sorted([r for r in rows if r['status']=='completed'],key=lambda r:r['completed_at'])
    scores=[r['overall_score'] for r in completed if r['overall_score'] is not None]
    return {'completed':len(completed),'average':round(sum(scores)/len(scores),1) if scores else None,'trend':completed[-10:],'latest':completed[-1] if completed else None,'active':[r for r in rows if r['status']=='in_progress'],'assignments':dashboard()['assignments'],'legacy_history':dashboard()['practice_history']}

@router.get('/interview-sessions/{sid}')
def session(sid:str):
    u=require_user('candidate')
    with DB() as db:return view(db,own(db,sid,u))

class AnswerInput(BaseModel):
    question_id:str
    text:str=Field(default='',max_length=12000)
    answer_format:Literal['mcq','code','pseudocode']='mcq'
    selected_option_ids:list[str]=Field(default_factory=list,max_length=10)
    answer_changes_count:int=Field(default=0,ge=0,le=1000)
    first_selection_time_seconds:float|None=Field(default=None,ge=0,le=86400)
    language:str=Field(default='',max_length=30)
    timed_out:bool=False

@router.post('/interview-sessions/{sid}/run')
async def run_samples(sid:str,body:AnswerInput):
    u=require_user('candidate')
    with DB() as db:
        row=own(db,sid,u);b=row.body;index=len(b['answers'])
        if b['status']!='in_progress' or index>=len(b['question_ids']) or b['question_ids'][index]!=body.question_id:
            raise HTTPException(409,'Run the current question only.')
        rubric=db.get(PracticeQuestion,body.question_id).body
    if not rubric.get('sample_tests'):raise HTTPException(422,'This question has no executable tests. Start a new Technical session.')
    if not body.text.strip():raise HTTPException(422,'Write your solution first.')
    try:return await grade(rubric,body.language,body.text)
    except RuntimeUnavailable as exc:raise HTTPException(503,str(exc))
    except ValueError as exc:raise HTTPException(422,str(exc))

@router.post('/interview-sessions/{sid}/answer')
async def answer(sid:str,body:AnswerInput):
    u=require_user('candidate')
    with DB() as db:
        row=own(db,sid,u);b=row.body;revision=row.revision
        previous=next((a for a in b['answers'] if a['question_id']==body.question_id),None)
        if previous:return previous
        if b['status']!='in_progress':raise HTTPException(409,'This session has ended.')
        index=len(b['answers'])
        if index>=len(b['question_ids']) or b['question_ids'][index]!=body.question_id:raise HTTPException(409,'Submit the current question first.')
        q=db.get(PracticeQuestion,body.question_id);rubric=q.body
    qtype=rubric.get('question_type','coding')
    is_mcq=qtype in {'mcq','mcq_single','mcq_multi','code_output','spot_bug','true_false'}
    if is_mcq:
        valid={o['id'] for o in rubric.get('options_json',[])};selected=list(dict.fromkeys(body.selected_option_ids))
        if not selected and body.text.strip():selected=[o['id'] for o in rubric.get('options_json',[]) if o['text'].strip().casefold()==body.text.strip().casefold()]
        if (not selected and not body.timed_out) or any(i not in valid for i in selected):raise HTTPException(422,'Choose a valid option before submitting.')
        if qtype!='mcq_multi' and len(selected)!=1 and not body.timed_out:raise HTTPException(422,'Choose one option for this question.')
        correct=set(rubric.get('correct_option_ids',[]));picked=set(selected)
        if qtype=='mcq_multi':raw=max(0,(len(picked&correct)-len(picked-correct))/max(1,len(correct)));score=round(raw*100)
        else:score=100 if picked==correct else (-25 if rubric.get('negative_marking') else 0)
        reason_score=None
        if qtype=='true_false' and body.text.strip():
            reason=await evaluate(rubric,body.text)
            if reason.get('status')=='scored':reason_score=reason['technical'];score=round(max(0,score)*.7+reason_score*.3)
        explanations=rubric.get('option_explanations_json',{})
        chosen_text=', '.join(next(o['text'] for o in rubric['options_json'] if o['id']==i) for i in selected) or 'No answer (time expired)'
        correct_text=', '.join(o['text'] for o in rubric['options_json'] if o['id'] in correct)
        detail=' '.join(explanations.get(i,'') for i in selected)
        analysis=f"Selected: {chosen_text}. Correct answer: {correct_text}. {detail} Concept to revise: {'; '.join(rubric['expected_points'])}"
        result={'status':'scored','source':'mcq_key','technical':max(0,score),'communication':None}
    else:
        if qtype=='code' and body.answer_format!='code':raise HTTPException(422,'Write code for this question.')
        if body.answer_format not in {'code','pseudocode'} or (not body.text.strip() and not body.timed_out):raise HTTPException(422,'Enter a code or pseudocode answer.')
        if body.answer_format=='pseudocode' and not rubric.get('accepts_pseudocode'):raise HTTPException(422,'This question requires code.')
        if body.answer_format=='code' and rubric.get('sample_tests') and body.text.strip():
            try:execution=await grade(rubric,body.language,body.text,include_hidden=True)
            except RuntimeUnavailable as exc:raise HTTPException(503,str(exc))
            except ValueError as exc:raise HTTPException(422,str(exc))
            result={'status':'scored','source':'sandbox_tests','technical':execution['score'],'communication':None,'execution':execution,
                    'strengths':[f"Passed {execution['passed']} of {execution['total']} tests."],
                    'missing_concepts':[] if execution['passed']==execution['total'] else ['Some tests failed. Review the input contract and edge cases.'],
                    'improvements':['Functional tests do not assess complexity or concurrency.']}
        else:
            result={'status':'scored','source':'timer','technical':0,'communication':None,'strengths':[],'missing_concepts':['No answer was submitted before the timer expired.'],'improvements':['Retry this question and outline the approach first.']} if body.timed_out and not body.text.strip() else await evaluate(rubric,body.text)
        if result.get('status')!='scored':raise HTTPException(503,'Evaluation is unavailable. Your draft is kept; retry submission.')
        review='Check logic gaps, missing edge cases, approach, and complexity.' if body.answer_format=='pseudocode' else 'Check correctness, edge cases, and complexity.'
        analysis=' '.join(['What worked: '+('; '.join(result.get('strengths',[])) or 'No specific strength identified.'),'Review: '+('; '.join(result.get('missing_concepts',[])) or review),'Next step: '+('; '.join(result.get('improvements',[])) or 'Add a concrete example.')])
    answer_text=body.text if not is_mcq else ', '.join(body.selected_option_ids)+((' — '+body.text.strip()) if body.text.strip() else '')
    entry={'question_id':body.question_id,'question':rubric['question'],'question_type':qtype,'chapter':rubric.get('chapter'),'category':rubric['category'],'answer':answer_text,'answer_format':'mcq' if is_mcq else body.answer_format,'selected_option_ids':body.selected_option_ids if is_mcq else [],'correct_option_ids':rubric.get('correct_option_ids',[]) if is_mcq else [],'option_explanations_json':rubric.get('option_explanations_json',{}) if is_mcq else {},'options_json':rubric.get('options_json',[]) if is_mcq else [],'answer_changes_count':body.answer_changes_count,'first_selection_time_seconds':body.first_selection_time_seconds,'language':body.language if body.answer_format=='code' else '','correctness_score':result['technical'],'communication':result.get('communication'),'answer_analysis_text':analysis,'source':result.get('source','ai'),'time_taken_seconds':round(time.time()-b['question_started_at']),'rubric':rubric['expected_points']}
    entry['execution']=result.get('execution')
    with DB() as db:
        event={'timestamp':time.time(),'event_type':'answer_submitted','words':len(body.text.split()),'elapsed_seconds':entry['time_taken_seconds'],'answer_changes_count':body.answer_changes_count,'first_selection_time_seconds':body.first_selection_time_seconds,'confidence_dip':body.answer_changes_count>=2}
        changed=db.execute(update(PracticeAttempt).where(PracticeAttempt.id==sid,PracticeAttempt.user_id==u.id,PracticeAttempt.revision==revision).values(body=b|{'answers':b['answers']+[entry],'question_started_at':time.time(),'events':b.get('events',[])+[event]},revision=revision+1))
        if not changed.rowcount:raise HTTPException(409,'The session changed in another tab. Refresh to continue.')
        db.commit()
    return entry

@router.post('/interview-sessions/{sid}/complete')
def complete(sid:str):
    u=require_user('candidate')
    with DB() as db:
        row=own(db,sid,u);b=row.body
        if b['status']=='completed':return view(db,row)
        if len(b['answers'])!=len(b['question_ids']):raise HTTPException(409,'Answer every question before completing.')
        scores={}
        for category in ['technical','aptitude','reasoning']:
            values=[a['correctness_score'] for a in b['answers'] if a['category']==category]
            scores[category]=round(sum(values)/len(values),1) if values else None
        comm=[a['communication'] for a in b['answers'] if a.get('communication') is not None]
        scores['communication']=round(sum(comm)/len(comm),1) if comm else None
        total=round(sum(a['correctness_score'] for a in b['answers'])/len(b['answers']),1)
        row.body=b|{'status':'completed','completed_at':time.time(),'overall_score':total,'scores':scores,'feedback':'Review the question breakdown below. Revisit missed concepts, then practice a different track.'};row.revision+=1;db.commit();return view(db,row)

@router.get('/interview-sessions/{sid}/results')
def results(sid:str):
    u=require_user('candidate')
    with DB() as db:
        row=own(db,sid,u)
        if row.body['status']!='completed':raise HTTPException(409,'Complete this session to see the full report.')
        return view(db,row)

@router.websocket('/ws/interview-sessions/{sid}')
async def realtime(ws:WebSocket,sid:str):
    # WebSockets bypass HTTP middleware: validate origin, cookie, role, owner and CSRF here.
    origin=ws.headers.get('origin','')
    expected=('https' if ws.url.scheme=='wss' else 'http')+'://'+ws.headers.get('host','')
    if origin!=expected:await ws.close(code=1008);return
    with DB() as db:
        login=db.get(LoginSession,hashed(ws.cookies.get('interview_auth','')))
        u=db.get(User,login.user_id) if login and login.expires>time.time() else None
        row=db.get(PracticeAttempt,sid)
        if not u or u.role!='candidate' or blocked(u) or not row or row.user_id!=u.id:await ws.close(code=1008);return
        user_id=u.id;csrf=login.csrf;login_id=login.id
    await ws.accept()
    try:
        message=await asyncio.wait_for(ws.receive_json(),timeout=10)
        if not hmac.compare_digest(csrf,hashed(str(message.get('csrf','')))):await ws.close(code=1008);return
        await ws.send_json({'type':'connected'})
        last=0.0
        while True:
            raw=await ws.receive_text()
            if len(raw)>15000:await ws.close(code=1009);return
            if time.monotonic()-last<.5:continue
            last=time.monotonic()
            import json
            message=json.loads(raw)
            with DB() as db:
                login=db.get(LoginSession,login_id);u=db.get(User,user_id);row=db.get(PracticeAttempt,sid)
                if not login or login.expires<=time.time() or not u or blocked(u) or not row:await ws.close(code=1008);return
                if row.body['status']!='in_progress':await ws.send_json({'type':'completed'});return
                words=len(str(message.get('text','')).split());elapsed=round(time.time()-row.body['question_started_at'])
                await ws.send_json({'type':'progress','words':words,'elapsed':elapsed,'answered':len(row.body['answers']),'total':len(row.body['question_ids']),'message':'Your final answer is evaluated after submission.'})
    except (WebSocketDisconnect,asyncio.TimeoutError,ValueError):return
