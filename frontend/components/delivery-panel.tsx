"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Check,
  Copy,
  Download,
  FileKey,
  FileSignature,
  Loader2,
  Package,
  UploadCloud,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  ApiError,
  downloadUrl,
  getArtifacts,
  pushImage,
} from "@/lib/api";
import type { ArtifactInfo, Job, PushResult } from "@/lib/types";

function CommandBlock({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("복사에 실패했습니다.");
    }
  }
  return (
    <div className="flex items-center gap-2 rounded-xl border bg-slate-50 px-3.5 py-2.5">
      <code className="flex-1 overflow-x-auto font-mono text-xs whitespace-nowrap text-slate-700">
        {command}
      </code>
      <button
        type="button"
        onClick={copy}
        className="shrink-0 text-muted-foreground transition-colors hover:text-foreground"
        aria-label="복사"
      >
        {copied ? (
          <Check className="size-4 text-emerald-500" />
        ) : (
          <Copy className="size-4" />
        )}
      </button>
    </div>
  );
}

export function DeliveryPanel({ job }: { job: Job }) {
  const [info, setInfo] = useState<ArtifactInfo | null>(null);
  const [target, setTarget] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [pushing, setPushing] = useState(false);
  const [pushResult, setPushResult] = useState<PushResult | null>(null);

  const load = useCallback(async () => {
    try {
      setInfo(await getArtifacts(job.id));
    } catch {
      setInfo(null);
    }
  }, [job.id]);

  useEffect(() => {
    // Async fetch — state is set after an await, not synchronously.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load, job.status]);

  async function handlePush(e: React.FormEvent) {
    e.preventDefault();
    const t = target.trim();
    if (!t) {
      toast.error("대상 레지스트리 주소를 입력해 주세요.");
      return;
    }
    setPushing(true);
    try {
      const result = await pushImage(job.id, t, username, password);
      setPushResult(result);
      toast.success(result.message);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "푸시에 실패했습니다.");
    } finally {
      setPushing(false);
    }
  }

  if (job.remediation === null) {
    return (
      <div className="rounded-2xl border border-dashed py-12 text-center text-sm text-muted-foreground">
        조치가 완료되면 결과물을 받을 수 있습니다.
      </div>
    );
  }

  const signed = job.signature?.signed === true;

  return (
    <div className="space-y-4">
      {/* Download */}
      <Card className="rounded-2xl ring-1 ring-border/60">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Download className="size-4 text-primary" />
            다운로드
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline" className="rounded-xl">
              <a href={downloadUrl(job.id, "image")} download>
                <Package /> 이미지 (.tar)
              </a>
            </Button>
            <Button
              asChild
              variant="outline"
              className="rounded-xl"
              disabled={!signed}
            >
              <a
                href={signed ? downloadUrl(job.id, "signature") : undefined}
                download
                aria-disabled={!signed}
                className={!signed ? "pointer-events-none opacity-50" : ""}
              >
                <FileSignature /> 서명 번들
              </a>
            </Button>
            <Button
              asChild
              variant="outline"
              className="rounded-xl"
              disabled={!signed}
            >
              <a
                href={signed ? downloadUrl(job.id, "pubkey") : undefined}
                download
                aria-disabled={!signed}
                className={!signed ? "pointer-events-none opacity-50" : ""}
              >
                <FileKey /> 공개키
              </a>
            </Button>
          </div>

          <div className="space-y-2.5">
            <div>
              <p className="mb-1.5 text-xs font-medium text-muted-foreground">
                내 도커에 불러오기
              </p>
              <CommandBlock
                command={info?.load_command ?? "docker load -i image.tar"}
              />
            </div>
            {signed && info?.verify_command && (
              <div>
                <p className="mb-1.5 text-xs font-medium text-muted-foreground">
                  서명 검증 (다운로드한 3개 파일을 같은 폴더에 두고 실행)
                </p>
                <CommandBlock command={info.verify_command} />
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Push to registry */}
      <Card className="rounded-2xl ring-1 ring-border/60">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <UploadCloud className="size-4 text-primary" />
            레지스트리로 내보내기
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handlePush} className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="target" className="text-xs font-medium">
                대상 주소
              </Label>
              <Input
                id="target"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                placeholder="ghcr.io/me/app:1.0-secure"
                autoComplete="off"
                spellCheck={false}
                className="h-11 rounded-xl font-mono text-sm"
                disabled={pushing}
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="username" className="text-xs font-medium">
                  사용자 (선택)
                </Label>
                <Input
                  id="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="off"
                  className="h-11 rounded-xl text-sm"
                  disabled={pushing}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password" className="text-xs font-medium">
                  토큰/비밀번호 (선택)
                </Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="off"
                  className="h-11 rounded-xl text-sm"
                  disabled={pushing}
                />
              </div>
            </div>
            <Button
              type="submit"
              disabled={pushing}
              className="rounded-xl font-semibold"
            >
              {pushing ? <Loader2 className="animate-spin" /> : <UploadCloud />}
              푸시 및 서명
            </Button>
            <p className="text-xs text-muted-foreground">
              인증을 비우면 서버에 이미 로그인된 자격증명(docker login)을
              사용합니다.
            </p>
          </form>

          {pushResult && (
            <>
              <Separator />
              <div className="space-y-2.5">
                <p className="text-sm font-semibold text-emerald-600">
                  {pushResult.message}
                </p>
                {pushResult.pull_command && (
                  <div>
                    <p className="mb-1.5 text-xs font-medium text-muted-foreground">
                      받는 쪽에서 pull
                    </p>
                    <CommandBlock command={pushResult.pull_command} />
                  </div>
                )}
                {pushResult.verify_command && (
                  <div>
                    <p className="mb-1.5 text-xs font-medium text-muted-foreground">
                      서명 검증
                    </p>
                    <CommandBlock command={pushResult.verify_command} />
                  </div>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
