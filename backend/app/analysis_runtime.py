"""Bounded, cancellable CPU process; never import ML runtimes into the web process."""
import asyncio
import json
import os
from pathlib import Path
import sys
import threading
from .config import settings

slot=threading.Lock()

async def run_analysis(kind,**payload):
    if not slot.acquire(blocking=False):return {'status':'unavailable','reason':'Analysis is busy. Try again shortly.'}
    process=None
    try:
        env=os.environ.copy()
        # The child needs runtime paths, not application credentials.
        for key in list(env):
            if any(word in key.upper() for word in ['KEY','PASSWORD','SECRET','DATABASE_URL','TOKEN']):env.pop(key,None)
        env['DEEPFACE_HOME']=str(Path(settings.analysis_model_dir).resolve())
        env['HF_HUB_OFFLINE']='1'
        env['TRANSFORMERS_OFFLINE']='1'
        request={'kind':kind,**payload,'model_path':str(Path(settings.analysis_model_dir).resolve()/'sentence')}
        process=await asyncio.create_subprocess_exec(settings.analysis_python or sys.executable,str(Path(__file__).with_name('analysis_worker.py')),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,env=env)
        stdout,_=await asyncio.wait_for(process.communicate(json.dumps(request).encode()),timeout=settings.analysis_timeout_seconds)
        if process.returncode or len(stdout)>64000:raise ValueError('Invalid analysis response')
        return json.loads(stdout)
    except asyncio.TimeoutError:return {'status':'unavailable','reason':'Analysis exceeded its time limit. Your interview is unaffected.'}
    except (OSError,ValueError):return {'status':'unavailable','reason':'Analysis runtime is unavailable. Check the optional setup.'}
    finally:
        if process and process.returncode is None:
            process.kill()
            await process.wait()
        slot.release()
