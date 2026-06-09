"use client";

import { useState } from "react";

import { ScanForm } from "@/components/scan-form";
import { JobTable } from "@/components/job-table";
import { HealthStrip } from "@/components/health-strip";

export function Dashboard() {
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="space-y-6">
      <ScanForm onCreated={() => setRefreshKey((k) => k + 1)} />
      <HealthStrip />
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-muted-foreground">최근 작업</h2>
        <JobTable refreshKey={refreshKey} />
      </section>
    </div>
  );
}
