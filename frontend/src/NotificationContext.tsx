/**
 * DOOF Notification Context
 *
 * Subtle, joke-powered notifications triggered by polling changes.
 * Sound effect plays at low volume on first notification per batch.
 * Anti-spam: 3s cooldown, max 3 visible, only fires on real data changes.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { pickRandom, TOAST_JOKES, IDLE_JOKES, TRAINING_JOKES, type JokeEntry } from "./personality-registry";

export type Notification = {
  id: number;
  text: string;
  detail?: string;
  kind: "change" | "info";
  createdAt: number;
};

type NotificationCtxType = {
  notifications: Notification[];
  push: (text: string, detail?: string, kind?: "change" | "info") => void;
};

const NotificationCtx = createContext<NotificationCtxType>({
  notifications: [],
  push: () => {},
});

/** Get a joke for a change category */
export function jokeForChange(category: string): string {
  const map: Record<string, JokeEntry[]> = {
    training: TRAINING_JOKES,
    memory: IDLE_JOKES,
    approved: TOAST_JOKES,
    feedback: TOAST_JOKES,
    model: IDLE_JOKES,
  };
  const source = map[category] || TOAST_JOKES;
  const pick = pickRandom(source, 1)[0];
  return pick?.text ?? "Something changed.";
}

/** Sound player — loads once, plays at 30% volume */
let audioEl: HTMLAudioElement | null = null;
let audioLoaded = false;

function playNotifSound() {
  try {
    if (!audioEl) {
      audioEl = new Audio("/assets/pierre.mp4");
      audioEl.volume = 0.3;
      audioEl.preload = "auto";
      audioEl.load();
      audioLoaded = true;
    }
    if (audioLoaded && audioEl) {
      audioEl.currentTime = 0;
      audioEl.play().catch(() => {});
    }
  } catch {
    // Sound not available — silent fallback
  }
}

const MAX_VISIBLE = 3;
const COOLDOWN_MS = 3000;
const AUTO_DISMISS_MS = 5000;

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const nextId = useRef(1);
  const lastPushAt = useRef(0);

  const push = useCallback((text: string, detail?: string, kind: "change" | "info" = "change") => {
    const now = Date.now();
    if (now - lastPushAt.current < COOLDOWN_MS) return;
    lastPushAt.current = now;

    const id = nextId.current++;
    const notif: Notification = { id, text, detail, kind, createdAt: now };

    setNotifications((prev) => {
      const next = [...prev, notif];
      // Keep only MAX_VISIBLE most recent
      return next.slice(-MAX_VISIBLE);
    });

    // Play sound on first notification of a batch
    playNotifSound();

    // Auto-dismiss
    setTimeout(() => {
      setNotifications((prev) => prev.filter((n) => n.id !== id));
    }, AUTO_DISMISS_MS);
  }, []);

  const value = useMemo(() => ({ notifications, push }), [notifications, push]);

  return (
    <NotificationCtx.Provider value={value}>
      {children}
    </NotificationCtx.Provider>
  );
}

export function useNotifications() {
  return useContext(NotificationCtx);
}
