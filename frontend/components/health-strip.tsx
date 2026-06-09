"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, XCircle, Activity } from "lucide-react";

import { getHealth } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Health, HealthTools } from "@/lib/types";

const TOOL_ORDER: (keyof HealthTools)[] = [
  "trivy",
  "grype",
  "copa",
  "cosign",
  "docker",
];

export function HealthStrip() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal)
      .then((h) => {
        setHealth(h);
        setError(false);
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(true);
      });
    return () => controller.abort();
  }, []);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <Activity className="size-3.5" />
        도구 상태
      </span>
      {error && (
        <span className="rounded-full border border-red-200 bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600">
          백엔드에 연결할 수 없습니다
        </span>
      )}
      {!error &&
        !health &&
        TOOL_ORDER.map((tool) => (
          <span
            key={tool}
            className="h-6 w-20 animate-pulse rounded-full bg-muted"
          />
        ))}
      {!error &&
        health &&
        TOOL_ORDER.map((tool) => {
          const ok = health.tools[tool];
          return (
            <span
              key={tool}
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold",
                ok
                  ? "border-green-200 bg-green-50 text-green-700"
                  : "border-slate-200 bg-slate-50 text-slate-400",
              )}
            >
              {ok ? (
                <CheckCircle2 className="size-3.5" />
              ) : (
                <XCircle className="size-3.5" />
              )}
              {tool}
            </span>
          );
        })}
    </div>
  );
}
