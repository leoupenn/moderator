"""Cross-platform serial port discovery (pyserial)."""
from __future__ import annotations

from typing import List, Optional, Tuple

import serial.tools.list_ports


def list_ports() -> List[Tuple[str, str]]:
    """Return [(device, description), ...] sorted by device name."""
    out: List[Tuple[str, str]] = []
    for p in serial.tools.list_ports.comports():
        desc = (p.description or "").strip() or p.device
        out.append((p.device, desc))
    out.sort(key=lambda x: x[0].lower())
    return out


def guess_default_port() -> Optional[str]:
    """Pick a likely controller port (same heuristics as original scripts)."""
    ports = list_ports()
    for device, desc in ports:
        low = desc.lower()
        if any(kw in low for kw in ("esp32", "usb", "uart", "xiao")):
            return device
    if ports:
        return ports[0][0]
    return None
