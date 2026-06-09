"""Smoke tests for the CLI in demo mode (no real tools needed)."""
import os

os.environ.setdefault("OYGUARD_DEMO_MODE", "true")

from app.cli import build_parser, cmd_fix, cmd_scan


def test_parser_wires_all_commands():
    parser = build_parser()
    for cmd in ("scan", "fix", "push", "sign"):
        ns = parser.parse_args([cmd, "nginx:1.25"] + (["t"] if cmd == "push" else []))
        assert ns.command == cmd
        assert callable(ns.func)


def test_fix_defaults_to_copa():
    ns = build_parser().parse_args(["fix", "nginx:1.25"])
    assert ns.strategy == "copa"
    assert ns.push is None


async def test_scan_runs_in_demo(capsys):
    ns = build_parser().parse_args(["scan", "nginx:1.25"])
    rc = await cmd_scan(ns)
    assert rc == 0
    assert "스캔 결과" in capsys.readouterr().out


async def test_fix_runs_in_demo(capsys):
    ns = build_parser().parse_args(["fix", "nginx:1.25", "--strategy", "copa"])
    rc = await cmd_fix(ns)
    assert rc == 0
    out = capsys.readouterr().out
    assert "조치 중" in out
    assert "oy-remediated" in out
