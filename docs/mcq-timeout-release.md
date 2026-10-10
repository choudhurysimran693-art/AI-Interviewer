# MCQ timeout and submission recovery

- When active question time expires, submit the selected option automatically. An unanswered expired question is recorded with zero marks. Advance only after the server saves it, including the final question.
- Required monitoring pauses freeze the question timer. A timed-out question waits for checks to recover before its automatic submission.
- Choices lock at expiry. Failed requests keep the selection and expose manual retry. Requests time out after 20 seconds; deterministic answer IDs make retries idempotent.
- Camera readiness now requires a recent server acknowledgement, rather than being overwritten by the next local check. Pause text identifies the local check or event sync error.
- Slow advisory device scans do not require a camera restart. Validated mandatory detection still gates answers.
- Synchronous gaze database work runs in the server thread pool, avoiding blocking the async event loop during database round trips.
- Test configuration disables real SMTP delivery.

Deploy the included files at their existing repository paths, then deploy the latest commit on Render. Live network latency and camera/device model performance have not been measured by these tests. This change does not claim to improve model inference speed.
