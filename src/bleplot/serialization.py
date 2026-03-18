"""
JSON config save / load.  Mirrors BSP's Serialization.cpp.
Data points are NOT saved — only layout and metadata.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bleplot.app import AppState


def save_config(path: str | Path, state: "AppState") -> None:
    doc: dict[str, Any] = {
        "version": "1.0",
        "variables": {},
        "plots": [],
        "ble": {
            "device_address": state.last_device_address,
            "device_name": state.last_device_name,
        },
    }

    for ident, info in state.info_snap.items():
        doc["variables"][str(ident)] = {
            "name": info.name,
            "color": list(info.color),
        }

    for plot in state.plot_monitor.plots:
        plot_doc: dict[str, Any] = {
            "name": plot.name,
            "height": plot.height,
            "time_frame": plot.time_frame,
            "autoscale": plot.autoscale,
            "other_x_axis": plot.other_x_axis,
            "x_axis_id": plot.x_axis_id,
            "x_axis_realtime": plot.x_axis_realtime,
            "variables": [
                {"id": vid, "y_axis": ax}
                for vid, ax in plot.variable_axes.items()
            ],
        }
        doc["plots"].append(plot_doc)

    Path(path).write_text(json.dumps(doc, indent=2), encoding="utf-8")


def load_config(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def apply_config(state: "AppState", doc: dict[str, Any]) -> None:
    """Apply a loaded config dict to the live AppState."""
    from bleplot.ui.plot_monitor import PlotMonitor
    from bleplot.ui.plot import Plot

    # Restore variable names / colors
    for str_id, var_doc in doc.get("variables", {}).items():
        ident = int(str_id)
        color = tuple(var_doc["color"])
        state.data_store.update_info(ident, name=var_doc["name"], color=color)

    # Restore BLE target
    ble_doc = doc.get("ble", {})
    state.last_device_address = ble_doc.get("device_address", "")
    state.last_device_name = ble_doc.get("device_name", "")

    # Restore plots
    state.plot_monitor.plots.clear()
    for i, plot_doc in enumerate(doc.get("plots", [])):
        p = Plot(name=plot_doc.get("name", f"Plot {i + 1}"),
                 plot_index=i)
        p.height = float(plot_doc.get("height", 300))
        p.time_frame = float(plot_doc.get("time_frame", 10.0))
        p.autoscale = bool(plot_doc.get("autoscale", True))
        p.other_x_axis = bool(plot_doc.get("other_x_axis", False))
        p.x_axis_id = plot_doc.get("x_axis_id", None)
        p.x_axis_realtime = bool(plot_doc.get("x_axis_realtime", True))
        for var_doc in plot_doc.get("variables", []):
            p.variable_axes[int(var_doc["id"])] = int(var_doc["y_axis"])
        state.plot_monitor.plots.append(p)

    if not state.plot_monitor.plots:
        state.plot_monitor.plots.append(
            Plot(name="Plot 1", plot_index=0)
        )
