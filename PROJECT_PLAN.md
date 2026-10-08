# AI Interviewer — Project Plan and Current Status

## Completed

### Candidate workspace

- Candidate dashboard with assigned-interview cards and correct scheduled, open, expired, and completed states.
- Open positions page with loading, error, empty, populated, duplicate-application, and company-name states.
- My applications page with loading, error, empty, filtered-empty, and populated states.
- My interviews and interview-results pages with status and report links.
- Candidate profile persistence for contact details, skills, resume, saved profile photo, consent, and completion progress.
- Resume reuse during scheduled interviews so candidates are not asked to upload it again.
- Fixed-role behavior for interviews already scheduled by HR.
- Practice tracks with non-repeating question progression and easy-to-hard unlocking.

### HR workspace

- Applications intake and filtering by role, status, and date.
- Recruitment roles with vacancy tracking and candidate pipeline data.
- Interview scheduling with current-time scheduling support, configurable windows, reminders, and resend support.
- Candidate resume and identity-photo review in HR candidate details.
- Dashboard metrics, pipeline distribution, analytics, reports, and monitoring alerts backed by database data.
- Demo data loading and clearing gated by the development environment setting.
- Multi-organization structure with organization-scoped HR data and candidate accounts shared across organizations.

### Interview safety and reliability

- Candidate pre-interview equipment check for camera, microphone, lighting, connection, fullscreen, and detector readiness.
- Saved profile-photo identity verification with consent and retry flow.
- Multiple-face detection is separate from device detection.
- First device detection warns; repeated configured device detection can terminate the interview.
- Multiple-face policy is independently configured and enforced.
- Gaze and camera-quality observations are review signals only and never affect scores.
- Live captions with a candidate-facing visibility toggle.
- Technical issue messaging and retry monitoring controls.
- Human-review explanations for monitoring observations.
- HR policy controls for warning thresholds, termination, account blocking, and review requirements.
- Audit metadata records the reviewer and review timestamp when an alert is marked reviewed.
- Candidate interview deletion is disabled; interview ownership remains with HR/administrators.
- Practice mode has optional monitoring and no hiring or enforcement effect.

### Notifications and reports

- Candidate dashboard notifications for assignments and interview reminders.
- Email/outbox delivery support, pending real SMTP credentials.
- Candidate post-interview reports with scores, approved-answer feedback, improvement steps, and separate monitoring observations.
- HR reports with timelines, evidence links, explanations, and export support.

## Deliberate safety boundary

The system does **not** infer or score emotions, stress, empathy, EQ, personality, or sentiment from faces or voices. It does not use those signals for hiring decisions. Safe alternatives are limited to observable and reviewable signals such as gaze availability, pauses, speaking pace, camera quality, device detections, multiple faces, fullscreen changes, and technical interruptions.

## Remaining configuration

- Replace placeholder SMTP values in `.env` with a real provider host, username, password/app password, and verified sender.
- Keep `ENABLE_DEMO_DATA` disabled in production.
- Set a persistent production `APP_SECRET`.
- Configure production database and public URL separately from development.
- Perform a physical browser walkthrough with camera and microphone permissions.

## Validation completed

- Backend Python compilation passed.
- Frontend TypeScript compilation passed.
- Existing backend and frontend test suites passed before the latest UI additions.
- A full Vite build was blocked locally by a Windows `spawn EPERM` restriction from esbuild; this is an environment issue rather than a TypeScript error.

## Suggested next steps

1. Configure SMTP credentials and send a test reminder and interview invitation.
2. Run the application and test a clean candidate-to-HR flow with one real account.
3. Verify camera, microphone, lighting, connection, identity retry, captions, and monitoring behavior in a real browser.
4. Confirm production environment variables and database separation before deployment.
