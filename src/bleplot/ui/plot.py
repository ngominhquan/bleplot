"""
Single plot widget — mirrors BSP's Plot.cpp.
Build once; update series data each frame via set_value.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import dearpygui.dearpygui as dpg

from bleplot.data_store import ScrollingData, DataInfo

if TYPE_CHECKING:
    pass

_COUNTER = 0


def _uid() -> str:
    global _COUNTER
    _COUNTER += 1
    return str(_COUNTER)


class Plot:
    """One resizable plot with dual Y-axes and optional custom X-axis."""

    MIN_HEIGHT     = 100
    DEFAULT_HEIGHT = 300

    def __init__(self, name: str, plot_index: int) -> None:
        self.name        = name
        self.plot_index  = plot_index
        self.height: float = self.DEFAULT_HEIGHT

        # identifier → y_axis index (0 = left, 1 = right)
        self.variable_axes: dict[int, int] = {}

        self.time_frame:       float = 10.0
        self.autoscale:        bool  = True
        self.other_x_axis:     bool  = False
        self.x_axis_id:        int | None = None
        self.x_axis_realtime:  bool  = True

        self.paused: bool = False
        self._paused_snap: dict[int, tuple[list[float], list[float]]] = {}
        self._paused_time: float = 0.0

        # DPG item tags
        uid = _uid()
        self._group_tag  = f"plot_grp_{uid}"
        self._tag        = f"plot_{uid}"
        self._xaxis_tag  = f"xaxis_{uid}"
        self._yaxis0_tag = f"y0_{uid}"
        self._yaxis1_tag = f"y1_{uid}"
        self._resize_tag = f"resize_{uid}"
        self._series_tags: dict[int, str] = {}
        self._series_themes: dict[int, int] = {}
        self._built = False

        # Resize state
        self._resize_dragging  = False
        self._resize_start_y   = 0.0
        self._resize_start_h   = 0.0

    # ------------------------------------------------------------------
    # Build DPG items (called once)
    # ------------------------------------------------------------------

    def build(self, parent: str | int) -> None:
        with dpg.group(tag=self._group_tag, parent=parent):
            with dpg.plot(
                tag=self._tag,
                label=self.name,
                height=int(self.height),
                width=-1,
            ):
                dpg.add_plot_legend()
                dpg.add_plot_axis(dpg.mvXAxis, label="Time [s]",
                                  tag=self._xaxis_tag)
                dpg.add_plot_axis(dpg.mvYAxis, label="Y1",
                                  tag=self._yaxis0_tag)
                dpg.add_plot_axis(dpg.mvYAxis, label="Y2",
                                  tag=self._yaxis1_tag)

            # Resize handle button
            dpg.add_button(
                tag=self._resize_tag,
                label="",
                height=6,
                width=-1,
                small=True,
            )

        # Register this plot as a drag-drop target (main area → Y1)
        dpg.set_item_drop_callback(self._tag, self._on_drop_main)
        dpg.set_item_payload_type(self._tag, "DND_PLOT")

        self._built = True

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def frame_update(
        self,
        data_snap: dict[int, ScrollingData],
        info_snap: dict[int, DataInfo],
        program_time: float,
        paused: bool,
    ) -> None:
        if not self._built:
            return

        if paused and not self.paused:
            self._freeze(data_snap, program_time)
        elif not paused and self.paused:
            self._paused_snap.clear()
        self.paused = paused

        self._update_series(data_snap, info_snap)
        self._update_axes(data_snap, program_time)
        self._handle_resize()
        self._handle_context_menu(data_snap, info_snap)

    # ------------------------------------------------------------------
    # Series management
    # ------------------------------------------------------------------

    def _ensure_series(self, ident: int, info: DataInfo) -> None:
        if ident in self._series_tags:
            return
        tag   = f"series_{self._tag}_{ident}"
        y_tag = (self._yaxis0_tag
                 if self.variable_axes.get(ident, 0) == 0
                 else self._yaxis1_tag)
        dpg.add_line_series([], [], label=info.name, parent=y_tag, tag=tag)

        theme = self._make_series_theme(info.color)
        dpg.bind_item_theme(tag, theme)
        self._series_tags[ident]   = tag
        self._series_themes[ident] = theme

    def _make_series_theme(self, color_f: tuple) -> int:
        c = tuple(int(x * 255) for x in color_f[:4])
        with dpg.theme() as t:
            with dpg.theme_component(dpg.mvLineSeries):
                dpg.add_theme_color(dpg.mvPlotCol_Line, c,
                                    category=dpg.mvThemeCat_Plots)
        return t

    def _update_series(
        self,
        data_snap: dict[int, ScrollingData],
        info_snap: dict[int, DataInfo],
    ) -> None:
        # Remove series for variables no longer assigned
        for k in [k for k in self._series_tags if k not in self.variable_axes]:
            tag = self._series_tags.pop(k)
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)
            theme = self._series_themes.pop(k, None)
            if theme and dpg.does_item_exist(theme):
                dpg.delete_item(theme)

        for ident, _y_ax in self.variable_axes.items():
            if ident not in data_snap or ident not in info_snap:
                continue
            self._ensure_series(ident, info_snap[ident])
            tag = self._series_tags[ident]
            if not dpg.does_item_exist(tag):
                continue

            if self.paused:
                xs, ys = self._paused_snap.get(ident, ([], []))
            else:
                sd = data_snap[ident]
                xs = sd.xs()
                ys = sd.ys()

            if self.other_x_axis and self.x_axis_id is not None:
                x_sd = data_snap.get(self.x_axis_id)
                if x_sd is not None:
                    xs = x_sd.ys()

            dpg.set_value(tag, [xs, ys])
            dpg.configure_item(tag, label=info_snap[ident].name)

    def _update_axes(
        self,
        data_snap: dict[int, ScrollingData],
        program_time: float,
    ) -> None:
        if not dpg.does_item_exist(self._xaxis_tag):
            return

        t = self._paused_time if self.paused else program_time

        if not self.other_x_axis:
            xmin = max(0.0, t - self.time_frame)
            xmax = max(xmin + self.time_frame, t)
            dpg.set_axis_limits(self._xaxis_tag, xmin, xmax)
        else:
            if self.x_axis_id is not None and self.x_axis_id in data_snap:
                vals = data_snap[self.x_axis_id].ys()
                if vals and self.x_axis_realtime:
                    dpg.set_axis_limits(self._xaxis_tag, min(vals), max(vals))
                else:
                    dpg.set_axis_limits_auto(self._xaxis_tag)

        if self.autoscale:
            dpg.set_axis_limits_auto(self._yaxis0_tag)
            dpg.set_axis_limits_auto(self._yaxis1_tag)

    # ------------------------------------------------------------------
    # Resize handle (drag to resize plot height)
    # ------------------------------------------------------------------

    def _handle_resize(self) -> None:
        if not dpg.does_item_exist(self._resize_tag):
            return
        if dpg.is_item_hovered(self._resize_tag):
            if dpg.is_mouse_button_down(dpg.mvMouseButton_Left):
                if not self._resize_dragging:
                    self._resize_dragging = True
                    self._resize_start_y  = dpg.get_mouse_pos()[1]
                    self._resize_start_h  = self.height
                else:
                    dy      = dpg.get_mouse_pos()[1] - self._resize_start_y
                    new_h   = max(self.MIN_HEIGHT, self._resize_start_h + dy)
                    self.height = new_h
                    if dpg.does_item_exist(self._tag):
                        dpg.configure_item(self._tag, height=int(new_h))
            else:
                self._resize_dragging = False
        elif not dpg.is_mouse_button_down(dpg.mvMouseButton_Left):
            self._resize_dragging = False

    # ------------------------------------------------------------------
    # Context menu (right-click on plot)
    # ------------------------------------------------------------------

    def _handle_context_menu(
        self,
        data_snap: dict[int, ScrollingData],
        info_snap: dict[int, DataInfo],
    ) -> None:
        if not dpg.does_item_exist(self._tag):
            return
        if not dpg.is_item_right_clicked(self._tag):
            return

        menu_tag = f"ctx_{self._tag}"
        if dpg.does_item_exist(menu_tag):
            dpg.delete_item(menu_tag)

        with dpg.window(
            tag=menu_tag,
            popup=True,
            no_title_bar=True,
            min_size=[180, 10],
        ):
            dpg.add_text("── Add to Y1 ──")
            for ident, info in info_snap.items():
                if ident not in self.variable_axes:
                    dpg.add_selectable(
                        label=info.name,
                        user_data=(ident, 0),
                        callback=lambda s, a, u: self._add_var(u[0], u[1]),
                    )

            dpg.add_separator()
            dpg.add_text("── Add to Y2 ──")
            for ident, info in info_snap.items():
                if ident not in self.variable_axes:
                    dpg.add_selectable(
                        label=info.name,
                        user_data=(ident, 1),
                        callback=lambda s, a, u: self._add_var(u[0], u[1]),
                    )

            dpg.add_separator()
            dpg.add_text("── Remove ──")
            for ident in list(self.variable_axes.keys()):
                name = info_snap[ident].name if ident in info_snap else str(ident)
                dpg.add_selectable(
                    label=name,
                    user_data=ident,
                    callback=lambda s, a, u: self._remove_var(u),
                )

            dpg.add_separator()
            dpg.add_checkbox(
                label="Autoscale Y",
                default_value=self.autoscale,
                callback=lambda s, a: setattr(self, "autoscale", a),
            )
            dpg.add_checkbox(
                label="Custom X axis",
                default_value=self.other_x_axis,
                callback=lambda s, a: setattr(self, "other_x_axis", a),
            )
            if self.other_x_axis:
                dpg.add_checkbox(
                    label="X realtime follow",
                    default_value=self.x_axis_realtime,
                    callback=lambda s, a: setattr(self, "x_axis_realtime", a),
                )
                dpg.add_text("Set X variable:")
                for ident, info in info_snap.items():
                    dpg.add_selectable(
                        label=info.name,
                        user_data=ident,
                        callback=lambda s, a, u: setattr(self, "x_axis_id", u),
                    )
            else:
                dpg.add_separator()
                dpg.add_slider_float(
                    label="Time window (s)",
                    default_value=self.time_frame,
                    min_value=1.0,
                    max_value=120.0,
                    callback=lambda s, a: setattr(self, "time_frame", a),
                )

    # ------------------------------------------------------------------
    # Drag-drop target callback
    # ------------------------------------------------------------------

    def _on_drop_main(self, sender, app_data) -> None:
        if isinstance(app_data, dict):
            ident = app_data.get("ident")
            if ident is not None:
                self._add_var(ident, 0)

    # ------------------------------------------------------------------
    # Variable add/remove
    # ------------------------------------------------------------------

    def _add_var(self, ident: int, y_axis: int) -> None:
        self.variable_axes[ident] = y_axis

    def _remove_var(self, ident: int) -> None:
        self.variable_axes.pop(ident, None)
        tag = self._series_tags.pop(ident, None)
        if tag and dpg.does_item_exist(tag):
            dpg.delete_item(tag)
        theme = self._series_themes.pop(ident, None)
        if theme and dpg.does_item_exist(theme):
            dpg.delete_item(theme)

    # ------------------------------------------------------------------
    # Pause
    # ------------------------------------------------------------------

    def _freeze(self, data_snap: dict[int, ScrollingData], t: float) -> None:
        self._paused_snap = {
            ident: (sd.xs(), sd.ys())
            for ident, sd in data_snap.items()
            if ident in self.variable_axes
        }
        self._paused_time = t

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def destroy(self) -> None:
        for theme in self._series_themes.values():
            if dpg.does_item_exist(theme):
                dpg.delete_item(theme)
        if dpg.does_item_exist(self._group_tag):
            dpg.delete_item(self._group_tag)
        self._built = False
