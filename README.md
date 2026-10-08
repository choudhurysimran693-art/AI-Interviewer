---
title: Interview Studio
emoji: 🌿
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
---

# Interview Studio

A resume-based practice and HR pilot application, with face-count observations and private device evidence pictures. React/Vite frontend, Python/FastAPI backend, Postgres and Supabase Storage adapters. See IMPLEMENTATION-NOTES.md for current verification limits.

## Start locally

Use Python 3.11, Node 22+, and FFmpeg. Run commands from this folder unless indicated otherwise.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
Set-Location frontend
npm install
npm run build
Set-Location ..
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log
```

Open **http://127.0.0.1:8000**. The built React application is served by FastAPI. For frontend development, run `npm run dev` in `frontend` and use port 5173; API requests proxy to port 8000.

### Restricted Windows environments

If Node child-process pipes fail with `spawn EPERM`, use the included equivalent WebAssembly compiler:

```powershell
# In frontend:
npm install --ignore-scripts --cache ../../../work/npm-cache
node node_modules/typescript/bin/tsc -b
node scripts/portable.mjs build
node scripts/portable.mjs test
```

The portable builder uses the official esbuild WASM transform and disables Vite's optional mapped-drive probe. Normal builds and the Docker build use native esbuild.

## What works without service keys

- Resume extraction, candidate profile review, five varied resume-based template questions.
- Typed answers, approved transcripts, camera observation reports, private report links, and browser PDF printing. Scores use the local rubric or the configured evaluation provider.
- HR exam mode pauses when the tab is hidden, the camera is turned off, or monitoring loses health; device warnings are shown once per session.
- SQLite and filesystem evidence **for local development only**.
- Audio transcription after the local Whisper model is downloaded; FFmpeg is required.
- Camera workers and local HR monitoring; model assets are downloaded to the browser.

Scoring works without external credentials through a deterministic local rubric labeled `local_rubric`. When `GEMINI_API_KEY` is configured, validated Gemini evaluation adds richer evidence and improvement advice. Camera observations and emotion labels never enter scoring.

## HR release gate

Production HR sessions cannot start until `DETECTOR_VALIDATION_FILE` points to passing operator-reviewed results. Local development allows HR screening so the interview flow, camera checks, and evidence upload behavior can be tested. **No passing validation file is included.** The object detector's real accuracy and performance have not been certified by automated unit tests.

1. Run an operator-managed validation on the intended Chrome/Edge computer.
2. Record the exact model commit revision and hardware/browser details.
3. Test `onnx-community/grounding-dino-tiny-ONNX` against at least 20 phone, 20 tablet and 20 negative clips. Use unique filenames and visible devices for at least five seconds. Include varied angles and confusing objects.
4. Repeat on CPU fallback separately; do not mix hardware results.
5. Review clips and results; copy the passing JSON file to `data/detector-validation.json` (or the configured path).
6. The backend checks at least 90% positive detection per device category, no more than one false-positive negative clip, and p95 latency below 1000ms.
7. Revalidate after changing the model, threshold, worker implementation, or supported hardware/browser.

The model downloads are substantial. Browser compatibility, device visibility, lighting, occlusion, and processing delays affect performance. Monitoring is browser-reported and is **not tamper-proof proctoring**. It cannot detect devices outside the camera's view. An event is not a cheating verdict.

## Cloud deployment

1. Create a Supabase project and run `migrations/001_initial.sql` in its SQL editor.
2. Use the Supabase session pooler Postgres URL with `postgresql+psycopg://` and `sslmode=require`. Keep database and service-role credentials server-side.
3. Create a Hugging Face **Docker Space** and upload this source tree (exclude `.venv`, `.env`, `node_modules`, local `data`, and test outputs).
4. Set Space secrets: `DATABASE_URL`, `APP_SECRET` (at least 32 random characters), `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`.
5. Set `ENVIRONMENT=production`, `EVIDENCE_BUCKET=interview-evidence`, and `PUBLIC_URL` to the HTTPS app URL. Use an available Gemini Flash model via `GEMINI_MODEL`.
6. Deploy the reviewed detector validation file at the configured path before enabling screening. Keep the same `APP_SECRET` across restarts so existing private links continue to work.
7. Run the deployed acceptance checklist in `docs/ACCEPTANCE.md`.

The backend refuses production startup without Postgres, Supabase storage configuration, and a strong application secret. No service keys or cloud accounts are included. Public deployment has not been performed.

Use one Uvicorn process: the database-backed job queue has one transcription consumer. Do not scale to multiple worker processes without adding atomic job claims and distributed rate limiting. Ordinary report data persists in Postgres; audio is temporary and interrupted transcription can require re-entry.

## Privacy and data flow

- Original resumes and raw extracted text are processed transiently and never persisted. Profile sanitization is heuristic; the candidate must review it before external AI use.
- Only approved profile content goes to question generation. Only question/rubric and approved transcript go to evaluation.
- Audio is deleted in a `finally` block after transcription attempts. Local model weights are retained for reuse.
- Face landmarks and ordinary camera frames remain in browser memory. HR device events upload a JPEG from the confirming frame to private storage. Backend re-encoding removes image metadata.
- Candidate/HR report tokens are different, cryptographically derived, and stored as hashes. Account-bound sessions additionally require the signed-in candidate or assigned HR account. Use HTTPS outside localhost. Legacy token-only records remain compatible and should be migrated or expired before production use.
- Create the first administrator with `python -m backend.app.manage create-admin`; administrators create HR and candidate accounts from the portal. Recovery is administrator-mediated and returns a one-use, expiring reset link rather than sending email.
- Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, and `PUBLIC_URL` to send one-use password-reset links directly to the account email. When SMTP is not configured or delivery fails, the request remains available to an administrator without exposing whether an email exists.
- Feelings live in a separate table and endpoint. Sharing is opt-in and revocable; consent changes are recorded with a version and timestamp. Existing downloaded copies cannot be recalled.
- Scores use approved text only. Feelings and camera events are not supplied to the evaluator and do not alter scores or generate hiring recommendations.
- Seven-day expiry blocks access immediately. A five-minute cleanup loop deletes expired rows and pictures while the app is awake, with startup cleanup and retry after storage failure. Sleeping free hosting can delay physical deletion until the app wakes.
- Logs omit request paths/tokens and personal content. Launch Uvicorn with `--no-access-log` as shown.

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
# In frontend:
npm test
npm run build
```

`frontend/scripts/browser-test.mjs` is a repeatable desktop/mobile practice-flow test using an isolated local Chrome profile. It requires a machine that allows Chrome's internal IPC. It also exports sample report PDFs. In the restricted development environment, use the connected browser for visual checks instead; do not interpret a browser-launch failure as an application test result.

See `docs/ACCEPTANCE.md` for what remains to validate with real devices and configured services.
