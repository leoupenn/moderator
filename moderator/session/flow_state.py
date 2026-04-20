"""Cross-screen state captured from the Figma flow (mode, character, genre, scores)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional


class GameMode(Enum):
    SINGLE = auto()
    MULTI = auto()


class MultiplayerMode(Enum):
    TIME_CHALLENGE = auto()
    RECREATE_RHYTHM = auto()


class Difficulty(Enum):
    NOVICE = auto()
    EXPERIENCED = auto()


# Character + genre are drawn from the Figma Component palette. Keeping them as
# enums keeps the navigator strongly typed, with display labels for the picker.
class Character(Enum):
    BABY_DUCK = ("Baby Duck", "duck_c1.svg")
    YOUNG_DUCK = ("Young Duck", "duck_c2.svg")
    NORMAL_DUCK = ("Normal Duck", "duck_c3.svg")
    COOL_DUCK = ("Cool Duck", "duck_c4.svg")
    SPY_DUCK = ("Spy Duck", "duck_c5.svg")

    @property
    def label(self) -> str:
        return self.value[0]

    @property
    def asset(self) -> str:
        return self.value[1]


class Genre(Enum):
    JAZZ = "Jazz"
    POP = "Pop"
    KPOP = "Kpop"
    JPOP = "Jpop"
    CLASSIC = "Classic"
    SIMPLE = "Simple"
    TECHNO = "Techno"
    BLUES = "Blues"
    SALSA = "Salsa"
    FUNK = "Funk"


class LevelTier(Enum):
    EASY = auto()
    NORMAL = auto()
    EXPERT = auto()


@dataclass
class RoundScore:
    player1: int = 0  # attempts it took for P1 (lower = better) or ms elapsed
    player2: int = 0
    winner: Optional[int] = None  # 1, 2, or None for tie


@dataclass
class FlowState:
    """Single-source-of-truth state that pages read/write as the user navigates."""

    mode: Optional[GameMode] = None
    multiplayer_mode: Optional[MultiplayerMode] = None
    difficulty: Optional[Difficulty] = None
    genre: Optional[Genre] = None
    character_p1: Character = Character.NORMAL_DUCK
    character_p2: Character = Character.NORMAL_DUCK
    rounds_total: int = 5
    current_round: int = 1
    level: LevelTier = LevelTier.NORMAL
    bpm: int = 80
    scores: List[RoundScore] = field(default_factory=list)

    def wins_p1(self) -> int:
        return sum(1 for s in self.scores if s.winner == 1)

    def wins_p2(self) -> int:
        return sum(1 for s in self.scores if s.winner == 2)

    def reset_match(self) -> None:
        self.current_round = 1
        self.scores = []

    def reset_all(self) -> None:
        self.mode = None
        self.multiplayer_mode = None
        self.difficulty = None
        self.genre = None
        self.character_p1 = Character.NORMAL_DUCK
        self.character_p2 = Character.NORMAL_DUCK
        self.rounds_total = 5
        self.level = LevelTier.NORMAL
        self.reset_match()
