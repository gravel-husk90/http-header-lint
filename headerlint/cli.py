"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys

from .parser import Issue, lint, split_lines


def _format_issue(issue: Issue, filename: str, lines: list[str]) -> str:
    header = f"{filename}:{issue.line}:{issue.col}: {issue.severity}: {issue.message} [{issue.code}]"
    if 1 <= issue.line <= len(lines):
        source = lines[issue.line - 1]
        pointer = " " * (issue.col - 1) + "^"
        return f"{header}\n    {source}\n    {pointer}"
    return header


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="headerlint",
        description=(
            "Check a raw block of HTTP headers for syntax errors and "
            "dangerous ambiguities, with exact line/column locations."
        ),
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="-",
        help="file containing header text, or '-' to read stdin (default)",
    )
    args = parser.parse_args(argv)

    if args.path == "-":
        text = sys.stdin.read()
        display_name = "<stdin>"
    else:
        try:
            with open(args.path, "r", newline="") as f:
                text = f.read()
        except OSError as exc:
            print(f"headerlint: cannot read {args.path}: {exc.strerror}", file=sys.stderr)
            return 2
        display_name = args.path

    issues = lint(text)
    lines = split_lines(text)

    for issue in issues:
        print(_format_issue(issue, display_name, lines), file=sys.stderr)

    if any(issue.severity == "error" for issue in issues):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
