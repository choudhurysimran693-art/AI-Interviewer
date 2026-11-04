# Fix the standalone spoken-interview bypass

Earlier fixes checked invitations that already had application/round metadata. A standalone HR invitation could have neither and still open five spoken questions. This patch requires HR assessment sessions to be attached to a configured application round by default, including session reads, question requests and resume requests. Private practice remains separate.

## Deploy and verify this exact update

1. Upload all files from `github-update-strict-aptitude-flow.zip` into the matching paths of the existing repository. Commit them and deploy that commit.
2. In Render environment settings set `REQUIRE_SEQUENTIAL_INTERVIEWS=true`. It defaults to true, but an explicit value prevents an old override from enabling standalone hiring interviews.
3. Open `/api/ready` on the deployed domain. It must contain `workflow_version: aptitude-first-2026-11-04` and `sequential_interviews: true`. The candidate Applications page also shows this version label. If absent, the deployed code is older than this patch.
4. HR opens Applications and reviews the affected candidate. If the already-shortlisted application has no rounds, click **Enable Aptitude-first rounds**. If it already has a stuck Resume Screening round, use **Approve resume screening** after reviewing the resume.
5. Candidate hard-refreshes and opens My applications → Aptitude / Reasoning → Start Round. An obsolete generic invitation now directs the candidate to the current hiring round instead of opening spoken questions.

The repair creates the standard sequence only where no application rounds exist. It requires an HR/admin account from the same organization and a shortlisted application. It cancels the application's obsolete generic assignment while retaining its records. Existing completed results are not erased. If the role has a different custom sequence, HR must configure the standard template before initialization; the repair refuses to overwrite an existing sequence silently.

For newly shortlisted roles with no configured rounds, the standard sequence is created automatically. Resume screening is approved by the HR shortlist decision, and Aptitude becomes the first active candidate assessment. The existing reviewed pass/fail logic and transactional next-round notifications are retained.

## Formats

- Resume Screening: HR document review.
- Aptitude / Reasoning: 15 question-bank MCQs.
- Technical Assessment: 15 technical MCQs.
- Technical / System Design Interview: existing interview questions.
- HR: existing behavioral interview.
- Final: HR's manual decision after the scheduled interview.

This patch does not convert the later spoken interviews into MCQs. Email requires the existing SMTP/Brevo configuration and `DRY_RUN=false`; a queued message or provider acceptance is not inbox-delivery confirmation.

## Checks

`backend/tests/test_strict_round_entry.py` exercises the production-default strict behavior: generic sessions cannot load/resume questions, newly shortlisted Java Developer applications with FastAPI resume skills start 15 aptitude MCQs, a next-round notice is queued, and authorized HR can repair an older shortlisted application. Historical standalone-interview regression tests explicitly disable the new setting to retain coverage of the optional compatibility mode. Production defaults to strict mode.

No live production account, deployment, email inbox, or camera was used during these checks. The ZIP contains the current combined source updates, not a standalone repository or credentials.
