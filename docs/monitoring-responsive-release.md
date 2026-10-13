# Monitoring responsiveness update

Apply these files over the existing app, commit, and deploy on Render.
Includes the previous MCQ timeout/submission patch.

Face counts now come from the face detector without being reduced by gaze landmark counts. Gaze inference runs at most once a second and gaze failures cannot suppress face results. Supplementary gaze samples are dropped while the event queue is busy, preventing their backlog from delaying warnings. A possible-device advisory appears on the first positive scan; confirmed events retain existing warning and review rules.

Verification: TypeScript, 48 frontend tests, production build, and face-worker mocked regression checks passed. Previous backend patch passed 82 tests. Camera accuracy and live latency have not been measured. The CPU tablet model remains potentially slow; this patch reduces optional work but does not guarantee faster device inference. Detection unavailable must not be interpreted as no device present.
