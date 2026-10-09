-- Additive upgrade for an existing deployed application. Back up the database first.
-- The backend applies the equivalent upgrade and idempotent template seed at startup.
BEGIN;
ALTER TABLE public.interview_rounds ADD COLUMN IF NOT EXISTS settings json NOT NULL DEFAULT '{}';
ALTER TABLE public.application_rounds ADD COLUMN IF NOT EXISTS scheduling json NOT NULL DEFAULT '{}';
CREATE TABLE IF NOT EXISTS public.round_templates (
 id varchar PRIMARY KEY, name varchar NOT NULL, description varchar NOT NULL, is_default boolean NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS public.round_template_items (
 id varchar PRIMARY KEY, template_id varchar NOT NULL REFERENCES public.round_templates(id),
 round_order integer NOT NULL, round_type varchar NOT NULL, round_name varchar NOT NULL,
 evaluation_mode varchar NOT NULL, default_instructions varchar NOT NULL,
 UNIQUE(template_id, round_order)
);
ALTER TABLE public.round_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.round_template_items ENABLE ROW LEVEL SECURITY;
INSERT INTO public.round_templates VALUES ('standard-technical-v1','Standard Technical Hiring','Six editable stages from resume review to a human-only final interview.',true) ON CONFLICT DO NOTHING;
INSERT INTO public.round_template_items VALUES
 ('standard-technical-v1-1','standard-technical-v1',1,'resume_screening','Resume Screening','auto_evaluated','Compare the submitted resume with role criteria. HR decides shortlist or reject.'),
 ('standard-technical-v1-2','standard-technical-v1',2,'aptitude','Aptitude / Reasoning Test','ai_scored','Complete the quantitative and reasoning questions.'),
 ('standard-technical-v1-3','standard-technical-v1',3,'technical','Technical Assessment','ai_scored','Complete the DSA questions and explain your reasoning.'),
 ('standard-technical-v1-4','standard-technical-v1',4,'technical_deep','Technical / System Design Interview','ai_conducted','Discuss project decisions, architecture, trade-offs, and testing.'),
 ('standard-technical-v1-5','standard-technical-v1',5,'hr','HR Round','ai_conducted','Discuss job-related collaboration, work scenarios, and logistics.'),
 ('standard-technical-v1-6','standard-technical-v1',6,'final_interview','Final Interview','human_only','Details will be shared separately. HR records the outcome after the live call.')
ON CONFLICT DO NOTHING;
COMMIT;
