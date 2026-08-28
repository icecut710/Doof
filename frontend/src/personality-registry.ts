/**
 * DOOF Personality & Easter-Egg Registry
 *
 * Centralized, human-authored entries only. NO AI-generated content.
 * Future releases add entries here — no UI component rewrites needed.
 *
 * RULES:
 * - Entries are approved product personality
 * - They are NOT training data
 * - They must never feed build_dataset(), tokenizer, approved_examples, or memories
 * - Technical values (GPU, VRAM, training progress) always remain REAL
 */

export type AssetEntry = {
  id: string;
  src: string;
  alt: string;
  /** CSS width for inline usage */
  size?: string;
};

export type JokeEntry = {
  id: string;
  text: string;
  category: "boot" | "status" | "toast" | "idle" | "training" | "sidebar";
  /** Weight for random selection (higher = more likely) */
  weight?: number;
  /** If true, skip in reduced-motion mode */
  motion?: boolean;
  enabled: boolean;
};

export type EasterEggAsset = {
  id: string;
  /** Supabase URL (online fallback) */
  remote: string;
  /** Local bundled path (primary) */
  local: string;
  alt: string;
  /** Max display size */
  maxWidth: string;
  maxHeight: string;
};

/* =========================================================
   APPROVED ASSETS
   ========================================================= */

export const ASSETS: EasterEggAsset[] = [
  {
    id: "walmart-watch",
    remote: "https://ekvjdgxpeusdchwrnlww.supabase.co/storage/v1/object/public/doof-assets/3A76D474-C2F5-4DE4-866A-04211F24EC8B.png",
    local: "/assets/easter-egg-1.png",
    alt: "$10 Walmart watch",
    maxWidth: "48px",
    maxHeight: "48px",
  },
  {
    id: "honda-civic",
    remote: "https://ekvjdgxpeusdchwrnlww.supabase.co/storage/v1/object/public/doof-assets/55055b89d8e5c98dac0fda489720a943-removebg-preview.png",
    local: "/assets/easter-egg-2.png",
    alt: "Honda Civic",
    maxWidth: "80px",
    maxHeight: "40px",
  },
  {
    id: "full-body",
    remote: "https://ekvjdgxpeusdchwrnlww.supabase.co/storage/v1/object/public/doof-assets/ChatGPT_Image_Jun_19_2026_07_14_23_PM-removebg-preview.png",
    local: "/assets/easter-egg-3.png",
    alt: "DOOF",
    maxWidth: "120px",
    maxHeight: "160px",
  },
  {
    id: "massage-chair",
    remote: "https://ekvjdgxpeusdchwrnlww.supabase.co/storage/v1/object/public/doof-assets/image0.jpg",
    local: "/assets/easter-egg-4.png",
    alt: "Massage chair",
    maxWidth: "100px",
    maxHeight: "80px",
  },
];

/* =========================================================
   APPROVED BOOT FLAVOR MESSAGES
   ========================================================= */

export const BOOT_JOKES: JokeEntry[] = [
  { id: "boot-computers", text: "Checking the computers\u2026", category: "boot", weight: 3, enabled: true },
  { id: "boot-microwave", text: "Warming up the giant microwave\u2026", category: "boot", weight: 3, enabled: true },
  { id: "boot-lightspeed", text: "Watching Lightspeed\u2026", category: "boot", weight: 2, enabled: true },
  { id: "boot-blue", text: "Checking whether every assignment is blue\u2026", category: "boot", weight: 2, enabled: true },
  { id: "boot-coop", text: "Inspecting the chicken coop\u2026", category: "boot", weight: 2, enabled: true },
  { id: "boot-tuna", text: "Locating the Big Old Rusty Tuna Can\u2026", category: "boot", weight: 2, enabled: true },
  { id: "boot-civic", text: "Negotiating with the Honda Civic\u2026", category: "boot", weight: 2, enabled: true },
  { id: "boot-redbull", text: "Checking the Red Bull mini-fridge\u2026", category: "boot", weight: 2, enabled: true },
  { id: "boot-business", text: "DOOF is ready for business.", category: "boot", weight: 3, enabled: true },
  { id: "boot-massage", text: "Verifying the massage chair\u2026", category: "boot", weight: 2, enabled: true },
  { id: "boot-shawarma", text: "Reheating shawarmas in the giant microwave\u2026", category: "boot", weight: 2, enabled: true },
  { id: "boot-llc", text: "Filing LLC paperwork with Greta\u2026", category: "boot", weight: 1, enabled: true },
  { id: "boot-naddaf", text: "Consulting the NADDAF Tobacco archives\u2026", category: "boot", weight: 1, enabled: true },
  { id: "boot-jury", text: "Avoiding jury duty\u2026", category: "boot", weight: 1, enabled: true },
  { id: "boot-watches", text: "Synchronizing ten-dollar Walmart watches\u2026", category: "boot", weight: 1, enabled: true },
];

