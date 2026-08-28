/**
 * DOOF voice. Funny primary + honest technical line.
 *
 * Now backed by the centralized personality registry.
 * Future releases add entries to personality-registry.ts — not here.
 */

import {
  STATUS_JOKES,
  SIDEBAR_JOKES,
  TOAST_JOKES,
  IDLE_JOKES,
  pickRandom,
  type JokeEntry,
} from "./personality-registry";

export type Voice = { label: string; detail: string };

/** Legacy voice lookup — maps old kind strings to registry entries. */
const LEGACY_LINES: Record<string, Voice[]> = {
  healthy: [
    { label: "Shawarmas: Fresh", detail: "All core services are responding normally." },
    { label: "Lebanon is secure", detail: "Runtime, database, and network are healthy." },
  ],
  degraded: [
    { label: "Grill: Uneven heat", detail: "Some services are slow or only partly available." },
  ],
  offline: [
    { label: "Lost in the desert", detail: "The local brain cannot be reached." },
  ],
  processing: [{ label: "Brain: Cooking", detail: "A request is running on the compute pool." }],
  ai: [{ label: "Brain: Awake", detail: "A model is ready for chat." }],
  ai_fallback: [
    { label: "Backup brain is on duty", detail: "The primary model failed. A fallback is answering." },
  ],
  music: [
    { label: "DOOF FM", detail: "Now playing: whatever the hell this is." },
  ],
  contribute_on: [
    { label: "This grill is open", detail: "This machine will accept remote jobs you allowed." },
  ],
  contribute_off: [
    { label: "This grill is for the house", detail: "Remote jobs are off. Local chat still works." },
  ],
  network_empty: [
    { label: "You are the only grill", detail: "No other nodes are online. Local fallback is active." },
  ],
};

/** Get a random joke from a category, falling back to legacy */
function pickFromCategory(category: JokeEntry["category"], fallback: string): Voice {
  const sourceMap: Record<string, JokeEntry[]> = {
    status: STATUS_JOKES,
    sidebar: SIDEBAR_JOKES,
    toast: TOAST_JOKES,
    idle: IDLE_JOKES,
  };
  const source = sourceMap[category];
  if (source) {
    const pick = pickRandom(source, 1)[0];
    if (pick) return { label: pick.text, detail: "" };
  }
  // Fallback to legacy
  const legacy = LEGACY_LINES[fallback] || LEGACY_LINES.healthy;
  return legacy[0];
}

export function voice(kind: string): Voice {
  // Map legacy kinds to categories
  const categoryMap: Record<string, JokeEntry["category"]> = {
    healthy: "status",
    degraded: "status",
    offline: "status",
    processing: "training",
    ai: "status",
    ai_fallback: "status",
    music: "idle",
    contribute_on: "sidebar",
    contribute_off: "sidebar",
    network_empty: "sidebar",
  };

  const category = categoryMap[kind];
  if (category) {
    return pickFromCategory(category, kind);
  }

  // Unknown kind — use legacy fallback
  const opts = LEGACY_LINES[kind] || LEGACY_LINES.healthy;
  return opts[0];
}

/** Get a random sidebar footer line */
export function sidebarFooter(online: boolean): string {
  if (!online) return "Lost in the desert";
  const pick = pickRandom(SIDEBAR_JOKES, 1)[0];
  return pick?.text ?? "Shawarmas: Fresh";
}

/** Get a random sidebar detail line */
export function sidebarDetail(online: boolean): string {
  if (!online) return "The brain is unreachable";
  return "All core services responding";
}

/** Get a random toast joke for training completion */
export function trainingToast(): string {
  const pick = pickRandom(TOAST_JOKES, 1)[0];
  return pick?.text ?? "Training complete.";
}

/** Get a random idle joke */
export function idleJoke(): string {
  const pick = pickRandom(IDLE_JOKES, 1)[0];
  return pick?.text ?? "";
}
