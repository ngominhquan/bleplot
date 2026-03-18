# BLEPlot - BLE Serial Plotter (Python Port of BetterSerialPlotter)

> Real-time BLE data plotter replicating the GUI and logic of BetterSerialPlotter (BSP),
> written in Python, cross-platform: Windows, macOS, Raspberry Pi.

---

## Confirmed Specifications

| Item                  | Decision                                                         |
|-----------------------|------------------------------------------------------------------|
| BLE protocol          | **Nordic UART Service (NUS)**                                    |
| Data format           | Identical to BSP: newline-terminated, whitespace-separated floats |
| Target BLE device     | **ESP32** (standard NUS firmware)                                |
| Simultaneous devices  | **One at a time** (matching BSP)                                 |
| GUI framework         | **Dear PyGui** (dearpygui)                                       |
| Raspberry Pi target   | **RPi 4 / RPi 5** (built-in BLE via `hci0`)                     |

### ESP32 NUS notes
- Default ESP32 BLE NUS MTU: 23 bytes (negotiated up to 517 bytes with `esp_ble_gatt_set_local_mtu`)
- Notifications may arrive mid-line; `parse_buffer` must accumulate across packets (line accumulator pattern)
- ESP32 NUS TX characteristic sends UTF-8 encoded strings matching BSP serial format exactly

---

## Technology Stack

| Concern              | Library                  | Rationale                                              |
|----------------------|--------------------------|--------------------------------------------------------|
| GUI + Plotting       | `dearpygui` (Dear PyGui) | Python-native ImGui wrapper with built-in ImPlot; closest visual match to BSP |
| BLE communication    | `bleak`                  | Cross-platform async BLE (WinRT on Windows, CoreBluetooth on macOS, BlueZ on Linux/RPi) |
| Async event loop     | `asyncio`                | Required by bleak; drives BLE I/O in background thread |
| Config persistence   | `json` (stdlib)          | Same format as BSP; no extra dependency               |
| CSV export           | `csv` (stdlib)           | Matches BSP export format                             |
| Packaging            | `pyproject.toml` + `pip` | Modern Python packaging                               |

**Python version:** 3.10+ (required for `match` statement, `asyncio.run`, modern type hints)

---

## Project Structure

```
bleplot/
├── CLAUDE.md               ← this file
├── pyproject.toml
├── README.md
├── src/
│   └── bleplot/
│       ├── __init__.py
│       ├── main.py             ← entry point, window init
│       ├── app.py              ← BLEPlot main class (≈ BSP.cpp)
│       ├── ble_manager.py      ← BLE scan/connect/receive (≈ SerialManager.cpp)
│       ├── data_store.py       ← ScrollingData, DataInfo, thread-safe buffer (≈ Utility.hpp)
│       ├── parser.py           ← line parsing, float extraction (≈ parse_line())
│       ├── ui/
│       │   ├── data_panel.py   ← left variable list + drag-drop (≈ DataPanel.cpp)
│       │   ├── plot_monitor.py ← multi-plot manager (≈ PlotMonitor.cpp)
│       │   ├── plot.py         ← single plot widget (≈ Plot.cpp)
│       │   └── ble_monitor.py  ← raw BLE output monitor (≈ SerialMonitor.cpp)
│       ├── serialization.py    ← JSON config save/load (≈ Serialization.cpp)
│       └── theme.py            ← color palette, UI theme constants
├── tests/
│   ├── test_parser.py
│   ├── test_data_store.py
│   └── test_ble_manager.py
└── tools/
    └── ble_simulator.py        ← test device that emits NUS-style BLE data (≈ bsp_tester)
```

---

## Architecture

```
BLE Thread (asyncio loop in daemon thread)
    bleak BleakClient
        → on_notification(data: bytes)
            → parser.parse_buffer(data)
                → parser.parse_line(line) → List[float]
            → app.append_all_data(values)   [thread-safe via threading.Lock]
            → app.print_buffer.append(line) [thread-safe]

Main Thread (Dear PyGui render loop)
    app.update() called each frame
        → copy locked data to render-safe buffer
        → DataPanel.render()
        → BLEManager.render()     ← device scan/connect controls
        → PlotMonitor.render()    ← all plots
            → Plot.render()       ← individual plots via dpg.add_line_series()
        → BLEMonitor.render()     ← raw text output
```

### Key data structures (≈ BSP)

