"""Novice tutorial pages — Figma section "Tutorial for Expert and Novices".

Seventeen small screens walk a first-time player through:

  1. Welcome → "Ready?"
  2. Metronome (animated counts + audio click)
  3. Metronome continued (same animation + Continue)
  4. Try-the-Tempo — spacebar tapping with ±150 ms window, green/red flash
  5. Explaining Counts
  6. Measure (four-line staff)
  7. Piano Sheets
  8. Hardware 1 — the 8-block grid
  9. Hardware 2 — grid + eight count circles
 10. Hardware 3 — hardware 2 + tempo pill + animation
 11. Hardware 4 — continues hardware 3 story
 12. Eighth note
 13. Quarter note
 14. Half note
 15. Whole note
 16. Trial 1 — play a simple rhythm
 17. Trial 2 — grid feedback (green = correct slot, red = wrong slot)

Every page is driven off a shared ``NoviceTutorialBase`` class so the header,
duck profile, continue pill, and help chip render identically across the flow.
Frames that need music (metronome, try-tempo, hardware 3/4) embed a
``MetronomeEngine`` that auto-starts on ``showEvent`` and auto-stops on
``hideEvent`` — leaving the page cleanly releases the audio device.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QKeyEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...game_logic import SLOTS
from ...phrase_audio import DEFAULT_COUNT_IN_QUARTERS, note_intervals_from_pattern
from ...session import FlowState
from ..theme import DESIGN_H, DESIGN_W, THEME
from ..widgets.asset_loader import asset_path
from ..widgets import (
    BEATS_PER_BAR,
    BpmInput,
    CountCircle,
    DuckMascot,
    FlowPage,
    MetronomeEngine,
    svg_widget,
)

# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------

_TITLE_PX = 96
_BODY_PX = 40
_HINT_PX = 54

_NOTE_BLOCK_COUNT = 8
_NOTE_BLOCK_W = 141
_NOTE_BLOCK_H = 278
_NOTE_BLOCK_GAP = 19  # 160 centres - 141 width


def _make_title(text: str, parent: QWidget, *, y: int = 32) -> QLabel:
    label = QLabel(text.upper(), parent)
    label.setObjectName("HeroTitle")
    f = QFont(THEME.font_display)
    f.setPixelSize(_TITLE_PX)
    label.setFont(f)
    label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    label.adjustSize()
    label.move(45, y)
    return label


def _make_body_text(text: str, parent: QWidget, *, size: int = _BODY_PX) -> QLabel:
    """Body copy rendered into the white rounded 'Frame 34' content well."""
    label = QLabel(text.upper(), parent)
    label.setStyleSheet(
        f"color: {THEME.white}; font-family: '{THEME.font_display}'; "
        f"font-size: {size}px; background: transparent;"
    )
    label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    return label


class _ContinuePill(QPushButton):
    """Dark 334×91 pill with 'Continue' (or any) text."""

    def __init__(self, text: str = "Continue", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("ChoiceDark")
        self.setFixedSize(334, 91)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class NoviceTutorialBase(FlowPage):
    """Common layout skeleton for every tutorial frame.

    Subclasses call ``self.place(...)`` for any frame-specific extras after
    ``super().__init__(...)``. Passing ``continue_text=None`` hides the CTA —
    used by the pure-metronome frame which needs the user to watch before
    the narrative "Continue" appears on the next page.
    """

    continue_clicked = Signal()

    def __init__(
        self,
        flow: FlowState,
        *,
        title: str,
        body: str,
        continue_text: Optional[str] = "Continue",
        show_duck: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(flow, parent)
        self._title_lbl = _make_title(title, self)

        if show_duck:
            # Small corner duck (130×130) used on every tutorial frame except
            # the cover screen, whose mascot sits centered.
            duck = DuckMascot("duck_med.svg", 130, 130, self)
            duck.move(45, 212)

        self._body_label = _make_body_text(body, self)
        self._body_label.setParent(self)
        self._body_label.setGeometry(244, 258, 1143, 100)

        self._continue: Optional[_ContinuePill] = None
        if continue_text is not None:
            self._continue = _ContinuePill(continue_text, self)
            self._continue.move(589, 866)
            self._continue.clicked.connect(self.continue_clicked.emit)
            self._continue.raise_()


def _layout_body_with_side_tempo(
    page: NoviceTutorialBase,
    tempo: BpmInput,
    *,
    body_width: int = 670,
    body_height: int | None = None,
    gap_px: int = 22,
) -> None:
    """Narrow the body copy and sit the BPM pill on the same row (right side).

    The old ``(989, 215)`` placement overlapped the wide body panel; Figma
    hardware frames keep **Tempo** beside the narrative instead.
    """
    y = 258
    h = body_height if body_height is not None else page._body_label.height()
    page._body_label.setGeometry(244, y, body_width, h)
    tempo.move(244 + body_width + gap_px, y)
    tempo.raise_()


# ---------------------------------------------------------------------------
# Frame 1 — Welcome to Tutorial (83:1328)
# ---------------------------------------------------------------------------


class NoviceWelcomeIntroPage(FlowPage):
    """Cover screen: big title + duck + 'Ready?' CTA."""

    ready_clicked = Signal()
    skip_clicked = Signal()

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(flow, parent)

        title = QLabel("Welcome to Tutorial!".upper(), self)
        title.setObjectName("HeroTitle")
        f = QFont(THEME.font_display)
        f.setPixelSize(_TITLE_PX)
        title.setFont(f)
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title.adjustSize()
        title.move((DESIGN_W - title.width()) // 2, 320)

        subtitle = QLabel(
            "We are going to have a quick music note introduction!".upper(), self
        )
        subtitle.setObjectName("HeroSubtitle")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(36)
        subtitle.setFont(sf)
        subtitle.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        subtitle.adjustSize()
        subtitle.move((DESIGN_W - subtitle.width()) // 2, 540)

        duck = DuckMascot("duck_large.svg", 160, 176, self)
        duck.move((DESIGN_W - 160) // 2, 640)

        ready = _ContinuePill("Ready?", self)
        ready.setFixedSize(334, 91)
        ready.move((DESIGN_W - 334) // 2, 820)
        ready.clicked.connect(self.ready_clicked.emit)

        skip = QPushButton("Skip tutorial", self)
        skip.setFlat(True)
        skip.setCursor(Qt.CursorShape.PointingHandCursor)
        skip.setStyleSheet(
            f"color: rgba(255,255,255,200); font-family: '{THEME.font_display}'; "
            f"font-size: 28px; background: transparent; border: none; text-decoration: underline;"
        )
        skip.clicked.connect(self.skip_clicked.emit)
        skip.adjustSize()
        skip.move((DESIGN_W - skip.width()) // 2, 820 + 91 + 14)


# ---------------------------------------------------------------------------
# Shared metronome row helper
# ---------------------------------------------------------------------------


def _build_count_row(
    labels: List[str],
    parent: QWidget,
    *,
    diameter: int,
    spacing: int,
    x: int,
    y: int,
) -> List[CountCircle]:
    circles: List[CountCircle] = []
    cx = x
    for lbl in labels:
        c = CountCircle(lbl, diameter, parent=parent)
        c.move(cx, y)
        circles.append(c)
        cx += diameter + spacing
    return circles


class _MetronomePageMixin(FlowPage):
    """Mix-in: owns a ``MetronomeEngine`` with two count rows.

    Top row = quarter beats 1/2/3/4. Bottom row = the 'and' eighth-note row
    that the hardware frames light up at half-beat offsets. Pages that only
    need the top row set ``_bottom_circles = []``.
    """

    _top_circles: List[CountCircle]
    _bottom_circles: List[CountCircle]

    def _init_metronome(
        self,
        *,
        bpm: int,
        play_audio: bool = True,
        show_eighths: bool = False,
    ) -> None:
        self._engine = MetronomeEngine(bpm=bpm, play_audio=play_audio, parent=self)
        self._show_eighths = show_eighths
        self._half_timer = QTimer(self)
        self._half_timer.setSingleShot(True)
        self._half_timer.timeout.connect(self._on_half_tick)
        self._engine.beat_tick.connect(self._on_beat_tick)

    def _on_beat_tick(self, beat: int) -> None:
        for idx, c in enumerate(self._top_circles):
            c.set_state(
                CountCircle.STATE_ON if idx == (beat - 1) else CountCircle.STATE_IDLE
            )
        for c in self._bottom_circles:
            c.set_state(CountCircle.STATE_IDLE)
        if self._show_eighths and self._bottom_circles:
            # Fire the matching 'and' circle half a beat later.
            self._half_timer.start(self._engine.beat_interval_ms // 2)
            self._pending_and_index = beat - 1

    def _on_half_tick(self) -> None:
        idx = getattr(self, "_pending_and_index", -1)
        if 0 <= idx < len(self._bottom_circles):
            for c in self._top_circles:
                c.set_state(CountCircle.STATE_IDLE)
            self._bottom_circles[idx].set_state(CountCircle.STATE_ON)

    def showEvent(self, event) -> None:  # noqa: D401 - Qt override
        super().showEvent(event)
        self._engine.start()

    def hideEvent(self, event) -> None:  # noqa: D401 - Qt override
        super().hideEvent(event)
        self._engine.stop()
        self._half_timer.stop()


# ---------------------------------------------------------------------------
# Frames 2+3 — Here's A Metronome (83:1352 & 87:1689)
# Only the 2nd variant has a Continue pill — the 1st is an interpolation
# step we synthesise by reusing the same layout.
# ---------------------------------------------------------------------------


class NoviceMetronomePage(NoviceTutorialBase, _MetronomePageMixin):
    """Two count rows + a read-only tempo pill, animated with audio clicks."""

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(
            flow,
            title="Here's A Metronome",
            body="These are counts & you can set the speed with Tempo — "
            "making it slower or faster.",
            continue_text="Continue",
            parent=parent,
        )
        self._top_circles = _build_count_row(
            ["1", "2", "3", "4"],
            self,
            diameter=131,
            spacing=31,
            x=214 + 20,
            y=448,
        )
        self._bottom_circles = _build_count_row(
            ["and", "and", "and", "and"],
            self,
            diameter=131,
            spacing=31,
            x=214 + 20,
            y=680,
        )

        self._tempo = BpmInput(initial=80, parent=self)
        self._tempo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        _layout_body_with_side_tempo(self, self._tempo, body_width=670, body_height=100)

        self._init_metronome(bpm=80, play_audio=True, show_eighths=True)
        self._tempo.value_changed.connect(self._engine.set_bpm)


# ---------------------------------------------------------------------------
# Frame 4 — Try the Tempo (87:1748)
# Spacebar ±150 ms grading; flash green/red on the active count circle.
# ---------------------------------------------------------------------------


class NoviceTryTheTempoPage(NoviceTutorialBase, _MetronomePageMixin):

    HIT_WINDOW_MS = 150

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(
            flow,
            title="Try It Yourself",
            body="Make the tempo faster or slower. Practice a couple of times!",
            continue_text="Continue",
            parent=parent,
        )

        hint = QLabel("Hit SpaceBar with the Tempo!".upper(), self)
        hint.setStyleSheet(
            f"color: {THEME.white}; font-family: '{THEME.font_display}'; "
            f"font-size: {_HINT_PX}px; background: transparent;"
        )
        hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        hint.adjustSize()
        hint.move((DESIGN_W - hint.width()) // 2, 374)

        _d = 131
        _gap = 31
        _row_w = 4 * _d + 3 * _gap
        _x0 = (DESIGN_W - _row_w) // 2
        self._top_circles = _build_count_row(
            ["1", "2", "3", "4"],
            self,
            diameter=_d,
            spacing=_gap,
            x=_x0,
            y=560,
        )
        self._bottom_circles = []

        self._tempo = BpmInput(initial=80, parent=self)
        _layout_body_with_side_tempo(self, self._tempo, body_width=670, body_height=100)

        self._init_metronome(bpm=80, play_audio=True, show_eighths=False)
        self._tempo.value_changed.connect(self._engine.set_bpm)

        # A small status label below the count row for hit/miss feedback text.
        self._feedback = QLabel("", self)
        self._feedback.setStyleSheet(
            f"color: {THEME.white}; font-family: '{THEME.font_display}'; "
            f"font-size: 40px; background: transparent;"
        )
        self._feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._feedback.setFixedSize(600, 50)
        self._feedback.move((DESIGN_W - 600) // 2, 810)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _on_beat_tick(self, beat: int) -> None:
        # Keep hit/miss feedback visible on the active beat — do not paint the
        # metronome "on" (blue) state over a successful green (or a red miss).
        for idx, c in enumerate(self._top_circles):
            if idx == beat - 1:
                if c.state in (CountCircle.STATE_HIT, CountCircle.STATE_MISS):
                    continue
                c.set_state(CountCircle.STATE_ON)
            else:
                c.set_state(CountCircle.STATE_IDLE)
        for c in self._bottom_circles:
            c.set_state(CountCircle.STATE_IDLE)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat() or event.key() not in (
            Qt.Key.Key_Space,
            Qt.Key.Key_Return,
        ):
            super().keyPressEvent(event)
            return
        offset_ms = self._engine.ms_to_nearest_beat()
        beat = self._engine.current_beat
        if 1 <= beat <= len(self._top_circles):
            target = self._top_circles[beat - 1]
            if offset_ms <= self.HIT_WINDOW_MS:
                target.set_state(CountCircle.STATE_HIT)
                self._feedback.setText(f"ON TEMPO ✓  ({offset_ms} ms)")
            else:
                target.set_state(CountCircle.STATE_MISS)
                self._feedback.setText(f"Off tempo  ({offset_ms} ms)")
        event.accept()


# ---------------------------------------------------------------------------
# Frame 5 — Explaining Counts (100:908)
# ---------------------------------------------------------------------------


class NoviceCountsPage(NoviceTutorialBase, _MetronomePageMixin):
    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(
            flow,
            title="What are these?",
            body="These are essentially counts.",
            parent=parent,
        )
        self._top_circles = _build_count_row(
            ["1", "2", "3", "4"],
            self,
            diameter=188,
            spacing=150,
            x=214 + 14,
            y=508,
        )
        self._bottom_circles = []
        self._init_metronome(bpm=72, play_audio=True, show_eighths=False)


# ---------------------------------------------------------------------------
# Frame 6 — Measure (100:982)
# ---------------------------------------------------------------------------


class _MeasureStaff(QWidget):
    """Four horizontal lines, 242 px tall — the Figma "Frame 5" notation group."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(1328, 242)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, _event) -> None:  # noqa: D401 - Qt override
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(THEME.white))
        pen.setWidth(2)
        p.setPen(pen)
        for i in range(4):
            y = int(i * (242 / 3))
            p.drawLine(0, y, self.width(), y)
        p.end()


