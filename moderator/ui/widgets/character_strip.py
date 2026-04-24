"""Character carousel — duck variants with left/right arrows and name pill."""
from __future__ import annotations

from typing import List

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap, QTransform
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...session.flow_state import Character
from .asset_loader import asset_path
from .duck_mascot import DuckMascot


_ROW_ORDER: List[Character] = [
    Character.KING_DUCK,
    Character.TOP_HAT_DUCK,
    Character.BASIC_DUCK,
    Character.VARIANT_4_DUCK,
]

_DUCK_SIZES = {
    0: QSize(239, 263),
    1: QSize(95, 105),
    2: QSize(55, 61),
}

_DUCK_OPACITIES = {
    0: 1.0,
    1: 0.75,
    2: 0.5,
}


class CharacterStrip(QFrame):
    """Blue rounded card containing the duck lineup and selection controls."""

    selection_changed = Signal(object)  # Character

    def __init__(
        self,
        player_label: str = "Player 1",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("CardBlue")
        self.setFixedSize(648, 530)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 28, 20, 28)
        outer.setSpacing(40)

        title = QLabel(player_label)
        title.setObjectName("PlayerTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(title)

        ducks_row = QHBoxLayout()
        ducks_row.setContentsMargins(0, 0, 0, 0)
        ducks_row.setSpacing(18)
        ducks_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._duck_widgets: dict[Character, DuckMascot] = {}
        self._duck_effects: dict[Character, QGraphicsOpacityEffect] = {}
        self._selection_animation: QParallelAnimationGroup | None = None
        for char in _ROW_ORDER:
            d = DuckMascot(char.asset, 95, 105)
            effect = QGraphicsOpacityEffect(d)
            d.setGraphicsEffect(effect)
            self._duck_widgets[char] = d
            self._duck_effects[char] = effect
            ducks_row.addWidget(d, 0, Qt.AlignmentFlag.AlignBottom)
        ducks_host = QWidget()
        ducks_host.setLayout(ducks_row)
        outer.addWidget(ducks_host, 0, Qt.AlignmentFlag.AlignCenter)

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
            pix = pix.transformed(QTransform().scale(-1, 1), _Qt.TransformationMode.SmoothTransformation)
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

        if self._selection_animation is not None:
            self._selection_animation.stop()
            self._selection_animation = None

        if not animate:
            for char, duck in self._duck_widgets.items():
                size = self._size_for(char)
                duck.setFixedSize(size)
                self._duck_effects[char].setOpacity(self._opacity_for(char))
            return

        group = QParallelAnimationGroup(self)
        for char, duck in self._duck_widgets.items():
            size = self._size_for(char)
            self._add_size_animation(group, duck, b"minimumSize", size)
            self._add_size_animation(group, duck, b"maximumSize", size)

            opacity_anim = self._make_animation(
                self._duck_effects[char],
                b"opacity",
                self._duck_effects[char].opacity(),
                self._opacity_for(char),
            )
            group.addAnimation(opacity_anim)

        self._selection_animation = group
        group.finished.connect(lambda: setattr(self, "_selection_animation", None))
        group.start()

    def _distance_from_current(self, character: Character) -> int:
        idx = self._order.index(character)
        raw = abs(idx - self._idx)
        return min(raw, len(self._order) - raw)

    def _size_for(self, character: Character) -> QSize:
        return _DUCK_SIZES.get(self._distance_from_current(character), _DUCK_SIZES[2])

    def _opacity_for(self, character: Character) -> float:
        return _DUCK_OPACITIES.get(self._distance_from_current(character), 0.5)

    def _add_size_animation(
        self,
        group: QParallelAnimationGroup,
        duck: DuckMascot,
        prop: bytes,
        end_size: QSize,
    ) -> None:
        anim = self._make_animation(duck, prop, duck.property(prop.decode()), end_size)
        group.addAnimation(anim)

    @staticmethod
    def _make_animation(obj, prop: bytes, start, end):
        from PySide6.QtCore import QPropertyAnimation

        anim = QPropertyAnimation(obj, prop)
        anim.setDuration(180)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        return anim
