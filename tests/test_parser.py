"""Tests for bleplot.parser"""
import pytest
from bleplot.parser import parse_line, parse_buffer


class TestParseLine:
    def test_integers(self):
        assert parse_line("1 2 3") == [1.0, 2.0, 3.0]

    def test_floats(self):
        assert parse_line("0.5 1.23 -3.7") == [0.5, 1.23, -3.7]

    def test_tab_separated(self):
        assert parse_line("1.0\t2.0\t3.0") == [1.0, 2.0, 3.0]

    def test_mixed_whitespace(self):
        assert parse_line("1.0  2.0\t3.0") == [1.0, 2.0, 3.0]

    def test_scientific_notation(self):
        assert parse_line("1e3 2.5e-2") == [1000.0, 0.025]

    def test_positive_sign(self):
        assert parse_line("+1.5 +2.5") == [1.5, 2.5]

    def test_single_value(self):
        assert parse_line("42.0") == [42.0]

    def test_empty_string(self):
        assert parse_line("") == []

    def test_non_numeric_rejected(self):
        assert parse_line("1.0 abc 3.0") == []

    def test_label_colon_format_rejected(self):
        # BSP rejects "label:value" format — not a pure float
        assert parse_line("sensor:1.0") == []

    def test_leading_trailing_spaces(self):
        assert parse_line("  1.0 2.0  ") == [1.0, 2.0]


class TestParseBuffer:
    def test_single_complete_line(self):
        data = b"1.0 2.0 3.0\n"
        rows, raw, acc, skip = parse_buffer(data, "", True)
        # first complete line is skipped
        assert rows == []
        assert acc == ""
        assert skip is False

    def test_second_call_delivers_data(self):
        data1 = b"1.0 2.0\n"
        rows1, _, acc, skip = parse_buffer(data1, "", True)
        assert rows1 == []

        data2 = b"3.0 4.0\n"
        rows2, raw2, acc, skip = parse_buffer(data2, acc, skip)
        assert rows2 == [[3.0, 4.0]]
        assert raw2 == ["3.0 4.0"]

    def test_partial_line_accumulation(self):
        # Notification split mid-line (common with small ESP32 MTU)
        data1 = b"1.0 "
        rows1, _, acc, skip = parse_buffer(data1, "", False)
        assert rows1 == []
        assert acc == "1.0 "

        data2 = b"2.0\n"
        rows2, _, acc, skip = parse_buffer(data2, acc, skip)
        assert rows2 == [[1.0, 2.0]]

    def test_multiple_lines_per_notification(self):
        data = b"1.0\n2.0\n3.0\n"
        # skip first
        rows, _, acc, skip = parse_buffer(data, "", True)
        assert rows == [[2.0], [3.0]]

    def test_incomplete_last_chunk(self):
        data = b"1.0 2.0\n3.0"
        rows, _, acc, skip = parse_buffer(data, "", False)
        assert rows == [[1.0, 2.0]]
        assert acc == "3.0"
