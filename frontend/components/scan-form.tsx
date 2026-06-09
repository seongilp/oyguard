"use client";

// Debounced autocomplete fetch legitimately sets state inside effects.
/* eslint-disable react-hooks/set-state-in-effect */

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, ScanLine, Star, Tag } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, createScan, suggestImages } from "@/lib/api";
import { requestNotifyPermission } from "@/lib/notify";
import type { Suggestion } from "@/lib/types";

interface ScanFormProps {
  onCreated?: () => void;
}

export function ScanForm({ onCreated }: ScanFormProps) {
  const router = useRouter();
  const [image, setImage] = useState("");
  const [autoRemediate, setAutoRemediate] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Docker Hub autocomplete state.
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const justPicked = useRef(false);
  const boxRef = useRef<HTMLDivElement>(null);

  // Debounced suggestion fetch as the user types.
  useEffect(() => {
    const q = image.trim();
    if (justPicked.current) {
      justPicked.current = false;
      return;
    }
    if (q.length < 2) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    const controller = new AbortController();
    const t = setTimeout(async () => {
      try {
        const data = await suggestImages(q, controller.signal);
        setSuggestions(data);
        setOpen(data.length > 0);
        setActive(-1);
      } catch {
        // ignore — autocomplete is best-effort
      }
    }, 200);
    return () => {
      clearTimeout(t);
      controller.abort();
    };
  }, [image]);

  // Close the dropdown on outside click.
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  function pick(value: string) {
    justPicked.current = true;
    setImage(value);
    setOpen(false);
    setActive(-1);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || suggestions.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => (i + 1) % suggestions.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => (i <= 0 ? suggestions.length - 1 : i - 1));
    } else if (e.key === "Enter" && active >= 0) {
      e.preventDefault();
      pick(suggestions[active].value);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = image.trim();
    if (!trimmed) {
      toast.error("이미지 URL을 입력해 주세요.");
      return;
    }
    setSubmitting(true);
    void requestNotifyPermission();
    try {
      const job = await createScan(trimmed, autoRemediate);
      toast.success("스캔을 시작했습니다.", { description: trimmed });
      setImage("");
      setAutoRemediate(false);
      onCreated?.();
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "스캔 시작에 실패했습니다.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="rounded-2xl border-0 shadow-md ring-1 ring-border/60">
      <CardContent className="p-6 sm:p-8">
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <Label htmlFor="image" className="text-sm font-semibold">
              컨테이너 이미지
            </Label>
            <div className="flex flex-col gap-3 sm:flex-row">
              <div ref={boxRef} className="relative flex-1">
                <Input
                  id="image"
                  value={image}
                  onChange={(e) => setImage(e.target.value)}
                  onKeyDown={onKeyDown}
                  onFocus={() => suggestions.length > 0 && setOpen(true)}
                  placeholder="nginx:1.25  ·  ghcr.io/org/app:tag"
                  autoComplete="off"
                  spellCheck={false}
                  role="combobox"
                  aria-expanded={open}
                  aria-autocomplete="list"
                  className="h-12 rounded-xl text-base"
                  disabled={submitting}
                />
                {open && (
                  <ul className="absolute z-20 mt-2 max-h-80 w-full overflow-auto rounded-xl border bg-popover p-1.5 shadow-lg">
                    {suggestions.map((s, i) => (
                      <li key={s.value}>
                        <button
                          type="button"
                          onMouseDown={(e) => {
                            e.preventDefault();
                            pick(s.value);
                          }}
                          onMouseEnter={() => setActive(i)}
                          className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left transition-colors ${
                            i === active ? "bg-accent" : "hover:bg-accent/60"
                          }`}
                        >
                          {s.kind === "tag" ? (
                            <Tag className="size-4 shrink-0 text-muted-foreground" />
                          ) : (
                            <ScanLine className="size-4 shrink-0 text-muted-foreground" />
                          )}
                          <span className="flex-1 truncate font-mono text-sm">
                            {s.value}
                          </span>
                          {s.official && (
                            <span className="shrink-0 rounded-md bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary">
                              official
                            </span>
                          )}
                          {s.kind === "repo" && s.stars > 0 && (
                            <span className="flex shrink-0 items-center gap-0.5 text-xs text-muted-foreground">
                              <Star className="size-3 fill-amber-400 text-amber-400" />
                              {s.stars >= 1000
                                ? `${(s.stars / 1000).toFixed(1)}k`
                                : s.stars}
                            </span>
                          )}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <Button
                type="submit"
                disabled={submitting}
                className="h-12 shrink-0 rounded-xl px-6 text-base font-semibold sm:w-40"
              >
                {submitting ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <ScanLine />
                )}
                스캔 시작
              </Button>
            </div>
          </div>

          <label className="flex w-fit cursor-pointer items-center gap-2.5 text-sm text-muted-foreground">
            <Checkbox
              checked={autoRemediate}
              onCheckedChange={(v) => setAutoRemediate(v === true)}
              disabled={submitting}
            />
            <span>
              <span className="font-medium text-foreground">자동 조치</span> —
              스캔 후 자동으로 취약점을 조치합니다
            </span>
          </label>
        </form>
      </CardContent>
    </Card>
  );
}
