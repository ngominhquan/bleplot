"""
PlotMonitor — manages the list of Plot instances and the toolbar.
Mirrors BSP's PlotMonitor.cpp.
"""
from __future__ import annotations

import csv
from typing import TYPE_CHECKING

import dearpygui.dearpygui as dpg

from bleplot.data_store import ScrollingData, DataInfo
from bleplot.ui.plot import Plot
from bleplot.theme import COLOR_BTN_ADD, COLOR_BTN_REMOVE, COLOR_BTN_PAUSE, COLOR_BTN_EXPORT

if TYPE_CHECKING:
    from bleplot.app import AppState

# Persistent toolbar item tags
_TB_PLOT_ALL   = "tb_plot_all"
_TB_AUTO_POP   = "tb_auto_populate"
_TB_PAUSE      = "tb_pause"
_TB_EXPORT     = "tb_export"
_TB_SAVE       = "tb_save"
_TB_LOAD       = "tb_load"
_TB_ADD_PLOT   = "tb_add_plot"
_TB_REM_PLOT   = "tb_rem_plot"


class PlotMonitor:
    def __init__(self) -> None:
        self.plots: list[Plot]     = []
        self.paused: bool          = False
        self.auto_populate: bool   = True
        self._plot_counter: int    = 0
        self._toolbar_built: bool  = False
        self._plots_parent: str | int = ""

        # Cached snapshots for export / Plot All callback
        self._last_data_snap: dict[int, ScrollingData] = {}
        self._last_info_snap: dict[int, DataInfo]      = {}

        # Button themes (built once)
        self._btn_themes: dict[str, int] = {}

    # ------------------------------------------------------------------
    # One-time plot structure build
    # ------------------------------------------------------------------

    def build_plots(self, plots_parent: str | int, state: "AppState") -> None:
        """Add the first default plot. Called once after UI is created."""
        self._plots_parent = plots_parent
        self._add_plot(plots_parent)

    def _build_toolbar(
        self,
        toolbar_tag: str | int,
        plots_parent: str | int,
        state: "AppState",
    ) -> None:
        """Create all toolbar buttons once with persistent tags."""
        with dpg.group(horizontal=True, parent=toolbar_tag):
            dpg.add_checkbox(
                tag=_TB_AUTO_POP,
                label="Auto Plot",
                default_value=self.auto_populate,
                callback=lambda s, a: setattr(self, "auto_populate", a),
            )
            dpg.add_button(
                tag=_TB_PLOT_ALL,
                label="Plot All",
                callback=self._do_plot_all,
            )
            btn_p = dpg.add_button(
                tag=_TB_PAUSE,
                label="Pause",
                callback=self._toggle_pause,
            )
            dpg.bind_item_theme(btn_p, self._btn_theme(COLOR_BTN_PAUSE, "pause"))

            btn_e = dpg.add_button(
                tag=_TB_EXPORT,
                label="Export CSV",
                callback=self._open_export_dialog,
            )
            dpg.bind_item_theme(btn_e, self._btn_theme(COLOR_BTN_EXPORT, "export"))

            dpg.add_button(
                tag=_TB_SAVE,
                label="Save Config",
                callback=lambda: self._open_save_dialog(state),
            )
            dpg.add_button(
                tag=_TB_LOAD,
                label="Load Config",
                callback=lambda: self._open_load_dialog(state),
            )

            btn_a = dpg.add_button(
                tag=_TB_ADD_PLOT,
                label="+ Plot",
                callback=lambda: self._add_plot(self._plots_parent),
            )
            dpg.bind_item_theme(btn_a, self._btn_theme(COLOR_BTN_ADD, "add"))

            btn_r = dpg.add_button(
                tag=_TB_REM_PLOT,
                label="- Plot",
                callback=self._remove_last_plot,
                show=False,
            )
            dpg.bind_item_theme(btn_r, self._btn_theme(COLOR_BTN_REMOVE, "remove"))

        self._toolbar_built = True

    def clear_all_variables(self) -> None:
        """Remove all variable assignments from every plot (called on new connect)."""
        for plot in self.plots:
            for ident in list(plot.variable_axes.keys()):
                plot._remove_var(ident)
            plot.other_x_axis = False
            plot.x_axis_id    = None

    def _add_plot(self, parent: str | int) -> None:
        self._plot_counter += 1
        p = Plot(name=f"Plot {self._plot_counter}", plot_index=len(self.plots))
        p.build(parent)
        self.plots.append(p)

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def frame_update(
        self,
        toolbar_tag: str | int,
        plots_parent: str | int,
        state: "AppState",
        data_snap: dict[int, ScrollingData],
        info_snap: dict[int, DataInfo],
        program_time: float,
    ) -> None:
        self._last_data_snap = data_snap
        self._last_info_snap = info_snap
        self._plots_parent   = plots_parent

        if not self._toolbar_built:
            self._build_toolbar(toolbar_tag, plots_parent, state)
        else:
            self._update_toolbar()

        if (self.auto_populate and info_snap
                and all(len(p.variable_axes) == 0 for p in self.plots)):
            self._do_plot_all()

        for plot in self.plots:
            plot.frame_update(data_snap, info_snap, program_time, self.paused)

    def _update_toolbar(self) -> None:
        """Update mutable toolbar state without recreating items."""
        dpg.configure_item(_TB_PAUSE, label="Resume" if self.paused else "Pause")
        dpg.configure_item(_TB_REM_PLOT, show=len(self.plots) > 1)

    # ------------------------------------------------------------------
    # Toolbar button theme helper
    # ------------------------------------------------------------------

    def _btn_theme(self, color: tuple, key: str) -> int:
        if key not in self._btn_themes:
            with dpg.theme() as t:
                with dpg.theme_component(dpg.mvButton):
                    dpg.add_theme_color(dpg.mvThemeCol_Button, color)
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered,
                                        tuple(min(255, c + 30) for c in color))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonActive,
                                        tuple(min(255, c + 50) for c in color))
            self._btn_themes[key] = t
        return self._btn_themes[key]

    # ------------------------------------------------------------------
    # Plot management
    # ------------------------------------------------------------------

    def _remove_last_plot(self) -> None:
        if len(self.plots) > 1:
            p = self.plots.pop()
            p.destroy()

    def _do_plot_all(self) -> None:
        if not self.plots:
            return
        for ident in self._last_info_snap:
            self.plots[0].variable_axes.setdefault(ident, 0)

    def _toggle_pause(self) -> None:
        self.paused = not self.paused

    # ------------------------------------------------------------------
    # CSV export
    # ------------------------------------------------------------------

    def _open_export_dialog(self) -> None:
        tag = "export_file_dialog"
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)
        with dpg.file_dialog(
            tag=tag,
            label="Export CSV",
            default_filename="data.csv",
            callback=lambda s, a: self._export_csv(a.get("file_path_name", "")),
            cancel_callback=lambda: None,
            modal=True,
            width=600,
            height=400,
        ):
            dpg.add_file_extension(".csv", color=(0, 255, 0, 255))
            dpg.add_file_extension(".*")

    def _export_csv(self, path: str) -> None:
        if not path:
            return
        data_snap = self._last_data_snap
        info_snap = self._last_info_snap
        idents    = sorted(data_snap.keys())
        headers   = ["Program Time [s]"] + [
            info_snap[i].name if i in info_snap else str(i) for i in idents
        ]
        ordered  = {i: data_snap[i].ordered() for i in idents}
        max_len  = max((len(v) for v in ordered.values()), default=0)

        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(headers)
            for row_idx in range(max_len):
                t_val, row = "", []
                for i in idents:
                    pts = ordered[i]
                    if row_idx < len(pts):
                        if not t_val:
                            t_val = f"{pts[row_idx][0]:.6f}"
                        row.append(f"{pts[row_idx][1]:.6f}")
                    else:
                        row.append("")
                w.writerow([t_val] + row)

    # ------------------------------------------------------------------
    # Config dialogs
    # ------------------------------------------------------------------

    def _open_save_dialog(self, state: "AppState") -> None:
        from bleplot.serialization import save_config

        tag = "save_cfg_dialog"
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)
        with dpg.file_dialog(
            tag=tag,
            label="Save Config",
            default_filename="bleplot_config.json",
            callback=lambda s, a: self._do_save(a.get("file_path_name", ""), state),
            cancel_callback=lambda: None,
            modal=True,
            width=600,
            height=400,
        ):
            dpg.add_file_extension(".json", color=(0, 255, 0, 255))
            dpg.add_file_extension(".*")

    def _do_save(self, path: str, state: "AppState") -> None:
        from bleplot.serialization import save_config
        from pathlib import Path

        if not path:
            return
        p = Path(path)
        if p.suffix.lower() != ".json":
            p = p.with_suffix(".json")
        try:
            save_config(p, state)
        except Exception as exc:
            print(f"[BLEPlot] Config save failed: {exc}")

    def _open_load_dialog(self, state: "AppState") -> None:
        tag = "load_cfg_dialog"
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)
        with dpg.file_dialog(
            tag=tag,
            label="Load Config",
            callback=lambda s, a: self._do_load(a.get("file_path_name", ""), state),
            cancel_callback=lambda: None,
            modal=True,
            width=600,
            height=400,
        ):
            dpg.add_file_extension(".json", color=(0, 255, 0, 255))
            dpg.add_file_extension(".*")

    def _do_load(self, path: str, state: "AppState") -> None:
        from bleplot.serialization import load_config, apply_config

        if not path:
            return
        try:
            doc = load_config(path)
            apply_config(state, doc)
        except Exception as exc:
            print(f"[BLEPlot] Config load failed: {exc}")
