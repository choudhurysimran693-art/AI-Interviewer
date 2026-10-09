# HR interviews with device detection disabled

**Superseded:** the current behavior restores device warnings for human review. See round-controls-release.md. The following describes the previous release only.

Production detector validation now controls only device detection and its penalties, rather than access to all assigned interviews. Without passing validation, the browser does not start the device worker, the server accepts heartbeats without object inference, and device events/warnings are rejected. Camera, microphone, face, focus, fullscreen, consent, authorization and evidence-storage requirements remain.

This does not fix tablet classification or certify the model. Existing historical events and terminations remain unchanged. Development retains its existing detector validation bypass.

## Deploy

Upload the package contents at the repository root, preserving backend/ and frontend/ paths. Commit and deploy the latest commit on the existing Render service. No environment variable or database migration is needed. Keep ENVIRONMENT=production.

After deployment, reload the page and start a fresh assigned test interview. Expect “Device detection is disabled” and an enabled Create interview button once the required profile and consents are filled in. Enable the camera and microphone, complete the face check, acknowledge the rules, then start in fullscreen. Confirm that answers can be submitted and completed, and that disconnecting the camera still pauses the interview. Confirm device detection is shown as disabled. Existing attempts are not reset by this patch.

Automated checks cover session creation, startup, heartbeat requirements, disabled-device event rejection and enabled-detector freshness. Real browser camera and Render verification are still required.
