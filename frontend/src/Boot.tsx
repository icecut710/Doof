import { useEffect, useState } from "react";

const PHASES = [
  { key: "runtime", label: "Warming up the shawarma machine…" },
  { key: "database", label: "Checking the grill…" },
  { key: "cloud", label: "Calling Lebanon…" },
  { key: "ai", label: "Finding the brain…" },
  { key: "network", label: "Setting the table…" },
  { key: "ready", label: "Shawarmas: Fresh" },
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
          setTimeout(() => onDone(), 420);
          return;
        }
      } catch {
        if (Date.now() - started > 8000) {
          // API never came up — still enter, chat will show offline honestly.
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

  return (
    <div className="relative flex h-screen w-screen items-center justify-center overflow-hidden bg-[#050506] text-zinc-200">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(124,58,237,0.12),transparent_55%)]" />
      <div className="relative z-10 flex w-[min(420px,90vw)] flex-col items-center px-6 text-center">
        <div className="doof-boot-mark flex h-16 w-16 items-center justify-center rounded-2xl border border-violet-400/25 bg-violet-500/[0.08] text-[22px] font-semibold tracking-tight text-violet-200 shadow-[0_0_40px_rgba(124,58,237,0.28)]">
          D
        </div>
        <div className="mt-5 text-[13px] font-medium tracking-[0.28em] text-zinc-500">DOOF</div>
        <div className="mt-4 min-h-[1.5em] text-[16px] font-medium text-zinc-100 text-balance">
          {failed ? "Lost in the desert" : label}
        </div>
        <div className="mt-1.5 min-h-[1.4em] text-[13px] leading-relaxed text-zinc-500 text-pretty">
          {failed ? "The runtime did not finish starting. You can still try to enter." : detail}
        </div>
        <div className="mt-6 h-1 w-full overflow-hidden rounded-full bg-white/[0.06]">
          <div
            className="h-full rounded-full bg-violet-400/80 transition-[width] duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
        {failed && (
          <button
            type="button"
            onClick={onDone}
            className="mt-5 rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-2 text-[13px] text-zinc-200"
          >
            Enter anyway
          </button>
        )}
      </div>
    </div>
  );
}
