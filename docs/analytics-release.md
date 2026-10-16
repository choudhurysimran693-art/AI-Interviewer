# Reports / Analytics update

Upload this patch into the existing repository, preserving paths. Include backend/requirements.txt and frontend/package.json plus package-lock.json: Render installs ReportLab and Recharts during build. No environment changes or new tables.

Endpoints under /api/analytics: score-distribution, by-position, trends, technical-communication, export/csv, export/pdf. All require HR/admin authentication and scope via the role organization. Optional position_id, date_from, date_to (YYYY-MM-DD). Inclusive date inputs are interpreted in UTC; invalid/reversed dates return 422, foreign role IDs return 404.

Existing data mapping: sessions.status=complete, sessions.body.ended_at is completion time, sessions.body.summary contains technical/communication/overall, sessions.body.position_id joins recruitment_positions. Incomplete/terminated sessions, missing completion times and unavailable overall scores are excluded. Historical sessions without a linked position cannot be assigned safely to an organization and are excluded. Existing score zero is real data, not missing. No candidate demographic or monitoring fields are used in scores.

SQL computes the distribution and averages. Bands are [0,20), [20,40), [40,60), [60,80), [80,100]. Positions with no scored sessions are omitted. By-position intentionally ignores the selected role and compares all organization roles with date filters, as requested; UI/PDF explain this. Blank dates mean all time except trends, which defaults to current and previous 11 months. Scatter is capped to the latest 3,000 scored sessions.

Exports use the same source and filters. CSV contains one row per scored completed session, UTF-8 BOM and spreadsheet-formula escaping. PDF contains filter descriptions, three summary tables and a scatter plot, with repeating table headers and page numbers.

Verification: API tests with two organizations, several roles/months, all score boundaries, null scores, incomplete/terminated exclusions, dates, empty results, CSV formula escaping and PDF text. Local Chromium checks with mocked responses cover charts, all-four-query filter updates, empty states, export URLs and reversed dates. Generated PDF pages visually inspected. TypeScript, 48 frontend tests and production build passed. PostgreSQL production runtime and live deployed data still need verification after deployment.

After deploying, open Reports / Analytics, select a role/date range, then download CSV and PDF. No data is expected until at least one linked interview is completed with a recorded score.
