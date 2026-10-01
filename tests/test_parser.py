import unittest

from headerlint.parser import lint, split_lines


def codes(text):
    return [(i.line, i.col, i.code) for i in lint(text)]


class SplitLinesTests(unittest.TestCase):
    def test_mixed_endings(self):
        self.assertEqual(split_lines("a\r\nb\nc"), ["a", "b", "c"])

    def test_trailing_newline_adds_no_line(self):
        self.assertEqual(split_lines("a\nb\n"), ["a", "b"])

    def test_interior_cr_is_kept(self):
        self.assertEqual(split_lines("a\rb\n"), ["a\rb"])

    def test_empty(self):
        self.assertEqual(split_lines(""), [])


class CleanInputTests(unittest.TestCase):
    def test_valid_response_headers(self):
        text = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 5\r\n\r\n"
        self.assertEqual(lint(text), [])

    def test_request_line_is_skipped(self):
        self.assertEqual(lint("GET /x HTTP/1.1\nHost: example.com\n"), [])

    def test_headers_without_start_line(self):
        self.assertEqual(lint("Host: example.com\n"), [])

    def test_body_after_blank_line_is_ignored(self):
        self.assertEqual(lint("A: b\n\nthis is not a header\n"), [])

    def test_empty_value_is_fine(self):
        self.assertEqual(lint("X-Empty:\n"), [])


class ErrorCodeTests(unittest.TestCase):
    def test_e001_missing_colon(self):
        self.assertEqual(codes("Not a header\n"), [(1, 13, "E001")])

    def test_e002_empty_name(self):
        self.assertEqual(codes(": value\n"), [(1, 1, "E002")])

    def test_indented_colon_line_is_folding_not_empty_name(self):
        # a leading-whitespace line is caught as E003 before the name is read
        self.assertEqual(codes("  : value\n"), [(1, 1, "E003")])

    def test_e003_obsolete_folding(self):
        text = "Foo: a\n  continued\n"
        self.assertEqual(codes(text), [(2, 1, "E003")])

    def test_e003_tab_folding(self):
        self.assertEqual(codes("Foo: a\n\tmore\n"), [(2, 1, "E003")])

    def test_e004_space_before_colon(self):
        self.assertEqual(codes("Content-Length : 348\n"), [(1, 15, "E004")])

    def test_e004_tab_before_colon(self):
        self.assertEqual(codes("Host\t: example.com\n"), [(1, 5, "E004")])

    def test_e005_invalid_name_character(self):
        self.assertEqual(codes("X-Bad Name: yes\n"), [(1, 6, "E005")])

    def test_e005_reports_only_first_bad_character(self):
        self.assertEqual(codes("A(B)C: v\n"), [(1, 2, "E005")])

    def test_e005_not_triggered_by_tchar_punctuation(self):
        self.assertEqual(lint("X-Weird_!#$%&'*+.^`|~: v\n"), [])

    def test_e006_conflicting_content_length(self):
        text = "Content-Length: 348\nContent-Length: 512\n"
        issues = lint(text)
        self.assertEqual([(i.line, i.col, i.code) for i in issues], [(2, 1, "E006")])
        self.assertIn("line 1", issues[0].message)

    def test_e006_matching_values_are_fine(self):
        self.assertEqual(lint("Content-Length: 5\nContent-Length:  5\n"), [])

    def test_e006_is_case_insensitive(self):
        text = "content-length: 1\nCONTENT-LENGTH: 2\n"
        self.assertEqual(codes(text), [(2, 1, "E006")])

    def test_e006_name_with_trailing_space_still_counts(self):
        text = "Content-Length : 1\nContent-Length: 2\n"
        self.assertEqual(codes(text), [(1, 15, "E004"), (2, 1, "E006")])

    def test_e006_each_conflicting_line_is_reported(self):
        text = "Content-Length: 1\nContent-Length: 2\nContent-Length: 3\n"
        self.assertEqual(codes(text), [(2, 1, "E006"), (3, 1, "E006")])

    def test_e007_embedded_cr(self):
        self.assertEqual(codes("X-Foo: a\rb\n"), [(1, 9, "E007")])

    def test_e007_not_triggered_by_crlf(self):
        self.assertEqual(lint("X-Foo: a\r\nY-Bar: b\r\n"), [])


class OrderingTests(unittest.TestCase):
    def test_issues_sorted_by_line_then_column(self):
        text = "Content-Length: 1\nBad Name : x\nContent-Length: 2\n"
        self.assertEqual(
            codes(text),
            [(2, 4, "E005"), (2, 9, "E004"), (3, 1, "E006")],
        )

    def test_severity_is_error_for_all_current_codes(self):
        text = "nocolon\n: x\n  fold\nA : b\nB C: d\nE: f\rg\n"
        self.assertTrue(all(i.severity == "error" for i in lint(text)))


if __name__ == "__main__":
    unittest.main()
