"""Design tokens pulled from the DoEG Beat It Wireframes Figma file.

Source: https://www.figma.com/design/7Io2x2ZkA0CstNq5SWaKx0/DoEG-Beat-It-Wireframes
Tokens are taken verbatim from the Color Palette (6:35) and Typography (6:47)
artboards; see FIGMA_NODES for per-screen traceability.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

FIGMA_FILE_URL = (
    "https://www.figma.com/design/7Io2x2ZkA0CstNq5SWaKx0/DoEG-Beat-It-Wireframes"
)

FIGMA_NODES: dict[str, str] = {
    "color_palette": "6:35",
    "typography": "6:47",
    "loading": "21:2404",
    "introduction": "8:74",
    "welcome": "6:21",
    "tutorial": "8:58",
    "sp_experience": "17:242",
    "sp_character": "21:1928",
    "sp_genre": "21:2139",
    "competition": "17:272",
    "char_choice_p1": "21:606",
    "char_choice_p2_waiting": "29:808",
    "rounds": "21:1520",
    "rounds_sp": "45:847",
    "levels": "21:507",
    "levels_sp": "45:875",
    "time_challenge": "21:477",
    "time_challenge_sp": "45:789",
    "rr_p1": "21:901",
    "rr_p2": "21:944",
    "results": "21:1223",
    "leaderboard": "21:1456",
}

DESIGN_W = 1512
DESIGN_H = 982


@dataclass(frozen=True)
class Theme:
    # Palette (from node 6:35)
    bg: str = "#535554"
    black: str = "#010101"
    accent_blue: str = "#94C4D8"
    accent_yellow: str = "#DFC22C"
    white: str = "#FFFFFF"

    # Extended tokens used across the wireframes
    dark_panel: str = "#1E1E1E"
    slate: str = "#33363F"
    mid_gray: str = "#444444"
    card_white: str = "#FFFFFF"
    scrim: str = "rgba(0, 0, 0, 0.5)"
    ghost_chip: str = "rgba(217, 217, 217, 0.4)"
    ghost_pill: str = "rgba(0, 0, 0, 0.3)"
    help_chip: str = "#D9D9D9"
    line_icon: str = "#33363F"
    fill_icon: str = "#222222"

    # Feedback on the rhythm grid (Grid Wordle Feedback node 31:1126)
    rhythm_cell_idle: str = "#FFFFFF"
    rhythm_cell_off: str = "#B8BEC8"
    rhythm_cell_correct: str = "#A2CEAB"
    rhythm_cell_incorrect: str = "#F9B5B5"
    rhythm_grid_bg: str = "#1E1E1E"

    # Type
    font_display: str = "Jersey 10"
    font_numeric: str = "Jersey 20"
    font_body: str = "Instrument Sans"
    font_fallback_stack: str = "system-ui, -apple-system, 'Segoe UI', sans-serif"

    # Sizes (Figma px)
    size_display_hero: int = 128
    size_display_1: int = 96
    size_display_2: int = 64
    size_heading_1: int = 48
    size_heading_2: int = 40
    size_heading_3: int = 36
    size_body: int = 32
    size_body_sm: int = 20

    # Radii
    radius_card: int = 20
    radius_pill: int = 100
    radius_chip: int = 14

    # Spacing
    space: int = 8


THEME = Theme()


def theme_css_vars(t: Theme = THEME) -> dict[str, str]:
    return {
        "bg": t.bg,
        "black": t.black,
        "accent_blue": t.accent_blue,
        "accent_yellow": t.accent_yellow,
        "white": t.white,
        "dark_panel": t.dark_panel,
        "slate": t.slate,
        "mid_gray": t.mid_gray,
        "card_white": t.card_white,
        "ghost_chip": t.ghost_chip,
        "ghost_pill": t.ghost_pill,
        "help_chip": t.help_chip,
        "rhythm_cell_idle": t.rhythm_cell_idle,
        "rhythm_cell_off": t.rhythm_cell_off,
        "rhythm_cell_correct": t.rhythm_cell_correct,
        "rhythm_cell_incorrect": t.rhythm_cell_incorrect,
        "rhythm_grid_bg": t.rhythm_grid_bg,
        "font_display": t.font_display,
        "font_body": t.font_body,
        "font_fallback": t.font_fallback_stack,
    }


def load_app_stylesheet(t: Theme = THEME) -> str:
    path = Path(__file__).with_name("styles.qss")
    raw = path.read_text(encoding="utf-8")
    for k, v in theme_css_vars(t).items():
        raw = raw.replace("{{" + k + "}}", v)
    return raw
