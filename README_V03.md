# DOOF v0.3 — Production Pass Notes

## What landed on `fix/production-polish`

### Preserved
- Chat, Memory, Training, Status, Models, Settings
- Supabase + Google + email verification
- Compute pool (typed jobs, scheduler, consent OFF by default)
- Per-machine IDs, heartbeats, LAN optional + Supabase/NAT queue
- Torch lazy load + torchdistribute protection
- Boot animation + personality system

### New
1. **Global network** — LAN remains an optimization; Supabase job queue + outbound poll is the primary path across NATs.
2. **Auto-updates** — `doof/updates/` checks a release manifest (SHA-256 verify, stage, rollback marker). UI: Updates tab.
3. **Admin Control Room** — role-gated (`profiles.role` in `admin`/`owner`). Health board, pool pause/resume, node list.
4. **Expanded contribution limits** — max_cpu/gpu/vram, allow_train/inference/embedding, only_while_open.
5. **Migration 005** — roles, release_manifests, audit_events, pool_control, extra node columns.
6. **Tests** — `test_updates.py`, `test_multi_node.py` (simulated A/B).

### Version
- Client/backend: **0.3.0**
- Protocol: **1**

## Pull locally

```bash
git fetch origin
git checkout fix/production-polish
git pull origin fix/production-polish
```

Or from main:

```bash
git clone https://github.com/icecut710/Doof.git
cd Doof
git checkout fix/production-polish
```

## Apply migration

Run `supabase/migrations/005_admin_updates.sql` on your Supabase project (SQL editor or CLI).

Promote yourself to owner if needed:

```sql
update public.profiles set role = 'owner' where email = 'you@example.com';
```

## Windows build

```bat
cd Doof
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller PySide6
cd frontend && npm install && npm run build && cd ..
python packaging/build_exe.py
```

Output: `dist/DOOF/DOOF.exe`

## Wire API hooks (important)

`doof/api_extra.py` provides `/api/updates/*` and `/api/admin/*`. Ensure `Handler.do_GET` / `do_POST` call:

```python
from doof.api_extra import try_handle
if try_handle(self, "GET", path, get_profile=lambda: _profile_from_token(_bearer_token(self)), read_json=lambda: {}):
    return
```

If your local tree already has this call, you are done. If not, add it at the top of `do_GET`/`do_POST` after `path = urlparse(...).path`.

## Honest limitations

- Real two-machine job claim across different networks was **not** executed in this environment (no dual Windows hosts). Use `tests/test_multi_node.py` as the deterministic harness; validate on your PC + friend PC.
- Full EXE binary swap after update still needs a small helper script on Windows (overlay path works for pure assets).
- Google OAuth click-through not re-tested live here.
- Set `DOOF_UPDATE_MANIFEST_URL` and fill `releases/manifest.json` download_url + sha256 when you publish a real build.

## PR

https://github.com/icecut710/Doof/pull/2
