import { useEffect, useMemo, useState } from "react";
import { getBootJokes, type JokeEntry } from "./personality-registry";

const PHASES = [
  { key: "runtime", label: "Waking DOOF\u2026" },
  { key: "database", label: "Checking the grill\u2026" },
  { key: "cloud", label: "Calling the kitchen\u2026" },
  { key: "ai", label: "Finding the brain\u2026" },
  { key: "network", label: "Checking the network\u2026" },
  { key: "ready", label: "Shawarmas: Fresh" },
];

/** Packaged static path: frontend/dist serves assets from /assets when copied, else public. */
const MRNADDAF_CANDIDATES = [
  "/assets/mrnaddaf.png",
  "/mrnaddaf.png",
  "./assets/mrnaddaf.png",
];

/** Ambient boot video \u2014 muted, low-opacity backdrop. Never blocks startup;
 *  prefers a bundled local copy and falls back through candidates silently. */
const VIDEO_CANDIDATES = [
  "/naddaf.mp4",
  "./assets/naddaf.mp4",
  "https://ekvjdgxpeusdchwrnlww.supabase.co/storage/v1/object/public/doof-assets/Naddaf.mp4",
];

type BootInfo = {
  phase?: string;
  ready?: boolean;
  failed?: boolean;
  label?: string;
  detail?: string;
};

