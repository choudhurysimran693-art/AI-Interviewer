# Equipment start update

Upload all files in github-update-equipment-start-combined.zip at their matching repository paths, commit and deploy. Hard-refresh the candidate page after deployment. This combines the prior workflow, notifications and assessment-interface fixes.

The camera tile now reports the actual camera/video readiness, independently of fullscreen/server monitoring. Begin still requires the configured camera, face, microphone (only when required), storage and device checks. Optional gaze model loading no longer delays the face detector's ready message. Evidence storage verification runs alongside detection with a 10-second timeout instead of blocking the detection loop indefinitely. The equipment panel names the pending or failed check and provides Retry equipment check. These changes do not bypass proctoring.

For a stuck legacy Resume Screening application, HR reviews the resume and uses Applications → Interview rounds → Approve resume screening. The first candidate assessment is then Aptitude / Reasoning. A reviewed pass opens Technical Assessment, then Technical / System Design, HR and manual Final Interview in order. Pass notifications include the next assigned round link and actual deadline; manual scheduling details follow from HR. Email is queued after the decision and requires valid SMTP/Brevo configuration with DRY_RUN=false and the deployed PUBLIC_URL.

Validation: TypeScript, production build, 55 frontend regression tests, 12 targeted backend workflow/notification tests, and the face-startup test passed. The startup test simulates optional landmark loading that never resolves and checks required face inference still runs. Live camera, actual email inbox delivery and production deployment were not verified.
