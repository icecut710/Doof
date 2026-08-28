import { useCallback, useEffect, useState } from "react";

type Balances = {
  pending?: number; approved?: number; paid?: number; reversed?: number;
  disclaimer?: string;
  history?: { id: string; job_type?: string; amount?: number; status?: string; created_at?: string }[];
  payouts?: { enabled?: boolean; label?: string; detail?: string };
};

function base() { try { return localStorage.getItem("doof_server") || ""; } catch { return ""; } }
function token() { return localStorage.getItem("doof_token") || sessionStorage.getItem("doof_token") || ""; }

export default function RewardsTab() {
  const [data, setData] = useState<Balances | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(async () => {
    setErr("");
    try {
      const res = await fetch(`${base()}/api/compute/rewards`, { headers: token() ? { Authorization: `Bearer ${token()}` } : {} });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not load rewards");
      setData(null);
    }
  }, []);
  useEffect(() => { void load(); }, [load]);
  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="mx-auto max-w-2xl space-y-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-zinc-600">Naddaf Rewards</div>
          <div className="mt-1 text-[15px] font-medium text-zinc-100">Compute contribution credits</div>
          <p className="mt-2 text-[13px] leading-relaxed text-zinc-500">
            Internal verified accounting for opt-in compute jobs. On-chain Naddaf token payouts are not enabled in this client.
          </p>
        </div>
        {err ? <div className="rounded-lg border border-amber-400/25 bg-amber-400/[0.06] px-3 py-2 text-[13px] text-amber-200">{err}</div> : null}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {([["Pending", data?.pending], ["Approved", data?.approved], ["Paid", data?.paid], ["Reversed", data?.reversed]] as const).map(([label, val]) => (
            <div key={label} className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-3">
              <div className="text-[11px] uppercase tracking-[0.12em] text-zinc-600">{label}</div>
              <div className="mt-1 text-[18px] font-semibold tabular-nums text-zinc-100">{val != null ? Number(val).toFixed(2) : "—"}</div>
            </div>
          ))}
        </div>
        <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3.5 py-3 text-[13px] text-zinc-400">
          <div className="text-[12px] font-medium text-zinc-300">{data?.payouts?.label || "On-chain payouts are not enabled yet"}</div>
          <p className="mt-1 text-zinc-500">{data?.payouts?.detail || data?.disclaimer || "Your verified contribution rewards are being tracked."}</p>
        </div>
        <button type="button" onClick={() => void load()} className="rounded-lg border border-white/[0.08] px-3 py-1.5 text-[12px] text-zinc-400 hover:border-white/[0.14] hover:text-zinc-200">Refresh</button>
      </div>
    </div>
  );
}
