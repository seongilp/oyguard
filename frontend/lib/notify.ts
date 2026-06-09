// Browser OS notifications for job completion, so users can start a scan and
// walk away. Falls back silently when the Notification API is unavailable or
// permission is denied — the dashboard still shows status either way.

import type { Job } from "./types";

export function canNotify(): boolean {
  return typeof window !== "undefined" && "Notification" in window;
}

export async function requestNotifyPermission(): Promise<void> {
  if (!canNotify()) return;
  if (Notification.permission === "default") {
    try {
      await Notification.requestPermission();
    } catch {
      // ignore — user can grant later
    }
  }
}

export function notifyJobDone(job: Job): void {
  if (!canNotify() || Notification.permission !== "granted") return;
  const ok = job.status === "signed";
  const title = ok ? "✅ 조치 완료" : "❌ 작업 실패";
  const body = ok
    ? `${job.image} → ${job.remediation?.new_image ?? "조치 완료"} (서명됨)`
    : `${job.image}: ${job.error ?? "실패"}`;
  try {
    const n = new Notification(title, { body, tag: job.id });
    n.onclick = () => {
      window.focus();
      window.location.href = `/jobs/${job.id}`;
    };
  } catch {
    // ignore
  }
}
