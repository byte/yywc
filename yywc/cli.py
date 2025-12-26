from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .export_reader import read_export
from .report import build_report
from .share_card import build_share_svg


def _parse_roles(value: str) -> set[str]:
    roles = {part.strip() for part in value.split(",") if part.strip()}
    if not roles:
        raise argparse.ArgumentTypeError("role list is empty")
    return roles


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="yywc",
        description="Generate a local 'Your Year With Chat' report from a ChatGPT data export zip.",
    )
    parser.add_argument("--export", required=True, help="Path to ChatGPT export .zip or extracted folder")
    parser.add_argument("--out", default="out", help="Output directory (default: out)")
    parser.add_argument(
        "--extract-dir",
        default=None,
        help="Optional directory to extract the zip into (default: temporary directory)",
    )
    parser.add_argument("--year", type=int, default=None, help="Filter to a specific year (default: all years)")
    parser.add_argument(
        "--role-scope",
        type=_parse_roles,
        default={"user", "assistant"},
        help="Comma-separated roles to include (default: user,assistant)",
    )
    parser.add_argument(
        "--redact",
        action="store_true",
        help="Redact likely personal data (emails/phones/urls) in report excerpts",
    )
    parser.add_argument(
        "--max-excerpts",
        type=int,
        default=12,
        help="Max conversation excerpts in report (default: 12)",
    )
    args = parser.parse_args(argv)

    export_path = Path(args.export).expanduser()
    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    extract_dir = Path(args.extract_dir).expanduser() if args.extract_dir else None
    dataset = read_export(export_path, year=args.year, role_scope=args.role_scope, extract_dir=extract_dir)
    report = build_report(
        dataset,
        year=args.year,
        redact=args.redact,
        max_excerpts=args.max_excerpts,
    )

    year_label = str(args.year) if args.year is not None else "All time"
    share_svg = build_share_svg(report.summary, year_label=year_label)

    (out_dir / "summary.json").write_text(json.dumps(asdict(report.summary), indent=2, ensure_ascii=False) + "\n")
    (out_dir / "report.html").write_text(report.html, encoding="utf-8")
    (out_dir / "share.svg").write_text(share_svg, encoding="utf-8")

    print(f"Wrote: {out_dir / 'report.html'}")
    print(f"Wrote: {out_dir / 'summary.json'}")
    print(f"Wrote: {out_dir / 'share.svg'}")
    return 0
