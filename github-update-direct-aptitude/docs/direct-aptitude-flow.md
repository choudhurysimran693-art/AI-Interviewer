# Start directly with Aptitude after shortlisting

The current default removes Resume Screening from the active interview sequence. Candidates see:

1. Aptitude / Reasoning Test (MCQs)
2. Technical Assessment (MCQs)
3. Technical / System Design Interview
4. HR Round
5. Final Interview (manual)

Shortlisting now opens Aptitude directly. A separate Approve resume screening action is no longer needed. Resume uploads may still be used for the application and later interview context; they do not introduce a candidate screening interview.

Deploy every file from `github-update-direct-aptitude.zip` at its matching repository path. In Render set:

```dotenv
REQUIRE_SEQUENTIAL_INTERVIEWS=true
INCLUDE_RESUME_SCREENING_ROUND=false
```

The second setting defaults to false. Existing six-round compatibility tests explicitly enable it; normal deployments use the five-round flow. Version shown in My applications and `/api/ready`: `aptitude-direct-2026-11-04`.

On application startup, already-shortlisted applications with later rounds all pending are activated at their first remaining round. Old Resume Screening records are retained for history but excluded from active progression and display. Their obsolete invitations are cancelled. Repeating startup does not create another Aptitude assignment. Applications already rejected or hired are not reopened. Applications already progressing through later rounds remain at their existing round.

The first notification says the candidate has been shortlisted and can start Aptitude, rather than claiming a resume-screening pass. Later reviewed passes continue to unlock the next round and queue notifications and emails through the existing outbox.

This combined source archive includes prior workflow, email, interface and startup fixes. It has not been deployed to your production account. Live camera and inbox delivery still depend on the deployment and provider configuration.
