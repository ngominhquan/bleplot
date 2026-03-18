"""
Dear PyGui theme matching BSP's dark ImGui look.
Call apply_theme() once after dpg.create_context().
"""
from __future__ import annotations

import dearpygui.dearpygui as dpg

# Status colours (RGBA 0-255)
COLOR_CONNECTED = (0, 200, 80, 255)
COLOR_CONNECTING = (255, 200, 0, 255)
COLOR_DISCONNECTED = (160, 160, 160, 255)
COLOR_ERROR = (220, 50, 50, 255)

# UI accent colours
COLOR_BTN_ADD = (38, 99, 178, 255)      # blue  — "Add Plot"
COLOR_BTN_REMOVE = (178, 38, 38, 255)   # red   — "Remove Plot"
COLOR_BTN_PAUSE = (178, 130, 38, 255)   # amber — "Pause"
COLOR_BTN_EXPORT = (38, 140, 80, 255)   # green — "Export"

# Plot colours (0-255 for DPG)
PLOT_COLORS_255: list[tuple[int, int, int, int]] = [
    (214, 39,  40,  255),
    (31,  119, 180, 255),
    (44,  160, 44,  255),
    (255, 127, 14,  255),
    (148, 103, 189, 255),
    (140, 86,  75,  255),
    (227, 119, 194, 255),
    (127, 127, 127, 255),
]

# Same colours as 0-1 floats (for DataInfo storage)
PLOT_COLORS_F: list[tuple[float, float, float, float]] = [
    (c[0] / 255, c[1] / 255, c[2] / 255, 1.0) for c in PLOT_COLORS_255
]


def apply_theme() -> None:
    with dpg.theme() as global_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg,       (15,  15,  15,  255))
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg,        (22,  22,  22,  255))
            dpg.add_theme_color(dpg.mvThemeCol_PopupBg,        (30,  30,  30,  240))
            dpg.add_theme_color(dpg.mvThemeCol_Border,         (60,  60,  60,  255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg,        (35,  35,  35,  255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (50,  50,  50,  255))
            dpg.add_theme_color(dpg.mvThemeCol_TitleBg,        (20,  20,  20,  255))
            dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive,  (30,  30,  30,  255))
            dpg.add_theme_color(dpg.mvThemeCol_MenuBarBg,      (20,  20,  20,  255))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg,    (10,  10,  10,  255))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab,  (60,  60,  60,  255))
            dpg.add_theme_color(dpg.mvThemeCol_CheckMark,      (100, 180, 100, 255))
            dpg.add_theme_color(dpg.mvThemeCol_SliderGrab,     (80,  80,  200, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Button,         (50,  50,  50,  255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered,  (70,  70,  70,  255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive,   (90,  90,  90,  255))
            dpg.add_theme_color(dpg.mvThemeCol_Header,         (50,  70,  100, 255))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered,  (60,  90,  130, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Tab,            (30,  30,  30,  255))
            dpg.add_theme_color(dpg.mvThemeCol_TabHovered,     (60,  80,  110, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TabActive,      (50,  70,  100, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Text,           (230, 230, 230, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TextDisabled,   (120, 120, 120, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Separator,      (60,  60,  60,  255))

            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding,    4)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding,     4)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding,     3)
            dpg.add_theme_style(dpg.mvStyleVar_PopupRounding,     4)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarRounding, 3)
            dpg.add_theme_style(dpg.mvStyleVar_GrabRounding,      3)
            dpg.add_theme_style(dpg.mvStyleVar_TabRounding,       3)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding,     8, 8)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing,       6, 4)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding,      4, 3)

    dpg.bind_theme(global_theme)


def color_for_status(status_str: str) -> tuple[int, int, int, int]:
    s = status_str.lower()
    if "connected" in s and "dis" not in s:
        return COLOR_CONNECTED
    if "connecting" in s or "scanning" in s:
        return COLOR_CONNECTING
    if "error" in s:
        return COLOR_ERROR
    return COLOR_DISCONNECTED
