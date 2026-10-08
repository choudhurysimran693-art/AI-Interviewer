"""Read-only compatibility for answers saved before assessment tools were retired.

No routes or new question selection live here. Retain historical review scores
and already-saved follow-up context so old reports and in-flight jobs stay valid.
"""
from .db import InterviewInteraction

def evaluated_question(db,q):
    item=db.get(InterviewInteraction,f'{q.id}:followup')
    return q.body if not item or not item.body.get('reply') else q.body|{'question':q.body['question']+'\nFollow-up: '+item.body['prompt']}

def effective_evaluation(a):
    original=a.body['evaluation'];reviews=a.body.get('human_reviews',[])
    if not reviews:return original
    latest=reviews[-1]
    return original|{'status':'scored','technical':latest['technical'],'communication':latest['communication'],'source':'human_review','review_reason':latest['reason']}