class NoviceMeasurePage(NoviceTutorialBase, _MetronomePageMixin):
    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(
            flow,
            title="What are these?",
            body="There are four per measure.",
            parent=parent,
        )
        staff = _MeasureStaff(self)
        staff.move(144, 493)

        self._top_circles = _build_count_row(
            ["1", "2", "3", "4"],
            self,
            diameter=188,
            spacing=150,
            x=214 + 14,
            y=508,
        )
        self._bottom_circles = []
        self._init_metronome(bpm=72, play_audio=True, show_eighths=False)


# ---------------------------------------------------------------------------
# Frame 7 — Piano Sheets (100:1057) — raster "image 9" (Figma node 100:1110)
# ---------------------------------------------------------------------------


def _piano_sheet_image_label(parent: QWidget) -> QLabel:
    """PNG exported from Figma (bundled as ``novice_piano_sheets.png``)."""
    lbl = QLabel(parent)
    lbl.setFixedSize(938, 446)
    lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("background: #FFFFFF; border-radius: 8px;")
    path = asset_path("novice_piano_sheets.png")
    if path.exists():
        pix = QPixmap(str(path))
        if not pix.isNull():
            # Match Figma's render of node 100:1110:
            # - img width: 100%
            # - img height: 130.09%
            # - img top: -30.07% (cropped/shifted up inside the fixed frame)
            frame_w, frame_h = 938, 446
            scaled_h = max(1, round(frame_h * 1.3009))
            y_off = round(frame_h * 0.3007)
            scaled = pix.scaled(
                frame_w,
                scaled_h,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            crop = scaled.copy(0, y_off, frame_w, frame_h)
            lbl.setPixmap(crop)
    return lbl


class NovicePianoSheetsPage(NoviceTutorialBase):
    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(
            flow,
            title="What are these?",
            body="These appear on music sheets too!",
            parent=parent,
        )
        sheet = _piano_sheet_image_label(self)
        sheet.move(347, 391)

        # Four tiny count clusters sprinkled across the staff (decorative).
        for (x, y) in [(536, 453), (882, 453), (528, 667), (872, 662)]:
            _build_count_row(
                ["", "", "", ""],
                self,
                diameter=45,
                spacing=36,
                x=x,
                y=y,
            )


# ---------------------------------------------------------------------------
# Hardware pages (100:1186 / 100:1303 / 100:1401 / 100:1479)
# ---------------------------------------------------------------------------


class _HardwareGrid(QWidget):
    """The slate 1355×364 grid housing 8 dark vertical note blocks."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        block_count: int = 8,
        active_blocks: Optional[List[int]] = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(1355, 364)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._block_count = block_count
        self._active = set(active_blocks or [])

    def set_active(self, indices: List[int]) -> None:
        self._active = set(indices)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: D401 - Qt override
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Outer frame
        p.setBrush(QColor("#3E3E3E"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(self.rect(), 14, 14)
        # Blocks
        start_x = 48
        gap = 19
        for i in range(self._block_count):
            x = start_x + i * (_NOTE_BLOCK_W + gap)
            color = QColor("#94C4D8") if i in self._active else QColor("#1E1E1E")
            p.setBrush(color)
            p.drawRoundedRect(x, 43, _NOTE_BLOCK_W, _NOTE_BLOCK_H, 10, 10)
        p.end()


class NoviceHardware1Page(NoviceTutorialBase):
    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(
            flow,
            title="Using our Hardware",
            body="How does our Grid work?",
            parent=parent,
        )
        grid = _HardwareGrid(self)
        grid.move(62, 451)


class _HardwareCountRowPage(NoviceTutorialBase, _MetronomePageMixin):
    """Hardware 2/3/4 — grid with 8 small labels and optional tempo pill."""

    _LABELS = ["1", "and", "2", "and", "3", "and", "4", "and"]

    def __init__(
        self,
        flow: FlowState,
        *,
        title: str,
        body: str,
        with_tempo: bool,
        bpm: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(flow, title=title, body=body, parent=parent)

        self._grid = _HardwareGrid(self)
        self._grid.move(62, 451)

        # The 8 small labeled circles sit beneath each note block.
        self._top_circles = []
        self._bottom_circles = []
        cluster_host = QWidget(self)
        cluster_host.setFixedSize(1266, 131)
        cluster_host.move(110, 577)
        cluster_host.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        for idx, label in enumerate(self._LABELS):
            c = CountCircle(label, 131, parent=cluster_host)
            c.move(idx * (131 + 31), 0)
            # Even indices are downbeats (1/2/3/4), odd are "and" eighth beats.
            if idx % 2 == 0:
                self._top_circles.append(c)
            else:
                self._bottom_circles.append(c)

        if with_tempo:
            self._tempo = BpmInput(initial=bpm, parent=self)
            _layout_body_with_side_tempo(
                self, self._tempo, body_width=600, body_height=130
            )
        else:
            self._tempo = None

        self._init_metronome(bpm=bpm, play_audio=with_tempo, show_eighths=True)
        if with_tempo:
            self._tempo.value_changed.connect(self._engine.set_bpm)

    def _on_beat_tick(self, beat: int) -> None:
        # Highlight the matching downbeat circle and the corresponding note block.
        for idx, c in enumerate(self._top_circles):
            c.set_state(
                CountCircle.STATE_ON if idx == (beat - 1) else CountCircle.STATE_IDLE
            )
        for c in self._bottom_circles:
            c.set_state(CountCircle.STATE_IDLE)
        self._grid.set_active([(beat - 1) * 2])
        if self._show_eighths:
            self._half_timer.start(self._engine.beat_interval_ms // 2)
            self._pending_and_index = beat - 1

    def _on_half_tick(self) -> None:
        idx = getattr(self, "_pending_and_index", -1)
        if 0 <= idx < len(self._bottom_circles):
            for c in self._top_circles:
                c.set_state(CountCircle.STATE_IDLE)
            self._bottom_circles[idx].set_state(CountCircle.STATE_ON)
            self._grid.set_active([idx * 2 + 1])


class NoviceHardware2Page(_HardwareCountRowPage):
    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(
            flow,
            title="The box is a measure",
            body="Here we still have four audible counts, but each count is split into "
            "1 and 'and'.",
            with_tempo=False,
            bpm=72,
            parent=parent,
        )


class NoviceHardware3Page(_HardwareCountRowPage):
    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(
            flow,
            title="The box is a measure",
            body="Four audible counts, each split into 1 and 'and' — try different tempos!",
            with_tempo=True,
            bpm=80,
            parent=parent,
        )


class NoviceHardware4Page(_HardwareCountRowPage):
    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(
            flow,
            title="The box is a measure",
            body="The faster you go, the denser the rhythm — give it a shot!",
            with_tempo=True,
            bpm=100,
            parent=parent,
        )


# ---------------------------------------------------------------------------
# Note type pages (100:1556 / 100:1654 / 100:1713 / 100:1777)
# ---------------------------------------------------------------------------

# Figma places the hardware tray at (105,450); Qt uses (62,451). Only grid
# overlays need to be shifted to match the painted blocks.
_FIGMA_GRID_ORIGIN_X = 105
_FIGMA_GRID_ORIGIN_Y = 450
_PAGE_GRID_X = 62
_PAGE_GRID_Y = 451


def _grid_symbol_page_rect(figma_x: int, figma_y: int, w: int, h: int) -> tuple[int, int, int, int]:
    return (
        _PAGE_GRID_X + (figma_x - _FIGMA_GRID_ORIGIN_X),
        _PAGE_GRID_Y + (figma_y - _FIGMA_GRID_ORIGIN_Y),
        w,
        h,
    )


@dataclass(frozen=True)
class _NoteExplainerFigmaLayout:
    """Static layout matching the Novice Introduction_* note frames in Figma."""

    body_well: tuple[int, int, int, int]
    body_symbol_size: tuple[int, int]
    body_symbol_asset: str
    direction_photo: str
    direction_photo_rect: tuple[int, int, int, int]
    caption_center_x: int
    caption_top: int
    grid_symbol_rect: tuple[int, int, int, int]
    grid_symbol_asset: str
    arrow_rect: tuple[int, int, int, int] | None = None


_EIGHTH_NOTE_LAYOUT = _NoteExplainerFigmaLayout(
    body_well=(199, 199, 802, 157),
    body_symbol_size=(120, 120),
    body_symbol_asset="novice_note_symbol_eighth.png",
    direction_photo="novice_note_direction_eighth.png",
    direction_photo_rect=(1024, 130, 521, 298),
    caption_center_x=1297,
    caption_top=130,
    grid_symbol_rect=_grid_symbol_page_rect(105, 511, 242, 242),
    grid_symbol_asset="novice_note_symbol_eighth.png",
    arrow_rect=(1120, 203, 34, 65),
)

_QUARTER_NOTE_LAYOUT = _NoteExplainerFigmaLayout(
    body_well=(214, 201, 687, 157),
    body_symbol_size=(120, 120),
    body_symbol_asset="novice_note_symbol_quarter.png",
    direction_photo="novice_note_direction_quarter.png",
    direction_photo_rect=(1001, 97, 474, 290),
    caption_center_x=1297,
    caption_top=103,
    grid_symbol_rect=_grid_symbol_page_rect(175, 509, 246, 246),
    grid_symbol_asset="novice_note_symbol_quarter.png",
    arrow_rect=None,
)

_HALF_NOTE_LAYOUT = _NoteExplainerFigmaLayout(
    body_well=(214, 201, 696, 157),
    body_symbol_size=(46, 120),
    body_symbol_asset="novice_note_symbol_half.png",
    direction_photo="novice_note_direction_half.png",
    direction_photo_rect=(949, 100, 517, 315),
    caption_center_x=1314,
    caption_top=103,
    grid_symbol_rect=_grid_symbol_page_rect(421, 493, 103, 266),
    grid_symbol_asset="novice_note_symbol_half.png",
    arrow_rect=(1202, 214, 34, 65),
)


def _place_rotated_direction_arrow(parent: QWidget, x: int, y: int, w: int, h: int) -> None:
    """Figma exports the chevron horizontal; the frames rotate it 90° for “down”."""
    from PySide6.QtSvg import QSvgRenderer

    path = asset_path("novice_note_direction_arrow.svg")
    if not path.exists():
        return
    renderer = QSvgRenderer(str(path))
    out_w, out_h = h, w
    pix = QPixmap(out_w, out_h)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.translate(out_w / 2, out_h / 2)
    p.rotate(90)
    p.translate(-w / 2, -h / 2)
    renderer.render(p, QRectF(0, 0, float(w), float(h)))
    p.end()
    lbl = QLabel(parent)
    lbl.setPixmap(pix)
    lbl.setFixedSize(out_w, out_h)
    lbl.move(x, y)
    lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)


class _NoteTypeBase(NoviceTutorialBase):
    """Shared layout for Eighth/Quarter/Half/Whole note explainers.

    When a ``GameSession`` is attached via :py:meth:`attach_session` *and*
    :py:attr:`AUTOPLAY_BLOCKS` is set, the page listens to the live hardware
    pattern and auto-plays the rhythm + advances to the next screen as soon
    as the physical blocks form the expected figure (one eighth-note block
    for Eighth, two contiguous blocks for Quarter, etc.).
    """

    # Number of contiguous filled grid blocks the connected controller must
    # report before the page auto-plays and advances. ``None`` disables the
    # behaviour (used by Whole note which stays manual via Continue).
    AUTOPLAY_BLOCKS: Optional[int] = None
    # If True, filled blocks must be exactly ``0 .. AUTOPLAY_BLOCKS-1`` (measure
    # start). If False, any contiguous run of that length counts (eighth note).
    AUTOPLAY_FROM_BLOCK_ZERO: bool = False

    def __init__(
        self,
        flow: FlowState,
        *,
        title: str,
        body: str,
        active_blocks: List[int],
        try_text: Optional[str],
        figma_note_layout: Optional[_NoteExplainerFigmaLayout] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(flow, title=title, body=body, parent=parent)

        self._autoplay_k_lo = min(active_blocks) if active_blocks else 0
        self._autoplay_k_hi = max(active_blocks) if active_blocks else _NOTE_BLOCK_COUNT - 1

        grid = _HardwareGrid(self, active_blocks=active_blocks)
        grid.move(62, 451)

        if figma_note_layout is not None:
            self._apply_figma_note_layout(figma_note_layout, grid, try_text)
        elif try_text is not None:
            prompt = QFrame(self)
            prompt.setObjectName("CardDark")
            prompt.setFixedSize(888, 86)
            prompt.move((DESIGN_W - 888) // 2, 766)
            v = QVBoxLayout(prompt)
            v.setContentsMargins(30, 12, 30, 12)
            lbl = QLabel(try_text.upper())
            lbl.setStyleSheet(
                f"color: {THEME.white}; font-family: '{THEME.font_display}'; "
                f"font-size: 32px; background: transparent;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(lbl)

        self._session = None
        self._autoplay_armed = False
        self._autoplay_timer: Optional[QTimer] = None
        self._pattern_connected = False

    def _apply_figma_note_layout(
        self,
        layout: _NoteExplainerFigmaLayout,
        grid: _HardwareGrid,
        try_text: Optional[str],
    ) -> None:
        """Bordered body well + notation glyph, 3D direction photo, grid overlay."""
        bx, by, bw, bh = layout.body_well
        well = QFrame(self)
        well.setGeometry(bx, by, bw, bh)
        well.setStyleSheet(
            "QFrame { border: 1px solid #FFFFFF; background: transparent; }"
        )

        sym_w, sym_h = layout.body_symbol_size
        pad_x, pad_y, gap = 30, 20, 10
        text_w = max(1, bw - pad_x * 2 - gap - sym_w)
        self._body_label.setParent(well)
        self._body_label.setWordWrap(True)
        self._body_label.setGeometry(pad_x, pad_y, text_w, bh - pad_y * 2)
        self._body_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )

        sym = QLabel(well)
        sym.setFixedSize(sym_w, sym_h)
        sym.move(bw - pad_x - sym_w, max(0, (bh - sym_h) // 2))
        sym.setScaledContents(True)
        sym.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        sym_path = asset_path(layout.body_symbol_asset)
        if sym_path.exists():
            s_pix = QPixmap(str(sym_path))
            if not s_pix.isNull():
                sym.setPixmap(s_pix)

        px, py, pw, ph = layout.direction_photo_rect
        photo = QLabel(self)
        photo.setGeometry(px, py, pw, ph)
        photo.setScaledContents(True)
        photo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        ppath = asset_path(layout.direction_photo)
        if ppath.exists():
            d_pix = QPixmap(str(ppath))
            if not d_pix.isNull():
                photo.setPixmap(d_pix)

        cap_w, cap_h = 220, 120
        cap = QLabel("Note the Direction!".upper(), self)
        cap.setStyleSheet(
            f"color: #FFE560; font-family: '{THEME.font_display}'; "
            f"font-size: 40px; background: transparent;"
        )
        cap.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        cap.setWordWrap(True)
        cx = layout.caption_center_x
        cap.setGeometry(cx - cap_w // 2, layout.caption_top, cap_w, cap_h)
        cap.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        if layout.arrow_rect is not None:
            ax, ay, aw, ah = layout.arrow_rect
            _place_rotated_direction_arrow(self, ax, ay, aw, ah)

        if try_text:
            row = QWidget(self)
            row_h = 90
            row.setFixedSize(DESIGN_W, row_h)
            row.move(0, 364)
            msg = QLabel(try_text.upper(), row)
            msg.setStyleSheet(
                f"color: {THEME.accent_blue}; font-family: '{THEME.font_display}'; "
                f"font-size: 48px; background: transparent;"
            )
            msg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            msg.adjustSize()
            play = svg_widget("play_vector.svg", 86, 86, row)
            inner_w = msg.width() + 20 + 86
            x0 = (DESIGN_W - inner_w) // 2
            msg.move(x0, max(0, (row_h - msg.height()) // 2))
            play.move(x0 + msg.width() + 20, max(0, (row_h - 86) // 2))

        gx, gy, gw, gh = layout.grid_symbol_rect
        over = QLabel(self)
        over.setGeometry(gx, gy, gw, gh)
        over.setScaledContents(True)
        over.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        gpath = asset_path(layout.grid_symbol_asset)
        if gpath.exists():
            gpix = QPixmap(str(gpath))
            if not gpix.isNull():
                over.setPixmap(gpix)
        over.raise_()
        if self._continue is not None:
            self._continue.raise_()
        self.help_button.raise_()

    # ----- controller hookup ------------------------------------------------
    def attach_session(self, session) -> None:
        """Subscribe to live hardware frames from the shared ``GameSession``."""
        if self._session is session:
            return
        self._session = session
        if self.AUTOPLAY_BLOCKS is None or self._pattern_connected:
            return
        session.live_pattern_changed.connect(self._on_live_pattern)
        self._pattern_connected = True

    def showEvent(self, event) -> None:  # noqa: D401 - Qt override
        super().showEvent(event)
        # Arm auto-advance each time the page becomes visible so back/forward
        # navigation keeps the gesture responsive.
        self._autoplay_armed = self.AUTOPLAY_BLOCKS is not None
        # If blocks were already inserted before this page was shown, the pattern
        # may not change again — re-evaluate once from the current live state.
        if self._autoplay_armed and self._session is not None:
            # Defer so pad reads can stabilize after the page transition.
            QTimer.singleShot(120, self._autoplay_flush_if_ready)

    def hideEvent(self, event) -> None:  # noqa: D401 - Qt override
        super().hideEvent(event)
        self._autoplay_armed = False
        if self._autoplay_timer is not None:
            self._autoplay_timer.stop()

    def _autoplay_flush_if_ready(self) -> None:
        if not self._autoplay_armed or self.AUTOPLAY_BLOCKS is None or self._session is None:
            return
        self._on_live_pattern(list(self._session.live_state))

    # ----- pattern matching -------------------------------------------------
    @staticmethod
    def _filled_blocks(pattern: List[int]) -> List[int]:
        """Return grid-block indices (0..7) occupied by the current pad pattern.

        Note type pages should treat held notes the same way the audio engine does:
        quarter/half blocks often present as an even-index start and an odd-index
        end (with the interior slots left 0). Using only "both pads in the pair
        are 1" works for a single eighth block but breaks for held notes.
        """
        n = min(SLOTS, len(pattern))
        gate = [False] * SLOTS
        for i in range(n):
            if pattern[i]:
                gate[i] = True
        for s, e in note_intervals_from_pattern(list(pattern)):
            for k in range(max(0, s), min(SLOTS - 1, e) + 1):
                gate[k] = True
        out: List[int] = []
        for k in range(_NOTE_BLOCK_COUNT):
            a_idx, b_idx = 2 * k, 2 * k + 1
            if b_idx < len(gate) and (gate[a_idx] or gate[b_idx]):
                out.append(k)
        return out

    def _has_partial_block_in_window(self, pattern: List[int]) -> bool:
        """Legacy helper (kept for minimal diff); held notes look 'partial' at ends.

        Quarter/half blocks can legitimately show only a start (even index) and
        end (odd index) with zeros in-between. Treating that as a blocker would
        prevent autoplay on those screens, so we no longer use this predicate.
        """
        _ = pattern
        return False

    def _on_live_pattern(self, pattern: List[int]) -> None:
        if not self._autoplay_armed or self.AUTOPLAY_BLOCKS is None:
            return
        blocks = self._filled_blocks(pattern)
        if len(blocks) != self.AUTOPLAY_BLOCKS:
            return
        # Require the filled blocks to be contiguous so a single eighth-note
        # block (k) or quarter-note block (k, k+1) triggers but two distant
        # eighth-notes do not.
        if blocks != list(range(blocks[0], blocks[0] + len(blocks))):
            return
        if self.AUTOPLAY_FROM_BLOCK_ZERO and blocks[0] != 0:
            return
        self._autoplay_armed = False
        self._play_and_advance()

    # ----- playback + advance ----------------------------------------------
    def _play_and_advance(self) -> None:
        session = self._session
        if session is None:
            self.continue_clicked.emit()
            return
        played = False
        try:
            played = session.play_current()
        except Exception:
            played = False
        # Compute a tail delay that fits the whole 16-step phrase at the
        # session's current BPM (240 s / bpm) with a small grace tail.
        if played:
            bpm = 80.0
            try:
                bpm = max(20.0, float(session.bpm()))
            except Exception:
                pass
            delay_ms = int(240000 / bpm) + 400
        else:
            # No audio (controller idle or sink unavailable) — still advance,
            # but wait long enough that the user sees the gesture land.
            delay_ms = 600
        if self._autoplay_timer is None:
            self._autoplay_timer = QTimer(self)
            self._autoplay_timer.setSingleShot(True)
            self._autoplay_timer.timeout.connect(self.continue_clicked.emit)
        else:
            self._autoplay_timer.stop()
        self._autoplay_timer.start(delay_ms)


class NoviceEighthNotePage(_NoteTypeBase):

    AUTOPLAY_BLOCKS = 1

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(
            flow,
            title="What is an Eighth note?",
            body="We have four audible counts that are split into 1 and\n"
            "therefore 4×2 = 8 — each 'grid' = 8th note.",
            active_blocks=[0],
            try_text="Try putting the 8th note block in! And play it",
            figma_note_layout=_EIGHTH_NOTE_LAYOUT,
            parent=parent,
        )


class NoviceQuarterNotePage(_NoteTypeBase):

    AUTOPLAY_BLOCKS = 2
    AUTOPLAY_FROM_BLOCK_ZERO = True

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(
            flow,
            title="What is a Quarter Note?",
            body="This is the four audible counts! This is a quarter note and "
            "represents one whole count!",
            active_blocks=[0, 1],
            try_text="Try putting the quarter note block in! And play it",
            figma_note_layout=_QUARTER_NOTE_LAYOUT,
            parent=parent,
        )


class NoviceHalfNotePage(_NoteTypeBase):

    AUTOPLAY_BLOCKS = 4
    AUTOPLAY_FROM_BLOCK_ZERO = True

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(
            flow,
            title="What is a Half Note?",
            body="This is two counts, which is a half note and holds for two counts!",
            active_blocks=[0, 1, 2, 3],
            try_text="Try putting the half note block in! And play it",
            figma_note_layout=_HALF_NOTE_LAYOUT,
            parent=parent,
        )


class NoviceWholeNotePage(_NoteTypeBase):
    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(
            flow,
            title="What is a Whole Note?",
            body="There's no Whole Note for our grid, but it's a useful concept — "
            "one note held for four whole counts.",
            active_blocks=list(range(_NOTE_BLOCK_COUNT)),
            try_text=None,
            parent=parent,
        )


# ---------------------------------------------------------------------------
# Trial 1 (100:1841) + Trial 2 (100:2225)
# ---------------------------------------------------------------------------


_SANDBOX_PLAY_ORANGE = "#E48706"
_SANDBOX_PLAY_ORANGE_HOVER = "#F29823"
_SANDBOX_PLAY_ORANGE_PRESSED = "#C27405"


class _SandboxPlayButton(QPushButton):
    """Orange "Play Your Rhythm" pill matching the Time Challenge button."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Play Your Rhythm", parent)
        self.setObjectName("SandboxPlayRhythmBtn")
        self.setFixedSize(316, 54)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        f = QFont(THEME.font_display)
        f.setPixelSize(32)
        self.setFont(f)
        self.setStyleSheet(
            "QPushButton#SandboxPlayRhythmBtn {"
            f"  background: {_SANDBOX_PLAY_ORANGE};"
            "   color: white;"
            "   border: none;"
            "   border-radius: 27px;"
            "   padding: 0 18px;"
            "}"
            "QPushButton#SandboxPlayRhythmBtn:hover {"
            f"  background: {_SANDBOX_PLAY_ORANGE_HOVER};"
            "}"
            "QPushButton#SandboxPlayRhythmBtn:pressed {"
            f"  background: {_SANDBOX_PLAY_ORANGE_PRESSED};"
            "}"
            "QPushButton#SandboxPlayRhythmBtn:disabled {"
            "   color: rgba(255,255,255,140);"
            "}"
        )


