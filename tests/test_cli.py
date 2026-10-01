import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

from headerlint.cli import main


def run(argv, stdin_text=None):
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        if stdin_text is None:
            code = main(argv)
        else:
            with mock.patch("sys.stdin", io.StringIO(stdin_text)):
                code = main(argv)
    return code, err.getvalue()


class CliTests(unittest.TestCase):
    def test_clean_stdin_exits_zero(self):
        code, err = run([], "HTTP/1.1 200 OK\nHost: example.com\n")
        self.assertEqual((code, err), (0, ""))

    def test_error_exits_one_and_points_at_column(self):
        code, err = run(["-"], "Content-Length : 5\n")
        self.assertEqual(code, 1)
        lines = err.splitlines()
        self.assertTrue(lines[0].startswith("<stdin>:1:15: error:"))
        self.assertTrue(lines[0].endswith("[E004]"))
        self.assertEqual(lines[1], "    Content-Length : 5")
        self.assertEqual(lines[2], "    " + " " * 14 + "^")

    def test_reads_file_and_uses_its_name(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "h.txt")
            with open(path, "w", newline="") as f:
                f.write("no colon here\r\n")
            code, err = run([path])
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith(f"{path}:1:14: error:"))

    def test_file_keeps_bare_cr(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "h.txt")
            with open(path, "w", newline="") as f:
                f.write("X-Foo: a\rb\r\n")
            code, err = run([path])
        self.assertEqual(code, 1)
        self.assertIn("[E007]", err)

    def test_missing_file_exits_two(self):
        code, err = run(["/nonexistent/headers.txt"])
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err)


if __name__ == "__main__":
    unittest.main()
