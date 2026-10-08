"""Review signals only. These values never feed answer evaluation."""
import json
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict

EVENTS = {
    'tab_switch': ('TAB_SWITCH', 'medium', 3),
    'window_blur': ('WINDOW_BLUR', 'low', 1),
    'fullscreen_exit': ('FULLSCREEN_EXIT', 'medium', 4),
    'copy_attempt': ('COPY_ATTEMPT', 'low', 1),
    'paste_attempt': ('PASTE_ATTEMPT', 'low', 1),
    'cut_attempt': ('CUT_ATTEMPT', 'low', 1),
    'context_menu': ('CONTEXT_MENU', 'low', 1),
    'no_face': ('NO_FACE', 'medium', 3),
    'multiple_faces': ('MULTIPLE_FACES', 'high', 8),
    'camera_disconnected': ('CAMERA_DISCONNECTED', 'high', 5),
    'microphone_disconnected': ('MICROPHONE_DISCONNECTED', 'medium', 3),
    'background_noise': ('ELEVATED_AUDIO_LEVEL', 'low', 0),
    'gaze_sample': ('GAZE_SAMPLE', 'low', 0),
    'gaze_violation': ('GAZE_AWAY', 'medium', 0),
    'tracking_unavailable': ('TRACKING_UNAVAILABLE', 'low', 0),
    'page_hidden': ('TAB_SWITCH', 'medium', 3),
    'device': ('DEVICE_DETECTED', 'high', 8),
    'screen_returned': ('SCREEN_RETURNED', 'low', 0),
    'security_lock_started': ('SECURITY_LOCK_STARTED', 'medium', 0),
    'security_lock_ended': ('SECURITY_LOCK_ENDED', 'low', 0),
    'exam_started': ('EXAM_STARTED', 'low', 0),
    'exam_terminated': ('EXAM_TERMINATED', 'high', 0),
}

class ProctorConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    max_fullscreen_exits: int = Field(default=3, ge=1, le=100)
    max_tab_switches: int = Field(default=3, ge=1, le=100)
    device_confidence: float = Field(default=.35, ge=.1, le=.99)
    face_absence_ms: int = Field(default=3000, ge=1000, le=60000)
    multiple_faces_ms: int = Field(default=2000, ge=500, le=60000)
    max_faces: int = Field(default=1, ge=1, le=5)
    device_confirm_frames: int = Field(default=3, ge=2, le=10)
    device_max_gap_ms: int = Field(default=2000, ge=1000, le=10000)
    device_result_max_age_ms: int = Field(default=30000, ge=5000, le=60000)
    review_score: int = Field(default=20, ge=1, le=100)
    auto_terminate: bool = False
    gaze_window_seconds: int = Field(default=30, ge=10, le=120)
    gaze_away_seconds: int = Field(default=5, ge=3, le=60)
    gaze_review_count: int = Field(default=3, ge=1, le=100)
    screen_lock_seconds: int = Field(default=120, ge=0, le=1800)
    max_violations: int = Field(default=2, ge=2, le=100)
    max_device_violations: int = Field(default=2, ge=2, le=100)
    max_multiple_face_violations: int = Field(default=2, ge=2, le=100)
    max_clipboard_attempts: int = Field(default=3, ge=2, le=100)
    max_camera_interruptions: int = Field(default=3, ge=2, le=100)
    max_face_absence_violations: int = Field(default=3, ge=2, le=100)
    block_account: bool = False
    block_seconds: int | None = Field(default=None, ge=60, le=31536000)
    weights: dict[str, int] = Field(default_factory=lambda: {k:v[2] for k,v in EVENTS.items()})

def load_config(path):
    config = ProctorConfig.model_validate(json.loads(Path(path).read_text())) if Path(path).exists() else ProctorConfig()
    if any(k not in EVENTS or v < 0 or v > 100 for k,v in config.weights.items()):
        raise ValueError('Invalid proctor event weights')
    return config.model_dump()

def describe(body, created):
    event_type, severity, _ = EVENTS[body['type']]
    if body['type'] == 'device':
        event_type = {'mobile phone':'PHONE_DETECTED','tablet computer':'TABLET_DETECTED'}.get(body.get('label'), 'DEVICE_DETECTED')
    return body | {'violation_type':'device_detected' if body['type']=='device' else body['type'], 'event_type':event_type, 'severity':severity,
                   'confidence':body.get('score'), 'occurred_at':created + body['timestamp']}

def summarize(rows, config):
    counts = {}
    score = 0
    for row in rows:
        kind = row['type']
        counts[kind] = counts.get(kind, 0) + 1
        score += 0 if kind.startswith('gaze_') else config['weights'].get(kind, 0)
    score = min(100, score)
    exceeded = (counts.get('fullscreen_exit',0) >= config['max_fullscreen_exits'] or
                counts.get('tab_switch',0) + counts.get('page_hidden',0) >= config['max_tab_switches'] or
                score >= config['review_score'])
    gaze=[r for r in rows if r['type']=='gaze_sample' and r.get('gaze_direction') not in (None,'off_screen')]
    eye_contact=round(100*sum(r['gaze_direction']=='center' for r in gaze)/len(gaze),1) if gaze else None
    gaze_review=counts.get('gaze_violation',0)>=config.get('gaze_review_count',3)
    return {'activity_score':score, 'counts':counts, 'review_required':exceeded or gaze_review,
            'terminate':exceeded and config['auto_terminate'],
            'gaze':{'eye_contact_percent':eye_contact,'samples':len(gaze)},
            'meaning':'Observed activity for human review; not proof of cheating or a hiring recommendation.'}
