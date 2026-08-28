/**
 * Offline-first asset loader for easter-egg images.
 *
 * Strategy:
 * 1. Try bundled local asset first (fast, no network)
 * 2. On failure, silently try Supabase remote URL
 * 3. On any failure, return null (never block UI)
 *
 * Assets are cached in memory after first load.
 */

import { useEffect, useState } from "react";
import { ASSETS } from "./personality-registry";

const assetCache = new Map<string, string | null>();

type UseEasterEggAssetResult = {
  src: string | null;
  loaded: boolean;
};

/**
 * Load an easter-egg asset with offline-first fallback.
 * Returns { src, loaded } — src is null if both local and remote failed.
 */
export function useEasterEggAsset(assetId: string): UseEasterEggAssetResult {
  const [src, setSrc] = useState<string | null>(() => assetCache.get(assetId) ?? null);
  const [loaded, setLoaded] = useState(() => assetCache.has(assetId));

  useEffect(() => {
    if (assetCache.has(assetId)) {
      setSrc(assetCache.get(assetId) ?? null);
      setLoaded(true);
      return;
    }

    const asset = ASSETS.find((a) => a.id === assetId);
    if (!asset) {
      assetCache.set(assetId, null);
      setSrc(null);
      setLoaded(true);
      return;
    }

    let alive = true;

    // Try local first
    const img = new Image();
    img.onload = () => {
      if (alive) {
        assetCache.set(assetId, asset.local);
        setSrc(asset.local);
        setLoaded(true);
      }
    };
    img.onerror = () => {
      // Try remote
      const img2 = new Image();
      img2.onload = () => {
        if (alive) {
          assetCache.set(assetId, asset.remote);
          setSrc(asset.remote);
          setLoaded(true);
        }
      };
      img2.onerror = () => {
        if (alive) {
          assetCache.set(assetId, null);
          setSrc(null);
          setLoaded(true);
        }
      };
      img2.src = asset.remote;
    };
    img.src = asset.local;

    return () => {
      alive = false;
    };
  }, [assetId]);

  return { src, loaded };
}

/**
 * Preload all easter-egg assets in background (call once at app mount).
 * Does not block — fires and forgets.
 */
export function preloadEasterEggAssets(): void {
  for (const asset of ASSETS) {
    if (assetCache.has(asset.id)) continue;
    const img = new Image();
    img.onload = () => assetCache.set(asset.id, asset.local);
    img.onerror = () => {
      const img2 = new Image();
      img2.onload = () => assetCache.set(asset.id, asset.remote);
      img2.onerror = () => assetCache.set(asset.id, null);
      img2.src = asset.remote;
    };
    img.src = asset.local;
  }
}
