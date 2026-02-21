"""PySide6 GUI for FLX4 Control — main window, tray icon, pad configuration."""
from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
    QPushButton, QRadioButton, QSizePolicy, QSpinBox, QSystemTrayIcon,
    QTabWidget, QVBoxLayout, QWidget,
)

from .config import Config
from .controller_bridge import ControllerBridge


# ---------------------------------------------------------------------------
# Global dark stylesheet
# ---------------------------------------------------------------------------
APP_STYLE = """
QWidget {
    background-color: #121212;
    color: #d0d0d0;
    font-size: 12px;
}
QMainWindow {
    background-color: #0e0e0e;
}
QGroupBox {
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
    font-weight: bold;
    color: #888;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}
QTabWidget::pane {
    border: 1px solid #252525;
    border-radius: 4px;
    background: #141414;
}
QTabBar::tab {
    background: #1a1a1a;
    color: #666;
    padding: 7px 18px;
    border: 1px solid #252525;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    min-width: 120px;
}
QTabBar::tab:selected {
    background: #1f1f1f;
    color: #e0e0e0;
    border-bottom: 2px solid #4dffaa;
}
QTabBar::tab:hover:!selected {
    background: #1c1c1c;
    color: #aaa;
}
QComboBox {
    background: #1a1a1a;
    border: 1px solid #303030;
    border-radius: 4px;
    padding: 5px 10px;
    min-width: 200px;
    color: #d0d0d0;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #1a1a1a;
    border: 1px solid #333;
    selection-background-color: #1a3a20;
    color: #d0d0d0;
}
QSpinBox {
    background: #1a1a1a;
    border: 1px solid #303030;
    border-radius: 4px;
    padding: 5px 8px;
    color: #d0d0d0;
    min-width: 60px;
}
QSpinBox::up-button, QSpinBox::down-button {
    background: #252525;
    border: none;
    width: 18px;
}
QCheckBox { color: #d0d0d0; spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #404040;
    border-radius: 3px;
    background: #1a1a1a;
}
QCheckBox::indicator:checked {
    background: #4dffaa;
    border-color: #4dffaa;
    image: none;
}
QLabel { color: #888; }
QLineEdit {
    background: #1a1a1a;
    border: 1px solid #303030;
    border-radius: 4px;
    padding: 5px 8px;
    color: #d0d0d0;
}
QPushButton {
    background: #1e1e1e;
    color: #d0d0d0;
    border: 1px solid #303030;
    border-radius: 4px;
    padding: 6px 14px;
    min-width: 70px;
}
QPushButton:hover { background: #252525; border-color: #404040; }
QPushButton:pressed { background: #141414; }
QPushButton:disabled { color: #444; border-color: #222; }
QDialog { background: #141414; }
QRadioButton { color: #d0d0d0; spacing: 6px; }
QRadioButton::indicator {
    width: 14px; height: 14px;
    border: 1px solid #404040;
    border-radius: 7px;
    background: #1a1a1a;
}
QRadioButton::indicator:checked {
    background: #4dffaa;
    border-color: #4dffaa;
}
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    color: #252525;
}
"""


# ---------------------------------------------------------------------------
# Icon factory
# ---------------------------------------------------------------------------

