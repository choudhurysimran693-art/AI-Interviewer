# Deploy the standard hiring template

## Before deployment

- Back up the Supabase database. Keep the same database connection and APP_SECRET.
- Existing pipelines retain their definitions. No existing accounts are moved from SQLite by this release.
- Run `migrations/003_round_templates.sql` on an existing deployed database. Startup also performs the equivalent additive column upgrade, creates missing tables, and seeds the template once.
- Keep a single application instance during migration and until the job queue supports distributed consumers.
- Upload the changed source and Dockerfile to the existing repository. Render then deploys the latest commit.
- Docker downloads the pinned q8 device model and checks its SHA-256; do not upload ONNX binaries. It also creates runtime storage owned by the non-root app user.
- Set DATA_DIR=/home/user/app/data and PUBLIC_URL=https://ai-interviewer-za5k.onrender.com. Use the existing SMTP and database secrets on Render only.

## Use the feature

1. HR opens Recruitment roles, saves a role, and opens Configure interview rounds.
2. Apply Standard Technical Hiring. Rename, reorder, disable, remove, or add stages before shortlisting anyone.
3. HR reviews the existing evidence-based resume screening and shortlists or rejects. Shortlisting passes the template resume stage and invites aptitude; no resume exam is created.
4. Aptitude uses bank questions with answer-key grading for MCQs. HR can opt into a score threshold; incomplete scoring always stays for human review.
5. Technical uses DSA bank content. Open-ended/code responses receive rubric feedback; they are not executed in this interview flow. The separate practice code runner still requires its own runtime.
6. Technical/System Design uses approved project context; HR uses job-related scenarios. HR decides each outcome.
7. Passing HR unlocks Final Interview as Awaiting scheduling. HR enters a future call time and candidate-visible details. No assignment, exam, question set, AI score, or proctoring session is created.
8. After the scheduled time, HR records pass/fail with required private notes. Passing Final Interview records Hired and consumes one vacancy; failure records Rejected. Repeating the same decision does not consume another vacancy.

Candidate trackers display scheduling details but never HR decision notes or a start action for human-only rounds.

## Editing limits

Templates are copied, not linked. Editing one role does not change the reusable default. Once candidates enter a pipeline, its definitions cannot be replaced; create a new role for a changed process. Final Interview must be the last enabled round. Automatic resume screening must be first.

## Acceptance checks

Run backend tests and frontend typecheck/tests/build. On staging, check a full pipeline with real camera permissions, email, and configured model access. Production monitoring validation remains required; this release does not bypass that gate. Local SQLite tests do not substitute for a Supabase/Postgres staging check.
