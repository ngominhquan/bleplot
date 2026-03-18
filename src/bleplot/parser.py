"""
Parse incoming BLE bytes (NUS UTF-8) into lists of floats.
Mirrors BSP's parse_buffer / parse_line logic exactly.
"""
import re

_SPLIT_RE = re.compile(r"[\t ]+")
_FLOAT_RE = re.compile(r"^[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$")


def parse_line(line: str) -> list[float]:
    """
    Split a single text line on whitespace/tab and validate every token
    as a floating-point number.  Returns [] if any token is non-numeric
    (matches BSP: whole line is discarded on any parse failure).
    """
    line = line.strip()
    if not line:
        return []
    tokens = _SPLIT_RE.split(line)
    values: list[float] = []
    for tok in tokens:
        if not tok:
            continue
        if not _FLOAT_RE.match(tok):
            return []
        try:
            values.append(float(tok))
        except ValueError:
            return []
    return values


def parse_buffer(
    data: bytes,
    accumulator: str,
    skip_first: bool,
) -> tuple[list[list[float]], list[str], str, bool]:
    """
    Process a raw BLE notification packet.

    Parameters
    ----------
    data        : raw bytes from BLE notification
    accumulator : partial line carried over from previous call
    skip_first  : True until the very first complete line has been discarded
                  (mirrors BSP's 'skip first line' behaviour to avoid partial
                  lines at the start of a session)

    Returns
    -------
    parsed_rows  : list of successfully parsed float rows
    raw_lines    : complete text lines (for the BLE monitor display)
    accumulator  : updated partial-line carry-over
    skip_first   : updated flag
    """
    text = accumulator + data.decode("utf-8", errors="replace")
    parts = text.split("\n")

    # Last element is either empty (line ended with \n) or a partial line
    accumulator = parts[-1]
    complete = parts[:-1]

    parsed_rows: list[list[float]] = []
    raw_lines: list[str] = []

    for line in complete:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        if skip_first:
            skip_first = False
            continue
        raw_lines.append(line_stripped)
        row = parse_line(line_stripped)
        if row:
            parsed_rows.append(row)

    return parsed_rows, raw_lines, accumulator, skip_first
