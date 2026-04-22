"""Shared widgets distilled from the DoEG Beat It Figma Components section."""
from __future__ import annotations

from .asset_loader import asset_path, duck_pixmap, svg_widget
from .bpm_input import BpmInput
from .character_strip import CharacterStrip
from .choice_button import ChoiceButton, ChoiceStyle
from .duck_mascot import DuckMascot
from .flow_page import FlowPage
from .help_button import HelpButton
from .metronome import BEATS_PER_BAR, CountCircle, MetronomeEngine, make_count_row
from .page_header import PageHeader
from .rhythm_track import RhythmTrackGrid

__all__ = [
    "BEATS_PER_BAR",
    "BpmInput",
    "CharacterStrip",
    "ChoiceButton",
    "ChoiceStyle",
    "CountCircle",
    "DuckMascot",
    "FlowPage",
    "HelpButton",
    "MetronomeEngine",
    "PageHeader",
    "RhythmTrackGrid",
    "asset_path",
    "duck_pixmap",
    "svg_widget",
    "make_count_row",
]
