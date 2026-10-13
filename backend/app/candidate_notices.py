"""Persistent candidate inbox. Notifications are saved in the scheduling transaction."""
import time
from .db import CandidateNotice, Organization, Recruiter, EmailDelivery, User


def add_notice(db, candidate_id, key, title, message, href, hr_id, **details):
    if db.get(CandidateNotice, key):
        return
    membership = db.get(Recruiter, hr_id)
    org = db.get(Organization, membership.organization_id) if membership else None
    db.add(CandidateNotice(id=key, candidate_id=candidate_id, body={
        'title': title, 'message': message, 'href': href,
        'company_name': org.name if org else '', 'created_at': time.time(),
        'read': False, **details,
    }))
    account=db.get(User,candidate_id)
    db.add(EmailDelivery(id=key,body={'recipient':account.email,'name':account.name,
        'title':title,'message':message,'href':href,'company':org.name if org else '', 'hr_id':hr_id,**details}))


def interview_notice(db, assignment, exam):
    add_notice(db, assignment.candidate_id, 'interview:'+assignment.id,
               'Your interview is scheduled', exam.body['title'],
               '/candidate/interview?assignment='+assignment.id, exam.hr_id,
               scheduled_at=exam.body.get('window_start_at', exam.body.get('opens_at')))