/* =========================================================
   APPROVED STATUS / SIDEBAR / TOAST JOKES
   ========================================================= */

export const STATUS_JOKES: JokeEntry[] = [
  { id: "status-shawarma", text: "Shawarmas: Fresh", category: "status", weight: 4, enabled: true },
  { id: "status-lebanon", text: "Lebanon is secure", category: "status", weight: 3, enabled: true },
  { id: "status-grill", text: "Grill: Uneven heat", category: "status", weight: 2, enabled: true },
  { id: "status-desert", text: "Lost in the desert", category: "status", weight: 2, enabled: true },
  { id: "status-brain", text: "Brain: Cooking", category: "status", weight: 3, enabled: true },
  { id: "status-awake", text: "Brain: Awake", category: "status", weight: 3, enabled: true },
  { id: "status-backup", text: "Backup brain is on duty", category: "status", weight: 2, enabled: true },
  { id: "status-fm", text: "DOOF FM", category: "status", weight: 1, enabled: true },
  { id: "status-open", text: "This grill is open", category: "status", weight: 2, enabled: true },
  { id: "status-house", text: "This grill is for the house", category: "status", weight: 2, enabled: true },
  { id: "status-only", text: "You are the only grill", category: "status", weight: 2, enabled: true },
];

export const SIDEBAR_JOKES: JokeEntry[] = [
  { id: "sidebar-fresh", text: "Shawarmas: Fresh", category: "sidebar", weight: 4, enabled: true },
  { id: "sidebar-desert", text: "Lost in the desert", category: "sidebar", weight: 2, enabled: true },
  { id: "sidebar-open", text: "This grill is open", category: "sidebar", weight: 2, enabled: true },
  { id: "sidebar-house", text: "This grill is for the house", category: "sidebar", weight: 2, enabled: true },
  { id: "sidebar-only", text: "You are the only grill", category: "sidebar", weight: 2, enabled: true },
];

export const TOAST_JOKES: JokeEntry[] = [
  { id: "toast-gpu", text: "GPU is hot and ready. Feed me something heavy.", category: "toast", weight: 2, enabled: true },
  { id: "toast-cpu", text: "Brain is loaded. CPU-only, but we make it work.", category: "toast", weight: 2, enabled: true },
  { id: "toast-nominal", text: "Systems nominal. I only bite when the context window is full.", category: "toast", weight: 2, enabled: true },
  { id: "toast-training", text: "Training complete. The brain grew a little today.", category: "toast", weight: 2, enabled: true },
  { id: "toast-shawarma", text: "Shawarmas are ready.", category: "toast", weight: 1, enabled: true },
  { id: "toast-coop", text: "Chicken coop is secure.", category: "toast", weight: 1, enabled: true },
];

export const IDLE_JOKES: JokeEntry[] = [
  { id: "idle-massage", text: "The massage chair is free if you need it.", category: "idle", weight: 2, enabled: true },
  { id: "idle-fishing", text: "Perfect day for fishing and hunting.", category: "idle", weight: 1, enabled: true },
  { id: "idle-shirt", text: "DOOF is wearing a shirt that matches his.", category: "idle", weight: 1, enabled: true },
  { id: "idle-monitor", text: "The laptop monitor setup is looking great today.", category: "idle", weight: 1, enabled: true },
  { id: "idle-funniest", text: 'Currently searching "Top Ten Funniest Words".', category: "idle", weight: 1, enabled: true },
  { id: "idle-civic", text: "The Honda Civic is parked and ready.", category: "idle", weight: 1, enabled: true },
];

