import { SEVERITY_STYLES } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ScanSummary } from "@/lib/types";

interface SeverityChipsProps {
  summary: ScanSummary | null | undefined;
  className?: string;
}

const ROWS: { key: keyof ScanSummary; severity: keyof typeof SEVERITY_STYLES }[] =
  [
    { key: "critical", severity: "CRITICAL" },
    { key: "high", severity: "HIGH" },
    { key: "medium", severity: "MEDIUM" },
    { key: "low", severity: "LOW" },
  ];

/** Compact inline severity counts for table rows. */
export function SeverityChips({ summary, className }: SeverityChipsProps) {
  if (!summary) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }

  return (
    <div className={cn("flex flex-wrap items-center gap-1", className)}>
      {ROWS.map(({ key, severity }) => {
        const count = summary[key];
        if (!count) return null;
        return (
          <span
            key={key}
            className={cn(
              "inline-flex items-center rounded-md border px-1.5 py-0.5 text-[11px] font-semibold tabular-nums",
              SEVERITY_STYLES[severity],
            )}
          >
            {severity[0]} {count}
          </span>
        );
      })}
      {summary.total === 0 && (
        <span className="inline-flex items-center rounded-md border border-green-200 bg-green-100 px-1.5 py-0.5 text-[11px] font-semibold text-green-700">
          취약점 없음
        </span>
      )}
    </div>
  );
}
