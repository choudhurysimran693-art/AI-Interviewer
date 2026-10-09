# Tablet detection and distinct-event policy

This release supersedes the EfficientDet device worker for live interviews. Both the interview and /detector-check use the same bundled Grounding DINO q8 worker with phone, tablet and laptop text prompts. This is an implementation change, not a claim of measured tablet accuracy. Frames are processed locally in the browser.

The first confirmed event creates a warning. A continuously visible device, or phone/tablet label flicker, is one event. A new event requires observations with no device spanning at least five seconds, followed by three fresh positive frames. With validated detection the second distinct event terminates the attempt; retries of an event do not add strikes. Without a passing production validation report, all device events remain review warnings without automatic termination.

Validation is now tied to model `grounding-dino-tiny-q8` and revision `ff690b0a8050566c290287545bd059350f3e9096`. Old EfficientDet reports cannot enable enforcement. Do not manufacture passing measurements. The existing acceptance requirements still apply: real phone/tablet/negative clips on intended hardware, reviewed predictions and measured latency.

## Deployment

Upload the ZIP contents to the repository root, including Dockerfile, frontend configuration and the small model metadata files. Docker downloads the pinned q8 weights and verifies their checksum; do not upload the ONNX weights through GitHub's web uploader. Keep the existing package.json/package-lock.json with Transformers.js 3.8.1. No environment or database migration is needed.

Commit and deploy on Render, then hard-refresh the app. The old HR-unavailable banner is removed by the included round-controls changes. Aptitude and technical retain 15 MCQs; HR retains voice answers. Camera access is required for device checks.

Open /detector-check and test real phone, tablet and negative images first. The new result identifies `grounding-dino-tiny-q8`, not EfficientDet. The model download is approximately 194 MB; CPU inference may be slow. The live equipment check must receive a successful fresh result before starting. A slow/failing model must be investigated rather than bypassed.

Automated tests cover selection decoding, label flicker, event confirmation/removal, retry deduplication, first warning, and second-event termination under validated conditions. The real-image headless browser check was blocked by local process-launch permissions, so real tablet accuracy, browser latency and the deployed Docker image remain unverified. The diagnostic page and scripts/check-tablet.mjs are provided for verification.
