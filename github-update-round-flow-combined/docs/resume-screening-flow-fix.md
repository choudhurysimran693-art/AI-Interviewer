# Start the configured six-round flow

Older definitions defaulted Resume Screening to `ai_conducted`, which produced a spoken resume interview. New definitions now normalize that round to `auto_evaluated` document screening. Attempts to start or mutate a legacy pipeline resume-screening session are blocked; independent resume-based practice is unchanged.

After deploying this combined patch:

1. Sign in as HR and open **Applications**.
2. Open the affected candidate. Review the uploaded resume and screening evidence.
3. Under **Interview rounds**, click **Approve resume screening** for the current stuck Resume Screening round.
4. The obsolete spoken screening assignment is cancelled, its records are retained, and Aptitude / Reasoning opens. A new round notification is queued through the existing notifier.
5. The candidate opens **My applications → Start Round** on Aptitude, or its invitation. Continue with Technical Assessment, Technical / System Design, HR, and the manual Final Interview as HR approves each outcome.

The approval endpoint is HR/admin-only and organization-scoped. It cannot approve a later round or reopen a rejected application. Repeating approval does not issue another assignment. It does not silently pass existing screening rounds during deployment.

New standard-template applications use HR shortlisting to approve document screening, then start Aptitude automatically as the current round. Questions for Aptitude and Technical Assessment use their existing MCQ bank; the later interview rounds use their existing interview flow.

Upload every file from `github-update-round-flow-combined.zip` at its matching repository path and deploy. This archive includes the preceding sequential-round and workflow-notification patch files as well as this fix, using the latest local versions. It is still an incremental update to your existing project, not an entire repository.

Tests: `python -m pytest backend/tests/test_resume_round_flow.py -q`. The regression suite also checks six-round progression, failure locking, notifications and authorization. No live deployment was performed.
