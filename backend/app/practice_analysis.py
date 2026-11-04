"""Candidate-only, opt-in practice tools. No storage of uploads or analysis results."""
import asyncio
import io
import tempfile
import threading
from pathlib import Path
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Response
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from .accounts import require_user
from .config import settings
from .analysis_runtime import run_analysis

router=APIRouter(prefix='/api/candidate/analysis')
media_slot=threading.Lock()

@router.get('/capabilities')
def capabilities():
    require_user('candidate')
    return {'semantic':settings.enable_semantic_analysis,'voice':settings.enable_voice_analysis,'expression':settings.enable_expression_analysis}

class Comparison(BaseModel):
    consent:bool=False
    answer:str=Field(min_length=1,max_length=15000)
    points:list[str]=Field(min_length=1,max_length=8)

@router.post('/semantic')
async def compare(body:Comparison,response:Response):
    require_user('candidate');response.headers['Cache-Control']='no-store'
    if not settings.enable_semantic_analysis:raise HTTPException(409,'Semantic analysis is not enabled.')
    if not body.consent:raise HTTPException(422,'Consent is required.')
    if not body.answer.strip() or any(not p.strip() or len(p)>1200 for p in body.points):raise HTTPException(422,'Provide an answer and reference points of up to 1200 characters each.')
    return await run_analysis('semantic',answer=body.answer,points=body.points)

@router.post('/{kind}')
async def analyze_media(kind:str,response:Response,consent:bool=Form(False),file:UploadFile=File(...)):
    require_user('candidate');response.headers['Cache-Control']='no-store'
    enabled={'voice':settings.enable_voice_analysis,'expression':settings.enable_expression_analysis}
    if kind not in enabled:raise HTTPException(404,'Analysis not found.')
    if not enabled[kind]:raise HTTPException(409,'This optional analysis is not enabled.')
    if not consent:raise HTTPException(422,'Consent is required before uploading media.')
    if not media_slot.acquire(blocking=False):raise HTTPException(429,'Media analysis is busy. Try again shortly.')
    try:
        raw=await file.read(5*1024*1024+1)
        if len(raw)>5*1024*1024:raise HTTPException(413,'Upload must be 5 MB or smaller.')
        with tempfile.TemporaryDirectory(prefix='interview-analysis-') as directory:
            if kind=='expression':
                try:
                    with Image.open(io.BytesIO(raw)) as image:
                        if image.width*image.height>12000000:raise ValueError()
                        image=image.convert('RGB');image.thumbnail((640,480));path=Path(directory)/'frame.jpg';image.save(path,format='JPEG')
                except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError):raise HTTPException(422,'Use a valid JPEG or PNG photo up to 12 megapixels.')
            else:
                # Decode arbitrary upload containers to a bounded mono WAV before Librosa.
                original=Path(directory)/'recording';original.write_bytes(raw);path=Path(directory)/'audio.wav';process=None
                try:
                    process=await asyncio.create_subprocess_exec('ffmpeg','-nostdin','-v','error','-protocol_whitelist','file,pipe','-i',str(original),'-t','30','-vn','-ar','16000','-ac','1',str(path),stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
                    await asyncio.wait_for(process.wait(),15)
                    if process.returncode:raise HTTPException(422,'The audio file could not be decoded.')
                except FileNotFoundError:raise HTTPException(503,'Audio analysis requires FFmpeg on the server.')
                except asyncio.TimeoutError:raise HTTPException(422,'Audio decoding exceeded its time limit.')
                finally:
                    if process and process.returncode is None:process.kill();await process.wait()
            return await run_analysis(kind,path=str(path))
    finally:
        await file.close()
        media_slot.release()


class AnswerConsent(BaseModel):
    consent:bool=False

@router.post('/answers/{aid}/similarity')
async def answer_similarity(aid:str,body:AnswerConsent,response:Response):
    import time
    from .db import DB,Answer,Question,Session
    user=require_user('candidate');response.headers['Cache-Control']='no-store'
    if not settings.enable_semantic_analysis:raise HTTPException(409,'Semantic analysis is not enabled.')
    if not body.consent:raise HTTPException(422,'Consent is required.')
    with DB() as db:
        answer=db.get(Answer,aid);session=db.get(Session,answer.session_id) if answer else None
        if not session or session.body.get('user_id')!=user.id or session.expires<=time.time() or session.status=='deleting':raise HTTPException(404,'Answer not found.')
        if not answer.body.get('approved'):raise HTTPException(409,'Approve your answer first.')
        question=db.get(Question,answer.body['question_id'])
        if not question:raise HTTPException(404,'Question not found.')
        if question.body.get('options') or answer.body.get('input')=='mcq':raise HTTPException(409,'MCQ answers use their answer key.')
        transcript=answer.body['transcript'];points=question.body.get('expected_points',[])[:8]
        if len(transcript)>15000 or any(not isinstance(p,str) or len(p)>1200 for p in points):raise HTTPException(422,'This answer or rubric exceeds the optional comparison limit.')
    return await run_analysis('semantic',answer=transcript,points=points)