def _cell_presence_from_pattern(pattern: List[int]) -> List[bool]:
    """Collapse a 16-slot pattern into the 8 visible beat cells.

    A cell lights if either of its two underlying slots is truthy *or* a
    decoded note interval (even-start / odd-end FIFO, matching the audio
    renderer) sustains across either slot. The sustain check makes held
    notes — e.g. a half note entered as a start at slot 0 and an end at
    slot 3 — light every beat they cover instead of just the endpoints.
    """
    n = min(SLOTS, len(pattern))
    gate = [False] * SLOTS
    for i in range(n):
        if pattern[i]:
            gate[i] = True
    for s, e in note_intervals_from_pattern(list(pattern)):
        for k in range(max(0, s), min(SLOTS - 1, e) + 1):
            gate[k] = True
    return [bool(gate[2 * i] or gate[2 * i + 1]) for i in range(8)]


class NoviceTrial1Page(NoviceTutorialBase):
    """Sandbox: insert blocks on the controller and watch the 8 beat circles
    light up in real time; press **Play Your Rhythm** to hear what you built.

    No scoring, no round tracking. Completion advances to Trial 2 via the
    Continue pill. If no controller is attached the circles stay idle and the
    play button still plays whatever's in the shared ``GameSession`` live
    state (so demos without hardware still work).
    """

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(
            flow,
            title="Try it yourself — we'll start easy",
            body="Insert blocks into the controller — this row shows which beats "
            "they cover. Press PLAY YOUR RHYTHM to hear your creation with a "
            "one-measure count-in.",
            continue_text="Continue",
            parent=parent,
        )

        host = QWidget(self)
        host.setFixedSize(1104, 131)
        host.move((DESIGN_W - 1104) // 2, 485)
        labels = ["1", "and", "2", "and", "3", "and", "4", "and"]
        self._cells: List[CountCircle] = []
        for i, l in enumerate(labels):
            c = CountCircle(l, 131, parent=host)
            c.move(i * (131 + 8), 0)
            self._cells.append(c)

        self._play_btn = _SandboxPlayButton(self)
        self._play_btn.move((DESIGN_W - 316) // 2, 676)
        self._play_btn.clicked.connect(self._on_play_rhythm)

        self._hint = QLabel(
            "No controller detected — insert the controller to sandbox.".upper(),
            self,
        )
        self._hint.setStyleSheet(
            f"color: rgba(255,255,255,160); font-family: '{THEME.font_display}'; "
            f"font-size: 22px; background: transparent;"
        )
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setFixedSize(900, 34)
        self._hint.move((DESIGN_W - 900) // 2, 744)

        self._session = None
        self._pattern_connected = False

    def attach_session(self, session) -> None:
        """Subscribe to the shared ``GameSession`` for live hardware frames."""
        if self._session is session:
            return
        self._session = session
        if not self._pattern_connected:
            session.live_pattern_changed.connect(self._on_live_pattern)
            self._pattern_connected = True
        # Seed with whatever the session already has so navigating back here
        # doesn't leave stale circles.
        try:
            self._apply_pattern(session.live_state)
        except Exception:
            self._clear_cells()
        self._refresh_hint()

    # ----- reactive visuals -------------------------------------------------
    def _on_live_pattern(self, pattern: List[int]) -> None:
        self._apply_pattern(list(pattern))
        self._refresh_hint()

    def _apply_pattern(self, pattern: List[int]) -> None:
        cells = _cell_presence_from_pattern(pattern)
        for c, on in zip(self._cells, cells):
            c.set_state(
                CountCircle.STATE_ON if on else CountCircle.STATE_IDLE
            )

    def _clear_cells(self) -> None:
        for c in self._cells:
            c.set_state(CountCircle.STATE_IDLE)

    def _refresh_hint(self) -> None:
        session = self._session
        if session is None:
            self._hint.setText(
                "Insert blocks and watch the circles light up.".upper()
            )
            return
        connected = False
        try:
            connected = bool(getattr(session, "is_connected", False))
        except Exception:
            connected = False
        if connected:
            self._hint.setText(
                "Each circle lights the beat its block covers.".upper()
            )
        else:
            self._hint.setText(
                "No controller detected — you can still press play to hear the "
                "current pattern.".upper()
            )

    # ----- playback ---------------------------------------------------------
    def _on_play_rhythm(self) -> None:
        session = self._session
        if session is None:
            return
        try:
            session.play_current(count_in_quarters=DEFAULT_COUNT_IN_QUARTERS)
        except Exception:
            pass

    def showEvent(self, event) -> None:  # noqa: D401 - Qt override
        super().showEvent(event)
        if self._session is not None:
            try:
                self._apply_pattern(self._session.live_state)
            except Exception:
                self._clear_cells()
            self._refresh_hint()
        else:
            self._clear_cells()

    def hideEvent(self, event) -> None:  # noqa: D401 - Qt override
        super().hideEvent(event)
        if self._session is not None:
            try:
                self._session.stop_playback()
            except Exception:
                pass


class _LegendDot(QWidget):
    """Solid filled disc used for the correct/incorrect legend swatches.

    Deliberately not a ``CountCircle`` — on this page we want the whole circle
    flooded with the feedback color instead of the beat-ring + inner-dot layout
    the gameplay circles use.
    """

    def __init__(self, color: str, diameter: int = 120, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(diameter, diameter)
        self._color = QColor(color)

    def paintEvent(self, _event) -> None:  # noqa: D401 - Qt override
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setBrush(self._color)
        p.setPen(QColor(0, 0, 0, 30))
        p.drawEllipse(1, 1, self.width() - 2, self.height() - 2)
        p.end()


class NoviceTrial2Page(NoviceTutorialBase):
    """Explains grid feedback: green = slot matches target, red = slot does not."""

    _LEGEND_CORRECT = "#A2CEAB"
    _LEGEND_INCORRECT = "#F9B5B5"

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(
            flow,
            title="Use the Lights",
            body="Green means that step is correct — a note where a note belongs, "
            "or a rest where a rest belongs. Red means that step is wrong.",
            continue_text="Start Playing",
            parent=parent,
        )
        self._body_label.setGeometry(244, 258, 1143, 140)

        legend = QWidget(self)
        legend.setFixedSize(1000, 160)
        legend.move((DESIGN_W - 1000) // 2, 560)
        legend.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        samples = [
            (self._LEGEND_CORRECT, "Correct"),
            (self._LEGEND_INCORRECT, "Incorrect"),
        ]
        slot_w = 1000 // len(samples)
        for i, (color, label) in enumerate(samples):
            dot = _LegendDot(color, 120, parent=legend)
            dot.move(i * slot_w + (slot_w - 120) // 2, 0)
            lbl = QLabel(label.upper(), legend)
            lbl.setStyleSheet(
                f"color: {THEME.white}; font-family: '{THEME.font_display}'; "
                f"font-size: 28px; background: transparent;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedSize(slot_w, 40)
            lbl.move(i * slot_w, 125)


# ---------------------------------------------------------------------------
# Ordered list of ``(route, class)`` — consumed by ``main_window.py``.
# ---------------------------------------------------------------------------

NOVICE_FLOW: List[tuple[str, type]] = [
    ("novice_intro", NoviceWelcomeIntroPage),
    ("novice_metronome", NoviceMetronomePage),
    ("novice_try_tempo", NoviceTryTheTempoPage),
    ("novice_counts", NoviceCountsPage),
    ("novice_measure", NoviceMeasurePage),
    ("novice_piano", NovicePianoSheetsPage),
    ("novice_hw1", NoviceHardware1Page),
    ("novice_hw2", NoviceHardware2Page),
    ("novice_hw3", NoviceHardware3Page),
    ("novice_hw4", NoviceHardware4Page),
    ("novice_eighth", NoviceEighthNotePage),
    ("novice_quarter", NoviceQuarterNotePage),
    ("novice_half", NoviceHalfNotePage),
    ("novice_whole", NoviceWholeNotePage),
    ("novice_trial1", NoviceTrial1Page),
    ("novice_trial2", NoviceTrial2Page),
]


__all__ = [
    "NOVICE_FLOW",
    "NoviceCountsPage",
    "NoviceEighthNotePage",
    "NoviceHalfNotePage",
    "NoviceHardware1Page",
    "NoviceHardware2Page",
    "NoviceHardware3Page",
    "NoviceHardware4Page",
    "NoviceMeasurePage",
    "NoviceMetronomePage",
    "NovicePianoSheetsPage",
    "NoviceQuarterNotePage",
    "NoviceTrial1Page",
    "NoviceTrial2Page",
    "NoviceTryTheTempoPage",
    "NoviceTutorialBase",
    "NoviceWelcomeIntroPage",
    "NoviceWholeNotePage",
]
