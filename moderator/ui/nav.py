"""Named-route navigator on top of QStackedWidget."""
from __future__ import annotations

from typing import Callable, Dict, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QStackedWidget, QWidget


class AppNavigator(QObject):
    """Lazy page factory with named routes.

    Usage:
        nav.register("welcome", lambda: WelcomePage(state))
        nav.go("welcome")

    Pages are constructed on first `go(name)` and reused thereafter. Emit
    `route_changed(name)` after switching.
    """

    route_changed = Signal(str)

    def __init__(self, stack: QStackedWidget, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._stack = stack
        self._factories: Dict[str, Callable[[], QWidget]] = {}
        self._pages: Dict[str, QWidget] = {}
        self._indexes: Dict[str, int] = {}
        self._current: Optional[str] = None

    def register(self, name: str, factory: Callable[[], QWidget]) -> None:
        self._factories[name] = factory

    def _ensure(self, name: str) -> QWidget:
        if name in self._pages:
            return self._pages[name]
        if name not in self._factories:
            raise KeyError(f"Route '{name}' not registered")
        page = self._factories[name]()
        self._pages[name] = page
        self._indexes[name] = self._stack.addWidget(page)
        return page

    def go(self, name: str) -> QWidget:
        page = self._ensure(name)
        self._stack.setCurrentIndex(self._indexes[name])
        self._current = name
        self.route_changed.emit(name)
        on_enter = getattr(page, "on_enter", None)
        if callable(on_enter):
            on_enter()
        return page

    def current(self) -> Optional[str]:
        return self._current

    def get(self, name: str) -> Optional[QWidget]:
        return self._pages.get(name)
