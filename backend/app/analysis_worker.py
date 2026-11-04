"""Single bounded analysis subprocess. Only JSON is returned to the parent."""
import contextlib
import json
import os
import sys
from pathlib import Path

os.environ['CUDA_VISIBLE_DEVICES']='-1'
os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
os.environ['TF_USE_LEGACY_KERAS']='1'
os.environ['USE_TF']='0'
os.environ['USE_FLAX']='0'
for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','TF_NUM_INTRAOP_THREADS','TF_NUM_INTEROP_THREADS']:os.environ[key]='1'
sys.path.insert(0,str(Path(__file__).resolve().parent))
from analysis_models import semantic,voice,expression


def main():
    request=json.loads(sys.stdin.read(200000))
    try:
        with contextlib.redirect_stdout(sys.stderr):
            kind=request['kind']
            if kind=='semantic':result=semantic(request['answer'],request['points'],request['model_path'])
            elif kind=='voice':result=voice(request['path'])
            elif kind=='expression':result=expression(request['path'])
            else:raise ValueError('Unknown analysis')
    except ImportError:result={'status':'unavailable','reason':'Optional analysis dependencies are not installed.'}
    except Exception:result={'status':'unavailable','reason':'Analysis could not be completed. Check the model setup and input, then retry.'}
    print(json.dumps(result,allow_nan=False))

if __name__=='__main__':main()
