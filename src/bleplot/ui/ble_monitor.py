"""
BLE Monitor — raw text output panel.
Mirrors BSP's SerialMonitor.cpp.
Content rebuilt each frame inside persistent group.
"""
from __future__ import annotations

import dearpygui.dearpygui as dpg

_SCROLL_TAG = "ble_monitor_scroll_cw"
_CHKBOX_TAG = "ble_monitor_autoscroll"


class BLEMonitor:
    def __init__(self) -> None:
        self.auto_scroll:  bool = True
        self._prev_count:  int  = 0
        self._built:       bool = False

    def rebuild(self, parent_tag: str | int, lines: list[str]) -> None:
        dpg.delete_item(parent_tag, children_only=True)

        dpg.add_checkbox(
            tag=_CHKBOX_TAG if not dpg.does_item_exist(_CHKBOX_TAG) else dpg.generate_uuid(),
            label="Auto-scroll",
            default_value=self.auto_scroll,
            callback=lambda s, a: setattr(self, "auto_scroll", a),
            parent=parent_tag,
        )

        with dpg.child_window(
            tag=_SCROLL_TAG if not dpg.does_item_exist(_SCROLL_TAG) else dpg.generate_uuid(),
            border=True,
            height=-1,
            width=-1,
            parent=parent_tag,
        ) as scroll_cw:
            for line in lines:
                dpg.add_text(line, color=(180, 220, 180, 255))

            if self.auto_scroll and len(lines) != self._prev_count:
                dpg.set_y_scroll(scroll_cw, dpg.get_y_scroll_max(scroll_cw))
                self._prev_count = len(lines)
