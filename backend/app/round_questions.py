"""Select reviewed bank content for template assessments; answers stay server-side."""
import random
from sqlalchemy import select
from .db import PracticeQuestion
from .question_bank import seed_bank

def select_questions(db, kind, level):
    if kind not in ('aptitude','technical'):return None
    seed_bank(db)
    difficulty={'junior':'easy','mid':'medium','senior':'hard'}.get(level,'easy')
    categories={'aptitude','reasoning'} if kind=='aptitude' else {'technical'}
    rows=[r.body for r in db.scalars(select(PracticeQuestion)) if r.body.get('category') in categories
          and (kind!='technical' or r.body.get('subcategory')=='DSA' or r.body.get('chapter'))]
    # Prefer the configured difficulty; fill from the bank if fewer than five exist.
    random.SystemRandom().shuffle(rows)
    rows.sort(key=lambda r:((not bool(r.get('options_json') and r.get('correct_option_ids'))) if kind=='aptitude' else False, r.get('difficulty')!=difficulty))
    chosen=[];seen=set()
    for r in rows:
        prompt=r['question']
        if prompt in seen:continue
        seen.add(prompt);chosen.append(r)
        if len(chosen)==5:break
    if len(chosen)<5:raise ValueError('The question bank needs at least five distinct questions.')
    result=[]
    for r in chosen:
        options=r.get('options_json') or []
        correct=r.get('correct_option_ids') or []
        mcq=bool(options and correct)
        prompt=r['question']
        if options:prompt+='\n\n'+'\n'.join(o['id'].upper()+'. '+o['text'] for o in options)
        if mcq:prompt+='\nEnter the correct option letter(s), separated by commas for multiple selections.'
        expected=[','.join(sorted(correct))] if mcq else r.get('expected_points',[])
        result.append({'question':prompt,'resume_basis':r.get('chapter') or r.get('subcategory',''),
            'category':'skill','source':'bank_mcq' if mcq else 'question_bank','expected_points':expected,
            'question_type':'verbal' if mcq else 'pseudocode','time_limit_seconds':r.get('time_limit_seconds',90)})
    return result

def grade_mcq(question, transcript):
    selected=','.join(sorted(set(transcript.strip().lower().replace(' ','').split(','))))
    correct=selected==question['expected_points'][0]
    score=100 if correct else 0
    return {'status':'scored','source':'answer_key','technical':score,'communication':score,
        'correctness':4 if correct else 0,'reasoning':0,'coverage':4 if correct else 0,'structure':0,'relevance':4 if correct else 0,
        'evidence':[transcript[:200]],'strengths':['Correct selection.'] if correct else [],
        'missing_concepts':[] if correct else ['The selection did not match the answer key.'],
        'improvements':[] if correct else ['Review the topic and work through the alternatives.']}