```python
@dataclass
class ScrollingData:
    identifier: int          # 0-255, unique per variable
    max_size: int = 5000
    offset: int = 0
    data: list[tuple[float, float]] = field(default_factory=list)  # (time, value)

@dataclass
class DataInfo:
    name: str
    color: tuple[float, float, float, float]  # RGBA 0-1
```

---

## Phase 1 — Project Bootstrap & BLE Scanning

**Goal:** Skeleton app window, BLE device scanner, connect/disconnect, raw bytes received.

### Tasks
- [ ] Create `pyproject.toml` with dependencies: `dearpygui`, `bleak`
- [ ] `main.py`: Create Dear PyGui viewport (1260×720), start render loop
- [ ] `ble_manager.py`:
  - Async BLE scanner using `bleak.BleakScanner`
  - List discovered devices (name + address) in UI dropdown
  - Connect to selected device via `bleak.BleakClient`
  - Subscribe to NUS TX characteristic notifications
  - `on_notification` callback stores raw bytes in queue
  - Disconnect handler
  - Run bleak event loop in a background daemon thread (`asyncio.run_coroutine_threadsafe`)
  - Connection status indicator (Disconnected / Connecting / Connected / Error) with color coding
- [ ] `app.py`: Skeleton with `ble_manager` instance, basic Dear PyGui window layout
- [ ] Test: can scan, see device list, connect, and print raw bytes to console

### BLE specifics
```python
NUS_SERVICE_UUID    = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX_CHAR_UUID    = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # device → host (notify)
NUS_RX_CHAR_UUID    = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # host → device (write)
```
Fall back to scanning ALL characteristics for notify property if NUS not found
(allows use with custom firmware).

### Platform notes
- **Windows**: bleak uses WinRT; no extra drivers needed on Win10+
- **macOS**: bleak uses CoreBluetooth; app needs Bluetooth permission in system prefs
- **Raspberry Pi**: requires `bluez` + `dbus`; `sudo apt install bluez python3-dbus`

---

## Phase 2 — Data Parsing & Thread-Safe Buffer

**Goal:** Parse incoming BLE bytes into floats; store in circular buffer; thread-safe access.

### Tasks
- [ ] `parser.py`:
  - `parse_buffer(data: bytes, line_accumulator: str) -> tuple[list[list[float]], str]`
    - Split on `0x0a` (newline), accumulate partial lines across notifications
    - Skip first incomplete line (matches BSP behavior)
    - Return complete parsed lines + updated accumulator
  - `parse_line(line: str) -> list[float]`
    - Split on `[\t ]+` regex
    - Validate each token: `[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?`
    - Convert to float; return empty list if any token invalid
    - Matches BSP behavior exactly
- [ ] `data_store.py`:
  - `ScrollingData` with circular buffer `add_point(x, y)`
  - `DataStore` class:
    - `threading.Lock` for thread safety
    - `append_all_data(values: list[float], timestamp: float)`
      - Auto-expand: new variables get new `ScrollingData` + `DataInfo` with auto-color
      - Circular assignment: variable index → identifier
    - `get_data(identifier) -> ScrollingData`
    - `get_info(identifier) -> DataInfo`
    - `copy_for_render() -> dict` (lock, snapshot, release — for main thread)
- [ ] `app.py`: Wire `on_notification` → `parser.parse_buffer()` → `data_store.append_all_data()`
- [ ] `data_store.py`: `print_buffer` as `collections.deque(maxlen=200)` for raw line history
- [ ] Tests: `test_parser.py`, `test_data_store.py` with known input strings

### Color palette (matches BSP)
```python
PLOT_COLORS = [
    (0.839, 0.153, 0.157, 1.0),  # red
    (0.122, 0.471, 0.706, 1.0),  # blue
    (0.173, 0.627, 0.173, 1.0),  # green
    (1.000, 0.498, 0.055, 1.0),  # orange
    (0.580, 0.404, 0.741, 1.0),  # purple
    (0.549, 0.337, 0.294, 1.0),  # brown
    (0.890, 0.467, 0.761, 1.0),  # pink
    (0.498, 0.498, 0.498, 1.0),  # gray
]
```

---

## Phase 3 — Core GUI: Data Panel + BLE Monitor

**Goal:** Left-side variable list; raw BLE monitor tab; top control bar.

