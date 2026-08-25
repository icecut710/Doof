# DOOF v0.3.0

**Private collaborative AI OS — local-first shared brain.**

DOOF is a continuously improving local-first AI system where knowledge persists, training folds approved memory into versioned brains, and connected machines can contribute compute without splitting model tensors across PCs.

## v0.3

- Chat, Memory, Training, Status, Models, Settings
- Local accounts plus Supabase-backed auth when configured
- Persistent per-machine IDs and node heartbeats
- Compute pool with typed jobs, scheduler, consent-off-by-default contribution controls
- Supabase job queue for cross-network/NAT workers; LAN is an optimization
- Hosted-brain inference path; no dependency on a third-party xAI runtime
- Auto-update manifest verification and rollback marker support
- Updates UI and role-gated Admin Control Room
- Expanded CPU/GPU/VRAM contribution limits and train/inference/embedding permissions
- Migration `005_admin_updates.sql`
- v0.3 tests for update handling and multi-node scheduling

## Version

- Client/backend: **0.3.0**
- Protocol: **1**

## Quick start — Windows

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller PySide6
cd frontend
npm install
npm run build
cd ..
python packaging/build_exe.py
```

Output: `dist/DOOF/DOOF.exe`

Or launch the development application with:

```bat
python -m doof gui
```

## v0.3 database migration

Apply `supabase/migrations/005_admin_updates.sql` after the earlier DOOF migrations.

To promote the first administrator:

```sql
update public.profiles set role = 'owner' where email = 'you@example.com';
```

## Compute model

DOOF shares **jobs**, not model tensors. A node claims one supported job, executes it locally, and reports the result. Supabase is the cross-network control plane; outbound polling works through NAT. Contribution is disabled by default until the user opts in.

## Updates

`doof/updates/` supports release-manifest checks, SHA-256 verification, staging, and rollback markers. Set `DOOF_UPDATE_MANIFEST_URL` when publishing a real release manifest.

## Honest limitations

- A real two-machine cross-network run still needs validation on two physical machines; `tests/test_multi_node.py` is the deterministic harness.
- A Windows EXE binary swap still needs a small overlay helper for full executable replacement.
- OAuth click-through must be tested against the configured Supabase project.

DOOF · local-first · shared brain · cinematic control center
