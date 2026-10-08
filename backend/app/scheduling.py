import math
import time
from fastapi import HTTPException

def validate_start(value:float):
    # datetime-local inputs omit seconds; allow the current minute and a short
    # submission delay, without accepting interviews scheduled in the past.
    if not math.isfinite(value) or value < time.time()-120:
        raise HTTPException(422,'Choose the current time or a future interview time.')
    return value
