"""Thin shell that wires FlowState + GameSession + AppNavigator to the UI."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QStackedWidget,
    QWidget,
)

from .session import FlowState, GameMode, GameSession, MultiplayerMode
from .ui import AppNavigator, DESIGN_H, DESIGN_W, FIGMA_FILE_URL, load_app_stylesheet
from .ui.pages import (
    CharacterChoiceP1Page,
    CharacterChoiceP2WaitingPage,
    CompetitionPage,
    IntroductionPage,
    LeaderboardPage,
    LevelsPage,
    LoadingPage,
    RecreateRhythmP1Page,
    RecreateRhythmP2Page,
    ResultsPage,
    RoundsPage,
    SinglePlayerCharacterPage,
    SinglePlayerExperiencePage,
    SinglePlayerGenrePage,
    TimeChallengePage,
    TutorialPage,
    WelcomePage,
)
from .ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    """Hosts the page stack, game session, and help-chip settings drawer."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Beat It! — Moderator")
        self.setStyleSheet(load_app_stylesheet())
        self.setMinimumSize(1280, 800)
        self.resize(DESIGN_W, DESIGN_H)

        self._flow = FlowState()
        self._session = GameSession(self)

        # Wrap the 1512×982 design canvas in a scroll area so smaller screens
        # still get the full fidelity Figma layout.
        self._stack = QStackedWidget()
        self._stack.setFixedSize(DESIGN_W, DESIGN_H)

        stage_host = QWidget()
        stage_host.setStyleSheet("background: #000;")
        stage_layout = QHBoxLayout(stage_host)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        stage_layout.addStretch(1)
        stage_layout.addWidget(self._stack)
        stage_layout.addStretch(1)

        scroller = QScrollArea()
        scroller.setWidget(stage_host)
        scroller.setWidgetResizable(True)
        scroller.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroller.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setCentralWidget(scroller)

        self._nav = AppNavigator(self._stack, self)

        self._register_routes()
        self._nav.go("loading")
        self._settings_dialog: Optional[SettingsDialog] = None

    # ----- route registration ---------------------------------------------
    def _register_routes(self) -> None:
        f, s = self._flow, self._session
        self._nav.register("loading", lambda: self._page_loading())
        self._nav.register("introduction", lambda: self._page_intro())
        self._nav.register("welcome", lambda: self._page_welcome())
        self._nav.register("tutorial", lambda: self._page_tutorial())
        self._nav.register("sp_experience", lambda: self._page_sp_experience())
        self._nav.register("sp_character", lambda: self._page_sp_character())
        self._nav.register("sp_genre", lambda: self._page_sp_genre())
        self._nav.register("competition", lambda: self._page_competition())
        self._nav.register("char_p1", lambda: self._page_char_p1())
        self._nav.register("char_p2", lambda: self._page_char_p2())
        self._nav.register("rounds", lambda: self._page_rounds())
        self._nav.register("levels", lambda: self._page_levels())
        self._nav.register("time_challenge", lambda: self._page_time_challenge())
        self._nav.register("rr_p1", lambda: self._page_rr_p1())
        self._nav.register("rr_p2", lambda: self._page_rr_p2())
        self._nav.register("results", lambda: self._page_results())
        self._nav.register("leaderboard", lambda: self._page_leaderboard())

    # ----- page factories (wire per-page signals here) ---------------------
    def _bind_help(self, page) -> None:
        btn = getattr(page, "help_button", None)
        if btn is None:
            return
        btn.settings_clicked.connect(self._open_settings)
        btn.question_clicked.connect(self._open_help)

    def _page_loading(self) -> LoadingPage:
        p = LoadingPage(self._flow)
        self._bind_help(p)
        p.finished.connect(lambda: self._nav.go("welcome"))
        return p

    def _page_intro(self) -> IntroductionPage:
        p = IntroductionPage(self._flow)
        self._bind_help(p)
        p.difficulty_selected.connect(self._on_introduction_answered)
        return p

    def _page_welcome(self) -> WelcomePage:
        p = WelcomePage(self._flow)
        self._bind_help(p)
        p.mode_selected.connect(self._on_mode_selected)
        return p

    def _page_tutorial(self) -> TutorialPage:
        p = TutorialPage(self._flow)
        self._bind_help(p)
        p.difficulty_selected.connect(lambda _d: self._nav.go("sp_character"))
        return p

    def _page_sp_experience(self) -> SinglePlayerExperiencePage:
        p = SinglePlayerExperiencePage(self._flow)
        self._bind_help(p)
        p.difficulty_selected.connect(lambda _d: self._nav.go("sp_character"))
        return p

    def _page_sp_character(self) -> SinglePlayerCharacterPage:
        p = SinglePlayerCharacterPage(self._flow)
        self._bind_help(p)
        p.confirmed.connect(lambda _c: self._nav.go("sp_genre"))
        return p

    def _page_sp_genre(self) -> SinglePlayerGenrePage:
        p = SinglePlayerGenrePage(self._flow)
        self._bind_help(p)
        p.confirmed.connect(lambda _g: self._nav.go("levels"))
        return p

    def _page_competition(self) -> CompetitionPage:
        p = CompetitionPage(self._flow)
        self._bind_help(p)
        p.mode_selected.connect(lambda _m: self._nav.go("char_p1"))
        return p

    def _page_char_p1(self) -> CharacterChoiceP1Page:
        p = CharacterChoiceP1Page(self._flow)
        self._bind_help(p)
        p.confirmed.connect(lambda: self._nav.go("char_p2"))
        return p

    def _page_char_p2(self) -> CharacterChoiceP2WaitingPage:
        p = CharacterChoiceP2WaitingPage(self._flow)
        self._bind_help(p)
        p.confirmed.connect(lambda: self._nav.go("rounds"))
        return p

    def _page_rounds(self) -> RoundsPage:
        p = RoundsPage(self._flow)
        self._bind_help(p)
        p.confirmed.connect(self._on_rounds_confirmed)
        return p

    def _page_levels(self) -> LevelsPage:
        p = LevelsPage(self._flow)
        self._bind_help(p)
        p.selected.connect(self._on_level_selected)
        return p

    def _page_time_challenge(self) -> TimeChallengePage:
        p = TimeChallengePage(self._flow, self._session)
        self._bind_help(p)
        p.round_complete.connect(lambda: self._nav.go("results"))
        return p

    def _page_rr_p1(self) -> RecreateRhythmP1Page:
        p = RecreateRhythmP1Page(self._flow, self._session)
        self._bind_help(p)
        p.submitted.connect(lambda: self._nav.go("rr_p2"))
        return p

    def _page_rr_p2(self) -> RecreateRhythmP2Page:
        p = RecreateRhythmP2Page(self._flow, self._session)
        self._bind_help(p)
        p.round_done.connect(self._on_rr_round_done)
        return p

    def _page_results(self) -> ResultsPage:
        p = ResultsPage(self._flow)
        self._bind_help(p)
        p.next_round.connect(self._on_next_round)
        p.finished.connect(lambda: self._nav.go("leaderboard"))
        return p

    def _page_leaderboard(self) -> LeaderboardPage:
        p = LeaderboardPage(self._flow)
        self._bind_help(p)
        p.back_home.connect(self._on_back_home)
        return p

    # ----- flow transitions ------------------------------------------------
    def _on_mode_selected(self, mode: GameMode) -> None:
        self._flow.reset_match()
        if mode == GameMode.SINGLE:
            self._nav.go("introduction")
        else:
            self._nav.go("competition")

    def _on_introduction_answered(self, diff) -> None:
        # Figma flow: 8:74 -> 8:58 (Tutorial) if Novice, otherwise skip straight
        # to Single Player Experience (17:242) -> Character pick.
        from .session import Difficulty
        if diff == Difficulty.NOVICE:
            self._nav.go("tutorial")
        else:
            self._nav.go("sp_experience")

    def _on_rounds_confirmed(self, _rounds: int) -> None:
        if self._flow.mode == GameMode.MULTI and self._flow.multiplayer_mode == MultiplayerMode.RECREATE_RHYTHM:
            self._nav.go("rr_p1")
        else:
            self._nav.go("levels")

    def _on_level_selected(self, _tier) -> None:
        if self._flow.mode == GameMode.MULTI and self._flow.multiplayer_mode == MultiplayerMode.RECREATE_RHYTHM:
            self._nav.go("rr_p1")
        else:
            self._nav.go("time_challenge")

    def _on_rr_round_done(self) -> None:
        self._nav.go("results")

    def _on_next_round(self) -> None:
        if self._flow.mode == GameMode.MULTI and self._flow.multiplayer_mode == MultiplayerMode.RECREATE_RHYTHM:
            self._nav.go("rr_p1")
        else:
            self._nav.go("time_challenge")

    def _on_back_home(self) -> None:
        self._flow.reset_all()
        self._nav.go("welcome")

    # ----- help chip handlers ---------------------------------------------
    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._flow, self._session, self)
        dlg.exec()

    def _open_help(self) -> None:
        QMessageBox.information(
            self,
            "Beat It! — Help",
            (
                "Single Player walks you through Tutorial → Character → Genre → "
                "Levels → Time Challenge.\n\n"
                "Multiplayer picks Time Challenge or Recreate Rhythm after "
                "character selection.\n\n"
                "Press D to submit for Player 1, K for Player 2. Spacebar plays the "
                "reference pattern.\n\n"
                f"Designs: {FIGMA_FILE_URL}"
            ),
        )

    # ----- shutdown --------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: D401
        self._session.shutdown()
        super().closeEvent(event)
