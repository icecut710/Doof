import { useCallback, useEffect, useState } from "react";

type Service = { status?: string; ms?: number; label?: string; detail?: string };
type NodeRow = {
  id: string;
  name: string;
  status?: string;
  state?: string;
  gpu?: string;
  accepting_jobs?: boolean;
  job_count?: number;
  max_jobs?: number;
  last_seen?: string | number;
  client_version?: string;
  stale?: boolean;
};

type AdminData = {
  allowed?: boolean;
  role?: string;
  health?: { overall?: string; services?: Record<string, Service> };
  pool?: { paused?: boolean; online?: number; accepting?: number; jobs_running?: number };
  nodes?: NodeRow[];
  version?: { client?: string; backend?: string; protocol?: string };
  error?: string;
};

function base() {
  try {
    return localStorage.getItem("doof_server") || "";
  } catch {
    return "";
  }
}

function token() {
  return localStorage.getItem("doof_token") || sessionStorage.getItem("doof_token") || "";
}

async function adminGet(): Promise<AdminData> {
  const res = await fetch(`${base()}/api/admin/overview`, {
    headers: token() ? { Authorization: `Bearer ${token()}` } : {},
  });
  return (await res.json()) as AdminData;
}

async function adminPost(path: string, body: Record<string, unknown>) {
  const res = await fetch(`${base()}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token() ? { Authorization: `Bearer ${token()}` } : {}),
    },
    body: JSON.stringify(body),
  });
  return res.json();
}

function Dot({ ok }: { ok?: boolean }) {
  return (
    <span
      className={[
        "inline-block h-1.5 w-1.5 rounded-full",
        ok ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.6)]" : "bg-amber-400",
      ].join(" ")}
    />
  );
}

export default function AdminTab({ online }: { online: boolean }) {
  const [data, setData] = useState<AdminData | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await adminGet());
    } catch {
      /* keep */
    }
  }, []);

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), online ? 8000 : 20000);
    return () => clearInterval(t);
  }, [load, online]);

  if (!data) {
    return (
      <div className="flex flex-1 items-center justify-center text-[13px] text-zinc-500">
        Opening Control Room…
      </div>
    );
  }

  if (data.allowed === false || data.error === "forbidden") {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
        <div className="text-[16px] font-semibold text-zinc-100">Control Room</div>
        <p className="max-w-sm text-[13px] text-zinc-500">
          This area is for owners and admins only. Your account does not have access.
        </p>
      </div>
    );
  }

  const services = data.health?.services || {};
  const nodes = data.nodes || [];

  const run = async (action: string) => {
    setBusy(true);
    try {
      if (action === "pause") await adminPost("/api/admin/pool/pause", { paused: true });
      if (action === "resume") await adminPost("/api/admin/pool/pause", { paused: false });
      if (action === "refresh") await load();
      setConfirm(null);
      await load();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-5">
      <div className="mb-5">
        <div className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">DOOF Control Room</div>
        <h1 className="mt-1 text-[22px] font-semibold tracking-tight text-zinc-50">
          {data.health?.overall === "healthy" ? "Operational" : "Needs attention"}
        </h1>
        <p className="mt-1 text-[13px] text-zinc-500">
          Role: {data.role || "admin"} · Backend {data.version?.backend || "—"} · Protocol{" "}
          {data.version?.protocol || "1"}
        </p>
      </div>

      <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {Object.entries(services).map(([name, s]) => (
          <div
            key={name}
            className="rounded-xl border border-white/[0.06] bg-[#0a0a0c]/90 px-3 py-2.5"
          >
            <div className="flex items-center justify-between">
              <span className="text-[12px] uppercase tracking-[0.12em] text-zinc-500">
                {name.replace(/_/g, " ")}
              </span>
              <Dot ok={s.status === "healthy"} />
            </div>
            <div className="mt-1 text-[14px] text-zinc-100">
              {s.label || s.status}
              {s.ms != null ? ` · ${s.ms}ms` : ""}
            </div>
            {s.detail && <div className="text-[11px] text-zinc-600">{s.detail}</div>}
          </div>
        ))}
      </div>

      <div className="mb-4 rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/90 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="text-[11px] uppercase tracking-[0.14em] text-zinc-500">Compute pool</div>
            <div className="mt-1 text-[15px] text-zinc-100">
              {data.pool?.paused ? "Paused" : "Running"} · {data.pool?.online ?? 0} online ·{" "}
              {data.pool?.accepting ?? 0} contributing · {data.pool?.jobs_running ?? 0} jobs
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => void run("refresh")}
              className="rounded-xl border border-white/[0.08] px-3 py-1.5 text-[12px] text-zinc-400 hover:text-zinc-200"
            >
              Refresh
            </button>
            {data.pool?.paused ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => void run("resume")}
                className="rounded-xl border border-emerald-400/25 bg-emerald-500/15 px-3 py-1.5 text-[12px] text-emerald-200"
              >
                Resume pool
              </button>
            ) : (
              <button
                type="button"
                disabled={busy}
                onClick={() => setConfirm("pause")}
                className="rounded-xl border border-amber-400/25 bg-amber-500/10 px-3 py-1.5 text-[12px] text-amber-200"
              >
                Pause pool
              </button>
            )}
          </div>
        </div>
        {confirm === "pause" && (
          <div className="mt-3 rounded-xl border border-amber-400/20 bg-amber-500/[0.06] p-3 text-[13px] text-zinc-300">
            Pause the entire compute pool? Remote jobs will stop until you resume.
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                onClick={() => setConfirm(null)}
                className="rounded-lg border border-white/[0.08] px-3 py-1 text-[12px] text-zinc-400"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void run("pause")}
                className="rounded-lg border border-amber-400/30 bg-amber-500/20 px-3 py-1 text-[12px] text-amber-100"
              >
                Pause pool
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/90 p-4">
        <div className="text-[11px] uppercase tracking-[0.14em] text-zinc-500">Nodes</div>
        <div className="mt-3 space-y-2">
          {nodes.map((n) => (
            <div
              key={n.id || n.name}
              className="flex flex-wrap items-start justify-between gap-2 rounded-xl border border-white/[0.05] bg-black/30 px-3 py-2.5"
            >
              <div>
                <div className="text-[14px] font-medium text-zinc-100">{n.name}</div>
                <div className="text-[12px] text-zinc-500">
                  {n.gpu || "CPU"} · jobs {n.job_count ?? 0}/{n.max_jobs ?? 1}
                  {n.client_version ? ` · v${n.client_version}` : ""}
                </div>
              </div>
              <div className="text-right text-[12px]">
                <div className={n.stale ? "text-zinc-600" : "text-emerald-300"}>
                  {n.stale ? "Offline" : n.accepting_jobs ? "Contributing" : "Online"}
                </div>
              </div>
            </div>
          ))}
          {nodes.length === 0 && (
            <div className="py-6 text-center text-[13px] text-zinc-600">No nodes registered.</div>
          )}
        </div>
      </div>
    </div>
  );
}
