# Assigned assessment interface

Aptitude and Technical MCQ rounds now use a practice-style question header: numbered submitted/current/upcoming progress, round title, question count, countdown with an urgent state, format/category badge, readable question text, and code snippet where provided. Answer cards use the more compact practice spacing and wrap long text on narrow screens. The irrelevant resume-basis box is hidden for these MCQ rounds.

Existing assigned-interview submission, expiry auto-submit, server grading, retry behavior, proctoring and progression are preserved. Progress indicators are informational, not skip buttons. Correct answers are not revealed during the hiring assessment. The technical round remains the existing MCQ assessment; this UI update does not introduce the practice coding sandbox or a new short-answer assessment backend.

Upload every file in github-update-assessment-interface-combined.zip into the matching repository paths and deploy. The combined archive includes the prior round-flow and notification patches using the latest local files. No credentials, database, or node_modules are included.

Validation: TypeScript and 55 existing frontend regression tests passed. The production build was checked. Live browser/camera interaction and production deployment were not performed for this UI patch.
