"""
BLEPlot main application class — mirrors BSP.cpp.
Owns all state; coordinates BLE, parsing, and UI.
"""
from __future__ import annotations

import time

import dearpygui.dearpygui as dpg
from bleak.backends.device import BLEDevice

from bleplot.ble_manager import BLEManager, ConnectionStatus
from bleplot.data_store import DataStore, ScrollingData, DataInfo
from bleplot.parser import parse_buffer
from bleplot.ui.data_panel import DataPanel
from bleplot.ui.plot_monitor import PlotMonitor
from bleplot.ui.ble_monitor import BLEMonitor
from bleplot.theme import color_for_status

# Tag constants
_TAG_PRIMARY     = "primary_window"
_TAG_BLE_BAR     = "ble_bar_grp"
_TAG_BODY        = "body_grp"
_TAG_DATA_PANEL  = "data_panel_cw"
_TAG_RIGHT       = "right_cw"
_TAG_TABBAR      = "main_tabbar"
_TAG_TAB_PLOTS   = "tab_plots"
_TAG_TAB_MONITOR = "tab_monitor"
_TAG_PLOT_AREA   = "plot_area_grp"
_TAG_MONITOR_GRP = "monitor_grp"

# BLE bar persistent item tags
_TAG_BLE_STATUS   = "ble_status_text"
_TAG_BLE_ERROR    = "ble_error_text"
_TAG_BLE_SCAN_BTN = "ble_scan_btn"
_TAG_BLE_COMBO    = "ble_device_combo"
_TAG_BLE_CONN_BTN = "ble_connect_btn"
_TAG_BLE_DISC_BTN = "ble_disconnect_btn"


class AppState:
    """Shared state passed to serialization helpers."""

    def __init__(self, data_store: DataStore, plot_monitor: PlotMonitor) -> None:
        self.data_store = data_store
        self.plot_monitor = plot_monitor
        self.info_snap: dict[int, DataInfo] = {}
        self.last_device_address: str = ""
        self.last_device_name: str = ""


