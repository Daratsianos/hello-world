# Outlook Trusted Sender Review + Unsubscribe Automation

This document lays out a **safe, two-step automation** for Outlook:

1. Fetch recent email senders.
2. Classify them as trusted vs not trusted.
3. Present a review list.
4. Wait for explicit approval (`"OK, unsubscribe from all"`).
5. Execute unsubscribes.
6. Run on a schedule.

## Important constraints

- Any inbox access requires user authentication and consent (Microsoft Graph OAuth).
- Unsubscribe actions are provider- and sender-dependent:
  - Preferred: `List-Unsubscribe` headers (`mailto` or one-click URL).
  - Fallback: move to junk/delete + block sender when unsubscribe is unavailable.
- You should never auto-unsubscribe without explicit approval for each batch.

## Recommended architecture

- **Language/Runtime:** Java 21.
- **Scheduler:** cron (or Quartz in-app scheduler).
- **Email API:** Microsoft Graph API (`Mail.Read`, `Mail.ReadWrite`, `MailboxSettings.Read`, minimal scopes).
- **Storage:** SQLite/Postgres for sender history and user decisions.
- **Policy engine:** weighted trust score + allow/deny lists.
- **Approval channel:** chat command, web UI button, or email reply token.

## Data model

### `sender_profile`
- `sender_domain` (PK)
- `sender_email`
- `first_seen_at`
- `last_seen_at`
- `messages_30d`
- `opened_30d`
- `replied_30d`
- `clicked_30d`
- `contains_invoice_keywords` (bool)
- `contains_security_keywords` (bool)
- `list_unsubscribe_available` (bool)
- `trust_score` (0-100)
- `status` (`trusted`, `review`, `candidate_unsubscribe`, `blocked`)

### `unsubscribe_batch`
- `batch_id` (PK)
- `created_at`
- `status` (`pending_approval`, `approved`, `executed`, `expired`)

### `unsubscribe_batch_item`
- `batch_id`
- `sender_domain`
- `reason`
- `action` (`unsubscribe_header`, `block_sender`, `move_to_junk`)
- `executed_at`
- `execution_result`

## Trust scoring example

Start from 50 and adjust:

- +25 if sender in manual allowlist.
- +20 if you replied in last 90 days.
- +10 if messages include work/billing/security keywords.
- -20 if never opened in 90 days.
- -15 if high volume (>10/week) and low engagement.
- -25 if marketing/newsletter and no clicks/replies ever.
- -30 if user previously unsubscribed similar sender.

Status mapping:

- `>= 70`: trusted
- `40..69`: review
- `< 40`: candidate_unsubscribe

## Batch flow

1. Scheduled job runs daily.
2. Pull recent messages and update sender profiles.
3. Build candidate list (`candidate_unsubscribe`).
4. Create `unsubscribe_batch` with itemized reasons.
5. Send summary to user:
   - sender
   - trust score
   - reason
   - planned action
6. Wait for approval command:
   - `OK unsubscribe from all` (all in batch)
   - `unsubscribe batch <id>`
   - optional future: per-sender approvals
7. Execute actions and log results.

## Microsoft Graph implementation notes

- Read messages: `/me/messages?$select=from,subject,receivedDateTime,internetMessageHeaders`
- Parse `internetMessageHeaders` for `List-Unsubscribe` and `List-Unsubscribe-Post`.
- For `mailto` unsubscribe: send templated message to target address.
- For one-click URL unsubscribe:
  - only allow HTTPS
  - validate domain against sender domain or known vendor list
  - use safe HTTP client with strict timeout and redirect limits
- If no unsubscribe path, fallback to block/move-to-junk rule.

## Safety guardrails

- Require explicit approval for each batch (do not auto-execute).
- Expire batch approvals after 24 hours.
- Max unsubscribes per run (e.g., 50).
- Keep immutable audit log of every action.
- Dry-run mode for first week.

## Suggested command contract

### User-facing
- `show unsubscribe candidates`
- `show trusted senders`
- `OK unsubscribe from all`
- `unsubscribe batch <batch_id>`
- `trust <sender@domain.com>`
- `never unsubscribe <domain.com>`

### Internal API
- `POST /automation/run-scan`
- `GET /automation/batches/{id}`
- `POST /automation/batches/{id}/approve`
- `POST /automation/batches/{id}/execute`

## Minimal rollout plan

1. Build read-only scanner + trust scoring report.
2. Add approval workflow.
3. Add unsubscribe execution for `List-Unsubscribe` only.
4. Add block/junk fallback.
5. Tune trust weights from your behavior data.

