"""DOOF voice — centralized, tasteful, never randomizes technical meaning.

Funny primary label + a smaller honest explanation. Jokes live here so the
rest of the app does not scatter shawarma copy.
"""
from __future__ import annotations

import hashlib
import random
from typing import Any

# (primary, technical) — primary is the joke; technical is always true.
_LINES: dict[str, list[tuple[str, str]]] = {
    "healthy": [
        ("Shawarmas: Fresh", "All core services are responding normally."),
        ("Lebanon is secure", "Runtime, database, and network are healthy."),
        ("Grill: Hot", "This machine is ready to cook."),
        ("Naddaf has entered the compute pool", "An additional contributor is online."),
        ("Red Bull reserves nominal", "Energy reserves are healthy."),
    ],
    "degraded": [
        ("Grill: Uneven heat", "Some services are slow or only partly available."),
        ("Shawarma is a little dry", "DOOF is up, but a backup path is in use."),
    ],
    "offline": [
        ("Lost in the desert", "The local brain cannot be reached."),
        ("Closed for lunch", "DOOF is offline until the runtime comes back."),
    ],
    "processing": [
        ("Brain: Cooking", "A request is running on the compute pool."),
        ("Sharpening the knife", "Work is in progress."),
    ],
    "overloaded": [
        ("Line out the door", "This node is at capacity. New jobs will wait."),
        ("Too many orders", "Load is high; extra work is being deferred."),
    ],
    "network": [
        ("Calling Lebanon", "Looking for other DOOF nodes."),
        ("The table is set", "Friends on this network can share compute."),
        ("The waterfountain has achieved consciousness", "The mesh network is fully aware."),
    ],
    "network_empty": [
        ("You are the only grill", "No other nodes are online. Local fallback is active."),
        ("Solo shift", "The compute pool has one machine: this one."),
    ],
    "ai": [
        ("Brain: Awake", "A local or remote model is ready for chat."),
        ("The secret recipe is loaded", "Inference is available."),
        ("The brain is thinking way too hard", "The model is under heavy load."),
    ],
    "ai_fallback": [
        ("Backup brain is on duty", "The primary model failed. A fallback is answering."),
        ("Cooking from memory", "Local weights are unavailable; shared memory is in use."),
        ("Borrowing compute from the smartest computer in the room", "A stronger model is handling this."),
        ("Convincing the model to lock in", "Persuading the fallback to give its best output."),
    ],
    "ai_down": [
        ("The local brain failed to start", "Chat fell back so the app stays usable."),
        ("No fire in the grill", "No model provider is available right now."),
    ],
    "music": [
        ("DOOF FM", "Ambient audio after sign-in. Mute anytime."),
        ("Now playing: whatever the hell this is", "Quiet loop. It will not block the UI."),
    ],
    "memory": [
        ("The family recipes", "Permanent shared memory for this brain."),
    ],
    "cpu": [
        ("Hands: Ready", "CPU inference is available on this machine."),
    ],
    "gpu": [
        ("Grill: Hot", "A GPU is available for heavier jobs."),
        ("The charcoal is lit", "CUDA/MPS can take GPU work."),
    ],
    "gpu_none": [
        ("Street cart energy", "CPU only — still a real grill, just slower."),
    ],
    "errors": [
        ("Something spilled in the kitchen", "A problem was caught. Details are folded away."),
    ],
    "loading": [
        ("Warming up the shawarma machine…", "Starting the local runtime."),
        ("Checking the grill…", "Opening the local database."),
        ("Calling Lebanon…", "Connecting cloud services, if configured."),
        ("Finding the brain…", "Checking the AI runtime without forcing a heavy load."),
        ("Checking the table…", "Looking for other DOOF nodes."),
        ("DOOF is thinking about it…", "Finishing startup."),
        ("Shawarmas: Fresh", "Ready."),
        ("Naddaf is negotiating with the GPU", "Hardware initialization in progress."),
        ("Teaching the neurons in the back row", "Warming up the model."),
        ("Checking classroom waterfountain pressure", "Verifying resource availability."),
        ("DOOF is pretending this was intentional", "Something unexpected happened, but it is fine."),
    ],
    "contribute_on": [
        ("This grill is open", "This machine will accept remote jobs you allowed."),
    ],
    "contribute_off": [
        ("This grill is for the house", "Remote jobs are off. Local chat still works."),
    ],
    "job_remote": [
        ("Sent to a stronger grill", "The scheduler routed this job to another node."),
    ],
    "job_local": [
        ("Cooking here", "No better node was free, so this machine handled it."),
    ],
    "cloud_connected": [
        ("Lebanon is on the line", "Supabase is connected. Shared state can sync."),
    ],
    "cloud_syncing": [
        ("Wrapping the order", "Syncing with the cloud control plane."),
    ],
    "cloud_offline": [
        ("Local kitchen only", "Cloud is not configured or not reachable."),
    ],
    "auth_google_ready": [
        ("Google is at the door", "Google sign-in is configured and available."),
    ],
    "auth_google_down": [
        ("Google took a smoke break", "Google sign-in is configured but not answering."),
    ],
    "auth_google_off": [
        ("No Google tonight", "Google sign-in is not configured on this brain."),
    ],
    "update_ready": [
        ("DOOF got less stupid", "A newer version is available."),
    ],
    "update_current": [
        ("Shawarmas are current", "You are on the latest compatible release."),
    ],
    "update_failed": [
        ("The upgrade order fell through", "Your current version is unchanged."),
    ],
    "work_along": [
        ("Work-A-Long protocol", "A collaborator is helping with the order."),
        ("Consulting the sacred Work-A-Long", "Distributed tasks are in progress."),
        ("Refilling the Classroom Waterfountain", "Pausing to hydrate the compute pool."),
    ],
    "hardware_active": [
        ("DOOF is using your GPU for an active AI workload", "The grill is running hot."),
    ],
    "hardware_idle": [
        ("DOOF compute idle", "The GPU is available but not cooking."),
        ("Grill cooling down", "Hardware resources are resting."),
    ],
    "update_checking": [
        ("Checking for updates...", "Querying the package index."),
        ("Asking Lebanon if there's a newer version", "Reaching out for version info."),
    ],
    "update_found": [
        ("New DOOF available", "A newer release was found."),
        ("DOOF got less stupid", "An upgrade is ready to apply."),
    ],
    "update_apply": [
        ("Applying update...", "Swapping in the new release."),
        ("Swapping the shawarma on the grill", "The update is being installed."),
    ],
    "neuralshawarma": [
        ("Neural Shawarma Index: optimal", "All brain cells are freshly wrapped."),
        ("The neurons are well-seasoned", "Model weights are loaded and ready."),
    ],
    "compute_goblins": [
        ("Compute goblins are resting", "Background workers are idle."),
        ("The goblins want more VRAM", "Workers are available but need GPU time."),
        ("Goblins dispatched", "Compute workers are active on a job."),
    ],
    "hallway_compute": [
        ("Hallway compute is live", "LAN nodes are sharing work."),
        ("The hallway is quiet", "No peer nodes are active right now."),
    ],
    "cafeteria_network": [
        ("Cafeteria network: operational", "The shared state is synchronized."),
        ("Lunch rush incoming", "Multiple clients are syncing."),
    ],
    "emergency_braincell": [
        ("Emergency braincell reserve: stocked", "Fallback knowledge base is loaded."),
        ("Last braincell: deployed", "The final fallback has been activated."),
    ],
    "rusty_tuna": [
        ("Rusty Tuna Can Protocol active", "Using minimal resources."),
        ("The tuna can is warm", "Running in low-resource mode."),
    ],
    "brain_update": [
        ("Brain update available", "A newer model is ready to download."),
        ("Fresh neurons delivered", "New model weights have been loaded."),
        ("The brain got a haircut", "Model has been updated."),
    ],
}


