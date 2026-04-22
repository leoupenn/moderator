"""Expert tutorial pages — Figma section "Tutorial for Expert and Novices".

Eleven screens that walk an *experienced* player through the hardware-specific
parts of the game only (no metronome/measure/piano intro; they already know
notation):

  1. Expert Introduction (cover) — ``87:1822``
  2. Expert Introduction_Hardware — ``102:2164`` (reuses ``NoviceHardware1Page``)
  3. Expert Introduction_Hardware2 — ``102:2181`` (reuses ``NoviceHardware2Page``)
  4. Expert Introduction_Hardware3 — ``102:2208`` (reuses ``NoviceHardware3Page``)
  5. Expert Introduction_hardware4 — ``102:2237`` (reuses ``NoviceHardware4Page``)
  6. Expert Introduction_eigth note — ``102:2266`` (reuses ``NoviceEighthNotePage``)
  7. Expert Introduction_quarterNote — ``102:2290`` (reuses ``NoviceQuarterNotePage``)
  8. Expert Introduction_halfNote — ``102:2314`` (reuses ``NoviceHalfNotePage``)
  9. Expert Introduction_wholeNote — ``102:2338`` (reuses ``NoviceWholeNotePage``)
 10. Try it yourself_Trial1 — ``102:2110`` (expert-specific layout)
 11. Try it yourself_tryAgain — ``102:2131`` (lights overlay)

The four *hardware* frames and the four *note-type* frames are pixel-identical
to their novice counterparts (same Figma layers/positions, only the parent
section name differs); reusing those classes keeps behaviour and audio in lock
step between the two paths.
"""
from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QWidget

from ...session import FlowState
from ..theme import DESIGN_W, THEME
from ..widgets import CountCircle, DuckMascot, FlowPage, svg_widget
from .novice_tutorial import (
    NoviceEighthNotePage,
    NoviceHalfNotePage,
    NoviceHardware1Page,
    NoviceHardware2Page,
    NoviceHardware3Page,
    NoviceHardware4Page,
    NoviceQuarterNotePage,
    NoviceTutorialBase,
    NoviceTrial2Page,
    NoviceWholeNotePage,
    _ContinuePill,
    _LegendDot,
)

# ---------------------------------------------------------------------------
# Frame 1 — Expert Introduction (87:1822)
# ---------------------------------------------------------------------------


