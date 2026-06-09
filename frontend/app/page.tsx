import { Dashboard } from "@/components/dashboard";

export default function Home() {
  return (
    <div className="space-y-8">
      <section className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
          <span className="font-extrabold text-slate-800">OY</span>
          <span className="font-semibold text-slate-500">GUARD</span>
        </h1>
        <p className="text-base text-muted-foreground sm:text-lg">
          컨테이너 이미지 취약점 스캔 · 조치 · 서명
        </p>
      </section>
      <Dashboard />
    </div>
  );
}
