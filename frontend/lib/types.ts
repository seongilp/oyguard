// Domain types mirroring docs/API_CONTRACT.md (v1).

export type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";

export type JobStatus =
  | "queued"
  | "scanning"
  | "scanned"
  | "remediating"
  | "remediated"
  | "signing"
  | "signed"
  | "failed";

export type RemediationStrategy = "copa" | "copa-all" | "in-place";

export type LogLevel = "info" | "warn" | "error";

export interface Vulnerability {
  id: string;
  severity: Severity;
  package: string;
  installed_version: string;
  fixed_version: string; // "" when no fix is available
  title: string;
  sources: string[];
}

export interface ScanSummary {
  critical: number;
  high: number;
  medium: number;
  low: number;
  unknown: number;
  total: number;
}

export interface ScanResult {
  summary: ScanSummary;
  vulnerabilities: Vulnerability[];
  trivy_summary: ScanSummary;
  grype_summary: ScanSummary;
  os_family: string;
}

export interface RemediationResult {
  new_image: string;
  base_image: string;
  strategy: RemediationStrategy;
  remaining: ScanSummary;
  fixed_count: number;
  dockerfile: string;
  // False when the post-patch re-scan could not run; counts are unverified.
  rescan_ok: boolean;
}

export interface SignatureResult {
  signed: boolean;
  reference: string;
  key: string;
  bundle: string | null;
}

export interface BaseAlternative {
  image: string;
  available: boolean;
  summary: ScanSummary;
  note: string;
  error: string;
}

export interface JobLog {
  ts: string;
  level: LogLevel;
  message: string;
}

export interface Job {
  id: string;
  image: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  scan: ScanResult | null;
  remediation: RemediationResult | null;
  signature: SignatureResult | null;
  alternatives: BaseAlternative[] | null;
  alternatives_running: boolean;
  logs: JobLog[];
  error: string | null;
}

export interface HealthTools {
  trivy: boolean;
  grype: boolean;
  cosign: boolean;
  docker: boolean;
  copa: boolean;
}

export interface Health {
  status: string;
  tools: HealthTools;
}

export interface DeleteResult {
  deleted: boolean;
}

export interface Suggestion {
  value: string;
  kind: "repo" | "tag";
  official: boolean;
  description: string;
  stars: number;
}

export interface ArtifactInfo {
  image: string;
  image_available: boolean;
  signature_available: boolean;
  pubkey_available: boolean;
  load_command: string;
  verify_command: string;
}

export interface PushResult {
  target: string;
  digest: string;
  signed: boolean;
  pull_command: string;
  verify_command: string;
  message: string;
}

export interface ApiEnvelope<T> {
  success: boolean;
  data: T | null;
  error: string | null;
}

export const TERMINAL_STATUSES: readonly JobStatus[] = ["signed", "failed"];

export function isTerminal(status: JobStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}
