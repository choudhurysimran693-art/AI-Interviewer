# Recruitment role cards

Extract this patch into the existing repository root, commit, and deploy. No new environment variables. Startup idempotently adds applications(position_id,status); existing unique interview_rounds(position_id,round_order) covers ordered rounds. Existing position JSON fields and organization FK are retained rather than creating duplicate tables.

GET /api/positions (also /api/recruitment/positions) defaults to open roles for compatibility. Use ?status=&include=pipeline_summary for all statuses with summaries. POST creates roles; PATCH /api/positions/{id} edits the role. Both aliases enforce organization ownership. Role cards compute days_open live. Level and screening_type are supported; legacy difficulty/question_set remain compatible. Screening type is descriptive; configure the actual round sequence in the rounds panel.

GET /api/positions/{id}/pipeline-summary returns seven lower-case count keys. One grouped SQL query handles all requested roles, using existing round states, with terminal hired/rejected taking precedence, then offers/passed HR, active resume screening, active interviews, shortlist, and legacy status fallbacks. Counts represent applications, not distinct candidate profiles. Zero-count stages are included.

Criteria endpoints GET/POST/PATCH/DELETE /api/positions/{id}/criteria reuse the existing bulk editor; DELETE clears criteria and rescreens applications. Round endpoints GET/POST/PATCH/DELETE /api/positions/{id}/rounds use ordered sequence replacement; individual add/edit/remove/reorder operations are submitted as the edited sequence. DELETE clears rounds only before any candidate round records exist. Existing apply-round-template endpoint remains available. Panels fetch only after expansion; initial roles view no longer requests the full dashboard.

Hire transactions retain the existing position row lock, increment only on the first hire transition, and close full roles. Editing capacity below hires is rejected; reopening at full capacity keeps the role closed.

Verification: two-role seven-stage seeded regression, single-query assertion, organization isolation, days open, paused roles, capacity edits, existing hiring/closure and template tests. 48 existing frontend tests and TypeScript/build pass. Live deployed browser end-to-end checks are not performed. After deployment create a role, expand each panel, save criteria/template, and verify the card refreshes after an application changes stage.
