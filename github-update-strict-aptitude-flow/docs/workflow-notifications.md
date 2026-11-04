# Round and hiring-stage notifications

## Upload

Extract `github-update-workflow-notifications.zip` into the latest AI Interviewer repository, keeping its folder paths. Commit all included files and deploy that commit. This is an incremental update for the existing React/FastAPI application and requires the preceding sequential-round update. It does not deploy itself or send a test email.

Startup creates the new `workflow_notifications` table using the application's existing SQLAlchemy setup. No existing table is replaced. The name `notifications` is already used for HR security events, so this additive table stores the requested fields: id, candidate_id, application_id, round_no, type, title, message, is_read, email_status, created_at. It has a unique constraint on application_id/round_no/type. Existing candidate inbox and email-outbox rows share its deterministic ID.

## Behavior

- `complete_round()` calls `notifier.notify()` inside its database transaction. A rollback removes the notification, inbox entry and queued email together.
- A pass queues `next_round`, naming the next round and using its actual assignment link and deadline. HR's initial shortlisting approves standard-template resume screening and queues this event once.
- A failure queues `rejected`, naming the round and using polite wording without exposing internal HR notes or unpublished scores.
- Final selection queues `selected`. Custom pipelines without a manual final round receive `rounds_completed` instead of a premature selection message.
- Hiring-stage changes also call the notifier. Nonterminal stage changes produce `stage_*` updates; unchanged stages do not create additional events.
- Manual interviews have no online assessment or deadline until HR schedules them. Their notification links to the application and says HR will share scheduling details, rather than inventing a start link or deadline. The existing scheduling invitation follows once HR sets the schedule.
- Existing round invitations and scheduling reminders remain available. The old separate shortlist email is replaced to avoid sending two shortlist messages.

Candidates see a bell/unread count, **Messages**, and an unread new-round banner under **My interviews**. Opening a message marks it read in the database and refreshes the count. HR can open **Candidates → View profile → Notification history** to see type, time and email status, or retry a failed email. All HR access is scoped to their organization.

## Email configuration

Settings load from `.env` locally or environment variables in deployment. Never commit credentials. For SMTP:

```dotenv
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.your-provider.com
SMTP_PORT=587
SMTP_USER=your-smtp-user
SMTP_PASSWORD=your-smtp-password
SMTP_FROM=interviews@your-domain.com
SMTP_USE_TLS=true
PUBLIC_URL=https://your-deployed-app.example
DRY_RUN=false
```

Port 465 uses implicit TLS. Port 587 uses STARTTLS when SMTP_USE_TLS is true. The existing Brevo integration remains supported with `EMAIL_PROVIDER=brevo`, `BREVO_API_KEY`, and `EMAIL_FROM`; do not replace a working Brevo configuration just to install this patch. Plain text and escaped HTML bodies are supported by both transports.

Set `DRY_RUN=true` in a development/test environment to print email messages to the server console without contacting the provider. The notification status becomes `dry_run`, not `sent`. This setting applies to the shared email transport, including recovery emails. Use test candidate data because the console output includes email content. Turn it off before testing actual delivery.

Delivery happens after commit through the existing background worker. Failure never rolls back round progression or removes the in-app message. `email_status` records a sanitized `failed: <reason>` without credentials/provider response bodies. Automatic retries use backoff, up to five attempts. **Retry email** resets the existing outbox row; it does not add a notification. An unconfigured provider leaves the outbox available for delivery once configured and shows a failed status to HR.

`sent` means accepted by the transport/provider, not confirmed inbox delivery. Database idempotency prevents duplicate events and duplicate enqueueing for repeated decisions. SMTP cannot guarantee exactly-once delivery if a process crashes after the server accepts a message but before the app records success; a stable Message-ID is used, but recipient servers need not deduplicate it.

## Verification

From the repository root, with backend dependencies installed:

```powershell
python -m pytest backend/tests/test_workflow_notifications.py -q
python -m pytest backend/tests -q
cd frontend
npm test
npm run build
node scripts/workflow-messages-browser-test.mjs
```

The backend tests cover round 1 → next round, round 3 failure, six-round selection, duplicate decisions, stage-dropdown rejection, retry after transport failure, dry run, missing configuration, transaction rollback, and organization/candidate access controls. Frontend tests cover message routing, unread/expired banners and HR retry rendering. The browser script uses mocked APIs and checks opening a message, persisted read state, bell refresh, banner removal and mobile width.

TypeScript, frontend tests and production build passed during implementation. The automated browser run was blocked at Chrome launch with `spawn EPERM`; it was not counted as passed. No live SMTP/Brevo delivery or production deployment was performed.
