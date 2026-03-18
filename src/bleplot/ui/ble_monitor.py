"""
BLE Monitor — raw text output panel.
Mirrors BSP's SerialMonitor.cpp.
Build once; append new lines incrementally each frame.
"""
from __future__ import annotations

from typing import Callable

import dearpygui.dearpygui as dpg

_SCROLL_TAG = "ble_monitor_scroll_cw"
_CHKBOX_TAG = "ble_monitor_autoscroll"
_CLEAR_TAG  = "ble_monitor_clear_btn"


class BLEMonitor:
    def __init__(self) -> None:
        self.auto_scroll: bool = True
        self._prev_count: int  = 0
        self._built:      bool = False

    def _on_autoscroll_toggle(self, value: bool) -> None:
        self.auto_scroll = value
        if value and dpg.does_item_exist(_SCROLL_TAG):
            # Immediate scroll when re-enabling
            dpg.set_y_scroll(
                _SCROLL_TAG, 999999,
                when=dpg.mvSetScrollFlags_Both,
            )

    def rebuild(
        self,
        parent_tag: str | int,
        lines: list[str],
        on_clear: Callable[[], None] | None = None,
    ) -> None:
        if not self._built:
            with dpg.group(horizontal=True, parent=parent_tag):
                dpg.add_checkbox(
                    tag=_CHKBOX_TAG,
                    label="Auto-scroll",
                    default_value=self.auto_scroll,
                    callback=lambda s, a: self._on_autoscroll_toggle(a),
                )
                dpg.add_button(
                    tag=_CLEAR_TAG,
                    label="Clear",
                    callback=on_clear or (lambda: None),
                )
            dpg.add_child_window(
                tag=_SCROLL_TAG,
                border=True,
                height=-1,
                width=-1,
                parent=parent_tag,
            )
            self._built = True

        current_count = len(lines)

        # Lines were cleared — wipe the scroll window
        if current_count < self._prev_count:
            dpg.delete_item(_SCROLL_TAG, children_only=True)
            self._prev_count = 0

        # Append only new lines
        new_lines = current_count > self._prev_count
        for line in lines[self._prev_count:]:
            dpg.add_text(line, color=(180, 220, 180, 255), parent=_SCROLL_TAG)

        # Scroll: use Both so it works whether content just changed or not
        if self.auto_scroll and new_lines:
            dpg.set_y_scroll(
                _SCROLL_TAG, 999999,
                when=dpg.mvSetScrollFlags_Both,
            )

        self._prev_count = current_count
