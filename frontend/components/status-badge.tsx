import { STATUS_META } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { JobStatus } from "@/lib/types";

interface StatusBadgeProps {
  status: JobStatus;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const meta = STATUS_META[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold",
        meta.className,
        className,
      )}
    >
      {meta.pulse && (
        <span className="relative flex size-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-75" />
          <span className="relative inline-flex size-1.5 rounded-full bg-current" />
        </span>
      )}
      {meta.label}
    </span>
  );
}
