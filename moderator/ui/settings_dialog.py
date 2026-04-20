"""Settings drawer opened from the Help chip (serial port / baud / BPM / network)."""
from __future__ import annotations

import socket
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..net import NetworkManager
from ..ports import guess_default_port, list_ports
from ..session import FlowState, GameSession, NetworkRole


def _best_guess_local_ip() -> str:
    """Return this machine's LAN IP so the host can read it aloud to P2."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # UDP connect doesn't actually send anything; it just picks a route
            # so the kernel fills in a plausible source address.
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        return ip
    except OSError:
        return "127.0.0.1"


class SettingsDialog(QDialog):
    connect_requested = Signal(str, int)
    disconnect_requested = Signal()
    home_requested = Signal()

    def __init__(
        self,
        flow: FlowState,
        session: GameSession,
        parent: QWidget | None = None,
        network: Optional[NetworkManager] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsDialog")
        self.setWindowTitle("Moderator — Settings")
        self.setModal(True)
        self.setMinimumWidth(500)

        self._flow = flow
        self._session = session
        self._network = network

        root = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addStretch(1)
        home_btn = QPushButton("Return to homepage")
        home_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        home_btn.clicked.connect(self.home_requested.emit)
        top.addWidget(home_btn, 0, Qt.AlignmentFlag.AlignRight)
        root.addLayout(top)

        # -------------------- Controller / audio --------------------------
        root.addWidget(self._section_title("Controller"))
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

        btn_row = QHBoxLayout()
        self._connect_btn = QPushButton(
            "Disconnect controller"
            if session.is_connected
            else "Connect controller"
        )
        self._connect_btn.clicked.connect(self._toggle_connection)
        btn_row.addWidget(self._connect_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        # -------------------- Network: two-computer MP --------------------
        root.addWidget(self._divider())
        root.addWidget(self._section_title("Multiplayer across two computers"))

        net_help = QLabel(
            "Host this game on Player 1's computer, then have Player 2 join it "
            "from another laptop on the same Wi-Fi network."
        )
        net_help.setStyleSheet("color: rgba(255,255,255,150); font-size: 12px;")
        net_help.setWordWrap(True)
        root.addWidget(net_help)

        net_form = QFormLayout()

        self._role_combo = QComboBox()
        self._role_combo.addItem("Solo / Local", NetworkRole.SOLO)
        self._role_combo.addItem("Host (Player 1)", NetworkRole.HOST)
        self._role_combo.addItem("Join as Player 2", NetworkRole.CLIENT)
        # Reflect current role.
        for i in range(self._role_combo.count()):
            if self._role_combo.itemData(i) == flow.network_role:
                self._role_combo.setCurrentIndex(i)
                break
        self._role_combo.currentIndexChanged.connect(self._on_role_changed)
        net_form.addRow(QLabel("Role"), self._role_combo)

        self._host_ip = QLineEdit(flow.host_ip or "")
        self._host_ip.setPlaceholderText("e.g. 192.168.1.42")
        net_form.addRow(QLabel("Host IP"), self._host_ip)

        self._host_port = QSpinBox()
        self._host_port.setRange(1024, 65535)
        self._host_port.setValue(flow.host_port or 8769)
        net_form.addRow(QLabel("Port"), self._host_port)

        root.addLayout(net_form)

        net_btn_row = QHBoxLayout()
        self._net_action_btn = QPushButton("Start host")
        self._net_action_btn.clicked.connect(self._toggle_network)
        net_btn_row.addWidget(self._net_action_btn)
        net_btn_row.addStretch(1)
        root.addLayout(net_btn_row)

        self._net_status = QLabel("")
        self._net_status.setStyleSheet(
            "color: rgba(255,255,255,200); font-size: 13px;"
        )
        self._net_status.setWordWrap(True)
        root.addWidget(self._net_status)

        self._local_ip_hint = QLabel("")
        self._local_ip_hint.setStyleSheet(
            "color: rgba(255,255,255,160); font-size: 12px;"
        )
        self._local_ip_hint.setWordWrap(True)
        root.addWidget(self._local_ip_hint)

        self._refresh_net_ui()

        if self._network is not None:
            self._network.status.connect(self._net_status.setText)
            self._network.host_listening.connect(self._on_host_listening)
            self._network.host_client_connected.connect(self._on_peer_connected)
            self._network.host_client_disconnected.connect(self._on_peer_left)
            self._network.client_connected.connect(self._on_client_connected)
            self._network.client_disconnected.connect(self._on_client_disconnected)

        # -------------------- Close row ----------------------------------
        root.addWidget(self._divider())
        close_row = QDialogButtonBox()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_row.addButton(close_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        root.addWidget(close_row)

        self._status = QLabel("")
        self._status.setStyleSheet("color: rgba(255,255,255,180); font-size: 12px;")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        session.serial_connected.connect(self._on_connected_changed)
        session.status_changed.connect(self._status.setText)

    # ----- section helpers -------------------------------------------------
    @staticmethod
    def _section_title(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: rgba(255,255,255,230); font-size: 14px; font-weight: 600;"
        )
        return lbl

    @staticmethod
    def _divider() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("color: rgba(255,255,255,60);")
        return f

    # ----- controller handlers --------------------------------------------
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
        self._connect_btn.setText(
            "Disconnect controller" if connected else "Connect controller"
        )

    # ----- network handlers ------------------------------------------------
    def _on_role_changed(self, _idx: int) -> None:
        self._refresh_net_ui()

    def _selected_role(self) -> NetworkRole:
        data = self._role_combo.currentData()
        return data if isinstance(data, NetworkRole) else NetworkRole.SOLO

    def _refresh_net_ui(self) -> None:
        role = self._selected_role()
        active = self._flow.network_role
        # Field visibility by role.
        self._host_ip.setEnabled(role == NetworkRole.CLIENT)
        # Action button label follows the live state on the flow, not the
        # combo selection.
        if active == NetworkRole.HOST:
            self._net_action_btn.setText("Stop hosting")
        elif active == NetworkRole.CLIENT:
            self._net_action_btn.setText("Disconnect from host")
        elif role == NetworkRole.HOST:
            self._net_action_btn.setText("Start host")
        elif role == NetworkRole.CLIENT:
            self._net_action_btn.setText("Join host")
        else:
            self._net_action_btn.setText("Apply")
        if active == NetworkRole.HOST:
            self._local_ip_hint.setText(
                f"Tell Player 2 to enter this IP: {_best_guess_local_ip()}  "
                f"(port {self._flow.host_port or 8769})"
            )
        else:
            self._local_ip_hint.setText("")

    def _toggle_network(self) -> None:
        if self._network is None:
            self._net_status.setText("Networking not initialised.")
            return
        active = self._flow.network_role
        # If something is already running, the button acts as "stop".
        if active != NetworkRole.SOLO:
            self._network.stop()
            self._net_status.setText("Disconnected.")
            self._refresh_net_ui()
            return
        role = self._selected_role()
        port = int(self._host_port.value())
        if role == NetworkRole.HOST:
            self._network.start_host(port)
        elif role == NetworkRole.CLIENT:
            ip = self._host_ip.text().strip()
            if not ip:
                self._net_status.setText("Enter the host computer's IP first.")
                return
            self._network.start_client(ip, port)
        else:
            self._net_status.setText("Set role to Host or Join to start a session.")
            return
        self._refresh_net_ui()

    # ----- network status signals -----------------------------------------
    def _on_host_listening(self, port: int) -> None:
        self._flow.host_port = port
        self._refresh_net_ui()

    def _on_peer_connected(self, addr: str) -> None:
        self._net_status.setText(f"Player 2 connected: {addr}")
        self._refresh_net_ui()

    def _on_peer_left(self, reason: str) -> None:
        self._net_status.setText(f"Player 2 left ({reason}).")
        self._refresh_net_ui()

    def _on_client_connected(self) -> None:
        self._net_status.setText(
            f"Connected to {self._flow.host_ip}:{self._flow.host_port} as Player 2."
        )
        self._refresh_net_ui()

    def _on_client_disconnected(self, reason: str) -> None:
        self._net_status.setText(f"Lost connection ({reason}).")
        self._refresh_net_ui()

    def closeEvent(self, event) -> None:  # noqa: D401 - Qt override
        self._flow.bpm = self._bpm.value()
        self._session.set_bpm(self._flow.bpm)
        super().closeEvent(event)
