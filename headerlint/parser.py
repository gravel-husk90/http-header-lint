"""Core linting logic.

The input is whatever a developer can get their hands on: a curl -D dump,
headers pasted out of the browser network tab, a chunk of a .http file. All
of these use CRLF or LF line endings inconsistently, so the first job is to
split the text into lines without losing track of where each character sits,
since every diagnostic below is only useful if the line/column it points at
is exactly right.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass

# RFC 7230 section 3.2.6: token = 1*tchar
TCHAR = set("!#$%&'*+-.^_`|~") | set(string.ascii_letters) | set(string.digits)

STATUS_LINE_RE = re.compile(r"^HTTP/\d\.\d \d{3}(?: .*)?$")
REQUEST_LINE_RE = re.compile(r"^[A-Za-z]+ \S+ HTTP/\d\.\d$")


@dataclass
class Issue:
    line: int
    col: int
    severity: str  # "error" or "warning"
    code: str
    message: str


def split_lines(text: str) -> list[str]:
    """Split on line endings, tolerating a mix of CRLF and bare LF.

    A trailing newline at the very end of the text does not produce a
    phantom empty final line, matching how editors show line counts.
    """
    raw_lines = text.split("\n")
    if raw_lines and raw_lines[-1] == "":
        raw_lines = raw_lines[:-1]
    return [line[:-1] if line.endswith("\r") else line for line in raw_lines]


def _split_field(raw: str) -> tuple[str, str] | None:
    colon = raw.find(":")
    if colon <= 0:
        return None
    return raw[:colon], raw[colon + 1 :]


def _check_line(raw: str, line_no: int) -> list[Issue]:
    issues: list[Issue] = []

    if raw[:1] in (" ", "\t"):
        issues.append(
            Issue(
                line_no,
                1,
                "error",
                "E003",
                "obsolete line folding: a header value must not continue on "
                "an indented line (RFC 7230 removed support for this)",
            )
        )
        return issues

    colon = raw.find(":")
    if colon == -1:
        issues.append(
            Issue(
                line_no,
                len(raw) + 1,
                "error",
                "E001",
                "missing ':' — a header line must be 'Name: value'",
            )
        )
        return issues

    name = raw[:colon]
    stripped_name = name.rstrip(" \t")

    if stripped_name == "":
        issues.append(
            Issue(line_no, 1, "error", "E002", "header field name is empty")
        )
        return issues

    if stripped_name != name:
        col = len(stripped_name) + 1
        issues.append(
            Issue(
                line_no,
                col,
                "error",
                "E004",
                "whitespace before ':' is not allowed (RFC 7230 section "
                "3.2.4) — some servers strip it and some don't, which is "
                "exactly the ambiguity request smuggling exploits",
            )
        )

    for idx, ch in enumerate(stripped_name):
        if ch not in TCHAR:
            issues.append(
                Issue(
                    line_no,
                    idx + 1,
                    "error",
                    "E005",
                    f"invalid character {ch!r} in header field name — only "
                    "letters, digits and !#$%&'*+-.^_`|~ are allowed "
                    "(RFC 7230 section 3.2.6)",
                )
            )
            break

    # split_lines() only strips a *trailing* CR from each line, so a bare CR
    # anywhere else in the value survives into `raw`. That's a line ending a
    # naive parser can act on even though ours didn't split there — the same
    # trick behind HTTP response splitting.
    value = raw[colon + 1 :]
    cr_idx = value.find("\r")
    if cr_idx != -1:
        issues.append(
            Issue(
                line_no,
                colon + 2 + cr_idx,
                "error",
                "E007",
                "embedded CR in header value with no following LF — a bare "
                "carriage return is treated as a line ending by some "
                "parsers, letting it splice in an extra header or response "
                "(CRLF injection / response splitting)",
            )
        )

    return issues


def lint(text: str) -> list[Issue]:
    """Lint a raw block of HTTP header text and return sorted issues."""
    issues: list[Issue] = []
    lines = split_lines(text)

    start = 0
    if lines and (STATUS_LINE_RE.match(lines[0]) or REQUEST_LINE_RE.match(lines[0])):
        start = 1

    content_lengths: list[tuple[int, str]] = []

    for i in range(start, len(lines)):
        raw = lines[i]
        if raw == "":
            break  # blank line marks the end of the header block
        line_no = i + 1
        issues.extend(_check_line(raw, line_no))

        field = _split_field(raw)
        if field is not None:
            name, value = field
            if name.rstrip(" \t").lower() == "content-length":
                content_lengths.append((line_no, value.strip()))

    if len(content_lengths) > 1:
        first_line, first_value = content_lengths[0]
        for line_no, value in content_lengths[1:]:
            if value != first_value:
                issues.append(
                    Issue(
                        line_no,
                        1,
                        "error",
                        "E006",
                        f"Content-Length value {value!r} conflicts with "
                        f"{first_value!r} on line {first_line} — a classic "
                        "HTTP request smuggling vector",
                    )
                )

    issues.sort(key=lambda issue: (issue.line, issue.col))
    return issues
