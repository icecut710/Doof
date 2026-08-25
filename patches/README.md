# DOOF v0.3 production patches

## Status

The full production fixes live on the agent worktree commits:

- `f84ac1722fdb3b3eff9116b24d61d58011b52037` — AI, memory→training, UI, updates, rewards
- `2d9596e4d0ea7bfed7d8b348138b5610363b05a7` — drop runtime data from git

## Apply from your machine

If GitHub is missing the large file updates, from a clone of `fix/production-polish`:

```bash
git fetch origin
git checkout fix/production-polish
# Prefer pushing from the agent worktree if you still have it:
#   cd /tmp/doof-work && git push origin fix/production-polish
```

Or ask the agent to finish pushing `doof/api.py`, `doof/compute/pool.py`, and `frontend/src/App.tsx` via the GitHub connector.

## What the production pass includes

- No universal "Add it in Memory, then train" refusal
- Pool cloud path = DOOF-hosted only (not xAI)
- Memory promote API + UI
- Updates / Admin / Rewards nav
- Device preference + train errors
- finish_pending_update on API startup
- v0.3 branding
- Database wording in Status
