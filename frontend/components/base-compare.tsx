"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Award, Layers, Loader2, ScanLine, XCircle } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { SeverityChips } from "@/components/severity-chips";
import { ApiError, compareBases, createScan } from "@/lib/api";
import { requestNotifyPermission } from "@/lib/notify";
import type { BaseAlternative, Job } from "@/lib/types";

export function BaseCompare({ job }: { job: Job }) {
  const router = useRouter();
  const [starting, setStarting] = useState(false);
  const [scanning, setScanning] = useState<string | null>(null);

  const running = job.alternatives_running || starting;
  const alts = job.alternatives;

  async function handleCompare() {
    setStarting(true);
    try {
      await compareBases(job.id);
      toast.success("베이스 비교를 시작했습니다.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "비교 시작에 실패했습니다.");
    } finally {
      setStarting(false);
    }
  }

  async function scanAlternative(image: string) {
    setScanning(image);
    void requestNotifyPermission();
    try {
      const newJob = await createScan(image, false);
      toast.success("새 베이스로 스캔을 시작했습니다.", { description: image });
      router.push(`/jobs/${newJob.id}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "스캔 시작에 실패했습니다.");
    } finally {
      setScanning(null);
    }
  }

  // Lowest-vuln available candidate that isn't the current image.
  const best = alts
    ?.filter((a) => a.available && a.image !== job.image)
    .reduce<BaseAlternative | null>(
      (acc, a) => (acc === null || a.summary.total < acc.summary.total ? a : acc),
      null,
    );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-2xl border bg-blue-50/50 p-4">
        <div className="space-y-1">
          <p className="flex items-center gap-1.5 text-sm font-semibold">
            <Layers className="size-4 text-primary" />
            하드닝 베이스 비교
          </p>
          <p className="text-xs text-muted-foreground">
            패치로는 못 고치는 취약점이 많습니다. 같은 소프트웨어의 더 작은
            베이스(alpine·slim·Chainguard)를 스캔해 비교합니다.
          </p>
        </div>
        <Button onClick={handleCompare} disabled={running} className="rounded-xl font-semibold">
          {running ? <Loader2 className="animate-spin" /> : <Layers />}
          {alts ? "다시 비교" : "비교 실행"}
        </Button>
      </div>

      {running && !alts && (
        <div className="flex items-center justify-center gap-2 rounded-2xl border border-dashed py-12 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          후보 베이스 이미지를 스캔하는 중… (이미지를 받아오므로 한두 번 걸립니다)
        </div>
      )}

      {!alts && !running && (
        <div className="rounded-2xl border border-dashed py-12 text-center text-sm text-muted-foreground">
          비교 실행을 누르면 더 안전한 베이스 후보를 찾아 취약점 수를 비교합니다.
        </div>
      )}

      {best && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm">
          <Award className="size-4 shrink-0 text-emerald-600" />
          <span>
            추천: <span className="font-mono font-semibold">{best.image}</span> 로
            바꾸면 취약점이{" "}
            <span className="font-semibold text-emerald-700">
              {job.scan?.summary.total ?? "?"} → {best.summary.total}
            </span>{" "}
            로 줄어듭니다.
          </span>
        </div>
      )}

      {alts && (
        <div className="overflow-hidden rounded-2xl border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-2.5 text-left font-medium">이미지</th>
                <th className="px-4 py-2.5 text-left font-medium">취약점</th>
                <th className="px-4 py-2.5 text-right font-medium" />
              </tr>
            </thead>
            <tbody>
              {alts.map((a) => {
                const isCurrent = a.image === job.image;
                const isBest = best?.image === a.image;
                return (
                  <tr
                    key={a.image}
                    className={`border-t ${isBest ? "bg-emerald-50/50" : ""}`}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm break-all">{a.image}</span>
                        {isCurrent && (
                          <span className="shrink-0 rounded-md bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600">
                            현재
                          </span>
                        )}
                        {isBest && (
                          <span className="shrink-0 rounded-md bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700">
                            추천
                          </span>
                        )}
                      </div>
                      {a.note && !isCurrent && (
                        <p className="mt-0.5 text-xs text-muted-foreground">{a.note}</p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {a.available ? (
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold tabular-nums">
                            {a.summary.total}
                          </span>
                          <SeverityChips summary={a.summary} />
                        </div>
                      ) : (
                        <span className="flex items-center gap-1 text-xs text-muted-foreground">
                          <XCircle className="size-3.5" />
                          {a.error || "사용 불가"}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {a.available && !isCurrent && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="rounded-lg"
                          disabled={scanning !== null}
                          onClick={() => scanAlternative(a.image)}
                        >
                          {scanning === a.image ? (
                            <Loader2 className="animate-spin" />
                          ) : (
                            <ScanLine />
                          )}
                          이 베이스로 스캔
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
