"""Background thread: serial read (16-int frames) + write queue for Arduino feedback."""
from __future__ import annotations

import queue
import serial
from PySide6.QtCore import QObject, QThread, Signal

from .serial_parser import parse_line


class SerialReaderWorker(QObject):
    """Reads `[...]` lines; outbound commands via enqueue_line() (thread-safe queue)."""

    frame = Signal(list)
    error = Signal(str)
    status = Signal(str)
    finished = Signal()

    def __init__(self, device: str, baud: int = 115200) -> None:
        super().__init__()
        self._device = device
        self._baud = baud
        self._ser: serial.Serial | None = None
        self._running = False
        self._write_queue: queue.SimpleQueue[str] = queue.SimpleQueue()

    def enqueue_line(self, s: str) -> None:
        """Call from any thread. Consumed inside run() — avoids Queued slots (no event loop in run)."""
        self._write_queue.put(s)

    def stop(self) -> None:
        self._running = False
        if self._ser and self._ser.is_open:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None

    def _flush_writes(self) -> None:
        if not self._ser or not self._ser.is_open:
            return
        while True:
            try:
                s = self._write_queue.get_nowait()
            except queue.Empty:
                break
            data = s.encode("utf-8")
            if not data.endswith(b"\n"):
                data += b"\n"
            try:
                self._ser.write(data)
                self._ser.flush()
            except Exception:
                pass

    def run(self) -> None:
        self._running = True
        try:
            self.status.emit(f"Opening {self._device} @ {self._baud} baud…")
            self._ser = serial.Serial(self._device, self._baud, timeout=0.25)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit()
            return

        self.status.emit("Connected.")
        while self._running and self._ser and self._ser.is_open:
            try:
                self._flush_writes()
                raw = self._ser.readline().decode("utf-8", errors="ignore")
                parsed = parse_line(raw)
                if parsed is not None:
                    self.frame.emit(parsed)
            except Exception as e:
                if self._running:
                    self.error.emit(str(e))
                break

        self.stop()
        self.status.emit("Disconnected.")
        self.finished.emit()


def start_reader_thread(device: str, baud: int) -> tuple[QThread, SerialReaderWorker]:
    thread = QThread()
    worker = SerialReaderWorker(device, baud)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    return thread, worker