def pick(kind: str, *, seed: str | None = None) -> tuple[str, str]:
    options = _LINES.get(kind) or _LINES["errors"]
    if seed is None:
        return random.choice(options)
    h = hashlib.sha256(f"{kind}:{seed}".encode()).digest()
    return options[int.from_bytes(h[:2], "big") % len(options)]


def boot_copy(phase: str) -> tuple[str, str]:
    mapping = {
        "runtime": "loading",
        "database": "loading",
        "cloud": "loading",
        "ai": "loading",
        "network": "loading",
        "ready": "healthy",
        "failed": "offline",
    }
    order = ["runtime", "database", "cloud", "ai", "network", "ready"]
    lines = _LINES["loading"]
    if phase == "failed":
        return _LINES["offline"][0]
    if phase == "ready":
        return _LINES["healthy"][0]
    if phase in order:
        return lines[min(order.index(phase), len(lines) - 1)]
    return pick(mapping.get(phase, "loading"))


def node_nickname(name: str, gpu: str | None, is_local: bool) -> str:
    if is_local:
        return f"{name} · this grill"
    gpu_l = (gpu or "").lower()
    if "rtx" in gpu_l or "cuda" in gpu_l or "nvidia" in gpu_l:
        return f"{name} · the hot grill"
    if not gpu or gpu.upper() == "CPU":
        return f"{name} · street cart"
    return name


def health_kind(*, online: bool, degraded: bool, busy: bool) -> str:
    if not online:
        return "offline"
    if busy:
        return "processing"
    if degraded:
        return "degraded"
    return "healthy"


def as_dict(kind: str, **extra: Any) -> dict[str, Any]:
    primary, technical = pick(kind)
    out: dict[str, Any] = {"kind": kind, "label": primary, "detail": technical}
    out.update(extra)
    return out


def random_loading() -> str:
    return random.choice(_LINES["loading"])[0]
