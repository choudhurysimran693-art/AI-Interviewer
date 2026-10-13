# Browser performance update

## Changes
- Camera requests at most 640 x 480 and 15 FPS.
- Retains existing non-overlapping face scans approximately 3 FPS, gaze landmarks at most 1 FPS, and lightweight phone scans at most 1 FPS. New object scans pause during answer submission.
- Reuses face and lightweight device worker canvases to reduce allocation churn.
- Red warning appears directly below camera preview. Detailed scanning timings remain available in Monitoring details. Required-check failures remain visible.
- Multiple-face detection and continuous interview monitoring remain active. Existing server warning counters and validation rules remain intact.

## Existing protections retained
Questions are already loaded as a complete list before the interview. MCQ submission waits for confirmed answer storage before moving forward; it does not generate the next question. This app uses MediaPipe Tasks, not legacy FaceMesh or TensorFlow COCO-SSD. Grounding DINO uses WebGPU where supported with CPU fallback. Tablet detection can still be slow on CPU. No guaranteed detection latency is claimed.

## Upload
Extract this cumulative patch and copy its contents into the existing GitHub repository root, preserving backend/, frontend/, docs/ and Dockerfile paths. Commit and deploy. This is a patch for the existing repository, not a standalone project. No secrets are included. Existing email environment configuration is still required; see email-scanning-release.md.

## Validation
TypeScript check, 48 frontend tests, face/device worker regression scripts and production build. Live webcam accuracy, GPU timing and deployed email delivery require verification on the deployed application.
