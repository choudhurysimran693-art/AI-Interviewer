"""Versioned standard hiring template and safe, additive schema upgrade."""
from sqlalchemy import inspect, text, select
from .db import RoundTemplate, RoundTemplateItem

TEMPLATE_ID = 'standard-technical-v1'
STANDARD = [
    ('resume_screening', 'Resume Screening', 'auto_evaluated', 'Compare the submitted resume with role criteria. HR decides shortlist or reject.'),
    ('aptitude', 'Aptitude / Reasoning Test', 'ai_scored', 'Complete the quantitative and reasoning questions.'),
    ('technical', 'Technical Assessment', 'ai_scored', 'Complete the DSA questions and explain your reasoning.'),
    ('technical_deep', 'Technical / System Design Interview', 'ai_conducted', 'Discuss project decisions, architecture, trade-offs, and testing.'),
    ('hr', 'HR Round', 'ai_conducted', 'Discuss job-related collaboration, work scenarios, and logistics.'),
    ('final_interview', 'Final Interview', 'human_only', 'Details will be shared separately. HR records the outcome after the live call.'),
]

def migrate(engine):
    for table, column in [('interview_rounds', 'settings'), ('application_rounds', 'scheduling')]:
        if column not in {c['name'] for c in inspect(engine).get_columns(table)}:
            with engine.begin() as c:
                c.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} JSON NOT NULL DEFAULT '{{}}'"))
    # Browser access goes through our authenticated API, never Supabase's public Data API.
    if engine.dialect.name == 'postgresql':
        with engine.begin() as c:
            for table in ['round_templates', 'round_template_items']:
                c.execute(text(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'))

def seed(db):
    if db.get(RoundTemplate, TEMPLATE_ID):
        return
    db.add(RoundTemplate(id=TEMPLATE_ID, name='Standard Technical Hiring', description='Six editable stages from resume review to a human-only final interview.', is_default=True))
    db.flush()
    for order, (kind, name, mode, instructions) in enumerate(STANDARD, 1):
        db.add(RoundTemplateItem(id=f'{TEMPLATE_ID}-{order}', template_id=TEMPLATE_ID, round_order=order,
            round_type=kind, round_name=name, evaluation_mode=mode, default_instructions=instructions))
    db.flush()

def items(db, tid):
    return list(db.scalars(select(RoundTemplateItem).where(RoundTemplateItem.template_id==tid).order_by(RoundTemplateItem.round_order)))
