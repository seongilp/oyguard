import { Card } from "@/components/ui/card";
import { SEVERITY_ACCENT, SEVERITY_LABELS } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ScanSummary } from "@/lib/types";

interface SeverityCardsProps {
  summary: ScanSummary | null | undefined;
}

const ORDER: {
  key: keyof ScanSummary;
  severity: keyof typeof SEVERITY_ACCENT;
}[] = [
  { key: "critical", severity: "CRITICAL" },
  { key: "high", severity: "HIGH" },
  { key: "medium", severity: "MEDIUM" },
  { key: "low", severity: "LOW" },
];

export function SeverityCards({ summary }: SeverityCardsProps) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {ORDER.map(({ key, severity }) => {
        const accent = SEVERITY_ACCENT[severity];
        const count = summary ? summary[key] : 0;
        return (
          <Card
            key={key}
            className={cn(
              "gap-1 rounded-2xl p-5 shadow-sm ring-1 ring-inset",
              accent.ring,
            )}
          >
            <span className="text-sm font-medium text-muted-foreground">
              {SEVERITY_LABELS[severity]}
            </span>
            <span
              className={cn(
                "text-3xl font-bold tabular-nums",
                count > 0 ? accent.text : "text-muted-foreground/50",
              )}
            >
              {count}
            </span>
          </Card>
        );
      })}
    </div>
  );
}