export const TRAINING_JOKES: JokeEntry[] = [
  { id: "train-cooking", text: "Brain: Cooking", category: "training", weight: 3, enabled: true },
  { id: "train-lightspeed", text: "Watching Lightspeed while training\u2026", category: "training", weight: 1, enabled: true },
  { id: "train-blue", text: "All assignments are blue. Training proceeds.", category: "training", weight: 1, enabled: true },
  { id: "train-microwave", text: "Reheating shawarmas while the brain learns.", category: "training", weight: 1, enabled: true },
];

/* =========================================================
   SELECTOR UTILITIES
   ========================================================= */

/**
 * Weighted random pick from a list of enabled entries.
 * Has cross-call rotation memory: the last few picks per list are avoided
 * (unless nothing else is available) so the same joke never repeats back-to-back.
 */
const RECENT_PER_LIST = 2;
const recentPicks = new WeakMap<object, string[]>();

export function pickRandom<T extends { weight?: number; enabled: boolean; id?: string }>(
  entries: T[],
  count: number = 1,
): T[] {
  const enabled = entries.filter((e) => e.enabled);
  if (!enabled.length) return [];

  // Avoid recently-shown entries when there are alternatives
  const recent = recentPicks.get(entries) ?? [];
  const fresh = enabled.filter((e) => !("id" in e && e.id && recent.includes(e.id)));
  const pool = fresh.length ? fresh : enabled;

  const picks: T[] = [];
  const used = new Set<number>();
  for (let i = 0; i < Math.min(count, pool.length); i++) {
    const totalWeight = pool.reduce((s, e, idx) => s + (used.has(idx) ? 0 : e.weight ?? 1), 0);
    if (totalWeight <= 0) break;
    let r = Math.random() * totalWeight;
    for (let j = 0; j < pool.length; j++) {
      if (used.has(j)) continue;
      r -= pool[j].weight ?? 1;
      if (r <= 0) {
        picks.push(pool[j]);
        used.add(j);
        break;
      }
    }
  }

  // Remember what was shown so it doesn't repeat too soon
  if (picks.length && picks.every((p) => "id" in p && typeof p.id === "string")) {
    const next = [...recent, ...picks.map((p) => (p as { id: string }).id)];
    recentPicks.set(entries, next.slice(-RECENT_PER_LIST));
  }
  return picks;
}

/** Get a joke by ID */
export function getJoke(id: string): JokeEntry | undefined {
  return [...BOOT_JOKES, ...STATUS_JOKES, ...SIDEBAR_JOKES, ...TOAST_JOKES, ...IDLE_JOKES, ...TRAINING_JOKES].find(
    (j) => j.id === id,
  );
}

/** Get an asset by ID */
export function getAsset(id: string): EasterEggAsset | undefined {
  return ASSETS.find((a) => a.id === id);
}

/** Get random boot jokes (called once at boot, memoized) */
export function getBootJokes(count: number = 3): JokeEntry[] {
  return pickRandom(BOOT_JOKES, count);
}

/** Get a random toast joke */
export function getToastJoke(): JokeEntry | undefined {
  return pickRandom(TOAST_JOKES, 1)[0];
}

/** Get a random sidebar status line */
export function getSidebarJoke(): JokeEntry | undefined {
  return pickRandom(SIDEBAR_JOKES, 1)[0];
}

/** Get a random idle joke */
export function getIdleJoke(): JokeEntry | undefined {
  return pickRandom(IDLE_JOKES, 1)[0];
}

/** Get a random training joke */
export function getTrainingJoke(): JokeEntry | undefined {
  return pickRandom(TRAINING_JOKES, 1)[0];
}
