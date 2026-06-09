import type {
  ApiEnvelope,
  ArtifactInfo,
  DeleteResult,
  Health,
  Job,
  PushResult,
  RemediationStrategy,
  Suggestion,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ??
  "http://localhost:8000";

/**
 * Thrown when the backend is unreachable or returns a non-success envelope.
 * The UI layer can catch this to render friendly Korean error states.
 */
export class ApiError extends Error {
  readonly status: number | null;

  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
}

async function request<T>(
  path: string,
  { method = "GET", body, signal }: RequestOptions = {},
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw err;
    }
    throw new ApiError("백엔드에 연결할 수 없습니다.", null);
  }

  let envelope: ApiEnvelope<T> | null = null;
  try {
    envelope = (await res.json()) as ApiEnvelope<T>;
  } catch {
    if (!res.ok) {
      throw new ApiError(`요청에 실패했습니다 (${res.status}).`, res.status);
    }
    throw new ApiError("응답을 해석할 수 없습니다.", res.status);
  }

  if (!res.ok || !envelope.success) {
    throw new ApiError(
      envelope.error ?? `요청에 실패했습니다 (${res.status}).`,
      res.status,
    );
  }

  if (envelope.data === null) {
    throw new ApiError("응답 데이터가 비어 있습니다.", res.status);
  }

  return envelope.data;
}

export function getHealth(signal?: AbortSignal): Promise<Health> {
  return request<Health>("/api/health", { signal });
}

export function suggestImages(
  q: string,
  signal?: AbortSignal,
): Promise<Suggestion[]> {
  return request<Suggestion[]>(
    `/api/registry/suggest?q=${encodeURIComponent(q)}`,
    { signal },
  );
}

export function createScan(
  image: string,
  autoRemediate: boolean,
): Promise<Job> {
  return request<Job>("/api/scans", {
    method: "POST",
    body: { image, auto_remediate: autoRemediate },
  });
}

export function listScans(signal?: AbortSignal): Promise<Job[]> {
  return request<Job[]>("/api/scans", { signal });
}

export function getScan(id: string, signal?: AbortSignal): Promise<Job> {
  return request<Job>(`/api/scans/${encodeURIComponent(id)}`, { signal });
}

export function remediate(
  id: string,
  strategy: RemediationStrategy,
): Promise<Job> {
  return request<Job>(`/api/scans/${encodeURIComponent(id)}/remediate`, {
    method: "POST",
    body: { strategy },
  });
}

export function compareBases(id: string): Promise<Job> {
  return request<Job>(`/api/scans/${encodeURIComponent(id)}/compare`, {
    method: "POST",
  });
}

export function sign(id: string, key: string): Promise<Job> {
  return request<Job>(`/api/scans/${encodeURIComponent(id)}/sign`, {
    method: "POST",
    body: { key },
  });
}

export function deleteScan(id: string): Promise<DeleteResult> {
  return request<DeleteResult>(`/api/scans/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

// ---- delivery ---------------------------------------------------------------

export function getArtifacts(
  id: string,
  signal?: AbortSignal,
): Promise<ArtifactInfo> {
  return request<ArtifactInfo>(
    `/api/scans/${encodeURIComponent(id)}/artifacts`,
    { signal },
  );
}

/** Direct browser-download URLs (served as file attachments by the backend). */
export function downloadUrl(
  id: string,
  kind: "image" | "signature" | "pubkey",
): string {
  return `${API_BASE}/api/scans/${encodeURIComponent(id)}/download/${kind}`;
}

export function pushImage(
  id: string,
  target: string,
  username: string,
  password: string,
): Promise<PushResult> {
  return request<PushResult>(`/api/scans/${encodeURIComponent(id)}/push`, {
    method: "POST",
    body: { target, username, password },
  });
}