### Tasks
- [ ] `theme.py`: Define Dear PyGui theme (dark background, accent colors matching BSP)
- [ ] `app.py`: Main window layout
  - Left panel (200px): DataPanel
  - Right area: tabbed or split — Plots / BLE Monitor
  - Top bar: BLE controls + action buttons
- [ ] `ui/data_panel.py`:
  - Table: [colored icon | variable name | latest value `%4.3f`]
  - Right-click context menu per row:
    - Editable name field
    - Color picker (Dear PyGui `add_color_edit`)
    - Per-plot axis submenu (populated after plots exist)
    - Save/Cancel buttons
  - Drag-drop source: payload = variable identifier int
    - `dpg.add_drag_payload` with type `"DND_PLOT"`
  - Only show values when BLE connected and data flowing (`baud_status` equivalent)
- [ ] `ui/ble_monitor.py`:
  - Child window with scrollable text
  - Checkbox: Auto-scroll toggle
  - Renders `print_buffer` deque contents
  - Auto-scrolls to bottom when enabled
- [ ] `ble_manager.py` UI portion (render method):
  - Device dropdown (discovered devices)
  - "Scan" button → triggers async scan
  - "Connect" / "Disconnect" button
  - Status indicator (color-coded text)
  - Custom UUID input field (collapsible, for non-NUS devices)

---

## Phase 4 — Plot Rendering

**Goal:** One or more real-time plots with all BSP plot features.

### Tasks
- [ ] `ui/plot.py` — Single plot widget:
  - `dpg.add_plot()` with dual Y-axes support (`dpg.add_plot_axis` × 3: x, y1, y2)
  - `dpg.add_line_series()` per variable, updated each frame
  - **Time-based X axis:** Show last `time_frame` seconds (default 10.0)
  - **Custom X axis mode:** Use one variable as X axis
  - **Autoscale Y toggle:** Auto-compute Y min/max from visible data
  - **Pause:** Freeze data snapshot; resume restores live feed
  - **Drag-drop targets:**
    - Main plot area → add variable to Y-axis 1
    - Y-axis 1 area → add to Y-axis 1
    - Y-axis 2 area → add to Y-axis 2
    - X-axis area → set as X variable (enables custom X mode)
  - **Context menu** (right-click):
    - Add variable submenu
    - Remove variable submenu
    - Toggle autoscale
    - Toggle X-axis real-time follow (when in custom X mode)
  - **Resize handle** at bottom of plot (drag to resize height)
  - Plot name displayed in title bar
- [ ] `ui/plot_monitor.py` — Plot manager:
  - List of `Plot` instances
  - "Add Plot" button (blue)
  - "Remove Plot" button (red, hidden if only 1 plot)
  - "Plot All Data" button — adds all current variables to first plot
  - "Pause / Resume" button — toggles all plots simultaneously
  - "Export CSV" button → file save dialog → CSV with time + all variables
  - "Save Config" / "Load Config" buttons

### Plot rendering notes
- Dear PyGui plots update via `dpg.set_value(series_tag, [x_list, y_list])` each frame
- Circular buffer data must be linearized for plotting:
  ```python
  data = scrolling_data.data
  offset = scrolling_data.offset
  ordered = data[offset:] + data[:offset]  # correct order
  xs = [p[0] for p in ordered]
  ys = [p[1] for p in ordered]
  ```
- X-axis limits: `dpg.set_axis_limits(x_axis_tag, xmin, xmax)`
- Y-axis autoscale: `dpg.set_axis_limits_auto(y_axis_tag)`

---

## Phase 5 — Configuration Save/Load & CSV Export

**Goal:** Full config persistence and data export matching BSP.

### Tasks
- [ ] `serialization.py`:
  - `save_config(path, app_state) -> None`
    - Serializes: all variable names/colors, all plot configs (axes, timeframe, height, variables per axis), BLE device address (not connection state)
    - Does NOT save data points (config only, like BSP)
  - `load_config(path) -> AppState`
    - Reconstructs UI state
    - Handles missing/extra fields gracefully
  - JSON format:
    ```json
    {
      "version": "1.0",
      "variables": {
        "0": {"name": "Sensor0", "color": [0.83, 0.15, 0.15, 1.0]}
      },
      "plots": [
        {
          "name": "Plot 1",
          "height": 300,
          "time_frame": 10.0,
          "autoscale": true,
          "variables": [
            {"id": 0, "y_axis": 0}
          ]
        }
      ],
      "ble": {
        "device_address": "AA:BB:CC:DD:EE:FF",
        "custom_tx_uuid": null
      }
    }
    ```
