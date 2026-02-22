"""PySide6 GUI for FLX4 Control — main window, tray icon, pad configuration."""
from __future__ import annotations

import platform
import socket
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
    QProgressBar, QPushButton, QRadioButton, QSizePolicy, QSpinBox,
    QSystemTrayIcon, QTabWidget, QVBoxLayout, QWidget,
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
    """App icon: dark circle, green ring, play triangle."""
    from PySide6.QtGui import QPen, QPolygon
    from PySide6.QtCore import QPoint
    icon = QIcon()
    for size in (16, 32, 48, 64, 128, 256):
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1a1a2e"))
        p.drawEllipse(1, 1, size - 2, size - 2)
        # Green ring
        rw = max(1, size // 18)
        p.setPen(QPen(QColor("#4dffaa"), rw))
        p.setBrush(Qt.BrushStyle.NoBrush)
        m = size // 8
        p.drawEllipse(m, m, size - 2 * m, size - 2 * m)
        # Play triangle
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#4dffaa"))
        cx = size // 2 + size // 20
        cy = size // 2
        s = size // 5
        poly = QPolygon([QPoint(cx - s, cy - s), QPoint(cx - s, cy + s), QPoint(cx + s, cy)])
        p.drawPolygon(poly)
        p.end()
        icon.addPixmap(pix)
    return icon


def _action_label(action: dict) -> str:
    """Human-readable label for an action dict."""
    _LABELS = {
        "none": "— none —",
        "media_play_pause": "Media: Play / Pause",
        "media_next": "Media: Next track",
        "media_previous": "Media: Previous track",
        "mute_mic": "Mute / Unmute mic",
        "app": "Open app",
        "sound": "Play sound",
    }
    atype = action.get("type", "none")
    base = _LABELS.get(atype, atype)
    name = action.get("name", "")
    return f"{base}  ({name})" if name else base


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

    def flash(self) -> None:
        """Briefly flash the button to indicate a press."""
        orig = self.styleSheet()
        self.setStyleSheet(
            "QPushButton { background: #2a5a2a; border: 1px solid #4dffaa; "
            "border-radius: 8px; color: #4dffaa; font-size: 10px; padding: 4px 2px; }"
        )
        QTimer.singleShot(120, lambda: self.setStyleSheet(orig))

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
# VolumeOverlay
# ---------------------------------------------------------------------------

class VolumeOverlay(QWidget):
    """Floating volume flyout that auto-hides after 1.5 s of inactivity."""

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(240, 72)
        self.setStyleSheet("""
            QWidget { background: #1a1a2a; border: 1px solid #303050; border-radius: 8px; }
            QLabel#title { color: #888; font-size: 11px; }
            QLabel#pct { color: #4dffaa; font-size: 20px; font-weight: bold; }
            QProgressBar {
                background: #252525; border: none; border-radius: 4px; height: 8px;
            }
            QProgressBar::chunk { background: #4dffaa; border-radius: 4px; }
        """)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        self._title = QLabel("")
        self._title.setObjectName("title")
        layout.addWidget(self._title)

        row = QHBoxLayout()
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(8)
        row.addWidget(self._bar, 1)
        self._pct = QLabel("0%")
        self._pct.setObjectName("pct")
        self._pct.setFixedWidth(50)
        self._pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self._pct)
        layout.addLayout(row)

    def show_volume(self, label: str, value: float) -> None:
        pct = int(value * 100)
        self._title.setText(label)
        self._bar.setValue(pct)
        self._pct.setText(f"{pct}%")
        self._position()
        self.show()
        self.raise_()
        self._timer.start(1500)

    def _position(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.right() - self.width() - 20, geo.bottom() - self.height() - 20)


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

    _apps_cache: list[str] = []  # class-level cache shared across instances

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
        # Pre-populate from cache immediately, then refresh in background
        if ProgramSwitcherDialog._apps_cache:
            self._set_apps(ProgramSwitcherDialog._apps_cache)
        self._start_bg_refresh()

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

    # --- Internal helpers ---

    def _set_apps(self, apps: list[str]) -> None:
        prev = self._selected_app
        self._apps = apps
        self._list.clear()
        if platform.system() == "Windows":
            from PySide6.QtWidgets import QFileIconProvider
            from PySide6.QtCore import QFileInfo
            _icon_provider = QFileIconProvider()
        for app in apps:
            from PySide6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(app)
            self._list.addItem(item)
        if apps:
            # Restore previous selection if possible
            try:
                idx = apps.index(prev)
            except ValueError:
                idx = 0
            self._selected = idx
            self._list.setCurrentRow(idx)
            self._selected_app = apps[idx]

    def _start_bg_refresh(self) -> None:
        import threading
        def _worker():
            from . import system_control
            apps = system_control.get_open_apps()
            ProgramSwitcherDialog._apps_cache = apps
            # Use a single-shot timer to update UI on main thread
            QTimer.singleShot(0, lambda: self._set_apps(apps) if self.isVisible() or not self._apps else None)
        threading.Thread(target=_worker, daemon=True).start()

    # --- Public methods called from MainWindow ---

    def refresh_apps(self) -> None:
        """Show cached apps immediately and refresh in background."""
        from . import system_control
        if not self._apps and ProgramSwitcherDialog._apps_cache:
            self._set_apps(ProgramSwitcherDialog._apps_cache)
        self._start_bg_refresh()

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
# Windows autostart helpers
# ---------------------------------------------------------------------------

_AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_AUTOSTART_NAME = "flx4control"


def _get_autostart() -> str:
    """Return 'off', 'on', or 'minimized'."""
    if platform.system() != "Windows":
        return "off"
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTOSTART_KEY) as k:
            val, _ = winreg.QueryValueEx(k, _AUTOSTART_NAME)
            if "--minimized" in val:
                return "minimized"
            return "on"
    except Exception:
        return "off"


def _set_autostart(mode: str) -> None:
    """mode: 'off' | 'on' | 'minimized'"""
    if platform.system() != "Windows":
        return
    try:
        import winreg
        import sys
        exe = sys.executable
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTOSTART_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if mode == "off":
                try:
                    winreg.DeleteValue(k, _AUTOSTART_NAME)
                except FileNotFoundError:
                    pass
            elif mode == "on":
                winreg.SetValueEx(k, _AUTOSTART_NAME, 0, winreg.REG_SZ, f'"{exe}" -m flx4control')
            elif mode == "minimized":
                winreg.SetValueEx(k, _AUTOSTART_NAME, 0, winreg.REG_SZ, f'"{exe}" -m flx4control --minimized')
    except Exception as exc:
        print(f"[autostart] {exc}")


def _mark_autostart_menu(off_act: QAction, on_act: QAction, min_act: QAction) -> None:
    state = _get_autostart()
    off_act.setCheckable(True)
    on_act.setCheckable(True)
    min_act.setCheckable(True)
    off_act.setChecked(state == "off")
    on_act.setChecked(state == "on")
    min_act.setChecked(state == "minimized")


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

        # --- Audio devices ---
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        form.addRow(sep2)

        # Microphone (input) device
        self.input_dev_combo = QComboBox()
        self.input_dev_combo.currentIndexChanged.connect(self._on_input_dev_changed)
        form.addRow("Microphone:", self.input_dev_combo)

        # Speaker (output) device
        self.output_dev_combo = QComboBox()
        self.output_dev_combo.currentIndexChanged.connect(self._on_output_dev_changed)
        form.addRow("Speaker:", self.output_dev_combo)

        refresh_btn = QPushButton("Refresh Devices")
        refresh_btn.setMaximumWidth(130)
        refresh_btn.clicked.connect(self._refresh_devices)
        form.addRow("", refresh_btn)

        # --- Deck button actions ---
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        form.addRow(sep3)

        self._btn_action_labels: dict[tuple, QLabel] = {}
        for deck in (1, 2):
            for btn_key, btn_display in (("PLAY_PAUSE", "Play/Pause"), ("CUE", "Cue")):
                lbl = QLabel(_action_label(self.config.get_button_action(deck, btn_key)))
                lbl.setStyleSheet("color: #aaa; min-width: 160px;")
                cfg_btn = QPushButton("Configure…")
                cfg_btn.setMaximumWidth(100)
                def _make_handler(d=deck, b=btn_key, l=lbl):
                    return lambda: self._configure_deck_button(d, b, l)
                cfg_btn.clicked.connect(_make_handler())
                row = QHBoxLayout()
                row.addWidget(lbl, 1)
                row.addWidget(cfg_btn)
                form.addRow(f"Deck {deck} — {btn_display}:", row)
                self._btn_action_labels[(deck, btn_key)] = lbl

        # Populate device lists
        self._refresh_devices()

    def _refresh_devices(self) -> None:
        from . import system_control

        saved_in = self.config.get_audio_input_device()
        saved_out = self.config.get_audio_output_device()

        # Rebuild input combo
        self.input_dev_combo.blockSignals(True)
        self.input_dev_combo.clear()
        self.input_dev_combo.addItem("System Default", None)
        self._input_devices: list = []
        for idx, name in system_control.list_audio_inputs():
            self.input_dev_combo.addItem(name, name)
            self._input_devices.append((idx, name))
        # Restore saved selection
        if saved_in:
            i = self.input_dev_combo.findText(saved_in)
            self.input_dev_combo.setCurrentIndex(max(0, i))
        self.input_dev_combo.blockSignals(False)

        # Rebuild output combo
        self.output_dev_combo.blockSignals(True)
        self.output_dev_combo.clear()
        self.output_dev_combo.addItem("System Default", None)
        self._output_devices: list = []
        for idx, name in system_control.list_audio_outputs():
            self.output_dev_combo.addItem(name, name)
            self._output_devices.append((idx, name))
        if saved_out:
            i = self.output_dev_combo.findText(saved_out)
            self.output_dev_combo.setCurrentIndex(max(0, i))
        self.output_dev_combo.blockSignals(False)

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

    def _on_input_dev_changed(self, idx: int) -> None:
        name = self.input_dev_combo.itemData(idx)  # None = system default
        self.config.set_audio_input_device(name)
        self.bridge.set_audio_devices(name, self.config.get_audio_output_device())

    def _on_output_dev_changed(self, idx: int) -> None:
        name = self.output_dev_combo.itemData(idx)
        self.config.set_audio_output_device(name)
        self.bridge.set_audio_devices(self.config.get_audio_input_device(), name)

    def _configure_deck_button(self, deck: int, button: str, label: QLabel) -> None:
        action = self.config.get_button_action(deck, button)
        dlg = PadConfigDialog(deck, 0, 0, action, self)
        dlg.setWindowTitle(f"Deck {deck} — {button.replace('_', '/')}")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_action = dlg.get_action()
            if new_action.get("type") == "sound" and new_action.get("source_path"):
                filename = self.config.import_sound_file(new_action["source_path"])
                new_action = {
                    "type": "sound",
                    "name": new_action.get("name", ""),
                    "file": filename,
                }
            self.config.set_button_action(deck, button, new_action)
            label.setText(_action_label(new_action))


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

        # Autostart submenu (Windows only)
        if platform.system() == "Windows":
            menu.addSeparator()
            autostart_menu = QMenu("Autostart", menu)
            off_act = QAction("Off", self)
            on_act = QAction("On (normal)", self)
            min_act = QAction("On (minimized)", self)
            off_act.triggered.connect(lambda: _set_autostart("off"))
            on_act.triggered.connect(lambda: _set_autostart("on"))
            min_act.triggered.connect(lambda: _set_autostart("minimized"))
            autostart_menu.addAction(off_act)
            autostart_menu.addAction(on_act)
            autostart_menu.addAction(min_act)
            # Check mark on current state
            _mark_autostart_menu(off_act, on_act, min_act)
            menu.addMenu(autostart_menu)

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
        self.bridge.pad_triggered.connect(self._on_pad_triggered)
        self.bridge.browse_turned.connect(self._on_browse_turned)
        self.bridge.program_load_pressed.connect(self._on_program_load)
        self.bridge.master_level_changed.connect(self._on_master_level)
        self.bridge.play_state_changed.connect(self._on_play_state_changed)
        self.bridge.volume_changed.connect(self._on_volume_changed)

        # Program switcher instance (created on demand)
        self._prog_switcher: Optional[ProgramSwitcherDialog] = None

        # Volume overlay
        self._vol_overlay = VolumeOverlay()

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
        # Switch the visible bank tab to match the controller
        self.bank_tabs.setCurrentIndex(tab)

    @Slot(int, int)
    def _on_pad_triggered(self, deck: int, pad: int) -> None:
        """Flash the pad in the GUI. If no action is configured, open config dialog."""
        bank = self.bridge.current_bank(deck)
        # Switch tab to the active bank
        self.bank_tabs.setCurrentIndex(bank)
        btn = self.pad_buttons.get((bank, deck, pad))
        if btn:
            btn.flash()
        # If pad has no action and the window is visible, open config
        action = self.config.get_pad_action(deck, bank, pad)
        if action.get("type", "none") == "none" and self.isVisible():
            self._open_pad_config(deck, bank, pad)

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

    @Slot(str, float)
    def _on_volume_changed(self, label: str, value: float) -> None:
        self._vol_overlay.show_volume(label, value)

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
# Windows first-run driver guide
# ---------------------------------------------------------------------------

