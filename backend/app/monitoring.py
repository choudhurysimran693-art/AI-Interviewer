import json
from pathlib import Path
from .config import settings

MODEL = 'grounding-dino-tiny-q8'
MODEL_REVISION = 'ff690b0a8050566c290287545bd059350f3e9096'


def validation_status():
    if settings.environment != 'production':
        return {'passed': True, 'reason': 'Local development mode. Production still requires detector validation results before release.',
                'model_revision': 'main', 'development_bypass': True}
    try:
        data = json.loads(Path(settings.detector_validation_file).read_text())
        runs = data['runs']
        passed = (data['model'] == MODEL and data['threshold'] == 0.35 and bool(data['hardware'])
                  and data['model_revision'] == MODEL_REVISION and len(runs) >= 60
                  and len({r['clip_id'] for r in runs}) == len(runs))
        for category in ['mobile phone', 'tablet computer']:
            subset = [r for r in runs if r['expected'] == category]
            passed = passed and len(subset) >= 20 and sum(bool(r['detected']) for r in subset) / len(subset) >= .9
        negatives = [r for r in runs if r['expected'] == 'none']
        latencies = sorted(float(n) for r in runs for n in r['latencies_ms'])
        passed = passed and len(negatives) >= 20 and sum(bool(r['detected']) for r in negatives) <= 1
        p95 = latencies[min(len(latencies)-1, int(len(latencies)*.95))]
        passed = passed and p95 < 1000
        return {'passed': bool(passed), 'reason': 'Validated on recorded test hardware.' if passed else 'Device validation criteria have not passed.',
                'hardware': data['hardware'], 'p95_ms': p95, 'model_revision': data['model_revision']}
    except Exception:
        return {'passed': False, 'reason': 'Awaiting 20 phone, 20 tablet, and 20 negative test clips plus latency validation.'}
