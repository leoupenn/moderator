"""Cross-screen state captured from the Figma flow (mode, character, genre, scores)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class GameMode(Enum):
    SINGLE = auto()
    MULTI = auto()


class NetworkRole(Enum):
    SOLO = auto()
    HOST = auto()
    CLIENT = auto()


class MultiplayerMode(Enum):
    TIME_CHALLENGE = auto()
    RECREATE_RHYTHM = auto()


class Difficulty(Enum):
    NOVICE = auto()
    EXPERIENCED = auto()


# Character + genre are drawn from the Figma Component palette. Keeping them as
# enums keeps the navigator strongly typed, with display labels for the picker.
class Character(Enum):
    BASIC_DUCK = ("Basic Duck", "duck_basic.svg")
    KING_DUCK = ("King Duck", "duck_king.svg")
    TOP_HAT_DUCK = ("Top Hat Duck", "duck_top_hat.svg")
    VARIANT_4_DUCK = ("Variant 4 Duck", "duck_variant4.svg")

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


def level_tier_for_single_player_genre(genre: Genre) -> LevelTier:
    """Single-player Time Challenge: each genre maps to one difficulty tier.

    There is exactly one target pattern per tier in ``TimeChallengePage``;
    genre choice selects tempo / pattern family without a separate levels
    screen.
    """
    easy = {Genre.JAZZ, Genre.POP, Genre.KPOP}
    normal = {Genre.JPOP, Genre.CLASSIC, Genre.SIMPLE, Genre.TECHNO}
    expert = {Genre.BLUES, Genre.SALSA, Genre.FUNK}
    if genre in easy:
        return LevelTier.EASY
    if genre in normal:
        return LevelTier.NORMAL
    if genre in expert:
        return LevelTier.EXPERT
    return LevelTier.NORMAL


# ----- Recreate Rhythm role rotation ----------------------------------------
# Players swap composer / recreator duties every round so Player 2 gets to
# invent rhythms on even rounds and Player 1 plays the guesser. Round numbers
# are 1-indexed (``FlowState.current_round`` starts at 1).


def rr_composer_player(round_num: int) -> int:
    """Which player invents the rhythm on ``round_num`` (1-indexed)."""
    return 1 if int(round_num) % 2 == 1 else 2


def rr_recreator_player(round_num: int) -> int:
    """Which player recreates the rhythm on ``round_num`` (1-indexed)."""
    return 2 if int(round_num) % 2 == 1 else 1


@dataclass
class RoundScore:
    player1: int = 0  # ms elapsed (Time Challenge) or mode-specific metric
    player2: int = 0
    winner: Optional[int] = None  # 1, 2, or None for tie
    attempts_p1: int = 1
    attempts_p2: int = 1


@dataclass
class FlowState:
    """Single-source-of-truth state that pages read/write as the user navigates."""

    mode: Optional[GameMode] = None
    multiplayer_mode: Optional[MultiplayerMode] = None
    difficulty: Optional[Difficulty] = None
    genre: Optional[Genre] = None
    character_p1: Character = Character.BASIC_DUCK
    character_p2: Character = Character.BASIC_DUCK
    rounds_total: int = 5
    current_round: int = 1
    level: LevelTier = LevelTier.NORMAL
    bpm: int = 80
    scores: List[RoundScore] = field(default_factory=list)

    # ----- networking (two-machine MP) ------------------------------------
    # Role of *this* instance. Host owns the authoritative session; client
    # mirrors what host broadcasts and sends only input/submit messages.
    network_role: NetworkRole = NetworkRole.SOLO
    host_ip: str = ""
    host_port: int = 8769
    # Which player this machine controls locally (1 on host, 2 on client).
    local_player: int = 1
    # Purely informational status string for the settings panel / UI.
    network_status: str = ""

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
        self.character_p1 = Character.BASIC_DUCK
        self.character_p2 = Character.BASIC_DUCK
        self.rounds_total = 5
        self.level = LevelTier.NORMAL
        self.reset_match()

    # ---------- serialization for the network state broadcast -------------
    # Only gameplay fields — the network_* fields are instance-local and not
    # sent over the wire (client keeps its own role, host_ip, etc.).
    def to_snapshot(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.name if self.mode else None,
            "multiplayer_mode": (
                self.multiplayer_mode.name if self.multiplayer_mode else None
            ),
            "difficulty": self.difficulty.name if self.difficulty else None,
            "genre": self.genre.name if self.genre else None,
            "character_p1": self.character_p1.name,
            "character_p2": self.character_p2.name,
            "rounds_total": self.rounds_total,
            "current_round": self.current_round,
            "level": self.level.name,
            "bpm": self.bpm,
            "scores": [
                {
                    "p1": s.player1,
                    "p2": s.player2,
                    "winner": s.winner,
                    "attempts_p1": s.attempts_p1,
                    "attempts_p2": s.attempts_p2,
                }
                for s in self.scores
            ],
        }

    def apply_snapshot(self, snap: Dict[str, Any]) -> None:
        """Mutate this FlowState to match a snapshot from the host."""
        def _enum_from_name(enum_cls, name):
            if not name:
                return None
            try:
                return enum_cls[name]
            except KeyError:
                return None

        self.mode = _enum_from_name(GameMode, snap.get("mode"))
        self.multiplayer_mode = _enum_from_name(
            MultiplayerMode, snap.get("multiplayer_mode")
        )
        self.difficulty = _enum_from_name(Difficulty, snap.get("difficulty"))
        self.genre = _enum_from_name(Genre, snap.get("genre"))
        c1 = _enum_from_name(Character, snap.get("character_p1"))
        if c1 is not None:
            self.character_p1 = c1
        c2 = _enum_from_name(Character, snap.get("character_p2"))
        if c2 is not None:
            self.character_p2 = c2
        self.rounds_total = int(snap.get("rounds_total", self.rounds_total))
        self.current_round = int(snap.get("current_round", self.current_round))
        lvl = _enum_from_name(LevelTier, snap.get("level"))
        if lvl is not None:
            self.level = lvl
        self.bpm = int(snap.get("bpm", self.bpm))
        self.scores = []
        for s in snap.get("scores", []) or []:
            self.scores.append(
                RoundScore(
                    player1=int(s.get("p1", 0)),
                    player2=int(s.get("p2", 0)),
                    winner=s.get("winner"),
                    attempts_p1=int(s.get("attempts_p1", 1)),
                    attempts_p2=int(s.get("attempts_p2", 1)),
                )
            )
