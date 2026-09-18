# headerlint

A command-line tool that checks a raw block of HTTP headers for syntax
problems and dangerous ambiguities, and points at the exact line and column
where each one lives.

## Why

HTTP headers look like plain text, so it's easy to assume any text file full
of `Name: value` lines is fine. It isn't. A stray space before a colon, a
second `Content-Length` header with a different value, an indented
continuation line — these all parse "successfully" in some tools and get
silently reinterpreted by others. That gap between how a proxy and an origin
server parse the same bytes is the basis of most HTTP request smuggling
bugs. `headerlint` exists to catch the small stuff before it becomes that
kind of bug, and to say exactly where the problem is instead of just "parse
error".

## Usage

Point it at a file:

```
$ headerlint response_headers.txt
```

Or pipe headers straight from curl:

```
$ curl -sD - -o /dev/null https://example.com | headerlint
```

Example input with a couple of problems:

```
HTTP/1.1 200 OK
Content-Type: text/html
Content-Length : 348
Content-Length: 512
X-Bad Name: yes
```

Output:

```
<stdin>:3:15: error: whitespace before ':' is not allowed (RFC 7230 section 3.2.4) — some servers strip it and some don't, which is exactly the ambiguity request smuggling exploits [E004]
    Content-Length : 348
                  ^
<stdin>:4:1: error: Content-Length value '512' conflicts with '348' on line 3 — a classic HTTP request smuggling vector [E006]
    Content-Length: 512
    ^
<stdin>:5:6: error: invalid character ' ' in header field name — only letters, digits and !#$%&'*+-.^_`|~ are allowed (RFC 7230 section 3.2.6) [E005]
    X-Bad Name: yes
         ^
```

Exit code is `1` if any error was reported, `0` otherwise. Reads stdin by
default, so `headerlint -` and plain `headerlint` behave the same.

## What it checks right now

| Code | Problem |
|------|---------|
| E001 | line has no `:` separating a field name from a value |
| E002 | field name is empty |
| E003 | obsolete line folding (a line starts with whitespace) |
| E004 | whitespace between the field name and the `:` |
| E005 | field name contains a character outside RFC 7230's `token` set |
| E006 | multiple `Content-Length` headers with conflicting values |

The first line is recognized as a status line or request line (e.g. `HTTP/1.1
200 OK`) and skipped, since real header dumps usually include it. A blank
line ends the header block, so anything after it (a response body, for
instance) is ignored rather than misread as more headers.

## Installing

No dependencies beyond the Python standard library.

```
$ pip install -e .
$ headerlint --help
```

## License

MIT, see [LICENSE](LICENSE).
