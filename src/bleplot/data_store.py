"""
Thread-safe data store: circular scrolling buffers + variable metadata.
Mirrors BSP's ScrollingData / DataInfo / append_all_data().
"""
from __future__ import annotations

import collections
import copy
import threading
from dataclasses import dataclass, field

# Import palette from theme to keep a single source of truth.
# Lazy import to avoid circular dependency at module load time.
def _get_plot_colors() -> list[tuple[float, float, float, float]]:
    from bleplot.theme import PLOT_COLORS_F  # noqa: PLC0415
    return PLOT_COLORS_F

MAX_BUFFER_SIZE = 5000
PRINT_BUFFER_SIZE = 200


@dataclass
class ScrollingData:
    identifier: int
    max_size: int = MAX_BUFFER_SIZE
    offset: int = 0
    data: list[tuple[float, float]] = field(default_factory=list)

    def add_point(self, x: float, y: float) -> None:
        if len(self.data) < self.max_size:
            self.data.append((x, y))
        else:
            self.data[self.offset] = (x, y)
            self.offset = (self.offset + 1) % self.max_size

    def latest_value(self) -> float | None:
        if not self.data:
            return None
        idx = (self.offset - 1) % len(self.data)
        return self.data[idx][1]

    def ordered(self) -> list[tuple[float, float]]:
        """Return points in chronological order."""
        if not self.data:
            return []
        if len(self.data) < self.max_size:
            return list(self.data)
        return self.data[self.offset:] + self.data[: self.offset]

    def xs(self) -> list[float]:
        return [p[0] for p in self.ordered()]

    def ys(self) -> list[float]:
        return [p[1] for p in self.ordered()]


@dataclass
class DataInfo:
    name: str
    color: tuple[float, float, float, float]


class DataStore:
    """
    Central, thread-safe repository for all incoming variable data.
    BLE thread writes via append_all_data(); render thread reads via
    copy_for_render().
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # identifier (int 0-254) → ScrollingData
        self._data: dict[int, ScrollingData] = {}
        # identifier → DataInfo
        self._info: dict[int, DataInfo] = {}
        # raw text lines for the BLE monitor
        self.print_buffer: collections.deque[str] = collections.deque(
            maxlen=PRINT_BUFFER_SIZE
        )
        self._next_id: int = 0
        self.data_flowing: bool = False  # ≈ baud_status

    # ------------------------------------------------------------------
    # Writer side (BLE thread)
    # ------------------------------------------------------------------

    def append_all_data(self, values: list[float], timestamp: float) -> None:
        """
        Add one row of values from the parser.  Auto-creates new
        ScrollingData / DataInfo entries as new variables appear.
        """
        with self._lock:
            for i, v in enumerate(values):
                if i not in self._data:
                    palette = _get_plot_colors()
                    color = palette[i % len(palette)]
                    self._data[i] = ScrollingData(identifier=i)
                    self._info[i] = DataInfo(name=f"Sensor {i}", color=color)
                self._data[i].add_point(timestamp, v)
            self.data_flowing = True

    def push_raw_line(self, line: str) -> None:
        with self._lock:
            self.print_buffer.append(line)

    def clear_raw_lines(self) -> None:
        with self._lock:
            self.print_buffer.clear()

    # ------------------------------------------------------------------
    # Reader side (render thread)
    # ------------------------------------------------------------------

    def copy_for_render(
        self,
    ) -> tuple[dict[int, ScrollingData], dict[int, DataInfo], list[str], bool]:
        """
        Return a deep-enough snapshot for the render thread.
        ScrollingData objects are shallow-copied (list reference copied, not
        the list itself) — sufficient because the render thread only reads.
        """
        with self._lock:
            data_snap = {k: copy.copy(v) for k, v in self._data.items()}
            # copy the list so the render thread gets a stable slice
            for k, sd in data_snap.items():
                sd.data = list(sd.data)
            info_snap = dict(self._info)
            lines_snap = list(self.print_buffer)
            flowing = self.data_flowing
        return data_snap, info_snap, lines_snap, flowing

    def update_info(self, identifier: int, name: str | None = None,
                    color: tuple | None = None) -> None:
        with self._lock:
            if identifier in self._info:
                if name is not None:
                    self._info[identifier].name = name
                if color is not None:
                    self._info[identifier].color = color

    def identifiers(self) -> list[int]:
        with self._lock:
            return list(self._data.keys())

    def reset(self) -> None:
        with self._lock:
            self._data.clear()
            self._info.clear()
            self.print_buffer.clear()
            self._next_id = 0
            self.data_flowing = False
