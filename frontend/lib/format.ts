import type { JobStatus, Severity } from "./types";

/** Tailwind classes for a severity chip/badge (Toss palette). */
export const SEVERITY_STYLES: Record<Severity, string> = {
  CRITICAL: "bg-red-100 text-red-700 border-red-200",
  HIGH: "bg-orange-100 text-orange-700 border-orange-200",
  MEDIUM: "bg-amber-100 text-amber-700 border-amber-200",
  LOW: "bg-slate-100 text-slate-600 border-slate-200",
  UNKNOWN: "bg-slate-100 text-slate-500 border-slate-200",
};

export const SEVERITY_LABELS: Record<Severity, string> = {
  CRITICAL: "치명적",
  HIGH: "높음",
  MEDIUM: "보통",
  LOW: "낮음",
  UNKNOWN: "알 수 없음",
};

/** Big-number card accent colors per severity. */
export const SEVERITY_ACCENT: Record<
  Exclude<Severity, "UNKNOWN">,
  { text: string; ring: string }
> = {
  CRITICAL: { text: "text-red-600", ring: "ring-red-100" },
  HIGH: { text: "text-orange-600", ring: "ring-orange-100" },
  MEDIUM: { text: "text-amber-600", ring: "ring-amber-100" },
  LOW: { text: "text-slate-500", ring: "ring-slate-100" },
};

export interface StatusMeta {
  label: string;
  className: string;
  pulse: boolean;
}

export const STATUS_META: Record<JobStatus, StatusMeta> = {
  queued: { label: "대기 중", className: "bg-slate-100 text-slate-600 border-slate-200", pulse: false },
  scanning: { label: "스캔 중", className: "bg-blue-100 text-blue-700 border-blue-200", pulse: true },
  scanned: { label: "스캔 완료", className: "bg-indigo-100 text-indigo-700 border-indigo-200", pulse: false },
  remediating: { label: "조치 중", className: "bg-blue-100 text-blue-700 border-blue-200", pulse: true },
  remediated: { label: "조치 완료", className: "bg-teal-100 text-teal-700 border-teal-200", pulse: false },
  signing: { label: "서명 중", className: "bg-blue-100 text-blue-700 border-blue-200", pulse: true },
  signed: { label: "서명 완료", className: "bg-green-100 text-green-700 border-green-200", pulse: false },
  failed: { label: "실패", className: "bg-red-100 text-red-700 border-red-200", pulse: false },
};

export function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(d);
}

export function relativeTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const diff = Date.now() - d.getTime();
  const sec = Math.round(diff / 1000);
  if (sec < 60) return "방금 전";
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}분 전`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}시간 전`;
  return formatTime(iso);
}