def make_icon() -> QIcon:
    size = 64
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Background circle
    p.setBrush(QColor("#1a1a2e"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(2, 2, size - 4, size - 4)

    # 4 pad squares in a 2×2 grid
    pad_sz = 18
    gap = 5
    ox = (size - 2 * pad_sz - gap) // 2
    oy = (size - 2 * pad_sz - gap) // 2
    colors = ["#4dffaa", "#4dffaa", "#4d9fff", "#4dffaa"]
    for row in range(2):
        for col in range(2):
            c = QColor(colors[row * 2 + col])
            p.setBrush(c)
            p.drawRoundedRect(ox + col * (pad_sz + gap), oy + row * (pad_sz + gap), pad_sz, pad_sz, 3, 3)
    p.end()
    return QIcon(pix)


# ---------------------------------------------------------------------------
# PadButton
# ---------------------------------------------------------------------------

class PadButton(QPushButton):
    configure_requested = Signal(int, int, int)  # deck, bank, pad

    _STYLES = {
        "none": """
            QPushButton {
                background: #191919; color: #383838;
                border: 1px solid #202020; border-radius: 8px;
                font-size: 10px; padding: 4px 2px;
            }
            QPushButton:hover { background: #1e1e1e; border-color: #2a2a2a; }
        """,
        "app": """
            QPushButton {
                background: #0c2e18; color: #4dffaa;
                border: 1px solid #175c30; border-radius: 8px;
                font-size: 10px; font-weight: bold; padding: 4px 2px;
            }
            QPushButton:hover { background: #0f3a1e; }
            QPushButton:pressed { background: #061408; }
        """,
        "sound": """
            QPushButton {
                background: #0c1a30; color: #4d9fff;
                border: 1px solid #1a3566; border-radius: 8px;
                font-size: 10px; font-weight: bold; padding: 4px 2px;
            }
            QPushButton:hover { background: #0f2040; }
            QPushButton:pressed { background: #060c18; }
        """,
    }

    def __init__(self, deck: int, bank: int, pad: int, parent: QWidget = None):
        super().__init__(parent)
        self.deck = deck
        self.bank = bank
        self.pad = pad
        self.setMinimumSize(95, 72)
        self.setMaximumSize(140, 100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(lambda: self.configure_requested.emit(deck, bank, pad))
        self.set_action({"type": "none"})

    _LABELS = {
        "media_play_pause": "▶/❚❚ Media",
        "media_next":       "⏭ Next",
        "media_previous":   "⏮ Prev",
        "mute_mic":         "🎙 Mute",
    }

    def set_action(self, action: dict) -> None:
        atype = action.get("type", "none")
        name = action.get("name", "").strip()
        label = f"Pad {self.pad + 1}"

        if atype == "none":
            self.setText(f"{label}\n—")
            self.setToolTip("")
        elif atype in self._LABELS:
            self.setText(f"{label}\n{self._LABELS[atype]}")
            self.setToolTip(self._LABELS[atype])
        else:
            display = (name[:12] + "…") if len(name) > 12 else name
            fallback = "App" if atype == "app" else "Sound"
            self.setText(f"{label}\n{display or fallback}")
            self.setToolTip(name or action.get("path", action.get("file", "")))

        # Use "app" style for media actions, "sound" for mute_mic
        style_key = atype if atype in self._STYLES else (
            "app" if atype in ("media_play_pause", "media_next", "media_previous")
            else "sound" if atype == "mute_mic"
            else "none"
        )
        self.setStyleSheet(self._STYLES[style_key])


# ---------------------------------------------------------------------------
# PadConfigDialog
# ---------------------------------------------------------------------------

class PadConfigDialog(QDialog):
    def __init__(
        self,
        deck: int,
        bank: int,
        pad: int,
        action: dict,
        parent: QWidget = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"Pad {pad + 1}  ·  Bank {bank + 1}  ·  Deck {deck}")
        self.setMinimumWidth(460)
        self.setModal(True)

        self._result_action: dict = {"type": "none"}
        self._source_sound_path: str = ""

        self._build_ui(action)

    def _build_ui(self, action: dict) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)

        # --- Action type ---
        type_box = QGroupBox("Action")
        type_layout = QVBoxLayout(type_box)

        self._btn_group = QButtonGroup(self)
        self.rb_none     = QRadioButton("No action")
        self.rb_app      = QRadioButton("Open app / file")
        self.rb_sound    = QRadioButton("Play sound")
        self.rb_playpause = QRadioButton("Media: Play / Pause")
        self.rb_next     = QRadioButton("Media: Next track")
        self.rb_previous = QRadioButton("Media: Previous track")
        self.rb_mute_mic = QRadioButton("Mute / Unmute microphone")
        for rb in (self.rb_none, self.rb_app, self.rb_sound,
                   self.rb_playpause, self.rb_next, self.rb_previous, self.rb_mute_mic):
            self._btn_group.addButton(rb)
            type_layout.addWidget(rb)
        root.addWidget(type_box)

        # --- App section ---
        self.app_box = QGroupBox("App / File")
        app_form = QFormLayout(self.app_box)
        app_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.app_name = QLineEdit(action.get("name", "") if action.get("type") == "app" else "")
        self.app_name.setPlaceholderText("Display name (optional)")
        app_form.addRow("Name:", self.app_name)

        path_row = QHBoxLayout()
        self.app_path = QLineEdit(action.get("path", "") if action.get("type") == "app" else "")
        self.app_path.setPlaceholderText("/Applications/Spotify.app")
        path_row.addWidget(self.app_path)
        browse_app_btn = QPushButton("Browse…")
        browse_app_btn.setMaximumWidth(80)
        browse_app_btn.clicked.connect(self._browse_app)
        path_row.addWidget(browse_app_btn)
        app_form.addRow("Path:", path_row)
        root.addWidget(self.app_box)

        # --- Sound section ---
        self.sound_box = QGroupBox("Sound File")
        sound_form = QFormLayout(self.sound_box)
        sound_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.sound_name = QLineEdit(action.get("name", "") if action.get("type") == "sound" else "")
        self.sound_name.setPlaceholderText("Display name (optional)")
        sound_form.addRow("Name:", self.sound_name)

        file_row = QHBoxLayout()
        self.sound_file_label = QLabel(action.get("file", "—") if action.get("type") == "sound" else "—")
        self.sound_file_label.setStyleSheet("color: #aaa; font-style: italic;")
        file_row.addWidget(self.sound_file_label, 1)
        browse_sound_btn = QPushButton("Browse…")
        browse_sound_btn.setMaximumWidth(80)
        browse_sound_btn.clicked.connect(self._browse_sound)
        file_row.addWidget(browse_sound_btn)
        sound_form.addRow("File:", file_row)

        preview_row = QHBoxLayout()
        preview_row.addStretch()
        self.preview_btn = QPushButton("▶  Preview")
        self.preview_btn.setMaximumWidth(100)
        self.preview_btn.clicked.connect(self._preview_sound)
        preview_row.addWidget(self.preview_btn)
        sound_form.addRow("", preview_row)
        root.addWidget(self.sound_box)

        # --- Buttons ---
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

        # --- Connect radio buttons ---
        for rb in (self.rb_none, self.rb_app, self.rb_sound,
                   self.rb_playpause, self.rb_next, self.rb_previous, self.rb_mute_mic):
            rb.toggled.connect(self._update_visibility)

        # --- Set initial state ---
        atype = action.get("type", "none")
        _rb_map = {
            "app": self.rb_app,
            "sound": self.rb_sound,
            "media_play_pause": self.rb_playpause,
            "media_next": self.rb_next,
            "media_previous": self.rb_previous,
            "mute_mic": self.rb_mute_mic,
        }
        rb_sel = _rb_map.get(atype, self.rb_none)
        rb_sel.setChecked(True)
        if atype == "sound":
            self._source_sound_path = action.get("file", "")
        self._update_visibility()

    def _update_visibility(self) -> None:
        self.app_box.setVisible(self.rb_app.isChecked())
        self.sound_box.setVisible(self.rb_sound.isChecked())
        self.adjustSize()

    def _browse_app(self) -> None:
        if platform.system() == "Darwin":
            file_filter = "Applications (*.app);;All Files (*)"
        elif platform.system() == "Windows":
            file_filter = "Programs (*.exe *.bat *.cmd);;All Files (*)"
        else:
            file_filter = "All Files (*)"

        path, _ = QFileDialog.getOpenFileName(
            self, "Select App or File", "", file_filter
        )
        if path:
            self.app_path.setText(path)
            if not self.app_name.text():
                self.app_name.setText(Path(path).stem)

    def _browse_sound(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Sound File",
            "",
            "Audio Files (*.wav *.mp3 *.ogg *.flac *.aiff *.aif);;All Files (*)",
        )
        if path:
            self._source_sound_path = path
            self.sound_file_label.setText(Path(path).name)
            if not self.sound_name.text():
                self.sound_name.setText(Path(path).stem)

    def _preview_sound(self) -> None:
        if self._source_sound_path:
            from .audio_player import play_sound
            play_sound(self._source_sound_path)

    def _on_accept(self) -> None:
        # Simple (no-config) action types
        _simple = {
            self.rb_playpause: "media_play_pause",
            self.rb_next:      "media_next",
            self.rb_previous:  "media_previous",
            self.rb_mute_mic:  "mute_mic",
        }
        for rb, atype in _simple.items():
            if rb.isChecked():
                self._result_action = {"type": atype}
                self.accept()
                return

        if self.rb_none.isChecked():
            self._result_action = {"type": "none"}
        elif self.rb_app.isChecked():
            path = self.app_path.text().strip()
            if not path:
                self.app_path.setFocus()
                return
            self._result_action = {
                "type": "app",
                "name": self.app_name.text().strip(),
                "path": path,
            }
        elif self.rb_sound.isChecked():
            if not self._source_sound_path:
                return
            self._result_action = {
                "type": "sound",
                "name": self.sound_name.text().strip(),
                "source_path": self._source_sound_path,
            }
        self.accept()

    def get_action(self) -> dict:
        return self._result_action


# ---------------------------------------------------------------------------
# ProgramSwitcherDialog
# ---------------------------------------------------------------------------

class ProgramSwitcherDialog(QDialog):
    """
    Frameless overlay that appears when the browse encoder is turned.
    Navigate with the encoder, select with BROWSE_LOAD deck 1,
    close with BROWSE_LOAD deck 2.
    Volume of the selected app is controlled by the MASTER_LEVEL knob.
    """

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMinimumWidth(360)
        self.setMaximumHeight(480)

        self._apps: list[str] = []
        self._selected: int = 0
        self._selected_app: str = ""

        self._build_ui()
        self._position_on_screen()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # Title bar
        title_row = QHBoxLayout()
        title_lbl = QLabel("Select Program")
        title_lbl.setStyleSheet("color: #e0e0e0; font-weight: bold; font-size: 13px;")
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setMaximumSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton { background: #2a2a2a; border: none; color: #888; border-radius: 4px; }"
            "QPushButton:hover { background: #cc3333; color: white; }"
        )
        close_btn.clicked.connect(self.hide)
        title_row.addWidget(close_btn)
        root.addLayout(title_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        # App list
        from PySide6.QtWidgets import QListWidget
        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget {
                background: #161616;
                border: 1px solid #252525;
                border-radius: 4px;
                color: #d0d0d0;
                font-size: 12px;
            }
            QListWidget::item:selected {
                background: #1a3a1a;
                color: #4dffaa;
            }
            QListWidget::item:hover { background: #1e1e1e; }
        """)
        self._list.itemActivated.connect(self._on_item_activated)
        root.addWidget(self._list, 1)

        # Volume bar
        self.vol_label = QLabel("Volume: — ")
        self.vol_label.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self.vol_label)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep2)

        hint = QLabel("LOAD 1: Focus app  ·  LOAD 2 / encoder press: Close  ·  MASTER knob: Volume")
        hint.setStyleSheet("color: #444; font-size: 10px;")
        hint.setWordWrap(True)
        root.addWidget(hint)

    def _position_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.center().x() - self.width() // 2, geo.top() + 40)

    # --- Public methods called from MainWindow ---

    def refresh_apps(self) -> None:
        from . import system_control
        self._apps = system_control.get_open_apps()
        self._list.clear()
        for app in self._apps:
            self._list.addItem(app)
        if self._apps:
            self._selected = 0
            self._list.setCurrentRow(0)
            self._selected_app = self._apps[0]

    def move_selection(self, steps: int) -> None:
        if not self._apps:
            return
        self._selected = (self._selected + steps) % len(self._apps)
        self._list.setCurrentRow(self._selected)
        self._selected_app = self._apps[self._selected]

    def select_current(self) -> None:
        """Focus the currently highlighted application."""
        if self._selected_app:
            from . import system_control
            system_control.focus_app(self._selected_app)
            self.hide()

    def set_app_volume(self, volume: float) -> None:
        """Set the audio volume of the selected application."""
        if not self._selected_app:
            return
        from . import system_control
        system_control.set_app_volume(self._selected_app, volume)
        pct = int(volume * 100)
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        self.vol_label.setText(f"Volume: {bar}  {pct}%")

    def _on_item_activated(self, item) -> None:
        self._selected_app = item.text()
        self.select_current()


# ---------------------------------------------------------------------------
# Volume/Scroll settings combos — option lists
# ---------------------------------------------------------------------------

_VOL_OPTIONS = [
    ("Deck 1 Channel Fader",  {"deck": 1,    "control": "CH_FADER"}),
    ("Deck 2 Channel Fader",  {"deck": 2,    "control": "CH_FADER"}),
    ("Master Level Knob",     {"deck": None, "control": "MASTER_LEVEL"}),
    ("Disabled",              {"deck": None, "control": None}),
]

_MIC_OPTIONS = [
    ("Deck 1 Channel Fader",  {"deck": 1,    "control": "CH_FADER"}),
    ("Deck 2 Channel Fader",  {"deck": 2,    "control": "CH_FADER"}),
    ("Disabled",              {"deck": None, "control": None}),
]

_SCROLL_OPTIONS = [
    ("Deck 1 Jog Wheel", 1),
    ("Deck 2 Jog Wheel", 2),
    ("Disabled",          0),
]


def _find_combo_index(options: list, value) -> int:
    for i, (_, v) in enumerate(options):
        if v == value:
            return i
    return 0


# ---------------------------------------------------------------------------
# SettingsWidget
# ---------------------------------------------------------------------------

class SettingsWidget(QGroupBox):
    def __init__(self, config: Config, bridge: ControllerBridge, parent: QWidget = None):
        super().__init__("Settings", parent)
        self.config = config
        self.bridge = bridge
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setVerticalSpacing(8)
        form.setHorizontalSpacing(16)

        # Output volume fader
        self.vol_combo = QComboBox()
        for label, _ in _VOL_OPTIONS:
            self.vol_combo.addItem(label)
        self.vol_combo.currentIndexChanged.connect(self._on_vol_changed)
        form.addRow("Output Volume:", self.vol_combo)

        # Mic volume fader
        self.mic_combo = QComboBox()
        for label, _ in _MIC_OPTIONS:
            self.mic_combo.addItem(label)
        self.mic_combo.currentIndexChanged.connect(self._on_mic_changed)
        form.addRow("Mic Volume:", self.mic_combo)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        form.addRow(sep)

        # Scroll jog wheel
        self.scroll_combo = QComboBox()
        for label, _ in _SCROLL_OPTIONS:
            self.scroll_combo.addItem(label)
        self.scroll_combo.currentIndexChanged.connect(self._on_scroll_changed)
        form.addRow("Scroll Jog Wheel:", self.scroll_combo)

        # Sensitivity
        self.sensitivity_spin = QSpinBox()
        self.sensitivity_spin.setRange(1, 20)
        self.sensitivity_spin.setSuffix("  clicks/step")
        self.sensitivity_spin.valueChanged.connect(self._on_sensitivity_changed)
        form.addRow("Scroll Sensitivity:", self.sensitivity_spin)

        # Reverse
        self.reverse_check = QCheckBox("Reverse scroll direction")
        self.reverse_check.stateChanged.connect(self._on_reverse_changed)
        form.addRow("", self.reverse_check)

    def _load_values(self) -> None:
        vol = self.config.get_volume_fader()
        self.vol_combo.setCurrentIndex(
            _find_combo_index(_VOL_OPTIONS, {"deck": vol.get("deck"), "control": vol.get("control")})
        )
        mic = self.config.get_mic_fader()
        self.mic_combo.setCurrentIndex(
            _find_combo_index(_MIC_OPTIONS, {"deck": mic.get("deck"), "control": mic.get("control")})
        )
        scroll_deck = self.config.get_scroll_deck()
        self.scroll_combo.setCurrentIndex(
            _find_combo_index(_SCROLL_OPTIONS, scroll_deck)
        )
        self.sensitivity_spin.setValue(self.config.get_scroll_sensitivity())
        self.reverse_check.setChecked(self.config.get_scroll_reverse())

    def _on_vol_changed(self, idx: int) -> None:
        _, val = _VOL_OPTIONS[idx]
        self.config.set_volume_fader(val.get("deck"), val.get("control"))

    def _on_mic_changed(self, idx: int) -> None:
        _, val = _MIC_OPTIONS[idx]
        self.config.set_mic_fader(val.get("deck"), val.get("control"))

    def _on_scroll_changed(self, idx: int) -> None:
        _, val = _SCROLL_OPTIONS[idx]
        self.config.set_scroll_deck(val)

    def _on_sensitivity_changed(self, val: int) -> None:
        self.config.set_scroll_sensitivity(val)

    def _on_reverse_changed(self, state: int) -> None:
        self.config.set_scroll_reverse(bool(state))


# ---------------------------------------------------------------------------
# MainWindow
# ---------------------------------------------------------------------------

BANK_NAMES = [
    "Bank 1  (HOT CUE)",
    "Bank 2  (PAD FX)",
    "Bank 3  (BEAT JUMP)",
    "Bank 4  (SAMPLER)",
]


class MainWindow(QMainWindow):
    def __init__(self, config: Config, bridge: ControllerBridge):
        super().__init__()
        self.config = config
        self.bridge = bridge

        # pad_buttons[(bank, deck, pad)] → PadButton
        self.pad_buttons: dict[tuple, PadButton] = {}

        self.setWindowTitle("FLX4 Control")
        self.setMinimumSize(760, 620)
        self.setWindowIcon(make_icon())

        self._build_ui()
        self._build_tray()
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(10)

        # --- Header ---
        header = QHBoxLayout()
        dot = "●"
        self.status_label = QLabel(f"{dot}  Not connected — retrying…")
        self.status_label.setStyleSheet("color: #ff6644; font-weight: bold;")
        header.addWidget(self.status_label)
        header.addStretch()

        self.bank_label = QLabel("Deck 1: Bank 1  |  Deck 2: Bank 1")
        self.bank_label.setStyleSheet("color: #4dffaa; font-size: 11px;")
        header.addWidget(self.bank_label)

        refresh_btn = QPushButton("Refresh LEDs")
        refresh_btn.setMaximumWidth(110)
        refresh_btn.setToolTip("Re-send all pad and tab LEDs to the controller")
        refresh_btn.clicked.connect(self.bridge.refresh_leds)
        header.addWidget(refresh_btn)
        root.addLayout(header)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        # --- Bank tabs ---
        self.bank_tabs = QTabWidget()
        for bank_idx in range(4):
            tab_widget = self._make_bank_tab(bank_idx)
            self.bank_tabs.addTab(tab_widget, BANK_NAMES[bank_idx])
        root.addWidget(self.bank_tabs, 1)

        # --- Settings ---
        self.settings = SettingsWidget(self.config, self.bridge)
        root.addWidget(self.settings)

        self.setCentralWidget(central)

    def _make_bank_tab(self, bank: int) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setSpacing(16)
        layout.setContentsMargins(10, 10, 10, 10)

        for deck in (1, 2):
            group = QGroupBox(f"Deck {deck}")
            grid = QGridLayout(group)
            grid.setSpacing(8)
            # Row 0: pads 0-3  /  Row 1: pads 4-7
            for pad in range(8):
                row, col = divmod(pad, 4)
                btn = PadButton(deck, bank, pad)
                action = self.config.get_pad_action(deck, bank, pad)
                btn.set_action(action)
                btn.configure_requested.connect(self._open_pad_config)
                grid.addWidget(btn, row, col)
                self.pad_buttons[(bank, deck, pad)] = btn
            layout.addWidget(group)

        return w

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(make_icon(), self)
        self.tray.setToolTip("FLX4 Control")

        menu = QMenu()
        show_act = QAction("Show / Hide Window", self)
        show_act.triggered.connect(self._toggle_window)
        menu.addAction(show_act)

        menu.addSeparator()
        reconnect_act = QAction("Reconnect Controller", self)
        reconnect_act.triggered.connect(self._reconnect)
        menu.addAction(reconnect_act)

        menu.addSeparator()
        quit_act = QAction("Quit", self)
        quit_act.triggered.connect(self._quit)
        menu.addAction(quit_act)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _connect_signals(self) -> None:
        self.bridge.controller_connected.connect(self._on_connected)
        self.bridge.controller_disconnected.connect(self._on_disconnected)
        self.bridge.tab_changed.connect(self._on_tab_changed)
        self.bridge.browse_turned.connect(self._on_browse_turned)
        self.bridge.program_load_pressed.connect(self._on_program_load)
        self.bridge.master_level_changed.connect(self._on_master_level)
        self.bridge.play_state_changed.connect(self._on_play_state_changed)

        # Program switcher instance (created on demand)
        self._prog_switcher: Optional[ProgramSwitcherDialog] = None

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot()
    def _on_connected(self) -> None:
        self.status_label.setText("●  Connected")
        self.status_label.setStyleSheet("color: #4dffaa; font-weight: bold;")
        self.tray.showMessage("FLX4 Control", "DDJ-FLX4 connected.", QSystemTrayIcon.MessageIcon.Information, 2000)

    @Slot()
    def _on_disconnected(self) -> None:
        self.status_label.setText("●  Not connected — retrying…")
        self.status_label.setStyleSheet("color: #ff6644; font-weight: bold;")

    @Slot(int, int)
    def _on_tab_changed(self, deck: int, tab: int) -> None:
        b1 = self.bridge.current_bank(1) + 1
        b2 = self.bridge.current_bank(2) + 1
        self.bank_label.setText(f"Deck 1: Bank {b1}  |  Deck 2: Bank {b2}")

    @Slot(int, int, int)
    def _open_pad_config(self, deck: int, bank: int, pad: int) -> None:
        action = self.config.get_pad_action(deck, bank, pad)
        dlg = PadConfigDialog(deck, bank, pad, action, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        raw = dlg.get_action()

        # Import sound file into app-data dir
        if raw.get("type") == "sound":
            src = raw.pop("source_path", "")
            if src:
                try:
                    filename = self.config.import_sound_file(src)
                except Exception as exc:
                    print(f"[gui] Failed to import sound: {exc}")
                    return
                raw["file"] = filename
            else:
                # Editing an existing sound assignment — keep original file
                old = self.config.get_pad_action(deck, bank, pad)
                raw["file"] = old.get("file", "")

        self.config.set_pad_action(deck, bank, pad, raw)
        btn = self.pad_buttons.get((bank, deck, pad))
        if btn:
            btn.set_action(raw)
        self.bridge.refresh_leds()

    @Slot(int)
    def _on_browse_turned(self, steps: int) -> None:
        """Show the program switcher on first turn; navigate on subsequent turns."""
        if self._prog_switcher is None:
            self._prog_switcher = ProgramSwitcherDialog(self)
        if not self._prog_switcher.isVisible():
            self._prog_switcher.refresh_apps()
            # Reposition in case screen geometry changed
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                self._prog_switcher.move(
                    geo.center().x() - self._prog_switcher.sizeHint().width() // 2,
                    geo.top() + 40,
                )
            self._prog_switcher.show()
            self._prog_switcher.raise_()
        self._prog_switcher.move_selection(steps)

    @Slot(int)
    def _on_program_load(self, deck: int) -> None:
        if self._prog_switcher and self._prog_switcher.isVisible():
            if deck == 1:
                self._prog_switcher.select_current()
            else:
                self._prog_switcher.hide()

    @Slot(float)
    def _on_master_level(self, value: float) -> None:
        if self._prog_switcher and self._prog_switcher.isVisible():
            self._prog_switcher.set_app_volume(value)

    @Slot(bool)
    def _on_play_state_changed(self, playing: bool) -> None:
        state = "▶  Playing" if playing else "❚❚  Paused"
        self.status_label.setText(
            f"●  Connected  ·  {state}"
            if self.bridge.connected else self.status_label.text()
        )

    # ------------------------------------------------------------------
    # Tray / window helpers
    # ------------------------------------------------------------------

    def _tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self._toggle_window()

    def _toggle_window(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _reconnect(self) -> None:
        """Force-restart the bridge (stop + start)."""
        self.bridge.stop()
        import threading, time
        def _restart():
            time.sleep(1)
            self.bridge.start()
        threading.Thread(target=_restart, daemon=True).start()

    def _quit(self) -> None:
        self.bridge.stop()
        QApplication.quit()

    # Override close → hide (keep running in tray)
    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "FLX4 Control",
            "Still running in the system tray.",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    # macOS: suppress pyautogui safety fail (cursor in corner)
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
    except ImportError:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("FLX4 Control")
    app.setOrganizationName("flx4control")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(APP_STYLE)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("[warn] System tray not available — window will stay open.")

    config = Config()
    bridge = ControllerBridge(config)
    bridge.start()

    window = MainWindow(config, bridge)
    window.show()

    ret = app.exec()
    bridge.stop()
    return ret
