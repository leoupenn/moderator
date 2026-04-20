"""Shared widgets distilled from the DoEG Beat It Figma Components section."""
from __future__ import annotations

from .asset_loader import asset_path, duck_pixmap, svg_widget
from .bpm_input import BpmInput
from .character_strip import CharacterStrip
from .choice_button import ChoiceButton, ChoiceStyle
from .duck_mascot import DuckMascot
from .flow_page import FlowPage
from .help_button import HelpButton
from .page_header import PageHeader
from .rhythm_track import RhythmTrackGrid

__all__ = [
    "BpmInput",
    "CharacterStrip",
    "ChoiceButton",
    "ChoiceStyle",
    "DuckMascot",
    "FlowPage",
    "HelpButton",
    "PageHeader",
    "RhythmTrackGrid",
    "asset_path",
    "duck_pixmap",
    "svg_widget",
]
