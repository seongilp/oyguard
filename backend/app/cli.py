"""oyguard CLI — the workhorse interface for container image remediation.

Image remediation is fundamentally a CI/CD-shaped problem: it belongs where the
images already live (a runner, a registry-adjacent host), operating by layer/
digest rather than shuttling multi-GB tarballs through a browser. This CLI wraps
the SAME services the web API uses (scanner / remediator / signer / delivery), so
behavior never diverges — but for large images it pushes straight to a registry
(no `docker save`, no tar download).

Run with:  uv run python -m app.cli <command> ...
       or:  ./oyguard <command> ...   (repo-root wrapper)

Commands:
  scan  <image>                              Scan with Trivy + Grype.
  fix   <image> [--strategy] [--push T]      Scan → remediate; optionally push+sign.
  push  <image> <target>                     Tag+push to a registry, then sign.
  sign  <image>                              Offline blob-sign a local image.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import uuid4

from .core import imageref
from .models import ScanResult, Severity
from .services import delivery, remediator, scanner, signer

# ANSI colors (skipped when not a TTY).
_TTY = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _TTY else text


_SEV_COLOR = {
    Severity.CRITICAL: "31;1",
    Severity.HIGH: "31",
    Severity.MEDIUM: "33",
    Severity.LOW: "90",
    Severity.UNKNOWN: "90",
}


def _print_summary(scan: ScanResult, title: str = "스캔 결과") -> None:
    s = scan.summary
    print(f"\n{_c('1', title)}  ({scan.os_family or 'unknown'})")
    print(
        f"  총 {_c('1', str(s.total))}건  "
        f"{_c('31;1', 'CRIT ' + str(s.critical))}  "
        f"{_c('31', 'HIGH ' + str(s.high))}  "
        f"{_c('33', 'MED ' + str(s.medium))}  "
        f"{_c('90', 'LOW ' + str(s.low))}"
    )


def _print_top_vulns(scan: ScanResult, limit: int = 10) -> None:
    fixable = [v for v in scan.vulnerabilities if v.fixed_version]
    if not fixable:
        return
    print(f"\n  {_c('1', '수정 가능한 취약점 (상위 ' + str(limit) + ')')}")
    for v in fixable[:limit]:
        sev = _c(_SEV_COLOR[v.severity], f"{v.severity.value:8}")
        print(f"    {sev} {v.id:18} {v.package} {v.installed_version} → {v.fixed_version}")


async def cmd_scan(args: argparse.Namespace) -> int:
    image = imageref.normalize_image(args.image)
    print(f"스캔 중: {_c('1', image)} …")
    scan = await scanner.scan_image(image)
    _print_summary(scan)
    _print_top_vulns(scan)
    return 0


async def cmd_fix(args: argparse.Namespace) -> int:
    image = imageref.normalize_image(args.image)
    print(f"스캔 중: {_c('1', image)} …")
    scan = await scanner.scan_image(image)
    _print_summary(scan, "조치 전")

    print(f"\n조치 중 (전략: {_c('1', args.strategy)}) …")
    rem = await remediator.remediate(image, scan, args.strategy)
    print(f"  새 이미지: {_c('1', rem.new_image)}  (전략 {rem.strategy})")
    if not rem.rescan_ok:
        print(_c("33", "  ⚠ 재스캔 실패 — 잔여 취약점 미확인 (아래는 조치 전 기준)"))
    print(
        f"  해소 {_c('32', str(rem.fixed_count))}건  ·  "
        f"잔여 {rem.remaining.total}건 "
        f"(CRIT {rem.remaining.critical}, HIGH {rem.remaining.high})"
    )

    if args.push:
        print(f"\n레지스트리 푸시 (tar 없이 digest): {_c('1', args.push)} …")
        res = await delivery.push_ref(
            rem.new_image, args.push, args.username, args.password, sign=not args.no_sign
        )
        print(f"  {_c('32', res.message)}")
        if res.pull_command:
            print(f"  pull:   {res.pull_command}")
        if res.verify_command:
            print(f"  verify: {res.verify_command}")
    return 0


async def cmd_push(args: argparse.Namespace) -> int:
    print(f"푸시: {_c('1', args.image)} → {_c('1', args.target)} …")
    res = await delivery.push_ref(
        args.image, args.target, args.username, args.password, sign=not args.no_sign
    )
    print(f"  {_c('32', res.message)}")
    if res.pull_command:
        print(f"  pull:   {res.pull_command}")
    if res.verify_command:
        print(f"  verify: {res.verify_command}")
    return 0


async def cmd_sign(args: argparse.Namespace) -> int:
    print(f"오프라인 서명 (blob): {_c('1', args.image)} …")
    sig = await signer.sign_image(args.image, f"cli-{uuid4().hex[:8]}", args.key)
    print(f"  {_c('32', '서명 완료')}  ref={sig.reference}  key={sig.key}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="oyguard", description="컨테이너 이미지 취약점 스캔·조치·서명 CLI")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("scan", help="이미지 스캔 (Trivy + Grype)")
    sp.add_argument("image")
    sp.set_defaults(func=cmd_scan)

    fp = sub.add_parser("fix", help="스캔 후 조치 (+선택적 push/sign)")
    fp.add_argument("image")
    fp.add_argument("--strategy", choices=["copa", "copa-all", "in-place"], default="copa")
    fp.add_argument("--push", metavar="TARGET", help="조치 후 푸시할 레지스트리 주소")
    fp.add_argument("--username", default="")
    fp.add_argument("--password", default="")
    fp.add_argument("--no-sign", action="store_true", help="푸시 시 서명 건너뛰기")
    fp.set_defaults(func=cmd_fix)

    pp = sub.add_parser("push", help="로컬 이미지를 레지스트리로 푸시+서명")
    pp.add_argument("image")
    pp.add_argument("target")
    pp.add_argument("--username", default="")
    pp.add_argument("--password", default="")
    pp.add_argument("--no-sign", action="store_true")
    pp.set_defaults(func=cmd_push)

    gp = sub.add_parser("sign", help="로컬 이미지 오프라인 서명 (blob)")
    gp.add_argument("image")
    gp.add_argument("--key", default="cosign.pub")
    gp.set_defaults(func=cmd_sign)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(args.func(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001 - surface a clean message to the shell
        print(_c("31;1", f"오류: {exc}"), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
