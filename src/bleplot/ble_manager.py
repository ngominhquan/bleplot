"""
BLE Manager — scan, connect, receive NUS notifications.

Runs a dedicated asyncio event loop in a background daemon thread.
All public methods are thread-safe (called from the DPG main thread).
Coroutines are submitted via asyncio.run_coroutine_threadsafe().

Background thread is the correct architecture on macOS: DPG's
render_dearpygui_frame() pumps Cocoa/AppKit which interferes with asyncio
if both run on the main thread.
"""
from __future__ import annotations

import asyncio
import enum
import threading
from typing import Callable

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

NUS_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # notify  device→host
NUS_RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # write   host→device


class ConnectionStatus(enum.Enum):
    DISCONNECTED = "Disconnected"
    SCANNING     = "Scanning…"
    CONNECTING   = "Connecting…"
    CONNECTED    = "Connected"
    ERROR        = "Error"


class BLEManager:
    """
    Owns a background asyncio event loop (daemon thread).
    Public API is thread-safe — safe to call from DPG callbacks.
    """

    def __init__(
        self,
        on_notification: Callable[[bytes], None],
        on_disconnect:   Callable[[], None],
    ) -> None:
        self._on_notification = on_notification
        self._on_disconnect   = on_disconnect

        self.status:        ConnectionStatus = ConnectionStatus.DISCONNECTED
        self.error_message: str              = ""
        self.discovered:    list[BLEDevice]  = []

        self._client:   BleakClient | None = None
        self._tx_char:  str                = NUS_TX_CHAR_UUID

        # Create the loop INSIDE the thread so macOS ObjC ownership is correct
        self._loop:  asyncio.AbstractEventLoop | None = None
        self._ready  = threading.Event()

        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="ble-asyncio"
        )
        self._thread.start()
        self._ready.wait()   # block until loop is running and ready

    # ------------------------------------------------------------------
    # Public thread-safe API (called from DPG main thread)
    # ------------------------------------------------------------------

    def scan(self, timeout: float = 5.0) -> None:
        asyncio.run_coroutine_threadsafe(self._scan(timeout), self._loop)

    def connect(self, device: BLEDevice) -> None:
        asyncio.run_coroutine_threadsafe(self._connect(device), self._loop)

    def disconnect(self) -> None:
        asyncio.run_coroutine_threadsafe(self._disconnect(), self._loop)

    def is_connected(self) -> bool:
        return self.status == ConnectionStatus.CONNECTED

    # ------------------------------------------------------------------
    # Background thread — owns the asyncio event loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        # Create and bind the loop inside this thread (important on macOS)
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._ready.set()          # unblock __init__
        self._loop.run_forever()   # runs until loop.stop() is called

    # ------------------------------------------------------------------
    # Async internals (run on the BLE thread)
    # ------------------------------------------------------------------

    async def _scan(self, timeout: float) -> None:
        self.status        = ConnectionStatus.SCANNING
        self.error_message = ""
        try:
            devices = await BleakScanner.discover(timeout=timeout)
            self.discovered = devices
        except Exception as exc:
            self.error_message = str(exc)
            self.status        = ConnectionStatus.ERROR
            return
        self.status = ConnectionStatus.DISCONNECTED

    async def _connect(self, device: BLEDevice) -> None:
        self.status        = ConnectionStatus.CONNECTING
        self.error_message = ""
        try:
            self._client = BleakClient(
                device,
                disconnected_callback=self._handle_disconnect,
            )
            await self._client.connect()

            tx_char = self._resolve_tx_char(self._client)
            if tx_char is None:
                raise RuntimeError("No notifiable characteristic found.")
            self._tx_char = tx_char

            await self._client.start_notify(self._tx_char,
                                            self._notification_handler)
            self.status = ConnectionStatus.CONNECTED
        except Exception as exc:
            self.error_message = str(exc)
            self.status        = ConnectionStatus.ERROR
            self._client       = None

    async def _disconnect(self) -> None:
        if self._client and self._client.is_connected:
            try:
                await self._client.stop_notify(self._tx_char)
                await self._client.disconnect()
            except Exception:
                pass
        self._client = None
        self.status  = ConnectionStatus.DISCONNECTED

    def _handle_disconnect(self, _client: BleakClient) -> None:
        self._client = None
        self.status  = ConnectionStatus.DISCONNECTED
        self._on_disconnect()

    def _notification_handler(self, _char, data: bytearray) -> None:
        self._on_notification(bytes(data))

    @staticmethod
    def _resolve_tx_char(client: BleakClient) -> str | None:
        for svc in client.services:
            for char in svc.characteristics:
                if char.uuid.lower() == NUS_TX_CHAR_UUID.lower():
                    return char.uuid
        for svc in client.services:
            for char in svc.characteristics:
                if "notify" in char.properties:
                    return char.uuid
        return None
