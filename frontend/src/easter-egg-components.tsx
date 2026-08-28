/**
 * Easter-egg visual components.
 *
 * These render approved assets in subtle, non-blocking ways.
 * All components silently degrade if assets fail to load.
 * Never block boot, login, chat, training, or navigation.
 */

import { useState, useEffect, useCallback } from "react";
import { useEasterEggAsset } from "./easter-egg-assets";

/* =========================================================
   HONDA CIVIC — tiny car driving across a surface
   ========================================================= */

export function HondaCivicDrive() {
  const { src, loaded } = useEasterEggAsset("honda-civic");
  const [visible, setVisible] = useState(false);
  const [pos, setPos] = useState(-100);

  useEffect(() => {
    if (!loaded || !src) return;
    // 5% chance to show on any render
    if (Math.random() > 0.05) return;

    setVisible(true);
    setPos(-100);

    const start = Date.now();
    const duration = 6000 + Math.random() * 4000;
    let raf: number;

    const animate = () => {
      const elapsed = Date.now() - start;
      const progress = Math.min(elapsed / duration, 1);
      // Ease in-out
      const eased = progress < 0.5
        ? 2 * progress * progress
        : 1 - Math.pow(-2 * progress + 2, 2) / 2;
      setPos(eased * (window.innerWidth + 200) - 100);
      if (progress < 1) {
        raf = requestAnimationFrame(animate);
      } else {
        setVisible(false);
      }
    };
    raf = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(raf);
      setVisible(false);
    };
  }, [loaded, src]);

  if (!visible || !src) return null;

  return (
    <div
      className="pointer-events-none fixed bottom-8 z-[90] opacity-60"
      style={{ left: `${pos}px`, transition: "none" }}
      aria-hidden
    >
      <img
        src={src}
        alt=""
        className="h-[28px] w-auto object-contain drop-shadow-[0_2px_8px_rgba(0,0,0,0.5)]"
        draggable={false}
      />
    </div>
  );
}

/* =========================================================
   MASSAGE CHAIR — rare idle visual
   ========================================================= */

export function MassageChairEgg({ show }: { show: boolean }) {
  const { src, loaded } = useEasterEggAsset("massage-chair");
  const [dismissed, setDismissed] = useState(false);

  // Auto-dismiss after 10s so it never lingers
  useEffect(() => {
    if (show && loaded && !dismissed) {
      const t = setTimeout(() => setDismissed(true), 10000);
      return () => clearTimeout(t);
    }
  }, [show, loaded, dismissed]);

  if (!show || !loaded || !src || dismissed) return null;

  return (
    <div className="pointer-events-auto absolute bottom-4 right-4 z-50 doof-fade">
      <div className="relative rounded-xl border border-white/[0.06] bg-[#09090b]/90 p-2 shadow-xl backdrop-blur-md">
        <button
          type="button"
          onClick={() => setDismissed(true)}
          className="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full border border-white/10 bg-zinc-800 text-[8px] text-zinc-400 hover:text-white"
          aria-label="Dismiss"
        >
          x
        </button>
        <img
          src={src}
          alt=""
          className="h-[60px] w-auto rounded-lg object-contain opacity-80"
          draggable={false}
        />
      </div>
    </div>
  );
}

/* =========================================================
   FULL BODY CUTOUT — rare training completion surprise
   ========================================================= */

export function TrainingCompleteEgg({ show }: { show: boolean }) {
  const { src, loaded } = useEasterEggAsset("full-body");
  const [dismissed, setDismissed] = useState(false);
  const [fadeOut, setFadeOut] = useState(false);

  const dismiss = useCallback(() => {
    setFadeOut(true);
    setTimeout(() => setDismissed(true), 400);
  }, []);

  // Auto-dismiss after 5s
  useEffect(() => {
    if (show && loaded && !dismissed) {
      const t = setTimeout(dismiss, 5000);
      return () => clearTimeout(t);
    }
  }, [show, loaded, dismissed, dismiss]);

  if (!show || !loaded || !src || dismissed) return null;

  return (
    <div
      className={`pointer-events-auto absolute bottom-6 left-1/2 z-50 -translate-x-1/2 ${fadeOut ? "opacity-0 transition-opacity duration-400" : "doof-fade"}`}
      onClick={dismiss}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Escape") dismiss(); }}
    >
      <div className="relative rounded-2xl border border-violet-400/20 bg-[#09090b]/90 p-3 shadow-[0_0_40px_rgba(124,58,237,0.2)] backdrop-blur-md">
        <div className="mb-1 text-center text-[10px] font-medium text-violet-300/80">
          Training complete!
        </div>
        <img
          src={src}
          alt=""
          className="h-[100px] w-auto rounded-xl object-contain"
          draggable={false}
        />
      </div>
    </div>
  );
}

/* =========================================================
   WALMART WATCH — rare toast companion
   ========================================================= */

export function WalmartWatchToast({ show }: { show: boolean }) {
  const { src, loaded } = useEasterEggAsset("walmart-watch");
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (show && loaded && !dismissed) {
      const t = setTimeout(() => setDismissed(true), 4000);
      return () => clearTimeout(t);
    }
  }, [show, loaded, dismissed]);

  if (!show || !loaded || !src || dismissed) return null;

  return (
    <div className="pointer-events-none fixed bottom-16 right-4 z-[100] doof-fade">
      <div className="flex items-center gap-2 rounded-xl border border-amber-400/20 bg-amber-950/60 px-3 py-2 shadow-lg backdrop-blur-md">
        <img
          src={src}
          alt=""
          className="h-6 w-6 rounded object-contain"
          draggable={false}
        />
        <span className="text-[11px] text-amber-200">$10 Walmart watch says: nice.</span>
      </div>
    </div>
  );
}
