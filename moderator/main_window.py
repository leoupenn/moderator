"""Turn-based rhythm game: P1 submits pattern, P2 copies; LEDs + Arduino feedback."""
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

from PySide6.QtCore import QByteArray, Qt, QThread, QTimer
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .phrase_audio import SAMPLE_RATE, render_held_sine_phrase
from .game_logic import (
    MAX_FAILED_ATTEMPTS,
    Phase,
    SLOTS,
    binary_pattern_for_playback,
    compare_patterns,
    feedback_led_chars,
    format_neopixel_all_green_serial,
    format_neopixel_clear_serial,
    normalize_pattern,
    slot_role,
)
from .ports import guess_default_port, list_ports
from .receiver import send_led as receiver_send_led
from .receiver import send_m_line as receiver_send_m_line
from .serial_parser import validate_sensed_pattern
from .serial_reader import SerialReaderWorker, start_reader_thread


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Moderator — Rhythm duel")
        self.resize(900, 560)

        self._state: List[int] = [0] * SLOTS
        self._frame_candidate: Optional[List[int]] = None
        self._stable_frame_count = 0
        self._sensing_stable = False
        self._phase = Phase.P1_INPUT
        self._p1_pattern: List[int] = [0] * SLOTS
        self._failed_attempts = 0
        self._last_feedback_matches: Optional[List[bool]] = None

        self._thread: Optional[QThread] = None
        self._worker: Optional[SerialReaderWorker] = None

        self._audio_sink: Optional[QAudioSink] = None

        self._playback_pattern: List[int] = [0] * SLOTS
        self._playback_timer = QTimer(self)
        self._playback_timer.timeout.connect(self._playback_tick)
        self._phrase_t0: float = 0.0
        self._phrase_T: float = 0.0
        self._playback_step_dur: float = 0.0

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # Serial
        serial_box = QGroupBox("Serial (controller + Arduino)")
        srow = QHBoxLayout(serial_box)
        self._port = QComboBox()
        self._port.setMinimumWidth(260)
        self._baud = QSpinBox()
        self._baud.setRange(1200, 2_000_000)
        self._baud.setValue(115200)
        self._btn_refresh = QPushButton("Refresh ports")
        self._btn_refresh.clicked.connect(self._refresh_ports)
        self._btn_connect = QPushButton("Connect")
        self._btn_connect.clicked.connect(self._toggle_connect)
        srow.addWidget(QLabel("Port:"))
        srow.addWidget(self._port, stretch=1)
        srow.addWidget(QLabel("Baud:"))
        srow.addWidget(self._baud)
        srow.addWidget(self._btn_refresh)
        srow.addWidget(self._btn_connect)
        root.addWidget(serial_box)

        self._phase_label = QLabel()
        self._phase_label.setWordWrap(True)
        ph = QFont()
        ph.setPointSize(11)
        ph.setBold(True)
        self._phase_label.setFont(ph)
        root.addWidget(self._phase_label)

        self._hint = QLabel()
        self._hint.setWordWrap(True)
        root.addWidget(self._hint)

        self._status = QLabel("Disconnected.")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        bpm_row = QHBoxLayout()
        bpm_row.addWidget(QLabel("Playback BPM:"))
        self._bpm = QDoubleSpinBox()
        self._bpm.setRange(20, 300)
        self._bpm.setValue(80)
        bpm_row.addWidget(self._bpm)
        bpm_row.addStretch()
        root.addLayout(bpm_row)

        # 16 slots + role row
        grid_box = QGroupBox("16 positions — even = note start · odd = note end")
        grid_outer = QVBoxLayout(grid_box)
        role_row = QHBoxLayout()
        mono = QFont("Menlo", 11)
        if not mono.exactMatch():
            mono = QFont("Consolas", 10)
        self._role_labels: list[QLabel] = []
        for i in range(SLOTS):
            r = QLabel("S" if slot_role(i) == "start" else "E")
            r.setAlignment(Qt.AlignmentFlag.AlignCenter)
            r.setFont(mono)
            r.setStyleSheet("color:#aaa;font-size:10px;")
            self._role_labels.append(r)
            role_row.addWidget(r)
        grid_outer.addLayout(role_row)

        idx_row = QHBoxLayout()
        for i in range(SLOTS):
            ix = QLabel(str(i))
            ix.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ix.setFont(mono)
            ix.setStyleSheet("color:#666;font-size:9px;")
            idx_row.addWidget(ix)
        grid_outer.addLayout(idx_row)

        cell_row = QHBoxLayout()
        self._cells: list[QLabel] = []
        for i in range(SLOTS):
            lab = QLabel("0")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setMinimumSize(40, 40)
            lab.setFont(mono)
            lab.setStyleSheet(
                "background:#2a2a2a;color:#888;border-radius:6px;padding:4px;"
            )
            self._cells.append(lab)
            cell_row.addWidget(lab)
        grid_outer.addLayout(cell_row)

        self._playback_bar = QLabel()
        self._playback_bar.setFont(mono)
        self._playback_bar.setText("")
        grid_outer.addWidget(self._playback_bar)
        root.addWidget(grid_box)

        # P1
        p1_box = QGroupBox("Player 1")
        p1r = QHBoxLayout(p1_box)
        self._btn_p1_submit = QPushButton("Submit / play my rhythm")
        self._btn_p1_submit.clicked.connect(self._p1_submit)
        p1r.addWidget(self._btn_p1_submit)
        p1r.addStretch()
        root.addWidget(p1_box)

        # P2
        p2_box = QGroupBox("Player 2")
        p2r = QVBoxLayout(p2_box)
        p2btns = QHBoxLayout()
        self._btn_p2_play_ref = QPushButton("Play reference rhythm (Player 1)")
        self._btn_p2_play_ref.clicked.connect(self._p2_play_reference)
        self._btn_p2_play_mine = QPushButton("Play my current rhythm")
        self._btn_p2_play_mine.clicked.connect(self._p2_play_mine)
        self._btn_p2_submit = QPushButton("Submit my rhythm for grading")
        self._btn_p2_submit.clicked.connect(self._p2_submit_grade)
        p2btns.addWidget(self._btn_p2_play_ref)
        p2btns.addWidget(self._btn_p2_play_mine)
        p2btns.addWidget(self._btn_p2_submit)
        p2r.addLayout(p2btns)
        self._attempt_label = QLabel()
        p2r.addWidget(self._attempt_label)
        root.addWidget(p2_box)

        # Feedback / reveal
        fb_box = QGroupBox("Grading")
        fbl = QVBoxLayout(fb_box)
        self._btn_feedback_continue = QPushButton("Continue")
        self._btn_feedback_continue.clicked.connect(self._feedback_continue)
        fbl.addWidget(self._btn_feedback_continue)

        self._btn_new_round = QPushButton("New round")
        self._btn_new_round.clicked.connect(self._new_round)
        fbl.addWidget(self._btn_new_round)

        reveal_lab = QLabel("Answer (after 5 failed attempts): black = note · white = rest")
        fbl.addWidget(reveal_lab)
        self._reveal_row = QHBoxLayout()
        self._reveal_cells: list[QLabel] = []
        for i in range(SLOTS):
            lab = QLabel()
            lab.setMinimumSize(40, 40)
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._reveal_cells.append(lab)
            self._reveal_row.addWidget(lab)
        fbl.addLayout(self._reveal_row)
        root.addWidget(fb_box)

        self._refresh_ports()
        self._sync_phase_ui()

    def _step_duration_s(self) -> float:
        bpm = float(self._bpm.value())
        return 60.0 / bpm / 4.0

    def _stop_playback(self) -> None:
        self._playback_timer.stop()
        if self._audio_sink:
            self._audio_sink.stop()
        self._playback_bar.setText("")

    def _play_phrase_macos_afplay(
        self, pattern: List[int], step_dur: float, phrase_s: float
    ) -> bool:
        """Play phrase via /usr/bin/afplay — reliable on macOS when Qt audio is flaky."""
        pcm = render_held_sine_phrase(
            pattern,
            step_duration_s=step_dur,
            sample_rate=SAMPLE_RATE,
            channels=2,
            encoding="int16",
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
            return False

        timeout = max(8.0, phrase_s + 4.0)

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
        return True

    def _write_pcm_chunks(self, io, pcm: bytes) -> bool:
        """QAudioSink's device often accepts only part of a large buffer per write."""
        offset = 0
        chunk_sz = 4096
        while offset < len(pcm):
            chunk = QByteArray(pcm[offset : offset + chunk_sz])
            written = io.write(chunk)
            if written is None or written < 0:
                return False
            if written == 0:
                if not io.waitForBytesWritten(200):
                    QApplication.processEvents()
                continue
            offset += written
        return offset == len(pcm)

    def _start_playback(self, pattern: List[int]) -> None:
        self._stop_playback()
        self._playback_pattern = binary_pattern_for_playback(pattern)
        step_dur = self._step_duration_s()
        phrase_s = SLOTS * step_dur

        if platform.system() == "Darwin" and shutil.which("afplay"):
            self._play_phrase_macos_afplay(
                self._playback_pattern, step_dur, phrase_s
            )
            self._phrase_t0 = time.monotonic()
            self._phrase_T = phrase_s
            self._playback_step_dur = step_dur
            self._playback_timer.start(50)
            return

        pcm = self._render_phrase_pcm(self._playback_pattern, step_dur)
        sink = self._ensure_audio_sink()
        sink.stop()
        try:
            sink.setBufferSize(max(262144, len(pcm) + 65536))
        except Exception:
            pass
        sink.setVolume(1.0)
        io = sink.start()
        if io is not None:
            self._write_pcm_chunks(io, pcm)
        self._phrase_t0 = time.monotonic()
        self._phrase_T = phrase_s
        self._playback_step_dur = step_dur
        self._playback_timer.start(50)

    def _render_phrase_pcm(self, pattern: List[int], step_dur: float) -> bytes:
        sink = self._ensure_audio_sink()
        fmt = sink.format()
        return render_held_sine_phrase(
            pattern,
            step_duration_s=step_dur,
            sample_rate=fmt.sampleRate(),
            channels=fmt.channelCount(),
            encoding=self._encoding_for_format(fmt),
        )

    def _playback_tick(self) -> None:
        elapsed = time.monotonic() - self._phrase_t0
        if elapsed >= self._phrase_T:
            self._playback_timer.stop()
            self._playback_bar.setText("Playback finished.")
            return
        i = min(SLOTS - 1, int(elapsed / self._playback_step_dur))
        bar = "".join(
            "▶" if j == i else ("█" if self._playback_pattern[j] else "·")
            for j in range(SLOTS)
        )
        self._playback_bar.setText(f"Playback: [{bar}] step {i:02d}")

    def _encoding_for_format(self, fmt: QAudioFormat) -> str:
        if fmt.sampleFormat() == QAudioFormat.Int16:
            return "int16"
        return "float32"

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

    def _sync_phase_ui(self) -> None:
        ph = self._phase
        if ph == Phase.P1_INPUT:
            self._phase_label.setText("Phase: Player 1 — set your rhythm on the controller.")
            self._hint.setText(
                "Even slots are note starts; odd slots are note ends. "
                "When ready, press Submit to lock your pattern for Player 2."
            )
            self._btn_p1_submit.setEnabled(True)
            self._btn_p2_play_ref.setEnabled(False)
            self._btn_p2_play_mine.setEnabled(False)
            self._btn_p2_submit.setEnabled(False)
            self._btn_feedback_continue.setVisible(False)
            self._btn_new_round.setVisible(False)
            for c in self._reveal_cells:
                c.setVisible(False)
        elif ph == Phase.P2_INPUT:
            self._phase_label.setText("Phase: Player 2 — recreate Player 1's rhythm.")
            self._hint.setText(
                "Use Play reference to hear P1's pattern. "
                "Play my current rhythm previews what you've set. "
                f"Submit for grading. Failed attempts: {self._failed_attempts}/{MAX_FAILED_ATTEMPTS}."
            )
            self._btn_p1_submit.setEnabled(False)
            self._btn_p2_play_ref.setEnabled(True)
            self._btn_p2_play_mine.setEnabled(True)
            self._btn_p2_submit.setEnabled(True)
            self._btn_feedback_continue.setVisible(False)
            self._btn_new_round.setVisible(False)
            for c in self._reveal_cells:
                c.setVisible(False)
        elif ph == Phase.FEEDBACK:
            self._phase_label.setText("Feedback — per-slot match (green = correct, red = wrong).")
            self._hint.setText(
                "NeoPixel strip (8 LEDs): pairs of start/end slots share one LED. "
                "Host sends C / P i r g b ×8 / S (indices in game_logic). "
                "Press Continue."
            )
            self._btn_p1_submit.setEnabled(False)
            self._btn_p2_play_ref.setEnabled(False)
            self._btn_p2_play_mine.setEnabled(False)
            self._btn_p2_submit.setEnabled(False)
            self._btn_feedback_continue.setVisible(True)
            self._btn_new_round.setVisible(False)
            for c in self._reveal_cells:
                c.setVisible(False)
        elif ph == Phase.ROUND_WON:
            self._phase_label.setText("Player 2 matched the rhythm!")
            self._hint.setText("Start a new round when ready.")
            self._btn_p1_submit.setEnabled(False)
            self._btn_p2_play_ref.setEnabled(False)
            self._btn_p2_play_mine.setEnabled(False)
            self._btn_p2_submit.setEnabled(False)
            self._btn_feedback_continue.setVisible(False)
            self._btn_new_round.setVisible(True)
            for c in self._reveal_cells:
                c.setVisible(False)
        elif ph == Phase.ROUND_LOST_REVEAL:
            self._phase_label.setText("5 failed attempts — correct answer:")
            self._hint.setText("Black = note (active slot), white = rest.")
            self._btn_p1_submit.setEnabled(False)
            self._btn_p2_play_ref.setEnabled(False)
            self._btn_p2_play_mine.setEnabled(False)
            self._btn_p2_submit.setEnabled(False)
            self._btn_feedback_continue.setVisible(False)
            self._btn_new_round.setVisible(True)
            for c in self._reveal_cells:
                c.setVisible(True)

        self._attempt_label.setText(
            f"Failed grading attempts: {self._failed_attempts} / {MAX_FAILED_ATTEMPTS}"
        )

    def _apply_feedback_cells(self, matches: List[bool]) -> None:
        chars = feedback_led_chars(matches)
        for i, ok in enumerate(matches):
            cell = self._cells[i]
            cell.setText(chars[i])
            if ok:
                cell.setStyleSheet(
                    "background:#143214;color:#6f6;border-radius:6px;padding:4px;font-weight:bold;"
                )
            else:
                cell.setStyleSheet(
                    "background:#3d1515;color:#f88;border-radius:6px;padding:4px;font-weight:bold;"
                )

    def _reset_cells_live(self) -> None:
        for i, v in enumerate(self._state):
            self._paint_live_cell(i, v)

    def _paint_live_cell(self, index: int, v: int) -> None:
        cell = self._cells[index]
        active = bool(v)
        cell.setText("1" if active else "0")
        if active:
            cell.setStyleSheet(
                "background:#1e4620;color:#7dffb0;border-radius:6px;padding:4px;font-weight:bold;"
            )
        else:
            cell.setStyleSheet(
                "background:#2a2a2a;color:#888;border-radius:6px;padding:4px;"
            )

    def _send_m_line(self, line: str) -> None:
        self._status.setText(receiver_send_m_line(self._worker, line))

    def _send_led_serial(self, matches: List[bool]) -> None:
        self._status.setText(receiver_send_led(self._worker, matches))

    def _fill_reveal(self) -> None:
        for i in range(SLOTS):
            active = bool(self._p1_pattern[i])
            c = self._reveal_cells[i]
            c.setText(str(i))
            if active:
                c.setStyleSheet(
                    "background:#111;color:#111;border:1px solid #444;border-radius:4px;"
                )
            else:
                c.setStyleSheet(
                    "background:#f0f0f0;color:#ccc;border:1px solid #ccc;border-radius:4px;"
                )

    def _p1_submit(self) -> None:
        if self._worker is not None and not self._sensing_stable:
            QMessageBox.warning(
                self,
                "Unstable controller read",
                "Wait until the pad read is stable (two identical valid frames in a row) "
                "before submitting your rhythm.",
            )
            return
        self._stop_playback()
        self._p1_pattern = binary_pattern_for_playback(self._state)
        self._failed_attempts = 0
        self._phase = Phase.P2_INPUT
        self._sync_phase_ui()
        self._reset_cells_live()

    def _p2_play_reference(self) -> None:
        self._start_playback(self._p1_pattern)

    def _p2_play_mine(self) -> None:
        if self._worker is not None and not self._sensing_stable:
            QMessageBox.warning(
                self,
                "Unstable controller read",
                "Playback skipped: the last serial frames were invalid or not stable. "
                "Check the connection and pads, then try again.",
            )
            return
        self._start_playback(self._state)

    def _p2_submit_grade(self) -> None:
        if self._worker is not None and not self._sensing_stable:
            QMessageBox.warning(
                self,
                "Unstable controller read",
                "Grading skipped: wait for a stable controller read before submitting.",
            )
            return
        self._stop_playback()
        attempt = binary_pattern_for_playback(self._state)
        matches, n_ok = compare_patterns(self._p1_pattern, attempt)
        self._last_feedback_matches = matches

        if n_ok == SLOTS:
            self._send_m_line(format_neopixel_all_green_serial())
            self._phase = Phase.ROUND_WON
            self._sync_phase_ui()
            self._reset_cells_live()
            QMessageBox.information(self, "Perfect", "Player 2 matched all 16 slots.")
            return

        self._failed_attempts += 1
        self._apply_feedback_cells(matches)
        self._send_led_serial(matches)
        self._phase = Phase.FEEDBACK
        self._sync_phase_ui()

    def _feedback_continue(self) -> None:
        if self._failed_attempts >= MAX_FAILED_ATTEMPTS:
            self._phase = Phase.ROUND_LOST_REVEAL
            self._fill_reveal()
            self._sync_phase_ui()
            return
        self._phase = Phase.P2_INPUT
        self._last_feedback_matches = None
        self._reset_cells_live()
        self._sync_phase_ui()

    def _new_round(self) -> None:
        self._stop_playback()
        self._phase = Phase.P1_INPUT
        self._failed_attempts = 0
        self._last_feedback_matches = None
        self._p1_pattern = [0] * SLOTS
        self._frame_candidate = None
        self._stable_frame_count = 0
        self._sensing_stable = False
        self._sync_phase_ui()
        self._reset_cells_live()
        # Only clear NeoPixels here: feedback stays lit until next P2 grade (frame starts with C) or new round.
        self._send_m_line(format_neopixel_clear_serial())

    def _refresh_ports(self) -> None:
        cur = self._port.currentData()
        self._port.clear()
        for device, desc in list_ports():
            label = f"{device} — {desc}"
            self._port.addItem(label, userData=device)
        if cur is not None:
            idx = self._port.findData(cur)
            if idx >= 0:
                self._port.setCurrentIndex(idx)
                return
        guess = guess_default_port()
        if guess:
            idx = self._port.findData(guess)
            if idx >= 0:
                self._port.setCurrentIndex(idx)

    def _toggle_connect(self) -> None:
        if self._thread is not None:
            self._disconnect_serial()
            self._btn_connect.setText("Connect")
            return
        if self._port.count() == 0:
            QMessageBox.warning(
                self, "No port", "No serial ports found. Is the controller plugged in?"
            )
            return
        device = self._port.currentData()
        if not device:
            QMessageBox.warning(self, "Port", "Select a serial port.")
            return
        baud = int(self._baud.value())
        self._frame_candidate = None
        self._stable_frame_count = 0
        self._sensing_stable = False
        self._thread, self._worker = start_reader_thread(device, baud)
        assert self._worker is not None
        self._worker.frame.connect(self._on_frame)
        self._worker.error.connect(self._on_serial_error)
        self._worker.status.connect(self._status.setText)
        self._worker.finished.connect(self._on_reader_finished)
        self._thread.start()
        self._btn_connect.setText("Disconnect")
        self._port.setEnabled(False)
        self._baud.setEnabled(False)

    def _disconnect_serial(self) -> None:
        if self._worker:
            self._worker.stop()
        if self._thread:
            self._thread.quit()
            self._thread.wait(5000)
        self._thread = None
        self._worker = None
        self._frame_candidate = None
        self._stable_frame_count = 0
        self._sensing_stable = False
        self._port.setEnabled(True)
        self._baud.setEnabled(True)
        self._status.setText("Disconnected.")

    def _on_reader_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._btn_connect.setText("Connect")
        self._port.setEnabled(True)
        self._baud.setEnabled(True)

    def _on_serial_error(self, msg: str) -> None:
        self._status.setText(f"Error: {msg}")
        QMessageBox.critical(self, "Serial error", msg)

    def _on_frame(self, arr: list) -> None:
        if self._phase == Phase.FEEDBACK or self._phase == Phase.ROUND_LOST_REVEAL:
            return
        if not validate_sensed_pattern(arr):
            self._sensing_stable = False
            self._stable_frame_count = 0
            self._frame_candidate = None
            return
        norm = normalize_pattern(arr)
        if self._frame_candidate is None or norm != self._frame_candidate:
            self._frame_candidate = norm[:]
            self._stable_frame_count = 1
        else:
            self._stable_frame_count += 1
        if self._stable_frame_count >= 2:
            self._state = binary_pattern_for_playback(norm)
            self._sensing_stable = True
            for i, v in enumerate(self._state):
                self._paint_live_cell(i, v)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._stop_playback()
        self._disconnect_serial()
        if self._audio_sink:
            self._audio_sink.stop()
            self._audio_sink = None
        event.accept()
