import { useCallback, useEffect, useState } from "react";

type UpdateInfo = {
  current?: string;
  latest?: string | null;
  available?: boolean;
  mandatory?: boolean;
  notes_human?: string;
  notes?: string;
  channel?: string;
  incompatible?: boolean;
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

type UpdateSettings = {
  channel?: string;
  check_on_start?: boolean;
};

export default function UpdatesTab() {
  const [info, setInfo] = useState<UpdateInfo | null>(null);
  const [settings, setSettings] = useState<UpdateSettings | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [showTech, setShowTech] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${base()}/api/updates/check`, {
        headers: token() ? { Authorization: `Bearer ${token()}` } : {},
      });
      setInfo((await res.json()) as UpdateInfo);
    } catch {
      setInfo({ error: "Could not check for updates.", current: "—" });
    }
    try {
      const res = await fetch(`${base()}/api/updates/settings`, {
        headers: token() ? { Authorization: `Bearer ${token()}` } : {},
      });
      if (res.ok) setSettings((await res.json()) as UpdateSettings);
    } catch {
      /* settings are optional */
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const apply = async () => {
    setBusy(true);
    setMsg("");
    try {
      const res = await fetch(`${base()}/api/updates/apply`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token() ? { Authorization: `Bearer ${token()}` } : {}),
        },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      setMsg(data.message || (data.ok ? "Update staged." : "Update failed."));
      await load();
    } catch {
      setMsg("Could not start the update.");
    } finally {
      setBusy(false);
    }
  };

  const saveSetting = async (patch: UpdateSettings) => {
    try {
      const res = await fetch(`${base()}/api/updates/settings`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token() ? { Authorization: `Bearer ${token()}` } : {}),
        },
        body: JSON.stringify(patch),
      });
      if (res.ok) setSettings((await res.json()) as UpdateSettings);
    } catch {
      /* keep previous */
    }
  };

  if (!info) {
    return (
      <div className="flex flex-1 items-center justify-center text-[13px] text-zinc-500">
        Checking for updates…
      </div>
    );
  }

  const upToDate = !info.available && !info.error;

  return (
    <div className="flex-1 overflow-y-auto p-5">
      <div className="mb-5">
        <div className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">DOOF Updates</div>
        <h1 className="mt-1 text-[22px] font-semibold tracking-tight text-zinc-50">
          {upToDate
            ? "You're up to date"
            : info.incompatible
              ? "Your DOOF is too old for this brain"
              : `DOOF ${info.latest} is ready`}
        </h1>
        <p className="mt-1 text-[13px] text-zinc-500">
          Current version · v{info.current || "—"}
          {info.channel ? ` · ${info.channel}` : ""}
        </p>
      </div>

      <div className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/90 p-4">
        {info.error && (
          <p className="text-[13px] text-amber-300/90">{info.error}</p>
        )}
        {upToDate && !info.error && (
          <p className="text-[14px] text-zinc-300">Shawarmas are current. No update needed.</p>
        )}
        {info.available && (
          <>
            <p className="text-[14px] leading-relaxed text-zinc-200">
              {info.notes_human || "Bug fixes and improvements."}
            </p>
            {info.notes && (
              <button
                type="button"
                className="mt-2 text-[12px] text-zinc-600 underline-offset-2 hover:text-zinc-400 hover:underline"
                onClick={() => setShowTech(!showTech)}
              >
                {showTech ? "Hide details" : "Details"}
              </button>
            )}
            {showTech && info.notes && (
              <pre className="mt-2 whitespace-pre-wrap rounded-lg bg-black/40 p-2 text-[11px] text-zinc-500">
                {info.notes}
              </pre>
            )}
            <div className="mt-4 flex gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => void apply()}
                className="rounded-xl border border-violet-400/30 bg-violet-600/70 px-4 py-2 text-[13px] font-medium text-white hover:bg-violet-500 disabled:opacity-40"
              >
                {busy ? "Working…" : "Update Now"}
              </button>
              {!info.mandatory && (
                <button
                  type="button"
                  onClick={() => setMsg("Okay — ask again later.")}
                  className="rounded-xl border border-white/[0.08] px-4 py-2 text-[13px] text-zinc-400"
                >
                  Later
                </button>
              )}
            </div>
          </>
        )}
        {msg && <p className="mt-3 text-[13px] text-zinc-400">{msg}</p>}
      </div>

      <div className="mt-3 rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/90 p-4">
        <div className="text-[11px] uppercase tracking-[0.14em] text-zinc-500">Update settings</div>
        {settings ? (
          <div className="mt-2 space-y-2">
            <label className="flex items-center justify-between gap-3">
              <span className="text-[13px] text-zinc-300">Check for updates when DOOF starts</span>
              <input
                type="checkbox"
                checked={Boolean(settings.check_on_start)}
                onChange={(e) => void saveSetting({ check_on_start: e.target.checked })}
                className="h-4 w-4 accent-violet-500"
              />
            </label>
            {settings.channel && (
              <p className="text-[12px] text-zinc-600">Channel: {settings.channel}</p>
            )}
          </div>
        ) : (
          <p className="mt-2 text-[12px] text-zinc-600">Settings unavailable.</p>
        )}
      </div>

      <p className="mt-4 max-w-md text-[12px] leading-relaxed text-zinc-600">
        Updates are verified before install. Native runtime changes still need a full release;
        everyday UI and brain logic can ship without a new giant EXE every time.
      </p>
    </div>
  );
}
