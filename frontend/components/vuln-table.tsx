import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SEVERITY_LABELS, SEVERITY_STYLES } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Vulnerability } from "@/lib/types";

interface VulnTableProps {
  vulnerabilities: Vulnerability[];
}

const SEVERITY_RANK: Record<string, number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
  UNKNOWN: 4,
};

export function VulnTable({ vulnerabilities }: VulnTableProps) {
  if (vulnerabilities.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-muted-foreground">
        발견된 취약점이 없습니다.
      </p>
    );
  }

  const sorted = [...vulnerabilities].sort(
    (a, b) =>
      (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9),
  );

  return (
    <div className="overflow-hidden rounded-xl border">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="pl-4">CVE</TableHead>
            <TableHead>심각도</TableHead>
            <TableHead>패키지</TableHead>
            <TableHead>버전</TableHead>
            <TableHead>출처</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((v, i) => (
            <TableRow key={`${v.id}-${v.package}-${i}`}>
              <TableCell className="pl-4 align-top font-mono text-xs font-medium">
                {v.id}
                {v.title && (
                  <p className="mt-0.5 max-w-xs truncate font-sans text-[11px] font-normal text-muted-foreground">
                    {v.title}
                  </p>
                )}
              </TableCell>
              <TableCell className="align-top">
                <span
                  className={cn(
                    "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold",
                    SEVERITY_STYLES[v.severity],
                  )}
                >
                  {SEVERITY_LABELS[v.severity]}
                </span>
              </TableCell>
              <TableCell className="align-top font-mono text-xs">
                {v.package}
              </TableCell>
              <TableCell className="align-top text-xs">
                <span className="text-muted-foreground">
                  {v.installed_version}
                </span>
                {v.fixed_version ? (
                  <>
                    <span className="mx-1 text-muted-foreground/50">→</span>
                    <span className="font-semibold text-teal-600">
                      {v.fixed_version}
                    </span>
                  </>
                ) : (
                  <span className="ml-1 text-muted-foreground/60">
                    (패치 없음)
                  </span>
                )}
              </TableCell>
              <TableCell className="align-top">
                <div className="flex flex-wrap gap-1">
                  {v.sources.map((s) => (
                    <span
                      key={s}
                      className="rounded border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
