# Round input and device warnings

**Detector update:** see tablet-device-release.md for the new Grounding DINO worker and distinct-device-event policy. The EfficientDet limitation below describes the earlier release.

This update supersedes the previous device-disabled fallback described in optional-device-monitoring.md.

- HR questions use microphone recordings with transcript review before scoring. The camera stays on for monitoring.
- Aptitude and technical rounds each use 15 MCQs. These rounds request camera access without requesting microphone access.
- Camera, face, fullscreen, focus, device-worker freshness and evidence storage remain required.
- In production without passing detector validation, possible phones and laptops trigger acknowledgement warnings and evidence for HR review. Repeated device events do not terminate the interview, restrict the account or affect answer scores. Duplicate event submissions do not add warnings.
- Existing face and fullscreen enforcement is unchanged. Validated-device deployments retain their previous enforcement policy.
- EfficientDet Lite0 does not have a tablet category. A tablet can be missed or labelled as a phone. Warnings are approximate, not findings of misconduct.

## Deploy and verify

Upload this package's backend, frontend and docs contents at the repository root. Commit and deploy the latest commit on the existing Render service. No database migration or environment change is required. Keep ENVIRONMENT=production. Reload the application after deployment.

Use fresh assignments for the new MCQ format. Previously generated question sets and completed attempts stay unchanged. Test that MCQ rounds request only camera permission, the HR round requests camera and microphone, and device warnings can be acknowledged without stopping the interview. Present and remove a phone, then repeat to check warning-only behavior and review evidence in the HR report. Test camera denial/disconnection and fullscreen enforcement separately.

Automated tests cover server permissions, monitoring requirements, device-warning deduplication and nontermination. Real camera/browser and Render validation remain required.
