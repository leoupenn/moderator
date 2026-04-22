"""Pages for every Figma frame in the DoEG Beat It wireframes flow."""
from __future__ import annotations

from .character_choice_p1_page import CharacterChoiceP1Page
from .character_choice_p2_waiting_page import CharacterChoiceP2WaitingPage
from .competition_page import CompetitionPage
from .introduction_page import IntroductionPage
from .leaderboard_page import LeaderboardPage
from .levels_page import LevelsPage
from .expert_tutorial import EXPERT_FLOW
from .loading_page import LoadingPage
from .novice_tutorial import NOVICE_FLOW
from .recreate_rhythm_p1_page import RecreateRhythmP1Page
from .recreate_rhythm_p2_page import RecreateRhythmP2Page
from .results_page import ResultsPage
from .rounds_page import RoundsPage
from .sp_character_page import SinglePlayerCharacterPage
from .sp_experience_page import SinglePlayerExperiencePage
from .sp_genre_page import SinglePlayerGenrePage
from .time_challenge_page import TimeChallengePage
from .tutorial_page import TutorialPage
from .welcome_page import WelcomePage

__all__ = [
    "CharacterChoiceP1Page",
    "CharacterChoiceP2WaitingPage",
    "CompetitionPage",
    "IntroductionPage",
    "LeaderboardPage",
    "LevelsPage",
    "EXPERT_FLOW",
    "LoadingPage",
    "NOVICE_FLOW",
    "RecreateRhythmP1Page",
    "RecreateRhythmP2Page",
    "ResultsPage",
    "RoundsPage",
    "SinglePlayerCharacterPage",
    "SinglePlayerExperiencePage",
    "SinglePlayerGenrePage",
    "TimeChallengePage",
    "TutorialPage",
    "WelcomePage",
]
