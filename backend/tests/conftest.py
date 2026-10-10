import os
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DATA_DIR'] = tempfile.mkdtemp(prefix='interview-tests-')
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(os.environ['DATA_DIR']) / 'test.db')
os.environ['APP_SECRET'] = 'test-secret-not-for-production-123456789'
os.environ['GEMINI_API_KEY'] = ''
os.environ['SMTP_HOST'] = ''
os.environ['SMTP_FROM'] = ''
os.environ['ENVIRONMENT'] = 'development'
os.environ['ENABLE_DEMO_DATA'] = 'true' # Legacy demo tests opt in explicitly.
import pytest
from fastapi.testclient import TestClient
from app.main import app, rate_windows
from app.db import Base, engine

@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    rate_windows.clear()
    # No lifespan worker: jobs are advanced explicitly for deterministic tests.
    client=TestClient(app)
    r=client.post('/api/auth/register',json={'email':'candidate@example.test','name':'Alex Example','password':'Test-passphrase-123'})
    assert r.status_code==200,r.text
    client.headers['X-CSRF-Token']=client.cookies['interview_csrf']
    return client
