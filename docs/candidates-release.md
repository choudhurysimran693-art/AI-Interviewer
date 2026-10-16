# Candidates page update

Upload this patch into the existing GitHub repository, preserving paths, then deploy. No new environment variables or core tables. Application.updated_at receives an idempotent startup index; existing candidate_id and position_id/status indexes are retained. Organization ownership is derived through applications and recruitment_positions, so no redundant candidate organization/status fields are created.

## API
- GET /api/candidates: search (literal case-insensitive name/email substring), position_id, min_score (0-100), stages (comma-separated OR), sort=modified_date, page, page_size (1-100). Returns items, total_count, organization_total, page, page_size.
- GET /api/candidates/filter-counts: same search/role/score filters, all seven stage keys, one GROUP BY. Selected stage filters do not restrict checkbox counts.
- PATCH /api/applications/bulk-move: application_ids (up to 100), target_stage. Ownership of every ID is resolved before mutation. Per-ID results include success/error, plus counts. Failed rows remain selected in the UI.
- GET /api/candidates/{candidate_user_id}: contact information, parsed profile, scoped application and round history, resume links where available, linked interview history. The card's profile URL is /hr/candidates?candidate={candidate_user_id}.

## Data semantics
Each card represents one application. id/application_id identifies the application; candidate_id identifies the user for profile navigation. A person applying to two positions appears twice with independent stages and scores. The score is the latest completed session's recorded overall for that application; scores from another application, active sessions and terminated sessions are not used. An unavailable latest score stays unassessed rather than inheriting an older score. Activity and invitation/round states identify In progress where no score is available. Modified date is applications.updated_at.

Stages reuse role_cards.pipeline_stage_expression. Role-card shortlist maps to shortlisted on this API; no second stored pipeline field is introduced. Hired/rejected and offer states take precedence over round activity.

## Bulk workflow rules
Bulk actions reuse applications.transition, including existing round eligibility, vacancy row locking, first-hire-only increment, role closure, and notifications. Applied applications may be shortlisted through the existing under-review transition. Interview moves require an existing assignment; schedule/invite the interview first. Closed or invalid transitions and moves that contradict active round progress return per-ID failures, rather than bypassing round decisions. An invalid/foreign ID never changes another organization's application.

## Frontend
One filter object and 300ms debounce coordinate list/count queries. Server pagination has current-page Select all. Filter or page changes clear selection. All seven checkbox stages are visible with live counts; minimum score above zero excludes unscored applications. Candidate status badges, three-column responsive grid, skeleton/loading/errors, two distinct empty states, pagination, and a scoped profile drawer are included. The candidates route no longer loads the full dashboard.

## Verification
API tests cover multiple roles/stages, multi-application candidates, score zero vs unavailable, combined filters, literal search, pagination, shared stage counts, permissions, profile isolation, partial bulk failures, hire capacity closure and idempotent re-hire. Local Chromium checks with mocked API data cover debounce, selection, partial failures, profile opening, empty states and mobile layout. TypeScript and production build pass; 48 frontend tests pass. Live deployment should still be checked with your organization's data.
