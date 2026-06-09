"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Hammer,
  Loader2,
  ServerCrash,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { StatusBadge } from "@/components/status-badge";
import { StatusStepper } from "@/components/status-stepper";
import { SeverityCards } from "@/components/severity-cards";
import { SeverityChips } from "@/components/severity-chips";
import { VulnTable } from "@/components/vuln-table";
import { JobLogs } from "@/components/job-logs";
import { DeliveryPanel } from "@/components/delivery-panel";
import { BaseCompare } from "@/components/base-compare";
import { ApiError, getScan, remediate, sign } from "@/lib/api";
import { notifyJobDone } from "@/lib/notify";
import { isTerminal } from "@/lib/types";
import type { Job, RemediationStrategy } from "@/lib/types";

const STRATEGIES: { value: RemediationStrategy; label: string }[] = [
  { value: "copa", label: "copa (리포트 패치)" },
  { value: "copa-all", label: "copa-all (전체 OS)" },
  { value: "in-place", label: "in-place (apt/apk)" },
];

const POLL_MS = 2000;
const DEFAULT_KEY = "cosign.pub";

export function JobDetail({ id }: { id: string }) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState<"remediate" | "sign" | null>(null);
  const [strategy, setStrategy] = useState<RemediationStrategy>("copa");
  // Bumped after an action (remediate/sign) to restart polling — a job that had
  // reached a terminal state (failed/signed) stops polling, so re-running a step
  // must re-arm the loop to observe the new transitions.
  const [pollNonce, setPollNonce] = useState(0);
  const mounted = useRef(true);
  const prevStatus = useRef<Job["status"] | null>(null);

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const data = await getScan(id, signal);
        if (!mounted.current) return data;
        const prev = prevStatus.current;
        if (prev !== null && !isTerminal(prev) && isTerminal(data.status)) {
          notifyJobDone(data);
        }
        prevStatus.current = data.status;
        setJob(data);
        setError(null);
        return data;
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return null;
        if (mounted.current) {
          setError(
            err instanceof ApiError ? err.message : "작업을 불러올 수 없습니다.",
          );
        }
        return null;
      }
    },
    [id],
  );

  useEffect(() => {
    mounted.current = true;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();

    async function tick() {
      const data = await refresh(controller.signal);
      if (!mounted.current) return;
      // Keep polling while the pipeline runs OR a base comparison is running.
      if (!data || !isTerminal(data.status) || data.alternatives_running) {
        timer = setTimeout(tick, POLL_MS);
      }
    }

    tick();
    return () => {
      mounted.current = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [refresh, pollNonce]);

  async function handleRemediate() {
    setActing("remediate");
    try {
      await remediate(id, strategy);
      // Optimistically move the stepper to "조치 중" and clear any prior failure
      // so the UI responds immediately; polling will then track the real state.
      setJob((j) => (j ? { ...j, status: "remediating", error: null } : j));
      prevStatus.current = "remediating";
      setPollNonce((n) => n + 1);
      toast.success("조치를 시작했습니다.");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "조치 실행에 실패했습니다.",
      );
    } finally {
      setActing(null);
    }
  }

  async function handleSign() {
    setActing("sign");
    try {
      await sign(id, DEFAULT_KEY);
      setJob((j) => (j ? { ...j, status: "signing", error: null } : j));
      prevStatus.current = "signing";
      setPollNonce((n) => n + 1);
      toast.success("서명을 시작했습니다.");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "서명에 실패했습니다.",
      );
    } finally {
      setActing(null);
    }
  }

  if (error && job === null) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-red-200 bg-red-50/50 py-16 text-center">
        <ServerCrash className="size-8 text-red-400" />
        <p className="text-sm font-medium text-red-600">{error}</p>
        <Button asChild variant="outline" className="rounded-xl">
          <Link href="/">대시보드로 돌아가기</Link>
        </Button>
      </div>
    );
  }

  if (job === null) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64 rounded-xl" />
        <Skeleton className="h-20 w-full rounded-2xl" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-2xl" />
          ))}
        </div>
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    );
  }

  const canRemediate =
    job.status === "scanned" ||
    job.status === "remediated" ||
    job.status === "failed";
  const canSign = job.status === "remediated";

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3">
        <Link
          href="/"
          className="inline-flex w-fit items-center gap-1 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          대시보드
        </Link>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-mono text-xl font-bold tracking-tight sm:text-2xl">
              {job.image}
            </h1>
            <StatusBadge status={job.status} />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value as RemediationStrategy)}
              disabled={!canRemediate || acting !== null}
              className="h-9 rounded-xl border border-input bg-background px-3 text-sm font-medium shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:opacity-50"
              aria-label="조치 전략"
            >
              {STRATEGIES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
            <Button
              onClick={handleRemediate}
              disabled={!canRemediate || acting !== null}
              className="rounded-xl font-semibold"
            >
              {acting === "remediate" ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Hammer />
              )}
              조치 실행
            </Button>
            <Button
              onClick={handleSign}
              disabled={!canSign || acting !== null}
              variant="outline"
              className="rounded-xl font-semibold"
            >
              {acting === "sign" ? (
                <Loader2 className="animate-spin" />
              ) : (
                <ShieldCheck />
              )}
              서명
            </Button>
          </div>
        </div>
      </div>

      <Card className="rounded-2xl shadow-sm ring-1 ring-border/60">
        <CardContent className="px-6 py-7">
          <StatusStepper job={job} />
        </CardContent>
      </Card>

      {job.status === "failed" && job.error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
          <span className="font-semibold">오류: </span>
          {job.error}
        </div>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-muted-foreground">
          취약점 요약
        </h2>
        <SeverityCards summary={job.scan?.summary} />
      </section>

      <Tabs defaultValue="vulns" className="w-full">
        <TabsList className="rounded-xl">
          <TabsTrigger value="vulns">취약점</TabsTrigger>
          <TabsTrigger value="bases">베이스 비교</TabsTrigger>
          <TabsTrigger value="remediation">조치</TabsTrigger>
          <TabsTrigger value="signature">서명</TabsTrigger>
          <TabsTrigger value="delivery">받기</TabsTrigger>
          <TabsTrigger value="logs">로그</TabsTrigger>
        </TabsList>

        <TabsContent value="vulns" className="mt-4">
          {job.scan ? (
            <VulnTable vulnerabilities={job.scan.vulnerabilities} />
          ) : (
            <EmptyTab text="스캔이 완료되면 취약점 목록이 표시됩니다." />
          )}
        </TabsContent>

        <TabsContent value="bases" className="mt-4">
          <BaseCompare job={job} />
        </TabsContent>

        <TabsContent value="remediation" className="mt-4">
          {job.remediation ? (
            <Card className="rounded-2xl ring-1 ring-border/60">
              <CardHeader>
                <CardTitle className="text-base">조치 결과</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {job.remediation.rescan_ok === false && (
                  <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    <span className="font-semibold">⚠ 재스캔 실패</span>
                    <span>
                      패치된 이미지를 다시 스캔하지 못해 잔여 취약점을 확인할 수
                      없습니다. 아래 수치는 조치 전 원본 기준이며, 직접 재스캔이
                      필요합니다.
                    </span>
                  </div>
                )}
                <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <Field label="새 이미지" value={job.remediation.new_image} mono />
                  <Field label="베이스 이미지" value={job.remediation.base_image} mono />
                  <Field label="전략" value={job.remediation.strategy} />
                  <Field
                    label="해결된 취약점"
                    value={
                      job.remediation.rescan_ok === false
                        ? "확인 불가"
                        : `${job.remediation.fixed_count}건`
                    }
                  />
                </dl>
                <div>
                  <p className="mb-1.5 text-xs font-medium text-muted-foreground">
                    {job.remediation.rescan_ok === false
                      ? "남은 취약점 (미확인 — 원본 기준)"
                      : "남은 취약점"}
                  </p>
                  <SeverityChips summary={job.remediation.remaining} />
                </div>
                <div>
                  <p className="mb-1.5 text-xs font-medium text-muted-foreground">
                    생성된 Dockerfile
                  </p>
                  <pre className="overflow-x-auto rounded-xl border bg-slate-50 p-4 font-mono text-xs leading-relaxed">
                    {job.remediation.dockerfile}
                  </pre>
                </div>
              </CardContent>
            </Card>
          ) : (
            <EmptyTab text="조치가 실행되면 결과가 여기에 표시됩니다." />
          )}
        </TabsContent>

        <TabsContent value="signature" className="mt-4">
          {job.signature ? (
            <Card className="rounded-2xl ring-1 ring-border/60">
              <CardHeader>
                <CardTitle className="text-base">서명 정보</CardTitle>
              </CardHeader>
              <CardContent>
                <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <Field
                    label="서명 상태"
                    value={job.signature.signed ? "서명됨" : "미서명"}
                  />
                  <Field label="키" value={job.signature.key} mono />
                  <div className="sm:col-span-2">
                    <Field label="레퍼런스" value={job.signature.reference} mono />
                  </div>
                </dl>
              </CardContent>
            </Card>
          ) : (
            <EmptyTab text="서명이 완료되면 정보가 여기에 표시됩니다." />
          )}
        </TabsContent>

        <TabsContent value="delivery" className="mt-4">
          <DeliveryPanel job={job} />
        </TabsContent>

        <TabsContent value="logs" className="mt-4">
          <JobLogs logs={job.logs} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function EmptyTab({ text }: { text: string }) {
  return (
    <div className="rounded-2xl border border-dashed py-12 text-center text-sm text-muted-foreground">
      {text}
    </div>
  );
}

function Field({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd
        className={`mt-0.5 text-sm font-medium break-all ${mono ? "font-mono" : ""}`}
      >
        {value}
      </dd>
    </div>
  );
}
