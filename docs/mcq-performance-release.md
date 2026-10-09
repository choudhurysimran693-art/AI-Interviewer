# MCQ speed and layout update

This release replaces the MCQ review/dropdown/queued-scoring/next-button sequence with one Submit & next action. The server validates the selected option IDs, scores against its private answer key, and commits the answer synchronously. The client advances only after the save succeeds. Retrying the same question returns the saved result without duplicating answers. Spoken HR answers retain recording and transcript review.

Options now use aligned radio buttons and text inside full-width pale-green rows. MCQ screens do not show live-caption controls.

Question-bank seeding now reads existing rows in one query and only updates changed content, instead of looking up and rewriting every question during each preparation request. This improves practice preparation and assigned MCQ generation without changing saved attempts.

For unvalidated device detection, slow/unavailable object scans no longer block answer submission or startup. The detector continues running in the background and unavailable scans are disclosed for review. Sampling is spaced out to reduce CPU pressure. Camera, microphone where required, face, fullscreen/focus, recent server heartbeats, evidence upload and termination checks are retained. Validated strict-device mode still requires fresh device results. This supersedes the older instruction requiring fresh unvalidated device inference before every answer.

## Deploy

Upload the contents of the combined ZIP to the existing repository root and redeploy the existing Render service. No migration or environment change is needed. Hard-refresh afterward. Test with a fresh assignment. Existing saved questions/answers are preserved.

Check that selecting an MCQ and pressing Submit & next saves it and advances directly, and that an unanswered selection or failed request does not advance. Test the final question, refresh/resume and temporary network failures. Practice preparation should avoid repeated database writes. Cold starts, connection delays and slow face/camera checks can still take time; no deployed latency measurements have been made for this patch.
