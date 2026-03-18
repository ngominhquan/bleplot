"""
BLE Simulator — emits NUS-style BLE data for development without hardware.

This script runs a software BLE peripheral using bless (if available) or
prints instructions for setting up an ESP32 NUS server.

Usage:
    python tools/ble_simulator.py [--rate 20] [--vars 3] [--pattern sine]

Patterns: sine, ramp, random, step

Without bless installed (most common), this acts as a TCP-to-BLE bridge:
the simulator exposes a TCP server on localhost:9876 that you can connect to
with a BLE-to-TCP proxy (like the one below), or just use the ESP32 firmware
provided in the README.

Install bless for a real GATT server:
    pip install bless
"""
from __future__ import annotations

import argparse
import asyncio
import math
import random
import socket
import sys
import time
import threading


# ---------------------------------------------------------------------------
# Data generators
# ---------------------------------------------------------------------------

def sine_values(t: float, n: int) -> list[float]:
    return [math.sin(t + i * math.pi / n) for i in range(n)]

def ramp_values(t: float, n: int) -> list[float]:
    return [(t * (i + 1)) % 10.0 for i in range(n)]

def random_values(t: float, n: int) -> list[float]:
    return [random.uniform(-1.0, 1.0) for _ in range(n)]

def step_values(t: float, n: int) -> list[float]:
    return [float(int(t) % (i + 2)) for i in range(n)]

GENERATORS = {
    "sine": sine_values,
    "ramp": ramp_values,
    "random": random_values,
    "step": step_values,
}


# ---------------------------------------------------------------------------
# TCP server mode (no extra deps, pair with serial-to-BLE firmware or proxy)
# ---------------------------------------------------------------------------

class TCPSimulator:
    """
    Listens on TCP localhost:9876.  Each connected client receives
    NUS-compatible text lines at the requested rate.
    """

    def __init__(self, rate: float, nvars: int, pattern: str) -> None:
        self.rate = rate
        self.nvars = nvars
        self.gen = GENERATORS[pattern]
        self._clients: list[socket.socket] = []
        self._lock = threading.Lock()

    def run(self) -> None:
        host, port = "127.0.0.1", 9876
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((host, port))
        srv.listen(5)
        print(f"[sim] TCP server listening on {host}:{port}")
        print(f"[sim] Connect BLEPlot to this via a TCP→BLE proxy,")
        print(f"[sim] or load a companion ESP32 sketch that proxies this.")

        accept_thread = threading.Thread(target=self._accept_loop, args=(srv,), daemon=True)
        accept_thread.start()

        start = time.monotonic()
        interval = 1.0 / self.rate
        while True:
            t = time.monotonic() - start
            vals = self.gen(t, self.nvars)
            line = " ".join(f"{v:.4f}" for v in vals) + "\n"
            data = line.encode()

            with self._lock:
                dead = []
                for c in self._clients:
                    try:
                        c.sendall(data)
                    except OSError:
                        dead.append(c)
                for c in dead:
                    self._clients.remove(c)

            print(f"\r[sim] t={t:7.2f}s  {line.strip()}", end="", flush=True)
            time.sleep(interval)

    def _accept_loop(self, srv: socket.socket) -> None:
        while True:
            conn, addr = srv.accept()
            print(f"\n[sim] Client connected: {addr}")
            with self._lock:
                self._clients.append(conn)


# ---------------------------------------------------------------------------
# BLE GATT server mode (requires: pip install bless)
# ---------------------------------------------------------------------------

NUS_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX_UUID      = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX_UUID      = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

async def run_ble_server(rate: float, nvars: int, pattern: str) -> None:
    try:
        from bless import BlessServer, BlessGATTCharacteristic, GATTCharacteristicProperties, GATTAttributePermissions
    except ImportError:
        print("[sim] 'bless' not installed. Run: pip install bless")
        print("[sim] Falling back to TCP mode.")
        TCPSimulator(rate, nvars, pattern).run()
        return

    gen = GENERATORS[pattern]

    server = BlessServer(name="BLEPlot-Sim", loop=asyncio.get_event_loop())

    await server.add_new_service(NUS_SERVICE_UUID)
    await server.add_new_characteristic(
        NUS_SERVICE_UUID,
        NUS_TX_UUID,
        GATTCharacteristicProperties.notify,
        None,
        GATTAttributePermissions.readable,
    )
    await server.add_new_characteristic(
        NUS_SERVICE_UUID,
        NUS_RX_UUID,
        GATTCharacteristicProperties.write | GATTCharacteristicProperties.write_without_response,
        None,
        GATTAttributePermissions.writeable,
    )

    await server.start()
    print(f"[sim] BLE GATT server advertising as 'BLEPlot-Sim'")
    print(f"[sim] Sending {nvars} {pattern} variables at {rate} Hz")

    start = time.monotonic()
    interval = 1.0 / rate
    try:
        while True:
            t = time.monotonic() - start
            vals = gen(t, nvars)
            line = " ".join(f"{v:.4f}" for v in vals) + "\n"
            data = line.encode()

            server.get_characteristic(NUS_TX_UUID).value = bytearray(data)
            server.update_value(NUS_SERVICE_UUID, NUS_TX_UUID)

            print(f"\r[sim] t={t:7.2f}s  {line.strip()}", end="", flush=True)
            await asyncio.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        await server.stop()
        print("\n[sim] Server stopped.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="BLEPlot NUS simulator")
    parser.add_argument("--rate",    type=float, default=20.0, help="Samples per second")
    parser.add_argument("--vars",    type=int,   default=3,    help="Number of variables")
    parser.add_argument("--pattern", choices=list(GENERATORS), default="sine")
    parser.add_argument("--ble",     action="store_true",
                        help="Use real BLE GATT server (requires bless)")
    args = parser.parse_args()

    if args.ble:
        asyncio.run(run_ble_server(args.rate, args.vars, args.pattern))
    else:
        TCPSimulator(args.rate, args.vars, args.pattern).run()


if __name__ == "__main__":
    main()
