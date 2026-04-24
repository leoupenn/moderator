"""Thin shell that wires FlowState + GameSession + AppNavigator to the UI."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .net import (
    MSG_ABORT_TO_HOME,
    MSG_ATTEMPTS_UPDATE,
    MSG_CHARACTER_SELECT,
    MSG_HELLO,
    MSG_INPUT_PATTERN,
    MSG_NAV,
    MSG_PLAY_REFERENCE,
    MSG_READY,
    MSG_REQUEST_NAV,
    MSG_ROUND_RESULT,
    MSG_RR_ATTEMPT,
    MSG_RR_RESULT,
    MSG_RR_TARGET,
    MSG_SELECT_LEVEL,
    MSG_START_ROUND,
    MSG_STATE,
    MSG_SUBMIT,
    MSG_TIME_CHALLENGE_CONTROL,
    MSG_WELCOME,
    NetworkManager,
    PROTOCOL_VERSION,
)
from .session import FlowState, GameMode, GameSession, Genre, MultiplayerMode, NetworkRole
from .session.flow_state import Character, LevelTier, level_tier_for_single_player_genre
from .ui import AppNavigator, DESIGN_H, DESIGN_W, FIGMA_FILE_URL, load_app_stylesheet
from .ui.theme import THEME
from .ui.pages import (
    EXPERT_FLOW,
    NOVICE_FLOW,
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
from .ui.pages.expert_tutorial import (
    ExpertIntroCoverPage,
    ExpertTryAgainPage,
)
from .ui.pages.novice_tutorial import NoviceWelcomeIntroPage
from .ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    """Hosts the page stack, game session, and help-chip settings drawer."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Beat It! — Moderator")
        # Apply the QSS globally via QApplication so styles cascade into every
        # child widget regardless of local stylesheets on page containers.
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(load_app_stylesheet())
        # Allow the window to shrink on smaller displays, but by default we
        # expand to fill the primary screen (see ``showEvent``).
        self.setMinimumSize(1024, 700)
        self.resize(DESIGN_W, DESIGN_H)
        self._has_filled_screen = False

        self._flow = FlowState()
        self._session = GameSession(self)
        self._net = NetworkManager(self._flow, self)
        # Guard flag to avoid bouncing route_changed → MSG_NAV → route_changed
        # when the client mirrors a host-driven navigation.
        self._applying_remote_nav = False

        # Wrap the 1512×982 design canvas in a scroll area so smaller screens
        # still get the full fidelity Figma layout.
        self._stack = QStackedWidget()
        self._stack.setFixedSize(DESIGN_W, DESIGN_H)

        stage_host = QWidget()
        stage_host.setObjectName("StageHost")
        stage_host.setStyleSheet(f"#StageHost {{ background: {THEME.bg}; }}")
        # Center the 1512×982 canvas both horizontally and vertically so empty
        # space around it (on larger displays) is symmetric, not left-hanging.
        v_stage = QVBoxLayout(stage_host)
        v_stage.setContentsMargins(0, 0, 0, 0)
        v_stage.addStretch(1)
        h_row = QHBoxLayout()
        h_row.setContentsMargins(0, 0, 0, 0)
        h_row.addStretch(1)
        h_row.addWidget(self._stack)
        h_row.addStretch(1)
        v_stage.addLayout(h_row)
        v_stage.addStretch(1)

        scroller = QScrollArea()
        scroller.setWidget(stage_host)
        scroller.setWidgetResizable(True)
        scroller.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroller.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setCentralWidget(scroller)

        self._nav = AppNavigator(self._stack, self)
        self._nav.route_changed.connect(self._on_route_changed)

        # Networking signal wiring — the manager itself is created above; we
        # only subscribe to the messages/status here.
        self._net.message_received.connect(self._on_net_message)
        self._net.host_client_connected.connect(self._on_peer_joined)

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
        self._register_tutorial_chain(NOVICE_FLOW)
        self._register_tutorial_chain(EXPERT_FLOW)

    def _register_tutorial_chain(self, flow_pages: list[tuple[str, type]]) -> None:
        """Register a novice/expert chain, wiring each page's CTA to the next.

        * Cover pages (``NoviceWelcomeIntroPage`` / ``ExpertIntroCoverPage``)
          emit ``ready_clicked`` + ``skip_clicked`` — we connect both.
        * ``ExpertTryAgainPage`` has an extra ``back_clicked`` signal that
          returns to the previous page (``Trial 1``).
        * Everything else uses ``continue_clicked``.
        """
        for idx, (route, cls) in enumerate(flow_pages):
            next_route = (
                flow_pages[idx + 1][0]
                if idx + 1 < len(flow_pages)
                else "sp_character"
            )
            prev_route = flow_pages[idx - 1][0] if idx > 0 else None

            def factory(
                cls=cls, route=route, next_route=next_route, prev_route=prev_route
            ):
                page = cls(self._flow)
                self._bind_help(page)
                # Note-type pages (8th / Quarter) auto-play + advance when the
                # matching physical block is slotted into the controller. They
                # opt in via ``attach_session``; other pages simply ignore it.
                if hasattr(page, "attach_session"):
                    page.attach_session(self._session)
                if isinstance(page, (NoviceWelcomeIntroPage, ExpertIntroCoverPage)):
                    page.ready_clicked.connect(
                        lambda nr=next_route: self._nav.go(nr)
                    )
                    page.skip_clicked.connect(lambda: self._nav.go("sp_character"))
                else:
                    page.continue_clicked.connect(
                        lambda nr=next_route: self._nav.go(nr)
                    )
                    if isinstance(page, ExpertTryAgainPage) and prev_route:
                        page.back_clicked.connect(
                            lambda pr=prev_route: self._nav.go(pr)
                        )
                return page

            self._nav.register(route, factory)

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
        # Kept registered for completeness (Figma 8:74), but not part of the
        # active flow — Welcome → Tutorial covers the same question.
        p = IntroductionPage(self._flow)
        self._bind_help(p)
        p.difficulty_selected.connect(lambda _d: self._nav.go("sp_character"))
        return p

    def _page_welcome(self) -> WelcomePage:
        p = WelcomePage(self._flow)
        self._bind_help(p)
        p.mode_selected.connect(self._on_mode_selected)
        return p

    def _page_tutorial(self) -> TutorialPage:
        p = TutorialPage(self._flow)
        self._bind_help(p)
        p.difficulty_selected.connect(self._on_tutorial_difficulty)
        return p

    def _on_tutorial_difficulty(self, difficulty) -> None:
        """Route the chosen skill level into its full tutorial walkthrough."""
        from .session.flow_state import Difficulty

        if difficulty == Difficulty.NOVICE:
            self._nav.go(NOVICE_FLOW[0][0])
        else:
            self._nav.go(EXPERT_FLOW[0][0])

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
        p.confirmed.connect(self._on_sp_genre_time_challenge)
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
    def _on_sp_genre_time_challenge(self, genre: Genre) -> None:
        """Single-player: genre picks Easy/Normal/Expert; one round then results."""
        tier = level_tier_for_single_player_genre(genre)
        self._flow.level = tier
        self._flow.bpm = {
            LevelTier.EASY: 60,
            LevelTier.NORMAL: 80,
            LevelTier.EXPERT: 110,
        }[tier]
        self._flow.rounds_total = 1
        self._flow.current_round = 1
        self._flow.scores = []
        self._nav.go("time_challenge")

    def _on_mode_selected(self, mode: GameMode) -> None:
        self._flow.reset_match()
        if mode == GameMode.SINGLE:
            # Skip the undecorated Introduction (8:74) — it's redundant with
            # Tutorial (8:58) which asks the same Novice / Experienced question
            # with the full mascot layout.
            self._nav.go("tutorial")
        else:
            self._nav.go("competition")

    def _on_rounds_confirmed(self, _rounds: int) -> None:
        if self._flow.mode == GameMode.MULTI and self._flow.multiplayer_mode == MultiplayerMode.RECREATE_RHYTHM:
            self._nav.go("rr_p1")
        else:
            self._nav.go("levels")

    def _on_level_selected(self, tier: LevelTier) -> None:
        self._apply_level_tier(tier)

    def _apply_level_tier(self, tier: LevelTier) -> None:
        """Set level + BPM from a Levels pick (host UI or client ``select_level``)."""
        self._flow.level = tier
        self._flow.bpm = {
            LevelTier.EASY: 60,
            LevelTier.NORMAL: 80,
            LevelTier.EXPERT: 110,
        }[tier]
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
        self._clear_feedback_leds()
        self._flow.reset_all()
        self._nav.go("welcome")

    def _clear_feedback_leds(self) -> None:
        """Clear controller feedback LEDs when leaving gameplay for home."""
        try:
            self._session.clear_feedback_leds()
        except Exception:
            pass

    # ----- networking: nav / state sync -----------------------------------
    def _on_route_changed(self, name: str) -> None:
        if name == "welcome":
            self._clear_feedback_leds()
        # Host broadcasts every navigation so the client mirrors exactly.
        # The client itself never sends nav messages — it only follows.
        if self._applying_remote_nav:
            return
        if self._flow.network_role == NetworkRole.HOST:
            self._net.send(MSG_STATE, route=name, flow=self._flow.to_snapshot())
            self._net.send(MSG_NAV, route=name)

    def _on_peer_joined(self, _addr: str) -> None:
        # Fresh client: push the current route + full flow snapshot so its UI
        # catches up to wherever we are.
        self._net.send(MSG_WELCOME, player_id=2, version=PROTOCOL_VERSION)
        cur = self._nav.current() or "welcome"
        self._net.send(MSG_STATE, route=cur, flow=self._flow.to_snapshot())
        self._net.send(MSG_NAV, route=cur)

    def _on_net_message(self, msg: dict) -> None:
        kind = msg.get("type")
        if kind == MSG_HELLO and self._flow.network_role == NetworkRole.HOST:
            # Handshake reply already sent in _on_peer_joined; nothing to do.
            return
        if kind == MSG_WELCOME and self._flow.network_role == NetworkRole.CLIENT:
            pid = int(msg.get("player_id", 2))
            self._flow.local_player = pid
            return
        if kind == MSG_STATE and self._flow.network_role == NetworkRole.CLIENT:
            snap = msg.get("flow") or {}
            self._flow.apply_snapshot(snap)
            route = msg.get("route")
            if isinstance(route, str):
                self._apply_remote_nav(route)
            return
        if kind == MSG_NAV and self._flow.network_role == NetworkRole.CLIENT:
            route = msg.get("route")
            if isinstance(route, str):
                self._apply_remote_nav(route)
            return
        if kind == MSG_ABORT_TO_HOME:
            self._clear_feedback_leds()
            self._flow.reset_all()
            self._apply_remote_nav("welcome")
            return
        if kind == MSG_CHARACTER_SELECT:
            self._apply_character_select(msg)
            return
        if kind == MSG_READY and self._flow.network_role == NetworkRole.HOST:
            from_player = int(msg.get("from_player", 0))
            screen = msg.get("screen")
            # Today the only READY the host listens for is Player 2 confirming
            # their duck on the ``char_p2`` screen. Advancing here also pushes
            # a MSG_NAV to the client via ``_on_route_changed``.
            if from_player == 2 and screen == "char_p2":
                self._nav.go("rounds")
            return
        if kind == MSG_SELECT_LEVEL and self._flow.network_role == NetworkRole.HOST:
            if self._nav.current() != "levels":
                return
            name = msg.get("level")
            if not isinstance(name, str):
                return
            try:
                tier = LevelTier[name]
            except KeyError:
                return
            self._apply_level_tier(tier)
            return
        if kind == MSG_REQUEST_NAV and self._flow.network_role == NetworkRole.HOST:
            self._handle_client_request_nav(msg)
            return
        if kind == MSG_TIME_CHALLENGE_CONTROL and self._flow.network_role == NetworkRole.HOST:
            if self._nav.current() != "time_challenge":
                return
            tc = self._nav.get("time_challenge")
            if tc is None:
                return
            action = msg.get("action")
            if action == "force_next_round" and hasattr(tc, "host_apply_force_finish"):
                tc.host_apply_force_finish()
            elif action == "play_reference" and hasattr(tc, "host_apply_play_reference"):
                tc.host_apply_play_reference()
            return
        # Time Challenge game messages — delegated to the page if present.
        if kind in (
            MSG_START_ROUND,
            MSG_INPUT_PATTERN,
            MSG_SUBMIT,
            MSG_ROUND_RESULT,
            MSG_PLAY_REFERENCE,
            MSG_ATTEMPTS_UPDATE,
        ):
            tc = self._nav.get("time_challenge")
            if tc is not None and hasattr(tc, "handle_network_message"):
                tc.handle_network_message(msg)
            return

        # Recreate Rhythm handshake. Players swap composer / recreator duties
        # every round so this message can travel in either direction:
        #   * host receives (client composed, even round) → seed the host's
        #     session and drive nav so both machines advance together;
        #   * client receives (host composed, odd round) → forward to the
        #     rr_p2 page which seeds its grading target.
        if kind == MSG_RR_TARGET:
            pattern = list(msg.get("pattern") or [])
            bpm = msg.get("bpm")
            bpm_val = int(bpm) if isinstance(bpm, int) and bpm > 0 else None
            if self._flow.network_role == NetworkRole.HOST:
                if (
                    self._flow.mode == GameMode.MULTI
                    and self._flow.multiplayer_mode
                    == MultiplayerMode.RECREATE_RHYTHM
                ):
                    self._session.set_manual_pattern(pattern)
                    if bpm_val is not None:
                        self._flow.bpm = bpm_val
                        self._session.set_bpm(float(bpm_val))
                    self._nav.go("rr_p2")
                return
            if self._flow.network_role == NetworkRole.CLIENT:
                rr2 = self._nav.get("rr_p2")
                if rr2 is not None and hasattr(rr2, "set_target"):
                    rr2.set_target(pattern, bpm_val)
            return

        # Recreate Rhythm live mirror — the recreator's machine sends this so
        # the spectator card stays in lock-step. Forward to rr_p2; the page
        # checks its round-role before applying.
        if kind == MSG_RR_ATTEMPT:
            rr2 = self._nav.get("rr_p2")
            if rr2 is not None and hasattr(rr2, "apply_remote_attempt"):
                rr2.apply_remote_attempt(msg)
            return

        # Recreate Rhythm round result — host-as-spectator records the score
        # and triggers nav; client-as-spectator just refreshes its visuals
        # (the host is authoritative for both).
        if kind == MSG_RR_RESULT:
            rr2 = self._nav.get("rr_p2")
            if rr2 is not None and hasattr(rr2, "apply_remote_result"):
                rr2.apply_remote_result(msg)
            return

    def _apply_character_select(self, msg: dict) -> None:
        """Mirror a peer's live character hover into ``flow`` and refresh UI.

        Bidirectional:
        - ``host -> client``: live preview of P1's current hover.
        - ``client -> host``: live preview of P2's current hover. After we
          update the flow, rebroadcast the full state snapshot so the
          client's copy stays consistent with ours.
        """
        try:
            player = int(msg.get("player", 0))
        except (TypeError, ValueError):
            return
        char_name = msg.get("character")
        try:
            character = Character[char_name] if isinstance(char_name, str) else None
        except KeyError:
            character = None
        if character is None or player not in (1, 2):
            return
        if player == 1:
            self._flow.character_p1 = character
        else:
            self._flow.character_p2 = character

        # Refresh whichever picker is currently on screen so the preview
        # actually redraws without waiting for a nav transition.
        cur = self._nav.current() or ""
        page = self._nav.get(cur)
        if page is not None and hasattr(page, "apply_remote_selection"):
            page.apply_remote_selection()

        # Host authoritatively rebroadcasts state so the client's flow stays
        # in sync and any other subscribers (e.g. result screen) see the
        # latest selection.
        if self._flow.network_role == NetworkRole.HOST:
            self._net.send(
                MSG_STATE, route=cur, flow=self._flow.to_snapshot()
            )

    def _handle_client_request_nav(self, msg: dict) -> None:
        """Apply a results-screen Continue from Player 2's machine."""
        if self._flow.mode != GameMode.MULTI:
            return
        route = msg.get("route")
        if not isinstance(route, str):
            return
        if self._nav.current() != "results":
            return
        allowed = {"leaderboard", "time_challenge", "rr_p1"}
        if route not in allowed:
            return
        last = self._flow.current_round >= self._flow.rounds_total
        if route == "leaderboard":
            if not last:
                return
            self._nav.go("leaderboard")
            return
        if last:
            return
        if route == "time_challenge":
            if self._flow.multiplayer_mode != MultiplayerMode.TIME_CHALLENGE:
                return
        elif route == "rr_p1":
            if self._flow.multiplayer_mode != MultiplayerMode.RECREATE_RHYTHM:
                return
        self._flow.current_round += 1
        self._nav.go(route)

    def _apply_remote_nav(self, route: str) -> None:
        self._applying_remote_nav = True
        try:
            self._nav.go(route)
        except KeyError:
            pass
        finally:
            self._applying_remote_nav = False

    # ----- networking: UI entry points ------------------------------------
    def start_host(self, port: int = 8769) -> None:
        self._net.start_host(port)

    def join_host(self, ip: str, port: int = 8769) -> None:
        self._net.start_client(ip, port)

    def stop_network(self) -> None:
        self._net.stop()

    @property
    def net(self) -> NetworkManager:
        return self._net

    def broadcast_state(self) -> None:
        """Rebroadcast the current route + full flow snapshot.

        Pages call this after mutating ``flow`` mid-screen (e.g. the host
        picking a round count) so the client's mirrored UI refreshes in
        real time without waiting for a navigation transition.
        """
        if self._flow.network_role != NetworkRole.HOST:
            return
        route = self._nav.current() or ""
        self._net.send(MSG_STATE, route=route, flow=self._flow.to_snapshot())

    # ----- help chip handlers ---------------------------------------------
    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._flow, self._session, self, network=self._net)
        dlg.home_requested.connect(lambda: (dlg.accept(), self._on_back_home_networked()))
        dlg.exec()

    def _on_back_home_networked(self) -> None:
        # If we're the host, tell P2 to follow us home. If we're the client,
        # just drop the connection; the host retains authority either way.
        if self._flow.network_role == NetworkRole.HOST:
            self._net.send(MSG_ABORT_TO_HOME)
        self._on_back_home()

    def _open_help(self) -> None:
        QMessageBox.information(
            self,
            "Beat It! — Help",
            (
                "Single Player walks you through Tutorial → Character → Genre → "
                "Time Challenge (genre sets Easy / Normal / Expert; one round) → "
                "Leaderboard → Home.\n\n"
                "Multiplayer picks Time Challenge or Recreate Rhythm after "
                "character selection.\n\n"
                "Press D to submit for Player 1, K for Player 2. Spacebar plays the "
                "reference pattern.\n\n"
                f"Designs: {FIGMA_FILE_URL}"
            ),
        )

    # ----- window lifecycle ------------------------------------------------
    def showEvent(self, event) -> None:  # noqa: D401
        super().showEvent(event)
        # On first show, expand the window to fill the screen it landed on so
        # the Figma canvas sits inside the largest possible stage.
        if self._has_filled_screen:
            return
        self._has_filled_screen = True
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        # Clamp to the screen's logical size and move to its origin so macOS
        # doesn't clip against the menu bar / dock.
        self.setGeometry(geo)

    # ----- shutdown --------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: D401
        self._session.shutdown()
        self._net.stop()
        super().closeEvent(event)
