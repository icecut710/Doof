/**
 * NotificationToast — subtle stacked notifications.
 *
 * - Slides in from right
 * - Auto-dismisses after 5s
 * - Max 3 visible (oldest dropped)
 * - Muted violet accent, low opacity
 * - No broken images, no network blocking
 */

import { useNotifications } from "./NotificationContext";

export default function NotificationToast() {
  const { notifications } = useNotifications();

  if (!notifications.length) return null;

  return (
    <div
      className="pointer-events-none fixed top-4 right-4 z-[90] flex flex-col items-end gap-1"
      aria-live="polite"
      aria-label="Notifications"
    >
      {notifications.map((n) => (
        <div
          key={n.id}
          className="doof-notif pointer-events-auto flex max-w-[280px] items-center gap-2 rounded-lg border border-violet-400/15 bg-[#0a0a0c]/85 px-3 py-2 text-[11px] leading-snug text-zinc-300 shadow-lg backdrop-blur-md"
        >
          <span className="mt-px shrink-0 text-violet-400/60">↯</span>
          <span className="min-w-0 flex-1 break-words">{n.text}</span>
          {n.detail && (
            <span className="shrink-0 text-[10px] text-zinc-600">{n.detail}</span>
          )}
        </div>
      ))}
    </div>
  );
}
