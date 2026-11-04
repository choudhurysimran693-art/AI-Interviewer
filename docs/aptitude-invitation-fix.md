# Aptitude-first invitation fix

Sessions now take round type and evaluation mode from the application's round definition, not copied invitation metadata. An obsolete generic invitation linked to an application with rounds is rejected with instructions to open the current round in My applications. Standalone HR interviews and private practice retain their separate behavior.

If a current Aptitude/Technical session has old spoken questions but no submitted answers, opening it reloads the question bank for its actual round. Submitted answers are never silently discarded; a mismatched attempt with answers needs HR review and a fresh invitation.

Deploy all files in github-update-aptitude-first-combined.zip, then hard-refresh. Candidate: open My applications and use Start Round on Aptitude / Reasoning, rather than an older resume-interview email link. If Resume Screening is still current, HR must first approve its document review using the existing Approve resume screening action.

Order: approved resume review → Aptitude / Reasoning → Technical Assessment → Technical / System Design Interview → HR → manual Final Interview. Existing reviewed-pass progression and next-round email notifications remain enabled.

This combined archive includes prior patches at their latest local versions. No deployment or real candidate session was accessed. Regression checks include deliberately stale invitation/session metadata and confirm fifteen aptitude MCQs replace unsubmitted legacy spoken questions.