class WindowsDriverGuideDialog(QDialog):
    """
    Shown once on first launch on Windows. Explains how to get the DDJ-FLX4
    recognised as a MIDI device and how to set up audio devices.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("DDJ-FLX4 — Windows Setup Guide")
        self.setMinimumWidth(540)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)

        # Header
        header = QLabel("Welcome to FLX4 Control")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #4dffaa;")
        root.addWidget(header)

        intro = QLabel(
            "Welcome! Here's what you need to know to get started on Windows."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #c0c0c0;")
        root.addWidget(intro)

        # Step 1
        step1 = QGroupBox("Step 1 — Connect the controller")
        s1l = QVBoxLayout(step1)
        s1l.addWidget(_guide_label(
            "The DDJ-FLX4 is <b>USB class-compliant</b> — no separate audio driver "
            "is required on Windows 10 or 11. If it already works with Rekordbox, "
            "it will work here too."
        ))
        s1l.addWidget(_guide_label("1. Connect the DDJ-FLX4 to your PC with a USB cable."))
        s1l.addWidget(_guide_label("2. Make sure the power switch on the controller is <b>ON</b>."))
        s1l.addWidget(_guide_label(
            "3. The app will detect it automatically within a few seconds and the "
            "status in the top bar will change to <b style='color:#4dffaa'>Connected</b>."
        ))
        root.addWidget(step1)

        # Step 2 — troubleshooting
        step2 = QGroupBox("Still not connecting?")
        s2l = QVBoxLayout(step2)
        s2l.addWidget(_guide_label(
            "If the controller stays <b style='color:#ff6644'>Not connected</b> even "
            "though it is plugged in and powered on, try the following:"
        ))
        s2l.addWidget(_guide_label("• Try a different USB cable or a different USB port."))
        s2l.addWidget(_guide_label(
            "• Close Rekordbox (or any other DJ software) — only one app can use "
            "the MIDI interface at a time."
        ))
        s2l.addWidget(_guide_label(
            "• Open <b>Device Manager</b> (Win+X → Device Manager) and check that "
            "<i>Pioneer DDJ-FLX4</i> appears under <i>Sound, video and game controllers</i>."
        ))
        s2l.addWidget(_guide_label(
            "• If the device shows a yellow warning icon, visit "
            "<b>pioneerdj.com</b> and download the Windows driver for the DDJ-FLX4."
        ))

        open_btn = QPushButton("Open Pioneer DJ Support Page")
        open_btn.clicked.connect(lambda: __import__("webbrowser").open(
            "https://www.pioneerdj.com/support/software/"
        ))
        open_btn.setStyleSheet(
            "QPushButton { background: #1a3a1a; color: #4dffaa; border: 1px solid #2a5a2a; "
            "border-radius: 4px; padding: 6px 14px; } "
            "QPushButton:hover { background: #1f4a1f; }"
        )
        s2l.addWidget(open_btn)
        root.addWidget(step2)

        # Step 3
        step3 = QGroupBox("Step 2 — Select your audio devices (optional)")
        s3l = QVBoxLayout(step3)
        s3l.addWidget(_guide_label(
            "If you want to use the <b>mic monitoring</b> feature (crossfader loopback), "
            "open the <b>Settings</b> panel and choose your <b>Microphone</b> and "
            "<b>Speaker</b> devices after the controller connects."
        ))
        root.addWidget(step3)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(self.accept)
        root.addWidget(btn_box)


def _guide_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color: #c0c0c0; margin-left: 4px;")
    lbl.setTextFormat(Qt.TextFormat.RichText)
    return lbl


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    # Single-instance guard: bind a local TCP port; second instance exits
    _lock_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _lock_sock.bind(("127.0.0.1", 47389))
        _lock_sock.listen(1)
    except OSError:
        print("[flx4control] Already running.")
        return 0

    start_minimized = "--minimized" in sys.argv

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

    # Apply saved audio devices to the loopback before connecting
    bridge.set_audio_devices(
        config.get_audio_input_device(),
        config.get_audio_output_device(),
    )

    window = MainWindow(config, bridge)
    if not start_minimized:
        window.show()

    # Show Windows driver guide on first launch
    if platform.system() == "Windows" and not config.is_driver_guide_shown():
        window.show()
        dlg = WindowsDriverGuideDialog(window)
        dlg.exec()
        config.mark_driver_guide_shown()

    ret = app.exec()
    bridge.stop()
    _lock_sock.close()
    return ret
