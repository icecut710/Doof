/** DOOF voice. Funny primary + honest technical line. */

export type Voice = { label: string; detail: string };

const LINES: Record<string, Voice[]> = {
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

export function voice(kind: string): Voice {
  const opts = LINES[kind] || LINES.healthy;
  return opts[0];
}