- [ ] `ui/plot_monitor.py`: Wire "Save Config" / "Load Config" to serialization
- [ ] CSV Export in `plot_monitor.py`:
  - Open file dialog via `dpg.add_file_dialog()` or `tkinter.filedialog` (fallback)
  - Header row: `"Program Time [s]", "Var0", "Var1", ...`
  - Data rows aligned by time index (variables may have different sample counts)
  - Use stdlib `csv` module

---

## Phase 6 — Polish, Packaging & Cross-Platform Testing

**Goal:** App feels complete, installable, works on all three platforms.

### Tasks
- [ ] `pyproject.toml`: Entry point `bleplot = "bleplot.main:main"`
- [ ] Icon: Convert BSP icon to `.ico` / `.icns` / `.png` for each platform
- [ ] Error handling:
  - BLE adapter not found → clear error dialog (not crash)
  - Device disconnects mid-session → auto-reconnect option or clean UI state reset
  - Config load failure → skip with warning, don't crash
  - Parse error on individual line → skip line, continue (matches BSP behavior)
- [ ] `tools/ble_simulator.py`:
  - Uses `bleak` server mode or hardware (ESP32 script) to emit NUS data
  - Emits `"0.5 1.2 3.7\n"` lines at configurable rate
  - Useful for development without physical hardware
- [ ] Platform-specific BLE adapter detection:
  ```python
  # Prefer built-in adapter (adapter index 0), list all available
  adapters = await BleakScanner.discover(adapter="hci0")  # Linux/RPi
  # Windows/macOS: bleak auto-selects default system adapter
  ```
- [ ] README.md:
  - Install instructions per platform
  - Raspberry Pi setup: `sudo apt install bluez python3-pip`
  - macOS: grant Bluetooth permission in System Preferences
  - Windows: Win10/11 with BT4.0+ adapter
- [ ] Test all three platforms:
  - Windows 10/11 (WinRT BLE)
  - macOS 12+ (CoreBluetooth)
  - Raspberry Pi OS Bookworm (BlueZ 5.6x)

---

## BSP → BLEPlot Feature Mapping

| BSP Feature                        | BLEPlot Equivalent                          |
|------------------------------------|---------------------------------------------|
| Serial port dropdown               | BLE device scan dropdown                   |
| Baud rate selector                 | Connection interval / MTU config (optional)|
| COM port enumeration               | `BleakScanner.discover()` async scan       |
| `mahi-com` serial read thread      | `bleak` async BLE notification callback    |
| `parse_line()` regex float parser  | `parser.parse_line()` — identical logic    |
| `ScrollingData` ring buffer        | `ScrollingData` dataclass with deque/list  |
| `DataInfo` name+color              | `DataInfo` dataclass                       |
| `BSP::append_all_data()`           | `DataStore.append_all_data()`              |
| `DataPanel` left column            | `ui/data_panel.py`                         |
| `Plot` ImPlot widget               | `ui/plot.py` using `dpg.add_plot()`        |
| `PlotMonitor` multi-plot manager   | `ui/plot_monitor.py`                       |
| `SerialMonitor` raw text view      | `ui/ble_monitor.py`                        |
| Drag-drop "DND_PLOT"               | Dear PyGui drag-drop payload               |
| JSON config save/load              | `serialization.py` JSON (same schema idea) |
| CSV export                         | stdlib `csv` writer                        |
| `mahi-gui` file dialogs            | `dpg.add_file_dialog()` or tkinter         |

---

## Dependencies (`pyproject.toml`)

```toml
[project]
name = "bleplot"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "dearpygui>=1.11",
    "bleak>=0.22",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio"]

[project.scripts]
bleplot = "bleplot.main:main"
```

---

## Known Constraints & Assumptions

- **NUS assumed** unless user specifies otherwise (see Open Questions #1)
- **One BLE device at a time** — matching BSP's one-serial-port model
- **Data format identical to BSP**: newline-terminated, whitespace-separated floats
- **No BLE write** to device (RX characteristic) in initial phases — notify only
- **5000 samples per variable** circular buffer — same as BSP default
- **200 lines** raw text monitor buffer — same as BSP
- **bleak** handles adapter preference automatically on all platforms; explicit `hci0` override available for RPi when multiple adapters present