class BLEPlotApp:
    WINDOW_W = 1260
    WINDOW_H = 720
    LEFT_W   = 215

    def __init__(self) -> None:
        self._data_store   = DataStore()
        self._plot_monitor = PlotMonitor()
        self._data_panel   = DataPanel()
        self._ble_monitor  = BLEMonitor()
        self.state = AppState(self._data_store, self._plot_monitor)

        self._ble = BLEManager(
            on_notification=self._on_ble_data,
            on_disconnect=self._on_ble_disconnect,
        )

        self._line_acc:   str  = ""
        self._skip_first: bool = True

        self._data_snap:    dict[int, ScrollingData] = {}
        self._info_snap:    dict[int, DataInfo]      = {}
        self._lines_snap:   list[str]                = []
        self._data_flowing: bool                     = False

        self._start_time    = time.monotonic()
        self._program_time: float = 0.0

        self._selected_device_idx: int = 0
        self._device_labels: list[str] = ["No devices found"]

    # ------------------------------------------------------------------
    # BLE callbacks (BLE thread)
    # ------------------------------------------------------------------

    def _on_ble_data(self, data: bytes) -> None:
        rows, raw_lines, self._line_acc, self._skip_first = parse_buffer(
            data, self._line_acc, self._skip_first
        )
        t = time.monotonic() - self._start_time
        for row in rows:
            self._data_store.append_all_data(row, t)
        for line in raw_lines:
            self._data_store.push_raw_line(line)

    def _on_ble_disconnect(self) -> None:
        self._line_acc   = ""
        self._skip_first = True

    # ------------------------------------------------------------------
    # Build static UI structure (called once)
    # ------------------------------------------------------------------

    def build_ui(self) -> None:
        vp_w = dpg.get_viewport_width()
        vp_h = dpg.get_viewport_height()

        with dpg.window(
            tag=_TAG_PRIMARY,
            label="BLEPlot",
            width=vp_w,
            height=vp_h,
            pos=(0, 0),
            no_title_bar=True,
            no_resize=True,
            no_move=True,
            no_bring_to_front_on_focus=True,
        ):
            # BLE control bar (persistent items, updated each frame)
            dpg.add_group(tag=_TAG_BLE_BAR, horizontal=False)
            dpg.add_separator()

            # Body row
            with dpg.group(tag=_TAG_BODY, horizontal=True):
                # Left: data panel child window (content rebuilt each frame)
                dpg.add_child_window(
                    tag=_TAG_DATA_PANEL,
                    width=self.LEFT_W,
                    border=True,
                    height=-1,
                )

                # Right: tab bar
                right_w = vp_w - self.LEFT_W - 24
                with dpg.child_window(tag=_TAG_RIGHT, width=right_w,
                                      border=False, height=-1):
                    with dpg.tab_bar(tag=_TAG_TABBAR):
                        with dpg.tab(tag=_TAG_TAB_PLOTS, label="Plots"):
                            # Toolbar rebuilt each frame; plot items persistent
                            dpg.add_group(tag="plot_toolbar_grp", horizontal=False)
                            dpg.add_separator()
                            dpg.add_group(tag=_TAG_PLOT_AREA, horizontal=False)

                        with dpg.tab(tag=_TAG_TAB_MONITOR, label="BLE Monitor"):
                            # Content rebuilt each frame
                            dpg.add_group(tag=_TAG_MONITOR_GRP, horizontal=False)

        # Resize callback to keep window filling viewport
        dpg.set_viewport_resize_callback(self._on_viewport_resize)

        # Build persistent BLE bar items
        self._build_ble_bar()

        # Build initial plot structure
        self._plot_monitor.build_plots(_TAG_PLOT_AREA, self.state)

    def _on_viewport_resize(self) -> None:
        vp_w = dpg.get_viewport_width()
        vp_h = dpg.get_viewport_height()
        dpg.configure_item(_TAG_PRIMARY, width=vp_w, height=vp_h)
        right_w = vp_w - self.LEFT_W - 24
        dpg.configure_item(_TAG_RIGHT, width=right_w)

    # ------------------------------------------------------------------
    # Per-frame update (called every frame)
    # ------------------------------------------------------------------

    def frame_update(self) -> None:
        self._program_time = time.monotonic() - self._start_time

        self._data_snap, self._info_snap, self._lines_snap, self._data_flowing = (
            self._data_store.copy_for_render()
        )
        self.state.info_snap = self._info_snap

        self._update_ble_bar()
        self._data_panel.rebuild(
            _TAG_DATA_PANEL, self.state,
            self._data_snap, self._info_snap, self._data_flowing,
        )
        self._plot_monitor.frame_update(
            "plot_toolbar_grp", _TAG_PLOT_AREA,
            self.state, self._data_snap, self._info_snap, self._program_time,
        )
        self._ble_monitor.rebuild(
            _TAG_MONITOR_GRP, self._lines_snap,
            on_clear=self._data_store.clear_raw_lines,
        )

    # ------------------------------------------------------------------
    # BLE control bar
    # ------------------------------------------------------------------

    def _build_ble_bar(self) -> None:
        """Called once from build_ui — creates persistent BLE bar items."""
        with dpg.group(horizontal=True, parent=_TAG_BLE_BAR):
            dpg.add_text(
                "● Disconnected",
                tag=_TAG_BLE_STATUS,
                color=color_for_status("Disconnected"),
            )
            dpg.add_text(
                "",
                tag=_TAG_BLE_ERROR,
                color=(220, 80, 80, 255),
                show=False,
            )
            dpg.add_spacer(width=10)
            dpg.add_button(
                tag=_TAG_BLE_SCAN_BTN,
                label="Scan",
                callback=self._do_scan,
            )
            dpg.add_combo(
                tag=_TAG_BLE_COMBO,
                items=["No devices found"],
                default_value="No devices found",
                width=300,
                callback=self._on_device_select_combo,
            )
            dpg.add_button(
                tag=_TAG_BLE_CONN_BTN,
                label="Connect",
                callback=self._do_connect,
                enabled=False,
            )
            dpg.add_button(
                tag=_TAG_BLE_DISC_BTN,
                label="Disconnect",
                callback=self._do_disconnect,
                show=False,
            )

    def _update_ble_bar(self) -> None:
        """Called every frame — updates BLE bar item states."""
        status     = self._ble.status
        status_str = status.value
        col        = color_for_status(status_str)

        dpg.configure_item(_TAG_BLE_STATUS, default_value=f"● {status_str}", color=col)

        if self._ble.error_message:
            dpg.configure_item(
                _TAG_BLE_ERROR,
                default_value=f"  {self._ble.error_message}",
                show=True,
            )
        else:
            dpg.configure_item(_TAG_BLE_ERROR, show=False)

        scanning = status == ConnectionStatus.SCANNING
        dpg.configure_item(
            _TAG_BLE_SCAN_BTN,
            label="Scan" if not scanning else "Scanning…",
            enabled=not scanning and not self._ble.is_connected(),
        )

        devices = self._ble.discovered
        self._device_labels = [
            f"{d.name or 'Unknown'} ({d.address})" for d in devices
        ] or ["No devices found"]

        if self._selected_device_idx >= len(self._device_labels):
            self._selected_device_idx = 0

        dpg.configure_item(
            _TAG_BLE_COMBO,
            items=self._device_labels,
            default_value=self._device_labels[self._selected_device_idx],
        )

        connected  = self._ble.is_connected()
        connecting = status == ConnectionStatus.CONNECTING
        dpg.configure_item(
            _TAG_BLE_CONN_BTN,
            label="Connect" if not connecting else "Connecting…",
            enabled=not connecting and bool(devices),
            show=not connected,
        )
        dpg.configure_item(_TAG_BLE_DISC_BTN, show=connected)

    def _do_scan(self) -> None:
        self._ble.scan(timeout=5.0)

    def _do_connect(self) -> None:
        devices = self._ble.discovered
        if not devices:
            return
        idx    = min(self._selected_device_idx, len(devices) - 1)
        device = devices[idx]
        self.state.last_device_address = device.address
        self.state.last_device_name    = device.name or ""
        self._data_store.reset()
        self._plot_monitor.clear_all_variables()
        self._line_acc   = ""
        self._skip_first = True
        self._start_time = time.monotonic()
        self._ble.connect(device)

    def _do_disconnect(self) -> None:
        self._ble.disconnect()

    def _on_device_select_combo(self, sender: int, app_data: str) -> None:
        label = app_data
        if label in self._device_labels:
            self._selected_device_idx  = self._device_labels.index(label)
            self.state.last_device_name = label
