"""Metronome engine + count-circle widget for the novice tutorial.

The ``MetronomeEngine`` emits ``beat_tick(index)`` once per quarter note at the
current BPM. Subscribers usually drive a row of ``CountCircle`` widgets and,
on the Try-the-Tempo screen, grade spacebar taps against ``last_beat_time``.

Audio click: generated once (reusing ``click_audio.make_stereo_click``) and
played through a per-engine ``QAudioSink`` in pull mode via a small
``QIODevice`` that queues bursts. Keeping it per-engine (rather than a shared
global sink) means the audio device is released the moment the user leaves
the tutorial.
"""
from __future__ import annotations

import time
from typing import List

from PySide6.QtCore import QIODevice, QObject, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices
from PySide6.QtWidgets import QWidget

from ...click_audio import SAMPLE_RATE, make_stereo_click

BEATS_PER_BAR: int = 4


class _ClickStream(QIODevice):
    """QIODevice that emits a short click on ``fire()`` and silence otherwise.

    Qt's ``QAudioSink`` in pull mode polls ``readData(maxlen)`` whenever it
    needs bytes. We keep a single click payload ready and return it once per
    ``fire()``, padding with zeros between clicks so the sink stays primed.
    """

    def __init__(self, click_bytes: bytes) -> None:
        super().__init__()
        self._click = click_bytes
        self._queue: bytes = b""
        self.open(QIODevice.OpenModeFlag.ReadOnly)

    def fire(self) -> None:
        self._queue += self._click

    def isSequential(self) -> bool:  # noqa: N802 - Qt override naming
        return True

    def readData(self, maxlen: int) -> bytes:  # noqa: N802 - Qt override naming
        if maxlen <= 0:
            return b""
        if self._queue:
            chunk = self._queue[:maxlen]
            self._queue = self._queue[maxlen:]
            if len(chunk) < maxlen:
                chunk += b"\x00" * (maxlen - len(chunk))
            return chunk
        return b"\x00" * maxlen

    def writeData(self, _data: bytes) -> int:  # noqa: N802 - Qt override naming
        return 0

    def bytesAvailable(self) -> int:  # noqa: N802 - Qt override naming
        return len(self._queue) + super().bytesAvailable()


