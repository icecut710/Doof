# DOOF v0.2 Alpha apply note

README, version, migration 002, and CLI are already on main.

Full `doof/api.py` and `frontend/src/App.tsx` for v0.2 (auth, Memory, Network, brain versions) are prepared; if they are not yet on this branch after the next push, pull latest main and re-run:

```bash
git pull origin main
python -m doof serve
cd frontend && npm install && npm run build && npm run preview
```

First signup becomes **Owner**. Friends sign up as **Trusted Users**. Memory is permanent. Training bumps brain version. Network heartbeats register workers.
