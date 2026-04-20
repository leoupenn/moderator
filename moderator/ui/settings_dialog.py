"""Settings drawer opened from the Help chip (serial port / baud / BPM)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..ports import guess_default_port, list_ports
from ..session import FlowState, GameSession


class SettingsDialog(QDialog):
    connect_requested = Signal(str, int)
    disconnect_requested = Signal()

    def __init__(
        self,
        flow: FlowState,
        session: GameSession,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsDialog")
        self.setWindowTitle("Moderator — Settings")
        self.setModal(True)
        self.setMinimumWidth(460)

        self._flow = flow
        self._session = session

        root = QVBoxLayout(self)
        form = QFormLayout()

        self._port = QComboBox()
        self._port.setEditable(True)
        self._refresh_ports()
        form.addRow(QLabel("Serial port"), self._port)

        refresh_btn = QPushButton("Refresh ports")
        refresh_btn.clicked.connect(self._refresh_ports)
        form.addRow(QLabel(""), refresh_btn)

        self._baud = QComboBox()
        for b in ("9600", "19200", "38400", "57600", "115200", "230400"):
            self._baud.addItem(b)
        self._baud.setCurrentText("115200")
        form.addRow(QLabel("Baud rate"), self._baud)

        self._bpm = QSpinBox()
        self._bpm.setRange(20, 240)
        self._bpm.setValue(flow.bpm)
        form.addRow(QLabel("Default BPM"), self._bpm)

        root.addLayout(form)

        self._status = QLabel("")
        self._status.setStyleSheet("color: rgba(255,255,255,180); font-size: 13px;")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        btn_row = QDialogButtonBox()
        self._connect_btn = QPushButton(
            "Disconnect" if session.is_connected else "Connect"
        )
        self._connect_btn.clicked.connect(self._toggle_connection)
        btn_row.addButton(self._connect_btn, QDialogButtonBox.ButtonRole.ActionRole)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addButton(close_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        root.addWidget(btn_row)

        session.serial_connected.connect(self._on_connected_changed)
        session.status_changed.connect(self._status.setText)

    def _refresh_ports(self) -> None:
        self._port.clear()
        for device, desc in list_ports():
            self._port.addItem(device, desc)
        default = guess_default_port()
        if default is not None:
            idx = self._port.findText(default)
            if idx >= 0:
                self._port.setCurrentIndex(idx)

    def _toggle_connection(self) -> None:
        if self._session.is_connected:
            self.disconnect_requested.emit()
            self._session.disconnect_serial()
            return
        port = self._port.currentText().strip()
        if not port:
            self._status.setText("Select a serial port first.")
            return
        try:
            baud = int(self._baud.currentText())
        except ValueError:
            baud = 115200
        self._flow.bpm = self._bpm.value()
        self._session.set_bpm(self._flow.bpm)
        self.connect_requested.emit(port, baud)
        self._session.connect_serial(port, baud)

    def _on_connected_changed(self, connected: bool) -> None:
        self._connect_btn.setText("Disconnect" if connected else "Connect")

    def closeEvent(self, event) -> None:  # noqa: D401 - Qt override
        self._flow.bpm = self._bpm.value()
        self._session.set_bpm(self._flow.bpm)
        super().closeEvent(event)
