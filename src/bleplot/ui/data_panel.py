"""
DataPanel — left-side variable list with drag-drop and right-click editing.
Mirrors BSP's DataPanel.cpp.
Content is rebuilt each frame inside the persistent child window.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import dearpygui.dearpygui as dpg

from bleplot.data_store import ScrollingData, DataInfo
from bleplot.theme import PLOT_COLORS_255, PLOT_COLORS_F

if TYPE_CHECKING:
    from bleplot.app import AppState


class DataPanel:
    def __init__(self) -> None:
        # Track which popup is open so we don't recreate it every frame
        self._open_popup: int | None = None

    def rebuild(
        self,
        parent_tag: str | int,
        state: "AppState",
        data_snap: dict[int, ScrollingData],
        info_snap: dict[int, DataInfo],
        data_flowing: bool,
    ) -> None:
        dpg.delete_item(parent_tag, children_only=True)

        dpg.add_text("INCOMING DATA", parent=parent_tag)
        dpg.add_separator(parent=parent_tag)

        if not info_snap:
            dpg.add_text("No data yet", color=(120, 120, 120, 255),
                         parent=parent_tag)
            return

        with dpg.table(
            parent=parent_tag,
            header_row=False,
            borders_innerV=False,
            borders_outerV=False,
            resizable=False,
        ):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=135)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=65)

            for ident in sorted(info_snap.keys()):
                info   = info_snap[ident]
                sd     = data_snap.get(ident)
                latest = sd.latest_value() if sd else None
                c255   = tuple(int(x * 255) for x in info.color[:4])

                with dpg.table_row():
                    # Name column with drag source
                    name_item = dpg.add_text(f"  {info.name}", color=c255)

                    with dpg.drag_payload(
                        parent=name_item,
                        drag_data={"ident": ident},
                        payload_type="DND_PLOT",
                    ):
                        dpg.add_text(f"  {info.name}", color=c255)

                    # Value column
                    if data_flowing and latest is not None:
                        dpg.add_text(f"{latest:8.3f}")
                    else:
                        dpg.add_text("---", color=(100, 100, 100, 255))

                # Right-click popup — only create when right-clicked
                if dpg.is_item_hovered(name_item) and dpg.is_mouse_button_released(
                    dpg.mvMouseButton_Right
                ):
                    self._open_edit_popup(ident, info, state)

    # ------------------------------------------------------------------
    # Edit popup
    # ------------------------------------------------------------------

    def _open_edit_popup(
        self,
        ident: int,
        info: DataInfo,
        state: "AppState",
    ) -> None:
        tag = f"edit_popup_{ident}"
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        name_tag  = f"ep_name_{ident}"
        color_tag = f"ep_color_{ident}"

        with dpg.window(
            tag=tag,
            popup=True,
            no_title_bar=True,
            min_size=[230, 10],
        ):
            dpg.add_text(f"Edit: {info.name}")
            dpg.add_separator()
            dpg.add_input_text(
                tag=name_tag,
                label="Name",
                default_value=info.name,
                width=190,
            )
            dpg.add_color_edit(
                tag=color_tag,
                label="Color",
                default_value=[int(x * 255) for x in info.color[:4]],
                width=190,
                no_alpha=True,
            )
            dpg.add_separator()
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Save",
                    user_data=(ident, name_tag, color_tag, tag),
                    callback=lambda s, a, u: self._save_edit(state, *u),
                )
                dpg.add_button(
                    label="Cancel",
                    user_data=tag,
                    callback=lambda s, a, u: dpg.delete_item(u),
                )

    def _save_edit(
        self,
        state: "AppState",
        ident: int,
        name_tag: str,
        color_tag: str,
        popup_tag: str,
    ) -> None:
        name     = dpg.get_value(name_tag)
        c255     = dpg.get_value(color_tag)
        color_f  = tuple(c / 255.0 for c in c255[:4])
        state.data_store.update_info(ident, name=name, color=color_f)
        if dpg.does_item_exist(popup_tag):
            dpg.delete_item(popup_tag)
