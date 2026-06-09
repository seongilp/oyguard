import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/format";
import type { JobLog } from "@/lib/types";

const LEVEL_STYLES: Record<JobLog["level"], string> = {
  info: "text-slate-500",
  warn: "text-amber-600",
  error: "text-red-600",
};

export function JobLogs({ logs }: { logs: JobLog[] }) {
  if (logs.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-muted-foreground">
        로그가 없습니다.
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border bg-slate-50">
      <ul className="divide-y divide-border/60 font-mono text-xs">
        {logs.map((log, i) => (
          <li key={i} className="flex gap-3 px-4 py-2">
            <span className="shrink-0 text-muted-foreground/70">
              {formatTime(log.ts)}
            </span>
            <span
              className={cn(
                "w-12 shrink-0 font-semibold uppercase",
                LEVEL_STYLES[log.level],
              )}
            >
              {log.level}
            </span>
            <span className="break-all text-foreground">{log.message}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
