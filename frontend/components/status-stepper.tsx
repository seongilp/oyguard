import { Check, Loader2, X } from "lucide-react";

import { cn } from "@/lib/utils";
import type { Job, JobStatus } from "@/lib/types";

type PhaseState = "done" | "active" | "pending" | "failed";

const PHASES = ["등록", "스캔", "조치", "서명"] as const;

// Which phases are done / active for each non-failed status.
const STATUS_PHASES: Record<Exclude<JobStatus, "failed">, PhaseState[]> = {
  queued: ["active", "pending", "pending", "pending"],
  scanning: ["done", "active", "pending", "pending"],
  scanned: ["done", "done", "pending", "pending"],
  remediating: ["done", "done", "active", "pending"],
  remediated: ["done", "done", "done", "pending"],
  signing: ["done", "done", "done", "active"],
  signed: ["done", "done", "done", "done"],
};

// In-progress statuses get a spinner on their active phase.
const IN_PROGRESS: ReadonlySet<JobStatus> = new Set([
  "queued",
  "scanning",
  "remediating",
  "signing",
]);

function failedPhases(job: Job): PhaseState[] {
  // 등록 always succeeds; infer how far we got from which results exist.
  const states: PhaseState[] = ["done", "pending", "pending", "pending"];
  if (job.scan) states[1] = "done";
  if (job.remediation) states[2] = "done";
  if (job.signature?.signed) states[3] = "done";
  // Mark the first not-done phase as failed.
  const idx = states.findIndex((s) => s !== "done");
  if (idx !== -1) states[idx] = "failed";
  return states;
}

export function StatusStepper({ job }: { job: Job }) {
  const states =
    job.status === "failed"
      ? failedPhases(job)
      : STATUS_PHASES[job.status];
  const spinning = IN_PROGRESS.has(job.status);

  return (
    <ol className="flex items-center">
      {PHASES.map((label, i) => {
        const state = states[i];
        const connectorActive = states[i - 1] === "done";
        return (
          <li key={label} className="flex flex-1 items-center last:flex-none">
            <div className="flex flex-col items-center gap-2">
              <span
                className={cn(
                  "flex size-9 items-center justify-center rounded-full text-sm font-bold transition-colors",
                  state === "done" && "bg-primary text-primary-foreground",
                  state === "active" &&
                    "bg-primary/10 text-primary ring-4 ring-primary/15",
                  state === "failed" && "bg-red-500 text-white",
                  state === "pending" &&
                    "bg-muted text-muted-foreground/50",
                )}
              >
                {state === "done" ? (
                  <Check className="size-4.5" strokeWidth={3} />
                ) : state === "failed" ? (
                  <X className="size-4.5" strokeWidth={3} />
                ) : state === "active" && spinning ? (
                  <Loader2 className="size-4.5 animate-spin" />
                ) : (
                  i + 1
                )}
              </span>
              <span
                className={cn(
                  "text-xs font-semibold whitespace-nowrap",
                  state === "done" && "text-foreground",
                  state === "active" && "text-primary",
                  state === "failed" && "text-red-600",
                  state === "pending" && "text-muted-foreground/50",
                )}
              >
                {label}
              </span>
            </div>
            {i < PHASES.length - 1 && (
              <span className="relative mx-2 h-0.5 flex-1 overflow-hidden rounded-full bg-border">
                <span
                  className={cn(
                    "absolute inset-0 rounded-full bg-primary transition-transform duration-500",
                    connectorActive ? "translate-x-0" : "-translate-x-full",
                  )}
                />
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
