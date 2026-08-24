// In-memory API response cache — makes tab switching feel instantaneous.
// Strategy: serve cached data immediately, refresh in the background
// (stale-while-revalidate). Mutations invalidate their resource.

type Entry = { data: unknown; at: number };

const store = new Map<string, Entry>();

export function cacheGet<T>(key: string): T | null {
  const e = store.get(key);
  return e ? (e.data as T) : null;
}

export function cacheAge(key: string): number | null {
  const e = store.get(key);
  return e ? e.at : null;
}

export function cacheSet(key: string, data: unknown) {
  store.set(key, { data, at: Date.now() });
}

export function cacheInvalidate(prefix: string) {
  for (const k of store.keys()) {
    if (k.startsWith(prefix)) store.delete(k);
  }
}

export function cacheClear() {
  store.clear();
}

// Identical in-flight GETs share one network request.
const inflight = new Map<string, Promise<unknown>>();

export function dedupe<T>(key: string, run: () => Promise<T>): Promise<T> {
  const existing = inflight.get(key) as Promise<T> | undefined;
  if (existing) return existing;
  const p = run().finally(() => inflight.delete(key));
  inflight.set(key, p);
  return p;
}