export default function Boot({
  onDone,
  apiBase,
}: {
  onDone: () => void;
  apiBase: string;
}) {
  const [phase, setPhase] = useState("runtime");
  const [label, setLabel] = useState(PHASES[0].label);
  const [failed, setFailed] = useState(false);
  const [detail, setDetail] = useState("Starting the local runtime.");
  const [imgSrc, setImgSrc] = useState(MRNADDAF_CANDIDATES[0]);
  const [imgFailed, setImgFailed] = useState(false);
  const [vidSrc, setVidSrc] = useState(VIDEO_CANDIDATES[0]);
  const [vidFailed, setVidFailed] = useState(false);
  const [reducedMotion] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  // Pick 3 random boot flavor messages once per mount (memoized)
  const bootFlavor: JokeEntry[] = useMemo(() => getBootJokes(3), []);

  // Kill the video if it takes too long to actually play \u2014 never block or distract.
  useEffect(() => {
    if (reducedMotion) return;
    const t = setTimeout(() => setVidFailed(true), 7000);
    const clear = () => clearTimeout(t);
    window.addEventListener("doof-video-playing", clear);
    return () => {
      clearTimeout(t);
      window.removeEventListener("doof-video-playing", clear);
    };
  }, [reducedMotion]);

  useEffect(() => {
    let stop = false;
    const started = Date.now();
    const tick = async () => {
      try {
        const r = await fetch(`${apiBase}/api/boot`, { cache: "no-store" });
        const d = (await r.json()) as BootInfo;
        if (stop) return;
        const p = d.phase || "runtime";
        setPhase(p);
        setLabel(d.label || PHASES.find((x) => x.key === p)?.label || PHASES[0].label);
        setDetail(d.detail || "");
        if (d.failed) {
          setFailed(true);
          return;
        }
        if (d.ready || p === "ready") {
          setTimeout(() => onDone(), 480);
          return;
        }
      } catch {
        if (Date.now() - started > 8000) {
          onDone();
          return;
        }
      }
      if (!stop) setTimeout(() => void tick(), 280);
    };
    void tick();
    const failSafe = setTimeout(() => onDone(), 12000);
    return () => {
      stop = true;
      clearTimeout(failSafe);
    };
  }, [apiBase, onDone]);

  const idx = Math.max(0, PHASES.findIndex((p) => p.key === phase));
  const pct = failed ? 100 : Math.round(((idx + 1) / PHASES.length) * 100);

  const onImgError = () => {
    const i = MRNADDAF_CANDIDATES.indexOf(imgSrc);
    if (i >= 0 && i < MRNADDAF_CANDIDATES.length - 1) {
      setImgSrc(MRNADDAF_CANDIDATES[i + 1]);
      return;
    }
    setImgFailed(true);
  };

  // Map each boot flavor to a phase index (spread evenly, no repeats)
  const flavorByPhase = useMemo(() => {
    const map = new Map<number, JokeEntry>();
    bootFlavor.forEach((joke, i) => {
      const phaseIdx = Math.min(i, PHASES.length - 1);
      if (!map.has(phaseIdx)) map.set(phaseIdx, joke);
    });
    return map;
  }, [bootFlavor]);

  return (
    <div className="relative flex h-screen w-screen items-center justify-center overflow-hidden bg-[#050506] text-zinc-200">
      {/* Ambient glows */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(124,58,237,0.16),transparent_55%)]" />
      <div
        className="pointer-events-none absolute left-1/2 top-1/2 h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full opacity-40"
        style={{
          background:
            "radial-gradient(circle, rgba(139,92,246,0.10) 0%, transparent 60%)",
        }}
      />
      {/* Video backdrop \u2014 muted, ambient, fails silently */}
      {!failed && !vidFailed && !reducedMotion && (
        <video
          src={vidSrc}
          autoPlay
          muted
          loop
          playsInline
          preload="auto"
          onPlaying={() => window.dispatchEvent(new Event("doof-video-playing"))}
          onError={() => {
            const i = VIDEO_CANDIDATES.indexOf(vidSrc);
            if (i >= 0 && i < VIDEO_CANDIDATES.length - 1) setVidSrc(VIDEO_CANDIDATES[i + 1]);
            else setVidFailed(true);
          }}
          className="pointer-events-none absolute inset-0 h-full w-full object-cover opacity-[0.13]"
        />
      )}
      {/* Scanline sweep */}
      {!failed && (
        <div
          className="pointer-events-none absolute inset-x-0 h-24 opacity-[0.05]"
          style={{
            background:
              "linear-gradient(180deg, transparent, rgba(167,139,250,0.6), transparent)",
            animation: "doof-scanline 2.6s linear infinite",
          }}
        />
      )}

      <div className="relative z-10 flex w-[min(440px,90vw)] flex-col items-center px-6 text-center">
        {/* Orbital emblem */}
        <div className="relative flex h-[128px] w-[128px] items-center justify-center">
          {/* Outer orbit */}
          <div
            className={`absolute inset-0 rounded-full border border-violet-400/15 ${failed ? "" : "doof-orbit-slow"}`}
          >
            <span className="absolute -top-[3px] left-1/2 h-1.5 w-1.5 -translate-x-1/2 rounded-full bg-violet-300 shadow-[0_0_8px_rgba(167,139,250,0.9)]" />
          </div>
          {/* Inner orbit (counter-rotating) */}
          <div
            className={`absolute inset-[14px] rounded-full border border-violet-400/10 ${failed ? "" : "doof-orbit-fast"}`}
          >
            <span className="absolute -bottom-[2px] left-1/2 h-1 w-1 -translate-x-1/2 rounded-full bg-fuchsia-300/80 shadow-[0_0_6px_rgba(240,171,252,0.8)]" />
          </div>
          {/* Core */}
          <div className="doof-boot-mark relative flex h-[76px] w-[76px] items-center justify-center overflow-hidden rounded-[20px] border border-violet-400/30 bg-violet-500/[0.06] shadow-[0_0_44px_rgba(124,58,237,0.35)]">
            {!imgFailed ? (
              <img
                src={imgSrc}
                alt="DOOF"
                onError={onImgError}
                className="h-full w-full object-cover"
                draggable={false}
              />
            ) : (
              <span className="text-[26px] font-semibold tracking-tight text-violet-200">D</span>
            )}
          </div>
        </div>

        {/* Wordmark */}
        <div className="mt-4 text-[13px] font-semibold tracking-[0.42em] text-zinc-400">
          D O O F
        </div>

        {/* Status line */}
        <div className="mt-4 min-h-[1.5em] text-[15px] font-medium text-zinc-100 text-balance">
          {failed ? "Lost in the desert" : label}
        </div>
        <div className="mt-1 min-h-[1.4em] text-[12px] leading-relaxed text-zinc-500 text-pretty">
          {failed
            ? "The runtime did not finish starting. You can still try to enter."
            : detail}
        </div>

        {/* Personality flavor line */}
        {!failed && flavorByPhase.has(idx) && (
          <div className="mt-2 min-h-[1.2em] text-[11px] italic text-violet-400/60">
            {flavorByPhase.get(idx)!.text}
          </div>
        )}

        {/* Phase checklist */}
        <div className="mt-5 grid w-full max-w-[260px] grid-cols-1 gap-[3px]">
          {PHASES.map((p, i) => {
            const done = i < idx && !failed;
            const active = i === idx && !failed;
            return (
              <div
                key={p.key}
                className={`flex items-center gap-2 rounded-md px-2 py-[3px] text-left text-[11px] transition-colors duration-300 ${
                  active
                    ? "bg-violet-500/[0.07] text-violet-200"
                    : done
                      ? "text-zinc-600"
                      : "text-zinc-800"
                }`}
              >
                <span
                  className={`flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border text-[8px] ${
                    done
                      ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-300"
                      : active
                        ? "border-violet-300/50 text-violet-300 doof-pulse"
                        : "border-white/[0.07]"
                  }`}
                >
                  {done ? "\u2713" : active ? "\u00b7" : ""}
                </span>
                {p.label}
              </div>
            );
          })}
        </div>

        {/* Shimmer progress bar */}
        <div className="relative mt-5 h-[3px] w-full max-w-[280px] overflow-hidden rounded-full bg-white/[0.05]">
          <div
            className="h-full rounded-full bg-gradient-to-r from-violet-500/70 via-fuchsia-400/80 to-violet-500/70 transition-[width] duration-500"
            style={{ width: `${pct}%` }}
          />
          {!failed && pct < 100 && (
            <div
              className="absolute inset-y-0 w-1/3 animate-[doof-shimmer_1.6s_linear_infinite] rounded-full"
              style={{
                background:
                  "linear-gradient(90deg, transparent, rgba(255,255,255,0.35), transparent)",
              }}
            />
          )}
        </div>
        <div className="mt-1.5 text-[10px] tabular-nums tracking-[0.18em] text-zinc-700">
          {failed ? "BOOT FAILED" : `${pct}%`}
        </div>

        {failed && (
          <button
            type="button"
            onClick={onDone}
            className="doof-btn doof-btn-primary mt-4"
          >
            Enter anyway
          </button>
        )}
      </div>
    </div>
  );
}