class MetronomeEngine(QObject):
    """Ticks 4/4 quarter notes at the current BPM with an audio click."""

    beat_tick = Signal(int)  # 1..BEATS_PER_BAR

    def __init__(
        self,
        bpm: int = 80,
        *,
        play_audio: bool = True,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._bpm = max(20, int(bpm))
        self._beat = 0
        self._last_beat_monotonic: float = 0.0
        self._play_audio = play_audio

        self._timer = QTimer(self)
        self._timer.setTimerType(self._timer.timerType())
        self._timer.timeout.connect(self._on_tick)

        self._sink: QAudioSink | None = None
        self._stream: _ClickStream | None = None

    # ----- control ---------------------------------------------------------
    def start(self) -> None:
        if self._timer.isActive():
            return
        self._beat = 0
        self._ensure_audio()
        self._timer.start(self._interval_ms())
        # Fire beat 1 immediately so the UI lights the first circle the moment
        # the user lands on the screen (instead of waiting one full beat).
        self._on_tick()

    def stop(self) -> None:
        self._timer.stop()
        if self._sink is not None:
            self._sink.stop()
            self._sink = None
        self._stream = None

    def set_bpm(self, bpm: int) -> None:
        self._bpm = max(20, int(bpm))
        if self._timer.isActive():
            self._timer.setInterval(self._interval_ms())

    def set_play_audio(self, enabled: bool) -> None:
        self._play_audio = bool(enabled)

    # ----- inspection ------------------------------------------------------
    @property
    def bpm(self) -> int:
        return self._bpm

    @property
    def current_beat(self) -> int:
        return self._beat

    @property
    def beat_interval_ms(self) -> int:
        return self._interval_ms()

    @property
    def last_beat_monotonic(self) -> float:
        return self._last_beat_monotonic

    def ms_since_last_beat(self) -> int:
        if self._last_beat_monotonic <= 0:
            return 10**9
        return int((time.monotonic() - self._last_beat_monotonic) * 1000)

    def ms_to_nearest_beat(self) -> int:
        """Absolute offset from now to the nearest quarter beat (ms)."""
        if self._last_beat_monotonic <= 0:
            return 10**9
        interval_ms = self._interval_ms()
        dt_ms = int((time.monotonic() - self._last_beat_monotonic) * 1000)
        return min(dt_ms, max(0, interval_ms - dt_ms))

    # ----- internals -------------------------------------------------------
    def _interval_ms(self) -> int:
        return max(1, int(60_000 / self._bpm))

    def _on_tick(self) -> None:
        self._beat = self._beat % BEATS_PER_BAR + 1
        self._last_beat_monotonic = time.monotonic()
        if self._play_audio and self._stream is not None:
            self._stream.fire()
        self.beat_tick.emit(self._beat)

    def _ensure_audio(self) -> None:
        if not self._play_audio or self._sink is not None:
            return
        try:
            device = QMediaDevices.defaultAudioOutput()
            fmt = QAudioFormat()
            fmt.setSampleRate(SAMPLE_RATE)
            fmt.setChannelCount(2)
            fmt.setSampleFormat(QAudioFormat.Int16)
            encoding = "int16"
            if not device.isFormatSupported(fmt):
                fmt.setSampleFormat(QAudioFormat.Float32)
                encoding = "float32"
                if not device.isFormatSupported(fmt):
                    fmt = device.preferredFormat()
                    encoding = (
                        "int16"
                        if fmt.sampleFormat() == QAudioFormat.Int16
                        else "float32"
                    )
            click_bytes = make_stereo_click(
                sample_rate=fmt.sampleRate() or SAMPLE_RATE,
                channels=fmt.channelCount() or 2,
                encoding=encoding,
                freq=1000.0,
                duration_s=0.05,
                volume=0.55,
            )
            self._stream = _ClickStream(click_bytes)
            self._sink = QAudioSink(device, fmt)
            self._sink.start(self._stream)
        except Exception:
            # Missing audio device shouldn't crash the tutorial — silence is
            # an acceptable fallback.
            self._sink = None
            self._stream = None


# ---------------------------------------------------------------------------
# CountCircle widget
# ---------------------------------------------------------------------------


class CountCircle(QWidget):
    """Circular beat indicator used on every metronome-style tutorial screen.

    States:
      * ``idle``   — white fill, ghosted stroke
      * ``on``     — accent-blue fill (the currently-playing beat)
      * ``hit``    — green flash (player nailed an on-tempo spacebar press)
      * ``miss``   — red flash (player missed)

    Caller decides what ``label`` to render ("1", "and", etc.). The circle
    is a plain painted widget so it can live anywhere on the canvas without
    dragging in another SVG.
    """

    STATE_IDLE = "idle"
    STATE_ON = "on"
    STATE_HIT = "hit"
    STATE_MISS = "miss"

    _COLORS = {
        STATE_IDLE: QColor("#FFFFFF"),
        STATE_ON: QColor("#94C4D8"),
        STATE_HIT: QColor("#A2CEAB"),
        STATE_MISS: QColor("#F9B5B5"),
    }

    def __init__(
        self,
        label: str = "",
        diameter: int = 131,
        *,
        text_color: str = "#1E1E1E",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(diameter, diameter)
        self._label = label
        self._state = self.STATE_IDLE
        self._text_color = QColor(text_color)

    def set_state(self, state: str) -> None:
        if state not in self._COLORS:
            return
        self._state = state
        self.update()

    def set_label(self, label: str) -> None:
        self._label = label
        self.update()

    @property
    def state(self) -> str:
        return self._state

    def paintEvent(self, _event) -> None:  # noqa: D401 - Qt override
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = self._COLORS[self._state]
        p.setBrush(color)
        p.setPen(QColor(0, 0, 0, 30))
        p.drawEllipse(1, 1, self.width() - 2, self.height() - 2)
        if self._label:
            p.setPen(self._text_color)
            f = QFont("Jersey 10")
            f.setPixelSize(max(24, int(self.height() * 0.38)))
            p.setFont(f)
            p.drawText(self.rect(), 0x0084, self._label)  # AlignCenter
        p.end()


def make_count_row(
    labels: List[str],
    *,
    diameter: int = 131,
    spacing: int = 31,
    parent: QWidget | None = None,
) -> tuple[QWidget, list[CountCircle]]:
    """Return a container host plus the inner ``CountCircle`` widgets.

    Rows on the tutorial frames are laid out in absolute coordinates (Figma
    puts each Count at a fixed x offset within a 1203-wide frame). We honour
    the spacing argument so callers can tweak it for the measure/grid frames
    where the circles are denser.
    """
    host = QWidget(parent)
    width = max(1, diameter * len(labels) + spacing * max(0, len(labels) - 1))
    host.setFixedSize(width, diameter)
    circles: list[CountCircle] = []
    x = 0
    for label in labels:
        c = CountCircle(label, diameter, parent=host)
        c.move(x, 0)
        circles.append(c)
        x += diameter + spacing
    return host, circles
