"""Gameplay controller — owns the Phase state machine, serial worker, and audio.

Extracted from the original MainWindow. Pages subscribe to Qt signals and emit
commands (`p1_submit`, `p2_submit_attempt`, `play_reference`, ...) without
reaching into hardware details.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from typing import List, Optional

from PySide6.QtCore import QByteArray, QObject, QThread, QTimer, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices
from PySide6.QtWidgets import QApplication

from ..game_logic import (
    MAX_FAILED_ATTEMPTS,
    Phase,
    SLOTS,
    binary_pattern_for_playback,
    compare_patterns,
    format_neopixel_all_green_serial,
    format_neopixel_clear_serial,
    normalize_pattern,
)
from ..phrase_audio import (
    SAMPLE_RATE,
    prepend_quarter_count_in_to_phrase,
    render_held_sine_phrase,
)
from ..receiver import send_led as receiver_send_led
from ..receiver import send_m_line as receiver_send_m_line
from ..serial_parser import validate_sensed_pattern
from ..serial_reader import SerialReaderWorker, start_reader_thread


class GameSession(QObject):
    """Turn-based rhythm gameplay state. Hardware + audio are opt-in."""

    live_pattern_changed = Signal(list)           # current P2 pad state
    p1_pattern_submitted = Signal(list)           # pattern P1 locked in
    phase_changed = Signal(object)                # Phase
    feedback_ready = Signal(list, int)            # matches, num_correct
    round_won = Signal()
    round_lost_reveal = Signal(list)              # reveal P1 pattern
    status_changed = Signal(str)
    serial_connected = Signal(bool)
    sensing_stable_changed = Signal(bool)
    attempts_changed = Signal(int)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._state: List[int] = [0] * SLOTS
        self._frame_candidate: Optional[List[int]] = None
        self._stable_frame_count = 0
        self._sensing_stable = False
        self._phase = Phase.P1_INPUT
        self._p1_pattern: List[int] = [0] * SLOTS
        self._failed_attempts = 0
        self._last_matches: Optional[List[bool]] = None

        self._thread: Optional[QThread] = None
        self._worker: Optional[SerialReaderWorker] = None

        self._audio_sink: Optional[QAudioSink] = None
        self._playback_pattern: List[int] = [0] * SLOTS
        self._playback_timer = QTimer(self)
        self._playback_timer.timeout.connect(self._on_playback_tick)
        self._phrase_t0: float = 0.0
        self._phrase_T: float = 0.0
        self._playback_step_dur: float = 0.0
        self._bpm: float = 80.0

    # ----- public API -----------------------------------------------------
    @property
    def phase(self) -> Phase:
        return self._phase

    @property
    def failed_attempts(self) -> int:
        return self._failed_attempts

    @property
    def max_failed_attempts(self) -> int:
        return MAX_FAILED_ATTEMPTS

    @property
    def live_state(self) -> List[int]:
        return list(self._state)

    @property
    def p1_pattern(self) -> List[int]:
        return list(self._p1_pattern)

    @property
    def is_connected(self) -> bool:
        return self._worker is not None

    def set_bpm(self, bpm: float) -> None:
        self._bpm = max(20.0, float(bpm))

    def bpm(self) -> float:
        return self._bpm

    # ----- serial ----------------------------------------------------------
    def connect_serial(self, port: str, baud: int) -> None:
        if self._worker is not None:
            return
        self._frame_candidate = None
        self._stable_frame_count = 0
        self._set_sensing_stable(False)
        self._thread, self._worker = start_reader_thread(port, baud)
        assert self._worker is not None
        self._worker.frame.connect(self._on_frame)
        self._worker.error.connect(self._on_serial_error)
        self._worker.status.connect(self.status_changed.emit)
        self._worker.finished.connect(self._on_reader_finished)
        self._thread.start()
        self.serial_connected.emit(True)

    def disconnect_serial(self) -> None:
        if self._worker:
            self._worker.stop()
        if self._thread:
            self._thread.quit()
            self._thread.wait(5000)
        self._thread = None
        self._worker = None
        self._frame_candidate = None
        self._stable_frame_count = 0
        self._set_sensing_stable(False)
        self.status_changed.emit("Disconnected.")
        self.serial_connected.emit(False)

    # ----- phase actions ---------------------------------------------------
    def start_new_match(self) -> None:
        self.stop_playback()
        self._phase = Phase.P1_INPUT
        self._failed_attempts = 0
        self._last_matches = None
        self._p1_pattern = [0] * SLOTS
        self._state = [0] * SLOTS
        self._frame_candidate = None
        self._stable_frame_count = 0
        self._set_sensing_stable(False)
        self.phase_changed.emit(self._phase)
        self.attempts_changed.emit(self._failed_attempts)
        self.live_pattern_changed.emit(list(self._state))
        self._safe_send(format_neopixel_clear_serial())

    def p1_submit(self) -> bool:
        """Lock P1 pattern and advance to P2 phase. False if read not stable."""
        if self._worker is not None and not self._sensing_stable:
            return False
        self.stop_playback()
        self._p1_pattern = binary_pattern_for_playback(self._state)
        self._failed_attempts = 0
        self._phase = Phase.P2_INPUT
        self.phase_changed.emit(self._phase)
        self.attempts_changed.emit(self._failed_attempts)
        self.p1_pattern_submitted.emit(list(self._p1_pattern))
        return True

    def set_manual_pattern(self, pattern: List[int]) -> None:
        """Let an AI/CPU preload a reference pattern (time-challenge SP target)."""
        self._p1_pattern = binary_pattern_for_playback(pattern)
        self._phase = Phase.P2_INPUT
        self._failed_attempts = 0
        self._last_matches = None
        self._state = [0] * SLOTS
        self.phase_changed.emit(self._phase)
        self.attempts_changed.emit(self._failed_attempts)
        self.p1_pattern_submitted.emit(list(self._p1_pattern))

    def play_reference(self, *, count_in_quarters: int = 0) -> None:
        """Play the locked reference (P1) pattern. Optional quarter-note count-in."""
        self._start_playback(self._p1_pattern, count_in_quarters=count_in_quarters)

    def play_current(self, *, count_in_quarters: int = 0) -> bool:
        """Play the live pad pattern. Optional quarter-note count-in."""
        if self._worker is not None and not self._sensing_stable:
            return False
        self._start_playback(self._state, count_in_quarters=count_in_quarters)
        return True

    def p2_submit(self) -> Optional[tuple[List[bool], int]]:
        """Grade P2 vs stored P1 reference. None if pad read not stable."""
        if self._worker is not None and not self._sensing_stable:
            return None
        self.stop_playback()
        attempt = binary_pattern_for_playback(self._state)
        matches, n_ok = compare_patterns(self._p1_pattern, attempt)
        self._last_matches = matches
        if n_ok == SLOTS:
            self._safe_send(format_neopixel_all_green_serial())
            self._phase = Phase.ROUND_WON
            self.phase_changed.emit(self._phase)
            self.round_won.emit()
            return matches, n_ok
        self._failed_attempts += 1
        self._safe_send_led(matches)
        self._phase = Phase.FEEDBACK
        self.phase_changed.emit(self._phase)
        self.feedback_ready.emit(matches, n_ok)
        self.attempts_changed.emit(self._failed_attempts)
        return matches, n_ok

    def feedback_continue(self) -> None:
        if self._failed_attempts >= MAX_FAILED_ATTEMPTS:
            self._phase = Phase.ROUND_LOST_REVEAL
            self.phase_changed.emit(self._phase)
            self.round_lost_reveal.emit(list(self._p1_pattern))
            return
        self._phase = Phase.P2_INPUT
        self._last_matches = None
        self.phase_changed.emit(self._phase)

    def new_round(self) -> None:
        self.start_new_match()

    # ----- internal serial/pad handling ------------------------------------
    def _on_frame(self, arr: list) -> None:
        if self._phase in (Phase.FEEDBACK, Phase.ROUND_LOST_REVEAL):
            return
        if not validate_sensed_pattern(arr):
            self._set_sensing_stable(False)
            self._stable_frame_count = 0
            self._frame_candidate = None
            return
        norm = normalize_pattern(arr)
        if self._frame_candidate is None or norm != self._frame_candidate:
            self._frame_candidate = list(norm)
            self._stable_frame_count = 1
        else:
            self._stable_frame_count += 1
        if self._stable_frame_count >= 2:
            self._state = binary_pattern_for_playback(norm)
            self._set_sensing_stable(True)
            self.live_pattern_changed.emit(list(self._state))

    def _on_reader_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._set_sensing_stable(False)
        self.serial_connected.emit(False)

    def _on_serial_error(self, msg: str) -> None:
        self.status_changed.emit(f"Error: {msg}")

    def _set_sensing_stable(self, stable: bool) -> None:
        if stable == self._sensing_stable:
            return
        self._sensing_stable = stable
        self.sensing_stable_changed.emit(stable)

    def _safe_send(self, line: str) -> None:
        self.status_changed.emit(receiver_send_m_line(self._worker, line))

    def _safe_send_led(self, matches: List[bool]) -> None:
        self.status_changed.emit(receiver_send_led(self._worker, matches))

    # ----- audio playback --------------------------------------------------
    def _step_duration_s(self) -> float:
        return 60.0 / max(20.0, self._bpm) / 4.0

    def stop_playback(self) -> None:
        self._playback_timer.stop()
        if self._audio_sink:
            self._audio_sink.stop()

    def _start_playback(self, pattern: List[int], *, count_in_quarters: int = 0) -> None:
        self.stop_playback()
        self._playback_pattern = binary_pattern_for_playback(pattern)
        step_dur = self._step_duration_s()
        phrase_s = SLOTS * step_dur
        bpm_f = max(20.0, self._bpm)
        count_in_s = (
            (count_in_quarters * (60.0 / bpm_f)) if count_in_quarters > 0 else 0.0
        )
        if platform.system() == "Darwin" and shutil.which("afplay"):
            self._play_phrase_macos_afplay(
                self._playback_pattern,
                step_dur,
                phrase_s,
                count_in_quarters=count_in_quarters,
            )
        else:
            self._play_phrase_qt_sink(
                self._playback_pattern,
                step_dur,
                count_in_quarters=count_in_quarters,
            )
        self._phrase_t0 = time.monotonic()
        self._phrase_T = count_in_s + phrase_s
        self._playback_step_dur = step_dur
        self._playback_timer.start(50)

    def _play_phrase_macos_afplay(
        self,
        pattern: List[int],
        step_dur: float,
        phrase_s: float,
        *,
        count_in_quarters: int,
    ) -> None:
        bpm_f = max(20.0, self._bpm)
        pcm = render_held_sine_phrase(
            pattern,
            step_duration_s=step_dur,
            sample_rate=SAMPLE_RATE,
            channels=2,
            encoding="int16",
        )
        if count_in_quarters > 0:
            pcm = prepend_quarter_count_in_to_phrase(
                pcm,
                sample_rate=SAMPLE_RATE,
                channels=2,
                encoding="int16",
                bpm=bpm_f,
                count_in_quarters=count_in_quarters,
            )
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            with wave.open(path, "wb") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(pcm)
        except OSError:
            try:
                os.unlink(path)
            except OSError:
                pass
            return
        total_s = phrase_s + (count_in_quarters * (60.0 / bpm_f) if count_in_quarters else 0.0)
        timeout = max(8.0, total_s + 4.0)

        def run() -> None:
            try:
                subprocess.run(
                    ["afplay", path],
                    check=False,
                    timeout=timeout,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
            finally:
                try:
                    os.unlink(path)
                except OSError:
                    pass

        threading.Thread(target=run, daemon=True).start()

    def _play_phrase_qt_sink(
        self,
        pattern: List[int],
        step_dur: float,
        *,
        count_in_quarters: int,
    ) -> None:
        sink = self._ensure_audio_sink()
        fmt = sink.format()
        enc = "int16" if fmt.sampleFormat() == QAudioFormat.Int16 else "float32"
        sr = int(fmt.sampleRate())
        ch = int(fmt.channelCount())
        pcm = self._render_phrase_pcm(pattern, step_dur)
        if count_in_quarters > 0:
            pcm = prepend_quarter_count_in_to_phrase(
                pcm,
                sample_rate=sr,
                channels=ch,
                encoding=enc,
                bpm=max(20.0, self._bpm),
                count_in_quarters=count_in_quarters,
            )
        sink.stop()
        try:
            sink.setBufferSize(max(262144, len(pcm) + 65536))
        except Exception:
            pass
        sink.setVolume(1.0)
        io = sink.start()
        if io is None:
            return
        offset, chunk_sz = 0, 4096
        while offset < len(pcm):
            chunk = QByteArray(pcm[offset : offset + chunk_sz])
            written = io.write(chunk)
            if written is None or written < 0:
                break
            if written == 0:
                if not io.waitForBytesWritten(200):
                    QApplication.processEvents()
                continue
            offset += written

    def _render_phrase_pcm(self, pattern: List[int], step_dur: float) -> bytes:
        sink = self._ensure_audio_sink()
        fmt = sink.format()
        enc = "int16" if fmt.sampleFormat() == QAudioFormat.Int16 else "float32"
        return render_held_sine_phrase(
            pattern,
            step_duration_s=step_dur,
            sample_rate=fmt.sampleRate(),
            channels=fmt.channelCount(),
            encoding=enc,
        )

    def _ensure_audio_sink(self) -> QAudioSink:
        if self._audio_sink is not None:
            return self._audio_sink
        dev = QMediaDevices.defaultAudioOutput()
        fmt = QAudioFormat()
        fmt.setSampleRate(SAMPLE_RATE)
        fmt.setChannelCount(2)
        fmt.setSampleFormat(QAudioFormat.Int16)
        if not dev.isFormatSupported(fmt):
            fmt_f = QAudioFormat()
            fmt_f.setSampleRate(SAMPLE_RATE)
            fmt_f.setChannelCount(2)
            fmt_f.setSampleFormat(QAudioFormat.Float32)
            if dev.isFormatSupported(fmt_f):
                fmt = fmt_f
            else:
                fmt = dev.preferredFormat()
                if fmt.sampleRate() <= 0:
                    fmt.setSampleRate(SAMPLE_RATE)
                if fmt.channelCount() <= 0:
                    fmt.setChannelCount(2)
        self._audio_sink = QAudioSink(dev, fmt)
        return self._audio_sink

    def _on_playback_tick(self) -> None:
        elapsed = time.monotonic() - self._phrase_t0
        if elapsed >= self._phrase_T:
            self._playback_timer.stop()

    # ----- shutdown --------------------------------------------------------
    def shutdown(self) -> None:
        self.stop_playback()
        self.disconnect_serial()
        if self._audio_sink:
            self._audio_sink.stop()
            self._audio_sink = None
