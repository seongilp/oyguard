"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ChevronRight, Inbox, ServerCrash } from "lucide-react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/status-badge";
import { SeverityChips } from "@/components/severity-chips";
import { ApiError, listScans } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { notifyJobDone } from "@/lib/notify";
import { isTerminal } from "@/lib/types";
import type { Job, JobStatus } from "@/lib/types";

const POLL_MS = 3000;

interface JobTableProps {
  /** Bumping this value forces an immediate refresh. */
  refreshKey?: number;
}

export function JobTable({ refreshKey = 0 }: JobTableProps) {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);
  // Track last-seen status per job so we can fire a notification exactly once
  // when a job transitions into a terminal state.
  const prevStatus = useRef<Map<string, JobStatus>>(new Map());
  const seeded = useRef(false);

  useEffect(() => {
    mounted.current = true;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();

    async function tick() {
      try {
        const data = await listScans(controller.signal);
        if (!mounted.current) return;
        // On the first poll, just record current states (don't notify for
        // jobs that were already finished before the page opened).
        for (const job of data) {
          const prev = prevStatus.current.get(job.id);
          if (
            seeded.current &&
            prev !== undefined &&
            !isTerminal(prev) &&
            isTerminal(job.status)
          ) {
            notifyJobDone(job);
          }
          prevStatus.current.set(job.id, job.status);
        }
        seeded.current = true;
        setJobs(data);
        setError(null);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (!mounted.current) return;
        setError(
          err instanceof ApiError ? err.message : "목록을 불러올 수 없습니다.",
        );
      } finally {
        if (mounted.current) {
          timer = setTimeout(tick, POLL_MS);
        }
      }
    }

    tick();
    return () => {
      mounted.current = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [refreshKey]);

  if (error && jobs === null) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-red-200 bg-red-50/50 py-12 text-center">
        <ServerCrash className="size-7 text-red-400" />
        <p className="text-sm font-medium text-red-600">{error}</p>
        <p className="text-xs text-muted-foreground">
          백엔드가 실행 중인지 확인해 주세요.
        </p>
      </div>
    );
  }

  if (jobs === null) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed py-14 text-center">
        <Inbox className="size-7 text-muted-foreground/50" />
        <p className="text-sm font-medium">아직 스캔 기록이 없습니다</p>
        <p className="text-xs text-muted-foreground">
          위에서 이미지를 입력해 첫 스캔을 시작해 보세요.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border bg-card">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="pl-5">이미지</TableHead>
            <TableHead>상태</TableHead>
            <TableHead>취약점</TableHead>
            <TableHead className="text-right">생성</TableHead>
            <TableHead className="w-10" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {jobs.map((job) => (
            <TableRow
              key={job.id}
              className="group cursor-pointer transition-colors hover:bg-accent/50"
            >
              <TableCell className="pl-5">
                <Link
                  href={`/jobs/${job.id}`}
                  className="block font-mono text-sm font-medium text-foreground"
                >
                  {job.image}
                </Link>
              </TableCell>
              <TableCell>
                <Link href={`/jobs/${job.id}`} className="block">
                  <StatusBadge status={job.status} />
                </Link>
              </TableCell>
              <TableCell>
                <Link href={`/jobs/${job.id}`} className="block">
                  <SeverityChips summary={job.scan?.summary} />
                </Link>
              </TableCell>
              <TableCell className="text-right text-xs text-muted-foreground">
                <Link href={`/jobs/${job.id}`} className="block">
                  {relativeTime(job.created_at)}
                </Link>
              </TableCell>
              <TableCell>
                <Link href={`/jobs/${job.id}`} className="block">
                  <ChevronRight className="size-4 text-muted-foreground/40 transition-colors group-hover:text-primary" />
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
