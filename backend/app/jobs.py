import asyncio
import os
from pathlib import Path
import subprocess
import time
from sqlalchemy import select
from .db import DB, Job, Answer, Question, Session
from .ai import evaluate
from .config import settings

whisper = None


def transcribe(path):
    global whisper
    wav = path + '.wav'
    try:
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', path, '-t', '91', '-ar', '16000', '-ac', '1', wav],
                       check=True, capture_output=True, timeout=40)
        if whisper is None:
            from faster_whisper import WhisperModel
            whisper = WhisperModel('tiny.en', device='cpu', compute_type='int8', download_root=str(Path(settings.data_dir) / 'models'))
        segments, info = whisper.transcribe(wav, language='en', vad_filter=True, word_timestamps=True)
        segments = list(segments)
        words = [w for s in segments for w in (s.words or [])]
        pauses = [max(0, b.start-a.end) for a, b in zip(words, words[1:])]
        span = words[-1].end - words[0].start if words else 0
        return {'transcript': ' '.join(s.text.strip() for s in segments), 'metrics': {
            'pause_fraction': round(sum(pauses)/span, 3) if span else None,
            'long_pause_count': sum(p >= 2 for p in pauses),
            'transcript_coverage': round(sum(w.end-w.start for w in words)/info.duration, 3) if info.duration else None,
            'audio_duration': min(info.duration, 90)}}
    finally:
        Path(path).unlink(missing_ok=True)
        Path(wav).unlink(missing_ok=True)


async def work_once():
    with DB() as db:
        job = db.scalars(select(Job)).all()
        job = next((j for j in job if j.body.get('status') == 'queued'), None)
        if not job:
            return False
        answer = db.get(Answer, job.body['answer_id'])
        session = db.get(Session, job.session_id)
        if not answer or not session or session.expires <= time.time() or session.status in ['deleting', 'complete', 'terminated']:
            job.body = job.body | {'status': 'failed', 'reason': 'Session no longer active.'}
            db.commit()
            return True
        job.body = job.body | {'status': 'running'}
        db.commit()
        jid, aid, version, kind = job.id, answer.id, job.body['version'], job.body['kind']
        path = job.body.get('path')
        question = db.get(Question, answer.body['question_id'])
        from .assessment_history import evaluated_question
        qbody, transcript = evaluated_question(db,question), answer.body['transcript']
        if kind!='transcribe' and answer.body.get('followup'):
            transcript+='\nFollow-up response: '+answer.body['followup']['reply']
    try:
        from .round_questions import grade_mcq
        result = await asyncio.to_thread(transcribe, path) if kind == 'transcribe' else grade_mcq(qbody,transcript) if qbody.get('source')=='bank_mcq' else await evaluate(qbody, transcript)
        with DB() as db:
            job, answer = db.get(Job, jid), db.get(Answer, aid)
            if job and answer:
                session=db.get(Session,job.session_id)
                if session and session.status not in ['complete','terminated','deleting'] and session.expires>time.time() and answer.body['version'] == version:
                    answer.body = answer.body | (result if kind == 'transcribe' else {'evaluation': result})
                job.body = {k: v for k, v in job.body.items() if k != 'path'} | {'status': 'done'}
                db.commit()
    except Exception:
        with DB() as db:
            job = db.get(Job, jid)
            if job:
                job.body = {k: v for k, v in job.body.items() if k != 'path'} | {'status': 'failed', 'reason': 'Processing failed. Review or type your answer and retry.'}
                db.commit()
        if path:
            Path(path).unlink(missing_ok=True)
    return True


async def worker(stop):
    # Restarting an interrupted job must not silently score stale content.
    with DB() as db:
        for job in db.scalars(select(Job)).all():
            if job.body.get('status') == 'running':
                if job.body.get('path'):
                    Path(job.body['path']).unlink(missing_ok=True)
                job.body = {k: v for k, v in job.body.items() if k != 'path'} | {'status': 'failed', 'reason': 'Server restarted. Please retry.'}
        db.commit()
    while not stop.is_set():
        try:
            if not await work_once():
                await asyncio.sleep(.5)
        except Exception:
            await asyncio.sleep(1)
