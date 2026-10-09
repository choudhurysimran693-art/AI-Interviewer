# Acceptance checklist

## Automated checks

- Backend: five-question typed flow; explicit unavailable scoring; transcript approval; immutable completed answers; consent grant/revocation; HR monitoring lock; cross-session authorization; evidence ownership/deletion; expiry cleanup; resume signature rejection and DOCX extraction; evaluator input isolation; exact evidence quotes; feelings validation.
- Frontend unit tests: three-frame confirmation, confidence cutoff, gap reset, one event while visible, five-second closure, cooldown, and face-event merging.
- TypeScript checking and production bundle compilation.

## Required release checks using real inputs

- [ ] 20 phone clips, 20 tablet clips, 20 negative clips, reviewed labels, pinned model revision, latency measurements.
- [ ] Matching validation on intended desktop Chrome and Edge computers and a separate CPU-fallback run.
- [ ] Camera permission denial, camera removal, worker failure, dark room, no face, multiple faces, tab visibility, and recovery.
- [ ] Record five English answers; listen and verify CPU transcripts, silence, corrupt audio, recording format compatibility, and transcript correction.
- [ ] Real Gemini evaluation: timeout/quota/malformed-output handling and evidence-grounded scoring.
- [ ] Real private Supabase bucket: access denial, valid upload/download, remote delete, and retry after outage.
- [ ] HR completion is blocked if a device picture is still pending.
- [ ] Consent changes are enforced in HR report/PDF views and direct endpoint requests.
- [ ] Desktop and mobile-width report print layouts; long transcripts and many events.
- [ ] Hugging Face cold start and restart preserve reports; interrupted jobs have recoverable status.
- [ ] Public HTTPS deployment, production secret stability, expiry, and cleanup after sleep.

Do not replace these checks with fabricated detections or a hand-authored passing validation file. Device detection and device penalties remain unavailable until detector validation passes. Assigned HR interviews can proceed with camera, microphone, face, fullscreen, focus and evidence-storage checks. The candidate UI must explicitly disclose disabled device detection. Validate this reduced monitoring mode on the deployed site before inviting candidates.
