# hello-world

This project is building an Outlook automation that:

1. Scans recent email senders.
2. Classifies each sender as trusted/review/unsubscribe-candidate.
3. Shows you a batch list first.
4. Executes unsubscribes only after your explicit command: `OK unsubscribe from all`.

## What I am making now

A practical **phase-1 prototype** you can run locally today:

- `prototype/unsubscribe_planner.py`
- Inputs: `sample_messages.json`, `allowlist.txt`, `denylist.txt`
- Output: trusted/review/candidate report
- Approval model: batch stays pending unless you pass `--approve-all`

## Quick start

```bash
python3 prototype/unsubscribe_planner.py \
  --input prototype/sample_messages.json \
  --allowlist prototype/allowlist.txt \
  --denylist prototype/denylist.txt
```

Approve and execute the current batch:

```bash
python3 prototype/unsubscribe_planner.py \
  --input prototype/sample_messages.json \
  --allowlist prototype/allowlist.txt \
  --denylist prototype/denylist.txt \
  --approve-all
```

## Next implementation plan

1. Replace local JSON input with Microsoft Graph (`/me/messages`) via OAuth.
2. Persist sender history + batches in SQLite/Postgres.
3. Add approval commands (`show candidates`, `OK unsubscribe from all`, `unsubscribe batch <id>`).
4. Add safe execution for `List-Unsubscribe` and fallback block/junk rules.
5. Schedule regular runs (cron/Quartz).

See `docs/outlook-trusted-unsubscribe-automation.md` for the full architecture.
