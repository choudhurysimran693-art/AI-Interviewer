# Red warnings, responsive scanning, marks emails

Upload all included files to their existing repository paths and deploy. This package includes previous timeout and monitoring fixes. No database migration is required.

## Email on Render Free

Render Free blocks SMTP ports 25, 465, and 587. Use the implemented Brevo HTTPS transport:

1. Create a Brevo account and verify the sender address/domain. Complete any provider account activation requirements.
2. Generate an API key (not an SMTP key).
3. In Render Environment set EMAIL_PROVIDER=brevo, BREVO_API_KEY=<private API key>, EMAIL_FROM=<verified sender address>, PUBLIC_URL=https://ai-interviewer-za5k.onrender.com.
4. Save and deploy. HR > Interviews > Email delivery shows configuration and recent queue status. Resend invitation queues a new email. Accepted by provider means submission succeeded, not guaranteed inbox delivery.
5. Test with a real registered recipient; example.test addresses cannot receive mail. Check Spam and Brevo delivery logs for rejection/bounces.

Invitations and completion marks notices use the persistent outbox, with up to five delivery attempts. Completion queues once. Recovery also uses the common HTTPS transport. SMTP remains available for hosts that permit it, including implicit TLS on port 465.

## Scanning and submissions

A lightweight EfficientDet CPU worker scans phones/laptops once a second separately from the tablet-capable Grounding DINO model. Immediate local warnings use a red banner. EfficientDet has no tablet class and cannot establish that a tablet is absent. Fast phone advisories do not issue automatic termination strikes; the existing confirmed detector policy remains independent.

Grounding DINO uses local fp16 WebGPU on compatible adapters for advisory scans, with q8 CPU fallback. Unsupported GPUs, model startup failures, invalid outputs, and inference exceptions trigger CPU fallback. Mandatory validated scanning keeps the original q8 model. Scans are spaced out to reduce contention, and new optional scans do not start while an answer is saving. Model execution already in progress can continue. Startup downloads are larger on first GPU use and depend on the connection.

Authentication, gaze database operations, and background job polling run off the server event loop. MCQ scoring saves synchronously without an AI job, and expired questions auto-submit. The heartbeat retries after an eight-second request timeout rather than remaining stuck indefinitely. Required camera/fullscreen/evidence checks and monitoring pauses still apply.

## Validation limits

Automated tests cover backend policies, transport requests, retry, queued invitation, result notification, and access isolation. Frontend build/type checking and worker regression tests cover warning logic. Camera accuracy, live GPU compatibility and device/answer latency still need measurements on the user's browser. Docker is not available locally, so the Docker image was not built locally. No universal real-time speed guarantee is claimed, especially for tablet inference on CPU and Render cold starts.

Sources: https://render.com/docs/free ; https://developers.brevo.com/docs/send-a-transactional-email ; https://huggingface.co/docs/transformers.js/guides/webgpu
