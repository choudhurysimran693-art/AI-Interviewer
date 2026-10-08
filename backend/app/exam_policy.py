import time
from sqlalchemy import select
from .db import Observation, Notification, User, Answer, Assignment
from .ai import aggregate

def notify(db,s,event,title,severity='medium',violation_type=None):
    hr=s.body.get('hr_id')
    if hr:
        key=f'{s.id}:{event}'
        if not db.get(Notification,key):
            db.add(Notification(id=key,hr_id=hr,session_id=s.id,body={'violation_type':violation_type,'title':title,'severity':severity,'timestamp':time.time(),'candidate':s.body['name'],'status':'unread','action_required':'Review the event timeline and candidate explanation.'}))

def system_event(db,s,kind,**metadata):
    db.add(Observation(session_id=s.id,body={'type':kind,'event_type':kind.upper(),'timestamp':time.time()-s.created,'occurred_at':time.time(),'duration':0,'stage':'security','severity':'high' if kind=='exam_terminated' else 'medium','metadata':metadata,'action_taken':kind,'limitation':'Configured policy action; not a finding of cheating.'}))

def restrict_organization(db,user,s,config):
    from .accounts import organization_scope
    org=organization_scope(db.get(User,s.body['hr_id']))
    restrictions=dict(user.body.get('organization_restrictions',{}))
    restrictions[org]={'until':time.time()+config['block_seconds'] if config.get('block_seconds') else None,'attempt':s.id}
    user.body=user.body|{'organization_restrictions':restrictions}

def release_lock(db,s):
    state=dict(s.body.get('security',{}))
    if state.get('lock_until') and state['lock_until']<=time.time():
        state['lock_until']=None;s.body=s.body|{'security':state};system_event(db,s,'security_lock_ended');db.commit()

def signal_warning(db,s,event_id,signal='device'):
    kind='device_detected' if signal=='device' else 'multiple_faces'
    title='Device' if signal=='device' else 'Multiple faces'
    threshold=2
    if s.mode!='hr' or not s.body.get('exam_id') or not s.body.get('exam_started_at'):return 'informational'
    state=dict(s.body.get('security',{}))
    ids=list(state.get(signal+'_warning_events',[]))
    if event_id in ids:return signal+'_warning_recorded'
    if s.status in ('complete','terminated'):return 'closed'
    count=min(threshold,len(ids)+1);ids.append(event_id)
    state.update({signal+'_warning_count':count,signal+'_warning_events':ids,'review_required':True})
    action=signal+'_warning'
    if count>=threshold:
        action='exam_terminated'
        state.update(attempt_used=True,terminated_reason=kind+'_repeat',terminated_at=time.time(),lock_until=None)
        s.status='terminated'
        for assignment in db.scalars(select(Assignment).where(Assignment.session_id==s.id)):
            assignment.body=assignment.body|{'status':'terminated','attempt_used':True,'terminated_reason':kind+'_repeat'}
        s.body=s.body|{'attempt_used':True,'terminated_reason':kind+'_repeat','ended_at':time.time()}
        config=s.body.get('proctor_config',{})
        if config.get('block_account') and s.body.get('user_id'):
            user=db.get(User,s.body['user_id'])
            restrict_organization(db,user,s,config)
            notify(db,s,'account_blocked','Candidate account restricted; administrator review required','high')
    s.body=s.body|{'security':state,signal+'_warning_count':count}
    system_event(db,s,action,violation_type=kind,strike=count,source_event=event_id)
    notify(db,s,signal+'-strike:'+str(count),f'{title} warning {count}/{threshold}'+(' — interview terminated' if count>=threshold else ' — candidate warned'),'high',violation_type=kind)
    return action


def device_warning(db,s,event_id):
    return signal_warning(db,s,event_id,'device')


def apply_policy(db,s,event_id,body,config,is_new):
    if body['type']=='device':return device_warning(db,s,event_id)
    if s.mode!='hr' or not s.body.get('exam_started_at'): return 'recorded'
    state=dict(s.body.get('security',{}));kind=body['type'];action='warning'
    if kind=='screen_returned':
        state['away']=False;s.body=s.body|{'security':state};return 'returned'
    if not is_new:return 'duration_updated'
    if kind=='multiple_faces':
        return signal_warning(db,s,event_id,'face')
    if kind in ['gaze_sample','gaze_violation']:
        if kind=='gaze_violation':
            state['gaze_violation_count']=state.get('gaze_violation_count',0)+1
            if state['gaze_violation_count']>=config.get('gaze_review_count',3):
                state['gaze_review_required']=True
                notify(db,s,'gaze_review','Repeated gaze-away estimates: supplementary review only','low')
            s.body=s.body|{'security':state}
        return 'supplementary_review'
    strike=False;threshold_reached=False
    state[kind+'_count']=state.get(kind+'_count',0)+1
    if kind in ['tab_switch','window_blur','fullscreen_exit']:
        if not state.get('away'):
            state['away']=True;state['screen_changes']=state.get('screen_changes',0)+1
            state['lock_until']=max(state.get('lock_until') or 0,time.time()+config['screen_lock_seconds'])
            system_event(db,s,'security_lock_started',until=state['lock_until']);strike=True;action='temporary_lock'
    elif kind in ['device','multiple_faces']:
        state[kind]=state.get(kind,0)+1;strike=True
    elif kind in ['copy_attempt','paste_attempt','cut_attempt','context_menu']:
        state['clipboard_attempts']=state.get('clipboard_attempts',0)+1
        threshold_reached=state['clipboard_attempts']>=config.get('max_clipboard_attempts',3)
    elif kind in ['camera_disconnected','microphone_disconnected']:
        state['media_interruptions']=state.get('media_interruptions',0)+1
        threshold_reached=state['media_interruptions']>=config.get('max_camera_interruptions',3)
    elif kind=='no_face':threshold_reached=state[kind+'_count']>=config.get('max_face_absence_violations',3)
    if kind=='tab_switch':threshold_reached=state[kind+'_count']>=config['max_tab_switches']
    if kind=='fullscreen_exit':threshold_reached=state[kind+'_count']>=config['max_fullscreen_exits']
    strike=strike or threshold_reached
    if strike:
        state['violations']=state.get('violations',0)+1
        notify(db,s,event_id,body.get('event_type',kind).replace('_',' '),'high' if kind in ['device','multiple_faces'] else 'medium')
        reached=(threshold_reached or state['violations']>=config['max_violations'] or state.get('device',0)>=config['max_device_violations'] or state.get('multiple_faces',0)>=config['max_multiple_face_violations'])
        if reached:
            state['review_required']=True
            if config['auto_terminate']:
                s.status='terminated';state['lock_until']=None;action='exam_terminated'
                s.body=s.body|{'ended_at':time.time(),'summary':aggregate([a.body['evaluation'] for a in db.scalars(select(Answer).where(Answer.session_id==s.id))])}
                system_event(db,s,'exam_terminated',reason='Configured repeated-violation threshold reached')
                if config['block_account'] and s.body.get('user_id'):
                    user=db.get(User,s.body['user_id'])
                    restrict_organization(db,user,s,config)
                    notify(db,s,'account_blocked','Candidate account restricted; administrator review required','high')
                notify(db,s,'terminated','Exam terminated; review required','high')
    s.body=s.body|{'security':state}
    return action

