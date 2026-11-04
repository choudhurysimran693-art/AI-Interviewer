# Sequential round workflow update

This update targets the existing React + FastAPI application. The workspace does not contain the described Streamlit app, components, widgets, styles, or mock_data modules. It preserves the current database and interview flow instead of introducing a second application.

## Files and responsibilities

- `backend/app/round_engine.py`: central reviewed-outcome transition, authorization, prior-round checks, score validation, next-round invitation and final hiring transition.
- `backend/app/rounds.py`: existing round API, history, initialization and compatibility wrapper for the engine.
- `backend/app/main.py`: checks previous rounds before starting an assigned interview.
- `frontend/src/Rounds.tsx` and `round-workflow.css`: current/locked/passed/failed round presentation and saved-attempt resume action.
- `backend/tests/test_sequential_progression.py`: pass-all-six, fail-at-three, skip prevention and resume metadata tests.
- `frontend/src/Rounds.test.tsx`: candidate actions and recruiter-only final decision controls.

## Workflow

1. HR configures the standard six-round template for a role before candidates enter its pipeline.
2. HR reviews the application and shortlists it. The existing workflow creates the configured round records at this point; shortlisting approves the template's resume screening round.
3. The current assessment displays **Start Round**. An already-started assessment displays **Resume Round**, which restores its existing session rather than creating another attempt.
4. Submitted assessments retain their results and await HR review. A reviewed pass opens only the next round. A reviewed failure rejects the application and leaves later rounds locked.
5. The final interview is scheduled and decided by HR. **Select candidate** uses the existing `hired` status and vacancy accounting; **Reject candidate** records failure.

The existing persisted session contains answers, question position and timing. The backend rejects starting or deciding a later round while an earlier round remains unpassed. Decision recording and successor invitation run within the caller's database transaction.

Reference score recommendations are 60/50/60/60/55 percent for rounds 1–5. They are not a new automatic hiring policy. Existing explicitly configured aptitude threshold behavior is retained. Candidate history continues to respect the existing score visibility rules.

## Scope compared with the Streamlit specification

This is an incremental progression/resume fix, not a full implementation of that specification. It retains the production statuses (`invited`, `completed`, `awaiting_scheduling`, etc.), creates rounds at shortlisting rather than application submission, and uses `hired` rather than `selected`. The `HANDLERS` dictionary contains screen/threshold metadata, not callable Streamlit renderers. It does not add a new R1 semantic upload screen, mixed short-answer R3 assessment, automatic threshold decisions for every round, or voice/behavior-weighted hiring scores. Existing assessment and interview screens remain in use.

## Upload and run

Extract `github-update-sequential-rounds.zip` and copy its files into the matching paths of the latest AI Interviewer repository, including new files. This patch depends on the existing application; it is not a standalone project archive. Commit the files and deploy the updated commit using the existing deployment configuration. No secrets or database files are included.

For local checks from the repository root (activate your backend environment first):

```powershell
python -m pytest backend/tests/test_sequential_progression.py -q
python -m pytest backend/tests -q
cd frontend
npm test
npm run build
```

The pass-all-six and fail-at-round-three simulations are separate parametrized cases in `test_sequential_progression.py`. They use an isolated test database and do not send real emails. To run one independently, add `-k pass-all-six` or `-k fail-at-round-three`.

For a manual check, use a test role with the six-round template, shortlist a test application, start and reload round 2, verify **Resume Round**, submit and review it, and check that only round 3 opens. Confirm a failed round leaves later rounds locked. Complete the remaining rounds and schedule the final manual interview before recording its decision.
