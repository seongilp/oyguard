import type { Metadata } from "next";
import { Geist_Mono } from "next/font/google";
import { ShieldCheck } from "lucide-react";
import Link from "next/link";

import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "oy-guard — 컨테이너 이미지 취약점 조치",
  description:
    "컨테이너 이미지 취약점 스캔 · 조치 · 서명을 한 곳에서. oy-guard.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className={`${geistMono.variable} h-full`}>
      <body className="min-h-full antialiased">
        <header className="sticky top-0 z-30 border-b border-border/60 bg-background/80 backdrop-blur">
          <div className="mx-auto flex h-14 w-full max-w-5xl items-center gap-2 px-4 sm:px-6">
            <Link href="/" className="flex items-center gap-2">
              <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <ShieldCheck className="size-4" />
              </span>
              <span className="text-base tracking-tight">
                <span className="font-extrabold text-slate-800">OY</span>
                <span className="font-semibold text-slate-500">GUARD</span>
              </span>
            </Link>
          </div>
        </header>
        <main className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 sm:py-10">
          {children}
        </main>
        <Toaster position="top-center" richColors />
      </body>
    </html>
  );
}