class ExpertIntroCoverPage(FlowPage):
    """Cover screen for the expert path — mirrors 87:1822.

    Design: big hero title, a centered white rounded band containing a short
    subtitle, a 130×130 duck to the left of the band, and the Ready pill + a
    small "Skip tutorial" link underneath.
    """

    ready_clicked = Signal()
    skip_clicked = Signal()

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(flow, parent)

        title = QLabel("How to use our Grid".upper(), self)
        title.setObjectName("HeroTitle")
        tf = QFont(THEME.font_display)
        tf.setPixelSize(96)
        title.setFont(tf)
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title.adjustSize()
        title.move((DESIGN_W - title.width()) // 2, 320)

        band = QFrame(self)
        band.setObjectName("CardWhite")
        band.setFixedSize(807, 79)
        band.move(386, 531)

        subtitle = QLabel(
            "Let's learn how to use the blocks".upper(), band
        )
        subtitle.setStyleSheet(
            f"color: {THEME.slate}; font-family: '{THEME.font_display}'; "
            f"font-size: 36px; background: transparent;"
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setGeometry(0, 0, 807, 79)

        duck = DuckMascot("duck_med.svg", 130, 130, self)
        duck.move(235, 505)

        ready = _ContinuePill("Ready?", self)
        ready.setFixedSize(334, 91)
        ready.move((DESIGN_W - 334) // 2, 720)
        ready.clicked.connect(self.ready_clicked.emit)

        skip = QPushButton("Skip tutorial", self)
        skip.setFlat(True)
        skip.setCursor(Qt.CursorShape.PointingHandCursor)
        skip.setStyleSheet(
            f"color: rgba(255,255,255,200); font-family: '{THEME.font_display}'; "
            f"font-size: 28px; background: transparent; border: none; "
            f"text-decoration: underline;"
        )
        skip.clicked.connect(self.skip_clicked.emit)
        skip.adjustSize()
        skip.move((DESIGN_W - skip.width()) // 2, 720 + 91 + 14)


# ---------------------------------------------------------------------------
# Shared "Play the Rhythm" body used by Trial1 and TryAgain.
# ---------------------------------------------------------------------------


def _build_trial_body(page: FlowPage) -> None:
    """Render the shared pieces of Trial1 / TryAgain in-place on ``page``."""
    # Header block — two stacked labels at the top-left of the canvas.
    title = QLabel("Try it yourself! We will start easy".upper(), page)
    title.setStyleSheet(
        f"color: {THEME.white}; font-family: '{THEME.font_display}'; "
        f"font-size: 52px; background: transparent;"
    )
    title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    title.adjustSize()
    title.move(35, 26)

    kicker = QLabel("Trial 1".upper(), page)
    kicker.setStyleSheet(
        f"color: {THEME.white}; font-family: '{THEME.font_display}'; "
        f"font-size: 32px; background: transparent;"
    )
    kicker.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    kicker.adjustSize()
    kicker.move(35, 95)

    # Rhythm strip with "Play the Rhythm..." prompt + a circular Play icon.
    strip = QFrame(page)
    strip.setObjectName("RhythmStrip")
    strip.setFixedSize(1086, 130)
    strip.move(213, 172)
    strip_lbl = QLabel("Play the Rhythm...", strip)
    strip_lbl.setObjectName("StripLabel")
    strip_lbl.setStyleSheet(
        f"color: {THEME.bg}; font-family: '{THEME.font_display}'; "
        f"font-size: 36px; background: transparent;"
    )
    strip_lbl.move(47, 45)
    strip_lbl.adjustSize()

    play = svg_widget("play_vector.svg", 80, 80, page)
    play.move(213 + 1086 - 135, 197)

    # 8 count circles centered horizontally.
    host = QWidget(page)
    host.setFixedSize(1104, 131)
    host.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    host.move(204, 429)
    labels = ["1", "and", "2", "and", "3", "and", "4", "and"]
    for i, l in enumerate(labels):
        c = CountCircle(l, 131, parent=host)
        c.move(i * (131 + 10), 0)

    # Footer: duck + big "Play Your Rhythm" pill + submit hint.
    footer_duck = DuckMascot("duck_med.svg", 124, 132, page)
    footer_duck.move(166, 663)

    play_pill = QFrame(page)
    play_pill.setObjectName("CardBlue")
    play_pill.setFixedSize(414, 91)
    play_pill.move(225 + 336, 731)  # Frame "Frame 36" offset inside "Frame"
    play_lbl = QLabel("Play Your Rhythm", play_pill)
    play_lbl.setStyleSheet(
        f"color: {THEME.white}; font-family: '{THEME.font_display}'; "
        f"font-size: 40px; background: transparent;"
    )
    play_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    play_lbl.setGeometry(0, 0, 414, 91)

    hint = QLabel("Press D to Submit Your Rhythm", page)
    hint.setStyleSheet(
        f"color: {THEME.white}; font-family: '{THEME.font_display}'; "
        f"font-size: 32px; background: transparent;"
    )
    hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    hint.adjustSize()
    hint.move((DESIGN_W - hint.width()) // 2, 842)


# ---------------------------------------------------------------------------
# Trial 1 (102:2110)
# ---------------------------------------------------------------------------


class ExpertTrial1Page(FlowPage):
    """Play-the-rhythm dry run for experts.

    No scoring — a Continue pill at the bottom right takes the player on to
    the Try-Again explainer. ``continue_clicked`` is emitted for navigation.
    """

    continue_clicked = Signal()

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(flow, parent)
        _build_trial_body(self)

        cta = _ContinuePill("Continue", self)
        cta.move(DESIGN_W - 334 - 72, 870)
        cta.clicked.connect(self.continue_clicked.emit)
        cta.raise_()


# ---------------------------------------------------------------------------
# Try Again (102:2131) — Trial 1 body + full-screen scrim teaching Correct /
# Incorrect, followed by a "Back" CTA that returns to Trial 1.
# ---------------------------------------------------------------------------


class ExpertTryAgainPage(FlowPage):

    continue_clicked = Signal()
    back_clicked = Signal()

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(flow, parent)
        _build_trial_body(self)

        # Full-screen overlay with the Correct / Incorrect legend. The shared
        # ``#Scrim`` QSS rule paints a translucent black over the page, which
        # made this explanation hard to read against the busy trial body —
        # swap in a solid theme-background fill just for this one overlay.
        scrim = QFrame(self)
        scrim.setObjectName("ExpertLightsScrim")
        scrim.setGeometry(0, 0, self.width(), self.height())
        scrim.setAutoFillBackground(True)
        scrim.setStyleSheet(
            f"QFrame#ExpertLightsScrim {{ background: {THEME.bg}; }}"
        )

        heading = QLabel(
            "Use the Lights on the Grid for what's wrong or right".upper(), scrim
        )
        heading.setStyleSheet(
            f"color: {THEME.white}; font-family: '{THEME.font_display}'; "
            f"font-size: 48px; background: transparent;"
        )
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setWordWrap(True)
        heading.setFixedSize(1096, 206)
        heading.move((DESIGN_W - 1096) // 2, 260)

        legend = QWidget(scrim)
        legend.setFixedSize(1000, 200)
        legend.move((DESIGN_W - 1000) // 2, 500)
        legend.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        samples = [
            (NoviceTrial2Page._LEGEND_CORRECT, "Correct"),
            (NoviceTrial2Page._LEGEND_INCORRECT, "Incorrect"),
        ]
        slot_w = 1000 // len(samples)
        for i, (color, label) in enumerate(samples):
            dot = _LegendDot(color, 130, parent=legend)
            dot.move(i * slot_w + (slot_w - 130) // 2, 0)
            lbl = QLabel(label.upper(), legend)
            lbl.setStyleSheet(
                f"color: {THEME.white}; font-family: '{THEME.font_display}'; "
                f"font-size: 36px; background: transparent;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedSize(slot_w, 50)
            lbl.move(i * slot_w, 140)

        back = _ContinuePill("Back", scrim)
        back.move(626, 770)
        back.clicked.connect(self.back_clicked.emit)

        cta = _ContinuePill("Start Playing", scrim)
        cta.move(626, 870)
        cta.clicked.connect(self.continue_clicked.emit)


# ---------------------------------------------------------------------------
# Route registration helper for MainWindow.
# ---------------------------------------------------------------------------

EXPERT_FLOW: List[tuple[str, type]] = [
    ("expert_intro", ExpertIntroCoverPage),
    ("expert_hw1", NoviceHardware1Page),
    ("expert_hw2", NoviceHardware2Page),
    ("expert_hw3", NoviceHardware3Page),
    ("expert_hw4", NoviceHardware4Page),
    ("expert_eighth", NoviceEighthNotePage),
    ("expert_quarter", NoviceQuarterNotePage),
    ("expert_half", NoviceHalfNotePage),
    ("expert_whole", NoviceWholeNotePage),
    ("expert_trial1", ExpertTrial1Page),
    ("expert_try_again", ExpertTryAgainPage),
]


__all__ = [
    "EXPERT_FLOW",
    "ExpertIntroCoverPage",
    "ExpertTrial1Page",
    "ExpertTryAgainPage",
]
