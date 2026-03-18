"""
Entry point — initialise Dear PyGui viewport and run the render loop.
BLE runs in its own background asyncio thread (see ble_manager.py).
"""
from __future__ import annotations

import dearpygui.dearpygui as dpg

from bleplot.app import BLEPlotApp
from bleplot.theme import apply_theme


def main() -> None:
    dpg.create_context()
    apply_theme()

    app = BLEPlotApp()

    dpg.create_viewport(
        title="BLEPlot",
        width=BLEPlotApp.WINDOW_W,
        height=BLEPlotApp.WINDOW_H,
        min_width=800,
        min_height=480,
    )
    dpg.setup_dearpygui()
    dpg.show_viewport()

    app.build_ui()

    while dpg.is_dearpygui_running():
        app.frame_update()
        dpg.render_dearpygui_frame()

    if app._ble.is_connected():
        app._ble.disconnect()
    dpg.destroy_context()


if __name__ == "__main__":
    main()
