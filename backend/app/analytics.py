"""Completed-session analytics, scoped by the position's organization."""
import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from xml.sax.saxutils import escape
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, func, case
from .accounts import require_user, organization_scope
from .db import DB, Session, RecruitmentPosition as Position

router=APIRouter(prefix='/api/analytics')
BANDS=[f'{n}-{n+20}' for n in range(0,100,20)]

def filters(position_id:str|None=None,date_from:date|None=None,date_to:date|None=None):
    user=require_user('hr','admin')
    if date_from and date_to and date_from>date_to:raise HTTPException(422,'From date must be on or before To date.')
    return {'organization':organization_scope(user),'position_id':position_id or None,'date_from':date_from,'date_to':date_to}

def source(db,f,by_position=False,trends=False):
    if f['position_id']:
        p=db.get(Position,f['position_id'])
        if not p or p.organization_id!=f['organization']:raise HTTPException(404,'Position not found.')
    score=Session.body['summary']['overall'].as_float()
    completed=Session.body['ended_at'].as_float()
    q=select(Session.id.label('session_id'),Position.id.label('position_id'),Position.body['title'].as_string().label('position_title'),
        Session.body['name'].as_string().label('candidate_name'),completed.label('completed_at'),
        Session.body['summary']['technical'].as_float().label('technical_score'),
        Session.body['summary']['communication'].as_float().label('communication_score'),score.label('overall_score'))
    q=q.join(Position,Session.body['position_id'].as_string()==Position.id).where(
        Position.organization_id==f['organization'],Session.status=='complete',completed.is_not(None),score.between(0,100))
    if f['position_id'] and not by_position:q=q.where(Position.id==f['position_id'])
    lower=f['date_from'];upper=f['date_to']
    if trends and not lower and not upper:
        today=datetime.now(timezone.utc).date();index=today.year*12+today.month-1-11
        lower=date(index//12,index%12+1,1);upper=today
    if lower:q=q.where(completed>=datetime.combine(lower,time.min,tzinfo=timezone.utc).timestamp())
    if upper:q=q.where(completed<datetime.combine(upper+timedelta(days=1),time.min,tzinfo=timezone.utc).timestamp())
    return q.subquery()

def distribution(db,f):
    s=source(db,f);band=case(*[(s.c.overall_score<n+20,BANDS[n//20]) for n in range(0,80,20)],else_=BANDS[-1])
    counts=dict(db.execute(select(band,func.count()).group_by(band)).all())
    return [{'band':b,'count':counts.get(b,0)} for b in BANDS]

def by_position(db,f):
    s=source(db,f,by_position=True)
    return [{'position_id':pid,'position_title':title,'average_score':round(avg,2)} for pid,title,avg in db.execute(select(s.c.position_id,s.c.position_title,func.avg(s.c.overall_score)).group_by(s.c.position_id,s.c.position_title).order_by(s.c.position_title,s.c.position_id))]

def trends(db,f):
    s=source(db,f,trends=True)
    month=func.to_char(func.timezone('UTC',func.to_timestamp(s.c.completed_at)),'YYYY-MM') if db.bind.dialect.name=='postgresql' else func.strftime('%Y-%m',s.c.completed_at,'unixepoch')
    return [{'month':m,'average_score':round(avg,2)} for m,avg in db.execute(select(month,func.avg(s.c.overall_score)).group_by(month).order_by(month))]

def scatter(db,f):
    s=source(db,f)
    return [{'technical_score':t,'communication_score':c} for t,c in db.execute(select(s.c.technical_score,s.c.communication_score).where(s.c.technical_score.between(0,100),s.c.communication_score.between(0,100)).order_by(s.c.completed_at.desc(),s.c.session_id).limit(3000))]

@router.get('/score-distribution')
def score_distribution(f=Depends(filters)):
    with DB() as db:return distribution(db,f)

@router.get('/by-position')
def position_averages(f=Depends(filters)):
    with DB() as db:return by_position(db,f)

@router.get('/trends')
def monthly_trends(f=Depends(filters)):
    with DB() as db:return trends(db,f)

@router.get('/technical-communication')
def technical_communication(f=Depends(filters)):
    with DB() as db:return scatter(db,f)

@router.get('/export/csv')
def export_csv(f=Depends(filters)):
    out=io.StringIO(newline='');writer=csv.writer(out)
    writer.writerow(['candidate_name','position','completed_at_utc','technical_score','communication_score','overall_score'])
    with DB() as db:
        s=source(db,f)
        for row in db.execute(select(s).order_by(s.c.completed_at,s.c.session_id)).mappings():
            values=[row['candidate_name'] or '',row['position_title'],datetime.fromtimestamp(row['completed_at'],timezone.utc).isoformat(),row['technical_score'],row['communication_score'],row['overall_score']]
            writer.writerow(["'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v for v in values])
    return Response(out.getvalue().encode('utf-8-sig'),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="interview-analytics.csv"','Cache-Control':'no-store'})

def pdf_report(f,role,dist,positions,months,points):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    out=io.BytesIO();styles=getSampleStyleSheet();story=[]
    def para(text,style='Normal'):story.append(Paragraph(escape(str(text)),styles[style]));story.append(Spacer(1,10))
    def table(headers,rows,widths):
        if not rows:para('No data for the selected filters.');return
        cells=[[Paragraph(escape(str(c)),styles['Normal']) for c in r] for r in [headers]+rows]
        t=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eaf0e7')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#d9e1d5'))]));story.append(t);story.append(Spacer(1,16))
    para('Recruitment analytics','Title');para('Completed interviews | '+datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC'))
    para('Role: '+role);para('Completion dates (UTC): '+str(f['date_from'] or 'Any')+' to '+str(f['date_to'] or 'Any'))
    para('Position averages compare all roles in your organization. Monthly trends default to the current and previous 11 months when dates are blank. Scatter includes up to 3,000 latest points.')
    para('Score distribution','Heading2');table(['Overall score band','Sessions'],[[r['band'],r['count']] for r in dist] if sum(r['count'] for r in dist) else [],[330,170])
    para('Average score by position','Heading2');table(['Position','Average / 100'],[[r['position_title'],r['average_score']] for r in positions],[330,170])
    para('Monthly score trends','Heading2');table(['Month (UTC)','Average / 100'],[[r['month'],r['average_score']] for r in months],[330,170])
    story.append(PageBreak())
    para('Technical / communication scores','Heading2')
    if points:
        from reportlab.graphics.shapes import Drawing, Line, String, Circle
        d=Drawing(500,260);d.add(Line(45,35,475,35));d.add(Line(45,35,45,235))
        for tick in range(0,101,20):
            d.add(String(45+4.3*tick,20,str(tick),fontSize=8,textAnchor='middle'));d.add(String(35,35+2*tick,str(tick),fontSize=8,textAnchor='end'))
        d.add(String(255,2,'Technical score (0-100)',fontSize=10,textAnchor='middle'));d.add(String(45,248,'Communication score (0-100)',fontSize=10))
        for p in points:d.add(Circle(45+4.3*p['technical_score'],35+2*p['communication_score'],2,fillColor=colors.HexColor('#527b66'),strokeColor=None))
        story.append(d)
    else:para('No data for the selected filters.')
    def footer(canvas,doc):canvas.setFont('Helvetica',8);canvas.drawString(45,24,'Private HR report | Page '+str(doc.page))
    SimpleDocTemplate(out,pagesize=A4,leftMargin=45,rightMargin=45,topMargin=40,bottomMargin=40).build(story,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()

@router.get('/export/pdf')
def export_pdf(f=Depends(filters)):
    with DB() as db:
        dist=distribution(db,f);positions=by_position(db,f);months=trends(db,f);points=scatter(db,f)
        role=db.get(Position,f['position_id']).body['title'] if f['position_id'] else 'All recruitment roles'
        content=pdf_report(f,role,dist,positions,months,points)
    return Response(content,media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="interview-analytics.pdf"','Cache-Control':'no-store'})
