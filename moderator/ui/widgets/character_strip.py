"""Character carousel — duck variants with left/right arrows and name pill."""
from __future__ import annotations

from typing import List

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QTransform
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...session.flow_state import Character
from .asset_loader import asset_path


_ROW_ORDER: List[Character] = [
    Character.KING_DUCK,
    Character.TOP_HAT_DUCK,
    Character.BASIC_DUCK,
    Character.VARIANT_4_DUCK,
]

_SELECTED_DUCK_SIZE = QSize(239, 263)


class _DuckCarouselStage(QWidget):
    """Fixed-size painted carousel so animation never changes layout bounds."""

    _SOURCE_SIZE = QSize(478, 526)

    def __init__(self, order: List[Character], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(608, 315)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._order = list(order)
        self._position = 0.0
        self._animation: QPropertyAnimation | None = None
        self._pixmaps = {char: self._render_duck(char) for char in self._order}

    def set_index(self, index: int, *, animate: bool) -> None:
        if self._animation is not None:
            self._animation.stop()
            self._animation = None
        index = index % len(self._order)
        if not animate:
            self._position = float(index)
            self.update()
            return

        count = len(self._order)
        delta = ((index - self._position + count / 2) % count) - count / 2
        if abs(delta) == count / 2:
            current = int(round(self._position)) % count
            delta = count / 2 if index > current else -count / 2
        target = self._position + delta

        anim = QPropertyAnimation(self, b"carouselPosition", self)
        anim.setDuration(360)
        anim.setStartValue(self._position)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutBack)
        anim.finished.connect(lambda: self._finish_animation(index))
        self._animation = anim
        anim.start()

    def _finish_animation(self, index: int) -> None:
        self._position = float(index)
        self._animation = None
        self.update()

    def _get_carousel_position(self) -> float:
        return self._position

    def _set_carousel_position(self, value: float) -> None:
        self._position = float(value)
        self.update()

    carouselPosition = Property(float, _get_carousel_position, _set_carousel_position)

    def paintEvent(self, _event) -> None:  # noqa: D401 - Qt override
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        center_x = self.width() / 2
        baseline_y = 287.0
        draw_specs = []
        for i, char in enumerate(self._order):
            dist = self._signed_distance(i)
            abs_dist = abs(dist)
            if abs_dist > 2.05:
                continue
            scale = self._scale_for(abs_dist)
            opacity = self._opacity_for(abs_dist)
            w = _SELECTED_DUCK_SIZE.width() * scale
            h = _SELECTED_DUCK_SIZE.height() * scale
            selected_weight = max(0.0, 1.0 - abs_dist)
            x = center_x + dist * 130.0 - w / 2
            y = baseline_y - h - selected_weight * 15.0
            draw_specs.append(
                (abs_dist, char, QRectF(x, y, w, h), opacity, selected_weight)
            )

        for _abs_dist, char, rect, opacity, selected_weight in sorted(
            draw_specs, key=lambda spec: spec[0], reverse=True
        ):
            if selected_weight > 0.01:
                self._paint_selection_glow(painter, rect, selected_weight)
            painter.setOpacity(opacity)
            painter.drawPixmap(
                rect,
                self._pixmaps[char],
                QRectF(self._pixmaps[char].rect()),
            )
        painter.setOpacity(1.0)
        painter.end()

    def _signed_distance(self, index: int) -> float:
        count = len(self._order)
        return ((index - self._position + count / 2) % count) - count / 2

    @staticmethod
    def _scale_for(abs_dist: float) -> float:
        if abs_dist <= 1.0:
            return 1.0 - abs_dist * 0.40
        return max(0.34, 0.60 - (abs_dist - 1.0) * 0.22)

    @staticmethod
    def _opacity_for(abs_dist: float) -> float:
        if abs_dist <= 1.0:
            return 1.0 - abs_dist * 0.34
        return max(0.20, 0.66 - (abs_dist - 1.0) * 0.38)

    @staticmethod
    def _paint_selection_glow(painter: QPainter, rect: QRectF, weight: float) -> None:
        glow = QRectF(rect)
        glow.adjust(-22, rect.height() * 0.72, 22, 28)
        painter.setOpacity(0.35 * weight)
        painter.setBrush(QColor(255, 255, 255, 90))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(glow)
        painter.setOpacity(0.16 * weight)
        painter.setBrush(QColor(148, 196, 216, 140))
        painter.drawEllipse(glow.adjusted(18, 9, -18, -9))
        painter.setOpacity(1.0)

    @classmethod
    def _render_duck(cls, character: Character) -> QPixmap:
        pix = QPixmap(cls._SOURCE_SIZE)
        pix.fill(Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(str(asset_path(character.asset)))
        painter = QPainter(pix)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        renderer.render(
            painter,
            QRectF(0, 0, cls._SOURCE_SIZE.width(), cls._SOURCE_SIZE.height()),
        )
        painter.end()
        return pix


class CharacterStrip(QFrame):
    """Rounded player card containing the duck lineup and selection controls."""

    selection_changed = Signal(object)  # Character

    def __init__(
        self,
        player_label: str = "Player 1",
        parent: QWidget | None = None,
        *,
        card_style: str = "CardBlue",
    ) -> None:
        super().__init__(parent)
        self.setObjectName(card_style)
        self.setFixedSize(648, 530)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 24, 20, 22)
        outer.setSpacing(22)

        title = QLabel(player_label)
        title.setObjectName("PlayerTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(title)

        self._duck_stage = _DuckCarouselStage(_ROW_ORDER, self)
        outer.addWidget(self._duck_stage, 0, Qt.AlignmentFlag.AlignCenter)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(50)
        controls.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._prev = self._make_arrow(mirror=False)
        self._prev.clicked.connect(self._go_prev)
        controls.addWidget(self._prev)

        self._name = QLabel()
        self._name.setObjectName("CharNamePill")
        self._name.setFixedSize(247, 65)
        self._name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls.addWidget(self._name)

        self._next = self._make_arrow(mirror=True)
        self._next.clicked.connect(self._go_next)
        controls.addWidget(self._next)

        controls_host = QWidget()
        controls_host.setLayout(controls)
        outer.addWidget(controls_host, 0, Qt.AlignmentFlag.AlignCenter)

        self._order = list(_ROW_ORDER)
        self._idx = 2  # default to the Figma Basic variant
        self._update_selection(animate=False)

    @staticmethod
    def _make_arrow(mirror: bool) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("ArrowChip")
        btn.setFixedSize(40, 40)
        # Render expand_left.svg into a pixmap, then horizontally flip it for
        # the right-arrow variant so we don't need a second asset.
        from PySide6.QtCore import Qt as _Qt
        from PySide6.QtGui import QPainter

        size = 24
        pix = QPixmap(size, size)
        pix.fill(_Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(str(asset_path("expand_left.svg")))
        painter = QPainter(pix)
        renderer.render(painter)
        painter.end()
        if mirror:
            pix = pix.transformed(
                QTransform().scale(-1, 1),
                _Qt.TransformationMode.SmoothTransformation,
            )
        btn.setIcon(QIcon(pix))
        btn.setIconSize(QSize(size, size))
        return btn

    def _go_prev(self) -> None:
        self._idx = (self._idx - 1) % len(self._order)
        self._update_selection(animate=True)
        self.selection_changed.emit(self.current())

    def _go_next(self) -> None:
        self._idx = (self._idx + 1) % len(self._order)
        self._update_selection(animate=True)
        self.selection_changed.emit(self.current())

    def current(self) -> Character:
        return self._order[self._idx]

    def set_current(self, character: Character, animate: bool = False) -> None:
        try:
            self._idx = self._order.index(character)
        except ValueError:
            return
        self._update_selection(animate=animate)

    def _update_selection(self, animate: bool) -> None:
        self._name.setText(self._order[self._idx].label)
        self._duck_stage.set_index(self._idx, animate=animate)
