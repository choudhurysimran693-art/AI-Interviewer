import csv
import io
from datetime import datetime,timezone
from pypdf import PdfReader
from test_accounts import staff
from app.db import DB,Session

def seed(hr,pid,score,when,status='complete',name='Candidate'):
    with DB() as db:
        db.add(Session(token_hash=pid+str(score)+when+status,mode='hr',status=status,expires=9999999999,body={'name':name,'position_id':pid,'ended_at':datetime.fromisoformat(when).replace(tzinfo=timezone.utc).timestamp(),'summary':{'technical':score,'communication':score,'overall':score}}));db.commit()

def setup(client):
    hr=staff();other=staff(email='analytics-other@example.test')
    p=[hr.post('/api/positions',json={'title':t}).json()['id'] for t in ['Alpha','Beta','Empty']]
    foreign=other.post('/api/positions',json={'title':'Secret role'}).json()['id']
    for score,when in [(0,'2026-01-01'),(20,'2026-01-31T23:59:59'),(40,'2026-02-01'),(60,'2026-02-10'),(80,'2026-03-01'),(100,'2026-03-02')]:seed(hr,p[0],score,when,name='=SUM(A1)')
    seed(hr,p[1],90,'2026-02-02');seed(other,foreign,99,'2026-02-02')
    seed(hr,p[0],88,'2026-02-03','terminated');seed(hr,p[0],77,'2026-02-03','active');seed(hr,p[0],None,'2026-02-04')
    return hr,other,p,foreign

def test_analytics_bands_averages_dates_and_empty(client):
    hr,other,p,foreign=setup(client)
    dist=hr.get('/api/analytics/score-distribution').json();assert [r['count'] for r in dist]==[1,1,1,1,3]
    avg=hr.get('/api/analytics/by-position').json();assert [r['position_title'] for r in avg]==['Alpha','Beta'];assert [r['average_score'] for r in avg]==[50,90]
    q='?position_id='+p[0]+'&date_from=2026-01-01&date_to=2026-01-31'
    assert sum(r['count'] for r in hr.get('/api/analytics/score-distribution'+q).json())==2
    assert hr.get('/api/analytics/trends'+q).json()==[{'month':'2026-01','average_score':10}]
    assert len(hr.get('/api/analytics/technical-communication'+q).json())==2
    assert hr.get('/api/analytics/trends?date_from=2026-01-01&date_to=2026-03-31').json()==[{'month':'2026-01','average_score':10},{'month':'2026-02','average_score':63.33},{'month':'2026-03','average_score':90}]
    assert hr.get('/api/analytics/technical-communication?position_id='+p[0]+'&date_from=2027-01-01').json()==[]
    assert hr.get('/api/analytics/by-position?position_id='+p[0]).json()==avg
    assert sum(r['count'] for r in hr.get('/api/analytics/score-distribution?position_id='+p[2]).json())==0
    assert hr.get('/api/analytics/trends?date_from=2027-01-01&date_to=2026-01-01').status_code==422
    for endpoint in ['score-distribution','by-position','trends','technical-communication','export/csv','export/pdf']:
        assert hr.get('/api/analytics/'+endpoint+'?position_id='+foreign).status_code==404
        assert client.get('/api/analytics/'+endpoint).status_code==403

def test_exports_same_filtered_data(client):
    hr,other,p,foreign=setup(client)
    q='?position_id='+p[0]+'&date_from=2026-01-01&date_to=2026-01-31'
    response=hr.get('/api/analytics/export/csv'+q);assert response.status_code==200
    rows=list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))));assert len(rows)==2
    assert rows[0]['candidate_name'].startswith("'=");assert all(r['position']=='Alpha' for r in rows)
    response=hr.get('/api/analytics/export/pdf'+q);assert response.status_code==200,response.text
    text=' '.join(p.extract_text() for p in PdfReader(io.BytesIO(response.content)).pages)
    assert '2026-01-01' in text and '2026-01-31' in text and 'Score distribution' in text
    assert 'Secret role' not in text and 'Monthly score trends' in text
    path=__import__('pathlib').Path('tmp/pdfs');path.mkdir(parents=True,exist_ok=True);(path/'analytics-preview.pdf').write_bytes(response.content)
