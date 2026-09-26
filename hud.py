import sys, datetime, json, os, keyboard
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PyQt6.QtWidgets import QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget

class HotkeyThread(QThread):
    hotkey_pressed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._hotkey_registered = False

    def run(self):
        try:
            keyboard.add_hotkey("ctrl+shift+h", self.hotkey_pressed.emit)
            self._hotkey_registered = True
            keyboard.wait()
        except Exception as exc:
            print(f"Hotkey Error: {exc}")
        finally:
            self._hotkey_registered = False

    def stop(self):
        try:
            keyboard.remove_hotkey("ctrl+shift+h")
        except Exception:
            pass

        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass

        try:
            keyboard.stop()
        except Exception:
            pass

        self.quit()
        self.wait()


def default_style():
    return {
        "clock_x": 0,
        "clock_y": 0,
        "clock_z": 1,
        "clock_font_size": 32,
        "clock_font_family": "Courier New",
        "clock_color": "#FF00FF",
        "clock_opacity": 0.75,
        "clock_24h": False,
        "clock_enabled": True,
        "bar_x": 0,
        "bar_y": 0,
        "bar_z": 0,
        "bar_height": 100,
        "bar_total_width": 100,
        "bar_color": "#C800C8",
        "bar_opacity": 0.5,
        "bar_mirror_vertical": True,
        "bar_mirror_horizontal": True,
        "bar_mirror_both": True,
    }


def compute_bar_dimensions(total_width, count):
    count = max(1, count)
    slot = total_width / count
    gap = max(0, round(slot * 0.2)) if count > 1 else 0
    gap = min(gap, max(0, slot - 1))
    thickness = max(1, slot - gap)
    return thickness, gap


SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hud_settings.json")

GENERAL_DEFAULTS = {
    "always_on_top": True,
    "ignore_inputs": False,
    "audio_enabled": False,
    "audio_device": "",
    "audio_bars": 64,
    "audio_sensitivity": 1.0,
    "audio_fps": 60,
}


def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
    except OSError as exc:
        print(f"Failed to save settings: {exc}")


class HexByteSpinBox(QSpinBox):
    def __init__(self):
        super().__init__()
        self.setRange(0, 255)
        self.setDisplayIntegerBase(16)

    def textFromValue(self, value):
        return f"{value:02X}"

    def valueFromText(self, text):
        try:
            return int(text, 16)
        except ValueError:
            return 0


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    try:
        return int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    except (ValueError, IndexError):
        return 0, 0, 0


def rgb_to_hex(r, g, b):
    return f"#{r:02X}{g:02X}{b:02X}"


class SettingsWindow(QWidget):
    settings_changed = pyqtSignal(bool, bool)
    action_requested = pyqtSignal(str)
    audio_toggled = pyqtSignal(bool)
    device_changed = pyqtSignal(str)
    audio_params_changed = pyqtSignal(int, float, int)
    style_changed = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HUD Settings")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.style = default_style()
        root = QVBoxLayout(self)
        tab_widget = QTabWidget(self)
        root.addWidget(tab_widget)
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        self.cb_top = QCheckBox("Always on Top (HUD)")
        self.cb_top.setChecked(True)
        self.cb_top.stateChanged.connect(self.emit_settings)
        general_layout.addWidget(self.cb_top)
        self.cb_ignore = QCheckBox("Ignore Inputs / Click-through (HUD)")
        self.cb_ignore.setChecked(False)
        self.cb_ignore.stateChanged.connect(self.emit_settings)
        general_layout.addWidget(self.cb_ignore)
        control_group = QGroupBox("Window Positioning")
        grid = QGridLayout()
        grid.setSpacing(2)
        def make_btn(text, action):
            btn = QPushButton(text)
            btn.setFixedSize(60, 30)
            btn.setAutoRepeat(True)
            btn.setAutoRepeatDelay(250)
            btn.setAutoRepeatInterval(15)
            btn.clicked.connect(lambda checked, a=action: self.action_requested.emit(a))
            return btn
        btn_max = QPushButton("Max / Res")
        btn_max.setFixedSize(70, 40)
        btn_max.clicked.connect(lambda: self.action_requested.emit("toggle_maximize"))
        grid.addWidget(btn_max, 3, 3, alignment=Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(make_btn("Grow", "grow_top"), 0, 3)
        grid.addWidget(make_btn("Shrink", "shrink_top"), 1, 3)
        grid.addWidget(make_btn("↑ Move", "move_up"), 2, 3)
        grid.addWidget(make_btn("Move ↓", "move_down"), 4, 3)
        grid.addWidget(make_btn("Shrink", "shrink_bottom"), 5, 3)
        grid.addWidget(make_btn("Grow", "grow_bottom"), 6, 3)
        grid.addWidget(make_btn("Grow", "grow_left"), 3, 0)
        grid.addWidget(make_btn("Shrink", "shrink_left"), 3, 1)
        grid.addWidget(make_btn("← Move", "move_left"), 3, 2)
        grid.addWidget(make_btn("Move →", "move_right"), 3, 4)
        grid.addWidget(make_btn("Shrink", "shrink_right"), 3, 5)
        grid.addWidget(make_btn("Grow", "grow_right"), 3, 6)
        control_group.setLayout(grid)
        general_layout.addWidget(control_group)
        center_group = QGroupBox("Center Window on Screen")
        center_layout = QHBoxLayout()
        btn_center_window_x = QPushButton("Center Horizontally")
        btn_center_window_x.clicked.connect(lambda: self.action_requested.emit("center_window_x"))
        center_layout.addWidget(btn_center_window_x)
        btn_center_window_y = QPushButton("Center Vertically")
        btn_center_window_y.clicked.connect(lambda: self.action_requested.emit("center_window_y"))
        center_layout.addWidget(btn_center_window_y)
        center_group.setLayout(center_layout)
        general_layout.addWidget(center_group)
        btn_quit = QPushButton("Quit Application")
        btn_quit.clicked.connect(QApplication.instance().quit)
        general_layout.addWidget(btn_quit)

        tab_widget.addTab(general_tab, "General")

        clock_tab = QWidget()
        clock_layout = QVBoxLayout(clock_tab)
        clock_group = QGroupBox("Clock")
        clock_grid = QGridLayout(clock_group)
        clock_grid.addWidget(QLabel("Position:"), 0, 0)
        self.clock_x = QSpinBox(); self.clock_x.setRange(-2000, 2000); self.clock_x.setValue(self.style["clock_x"]); self.clock_x.valueChanged.connect(self.emit_style_settings); clock_grid.addWidget(self.clock_x, 0, 1)
        clock_grid.addWidget(QLabel("X"), 0, 2)
        self.clock_y = QSpinBox(); self.clock_y.setRange(-2000, 2000); self.clock_y.setValue(self.style["clock_y"]); self.clock_y.valueChanged.connect(self.emit_style_settings); clock_grid.addWidget(self.clock_y, 0, 3)
        clock_grid.addWidget(QLabel("Y"), 0, 4)
        self.clock_z = QSpinBox(); self.clock_z.setRange(-2000, 2000); self.clock_z.setValue(self.style["clock_z"]); self.clock_z.valueChanged.connect(self.emit_style_settings); clock_grid.addWidget(self.clock_z, 0, 5)
        clock_grid.addWidget(QLabel("Z"), 0, 6)
        clock_grid.addWidget(QLabel("Font:"), 1, 0)
        self.clock_font = QComboBox(); self.clock_font.addItems(["Courier New", "Arial", "Consolas", "Segoe UI", "Verdana"]); self.clock_font.setCurrentText(self.style["clock_font_family"]); self.clock_font.currentTextChanged.connect(self.emit_style_settings); clock_grid.addWidget(self.clock_font, 1, 1, 1, 2)
        self.clock_font_size = QSpinBox(); self.clock_font_size.setRange(8, 120); self.clock_font_size.setValue(self.style["clock_font_size"]); self.clock_font_size.valueChanged.connect(self.emit_style_settings); clock_grid.addWidget(self.clock_font_size, 1, 3)
        clock_r, clock_g, clock_b = hex_to_rgb(self.style["clock_color"])
        self.clock_color_r = HexByteSpinBox(); self.clock_color_r.setValue(clock_r); self.clock_color_r.valueChanged.connect(self.emit_style_settings)
        self.clock_color_g = HexByteSpinBox(); self.clock_color_g.setValue(clock_g); self.clock_color_g.valueChanged.connect(self.emit_style_settings)
        self.clock_color_b = HexByteSpinBox(); self.clock_color_b.setValue(clock_b); self.clock_color_b.valueChanged.connect(self.emit_style_settings)
        clock_color_row = QHBoxLayout(); clock_color_row.addWidget(self.clock_color_r); clock_color_row.addWidget(self.clock_color_g); clock_color_row.addWidget(self.clock_color_b)
        clock_grid.addLayout(clock_color_row, 1, 4)
        self.clock_opacity = QDoubleSpinBox(); self.clock_opacity.setRange(0.01, 1.0); self.clock_opacity.setSingleStep(0.01); self.clock_opacity.setValue(self.style["clock_opacity"]); self.clock_opacity.valueChanged.connect(self.emit_style_settings); clock_grid.addWidget(self.clock_opacity, 1, 5)
        self.clock_24h = QCheckBox("24-Hour Format"); self.clock_24h.setChecked(self.style["clock_24h"]); self.clock_24h.stateChanged.connect(self.emit_style_settings); clock_grid.addWidget(self.clock_24h, 2, 0, 1, 3)
        self.clock_enabled = QCheckBox("Enable Clock"); self.clock_enabled.setChecked(self.style["clock_enabled"]); self.clock_enabled.stateChanged.connect(self.emit_style_settings); clock_grid.addWidget(self.clock_enabled, 2, 3, 1, 2)
        btn_center_clock_x = QPushButton("Center Horizontally")
        btn_center_clock_x.clicked.connect(lambda: self.action_requested.emit("center_clock_x"))
        clock_grid.addWidget(btn_center_clock_x, 3, 0, 1, 3)
        btn_center_clock_y = QPushButton("Center Vertically")
        btn_center_clock_y.clicked.connect(lambda: self.action_requested.emit("center_clock_y"))
        clock_grid.addWidget(btn_center_clock_y, 3, 3, 1, 3)

        clock_layout.addWidget(clock_group)
        tab_widget.addTab(clock_tab, "Clock")
        bar_tab = QWidget()
        bar_layout = QVBoxLayout(bar_tab)
        bar_group = QGroupBox("Audio Bars")
        bar_grid = QGridLayout(bar_group)
        bar_grid.addWidget(QLabel("Position:"), 0, 0)
        self.bar_x = QSpinBox(); self.bar_x.setRange(-2000, 2000); self.bar_x.setValue(self.style["bar_x"]); self.bar_x.valueChanged.connect(self.emit_style_settings); bar_grid.addWidget(self.bar_x, 0, 1)
        bar_grid.addWidget(QLabel("X"), 0, 2)
        self.bar_y = QSpinBox(); self.bar_y.setRange(-2000, 2000); self.bar_y.setValue(self.style["bar_y"]); self.bar_y.valueChanged.connect(self.emit_style_settings); bar_grid.addWidget(self.bar_y, 0, 3)
        bar_grid.addWidget(QLabel("Y"), 0, 4)
        self.bar_z = QSpinBox(); self.bar_z.setRange(-2000, 2000); self.bar_z.setValue(self.style["bar_z"]); self.bar_z.valueChanged.connect(self.emit_style_settings); bar_grid.addWidget(self.bar_z, 0, 5)
        bar_grid.addWidget(QLabel("Z"), 0, 6)
        bar_grid.addWidget(QLabel("Size:"), 1, 0)
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        self.bar_height = QSpinBox(); self.bar_height.setRange(20, screen_geometry.height()); self.bar_height.setValue(self.style["bar_height"]); self.bar_height.valueChanged.connect(self.emit_style_settings); bar_grid.addWidget(self.bar_height, 1, 1)
        bar_grid.addWidget(QLabel("H"), 1, 2)
        self.bar_total_width = QSpinBox(); self.bar_total_width.setRange(20, screen_geometry.width()); self.bar_total_width.setValue(self.style["bar_total_width"]); self.bar_total_width.valueChanged.connect(self.emit_style_settings); self.bar_total_width.valueChanged.connect(self.update_bar_actuals); bar_grid.addWidget(self.bar_total_width, 1, 3)
        bar_grid.addWidget(QLabel("W"), 1, 4)
        self.bar_thickness_actual = QLabel()
        bar_grid.addWidget(QLabel("Bar Thickness:"), 2, 0)
        bar_grid.addWidget(self.bar_thickness_actual, 2, 1)
        self.bar_gap_actual = QLabel()
        bar_grid.addWidget(QLabel("Bar Gap:"), 2, 2)
        bar_grid.addWidget(self.bar_gap_actual, 2, 3)
        bar_grid.addWidget(QLabel("Color:"), 3, 0)
        bar_r, bar_g, bar_b = hex_to_rgb(self.style["bar_color"])
        self.bar_color_r = HexByteSpinBox(); self.bar_color_r.setValue(bar_r); self.bar_color_r.valueChanged.connect(self.emit_style_settings)
        self.bar_color_g = HexByteSpinBox(); self.bar_color_g.setValue(bar_g); self.bar_color_g.valueChanged.connect(self.emit_style_settings)
        self.bar_color_b = HexByteSpinBox(); self.bar_color_b.setValue(bar_b); self.bar_color_b.valueChanged.connect(self.emit_style_settings)
        bar_color_row = QHBoxLayout(); bar_color_row.addWidget(self.bar_color_r); bar_color_row.addWidget(self.bar_color_g); bar_color_row.addWidget(self.bar_color_b)
        bar_grid.addLayout(bar_color_row, 3, 1)
        self.bar_opacity = QDoubleSpinBox(); self.bar_opacity.setRange(0.01, 1.0); self.bar_opacity.setSingleStep(0.01); self.bar_opacity.setValue(self.style["bar_opacity"]); self.bar_opacity.valueChanged.connect(self.emit_style_settings); bar_grid.addWidget(self.bar_opacity, 3, 2)
        self.bar_mirror_vertical = QCheckBox("Mirror Vertically"); self.bar_mirror_vertical.setChecked(self.style["bar_mirror_vertical"]); self.bar_mirror_vertical.stateChanged.connect(self.emit_style_settings); self.bar_mirror_vertical.stateChanged.connect(self.update_bar_actuals)
        self.bar_mirror_horizontal = QCheckBox("Mirror Horizontally"); self.bar_mirror_horizontal.setChecked(self.style["bar_mirror_horizontal"]); self.bar_mirror_horizontal.stateChanged.connect(self.emit_style_settings); self.bar_mirror_horizontal.stateChanged.connect(self.update_bar_actuals)
        self.bar_mirror_both = QCheckBox("Mirror Both (Diagonal)"); self.bar_mirror_both.setChecked(self.style["bar_mirror_both"]); self.bar_mirror_both.stateChanged.connect(self.emit_style_settings); self.bar_mirror_both.stateChanged.connect(self.update_bar_actuals)
        mirror_row = QGridLayout(); mirror_row.addWidget(self.bar_mirror_vertical, 0, 0); mirror_row.addWidget(self.bar_mirror_horizontal, 0, 1); mirror_row.addWidget(self.bar_mirror_both, 0, 2)
        bar_grid.addLayout(mirror_row, 4, 0, 1, 7)
        btn_center_bars_x = QPushButton("Center Horizontally")
        btn_center_bars_x.clicked.connect(lambda: self.action_requested.emit("center_bars_x"))
        bar_grid.addWidget(btn_center_bars_x, 5, 0, 1, 3)
        btn_center_bars_y = QPushButton("Center Vertically")
        btn_center_bars_y.clicked.connect(lambda: self.action_requested.emit("center_bars_y"))
        bar_grid.addWidget(btn_center_bars_y, 5, 3, 1, 3)
        bar_layout.addWidget(bar_group)
        audio_group = QGroupBox("Audio Visualizer Settings")
        audio_layout = QVBoxLayout()
        self.cb_audio = QCheckBox("Enable Audio Visualizer")
        self.cb_audio.setChecked(False)
        self.cb_audio.stateChanged.connect(lambda: self.audio_toggled.emit(self.cb_audio.isChecked()))
        audio_layout.addWidget(self.cb_audio)
        audio_layout.addWidget(QLabel("Select Device:"))
        self.combo_device = QComboBox()
        self.combo_device.setEnabled(False)
        self.combo_device.currentTextChanged.connect(lambda text: self.device_changed.emit(text))
        audio_layout.addWidget(self.combo_device)
        param_layout = QGridLayout()
        param_layout.addWidget(QLabel("Bars:"), 0, 0)
        self.spin_bars = QSpinBox()
        self.spin_bars.setRange(1, 1025)
        self.spin_bars.setValue(64)
        self.spin_bars.valueChanged.connect(self.emit_audio_params)
        self.spin_bars.valueChanged.connect(lambda: self.update_bar_actuals())
        param_layout.addWidget(self.spin_bars, 0, 1)
        param_layout.addWidget(QLabel("Sensitivity:"), 1, 0)
        self.spin_sens = QDoubleSpinBox()
        self.spin_sens.setRange(0.01, 10.0)
        self.spin_sens.setSingleStep(0.01)
        self.spin_sens.setValue(1.0)
        self.spin_sens.valueChanged.connect(self.emit_audio_params)
        param_layout.addWidget(self.spin_sens, 1, 1)
        param_layout.addWidget(QLabel("Target FPS:"), 2, 0)
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 60)
        self.spin_fps.setValue(60)
        self.spin_fps.valueChanged.connect(self.emit_audio_params)
        param_layout.addWidget(self.spin_fps, 2, 1)
        audio_layout.addLayout(param_layout)
        self.audio_stats = QLabel("Audio off")
        audio_layout.addWidget(self.audio_stats)
        audio_group.setLayout(audio_layout)
        bar_layout.addWidget(audio_group)
        self.update_bar_actuals()
        self.audio_controls = [
            self.combo_device,
            self.spin_bars,
            self.spin_sens,
            self.spin_fps,
        ]
        self.set_audio_controls_enabled(False)
        tab_widget.addTab(bar_tab, "Audio Bars")
        root.addWidget(tab_widget)

    def get_style(self):
        return {
            "clock_x": self.clock_x.value(),
            "clock_y": self.clock_y.value(),
            "clock_z": self.clock_z.value(),
            "clock_font_size": self.clock_font_size.value(),
            "clock_font_family": self.clock_font.currentText(),
            "clock_color": rgb_to_hex(self.clock_color_r.value(), self.clock_color_g.value(), self.clock_color_b.value()),
            "clock_opacity": self.clock_opacity.value(),
            "clock_24h": self.clock_24h.isChecked(),
            "clock_enabled": self.clock_enabled.isChecked(),
            "bar_x": self.bar_x.value(),
            "bar_y": self.bar_y.value(),
            "bar_z": self.bar_z.value(),
            "bar_height": self.bar_height.value(),
            "bar_total_width": self.bar_total_width.value(),
            "bar_color": rgb_to_hex(self.bar_color_r.value(), self.bar_color_g.value(), self.bar_color_b.value()),
            "bar_opacity": self.bar_opacity.value(),
            "bar_mirror_vertical": self.bar_mirror_vertical.isChecked(),
            "bar_mirror_horizontal": self.bar_mirror_horizontal.isChecked(),
            "bar_mirror_both": self.bar_mirror_both.isChecked(),
        }

    def emit_style_settings(self):
        self.style = self.get_style()
        self.style_changed.emit(self.style.copy())

    def update_bar_actuals(self):
        columns = 2 if (self.bar_mirror_horizontal.isChecked() or self.bar_mirror_both.isChecked()) else 1
        quadrant_width = self.bar_total_width.value() / columns
        thickness, gap = compute_bar_dimensions(quadrant_width, self.spin_bars.value())
        self.bar_thickness_actual.setText(f"{thickness:.1f} px")
        self.bar_gap_actual.setText(f"{gap:.1f} px")

    def set_audio_controls_enabled(self, enabled):
        for widget in self.audio_controls:
            widget.setEnabled(enabled)

    def populate_devices(self, devices):
        current = self.combo_device.currentText()
        self.combo_device.blockSignals(True)
        self.combo_device.clear()
        self.combo_device.addItems(devices)
        if current in devices:
            self.combo_device.setCurrentText(current)
        self.combo_device.blockSignals(False)
        if self.combo_device.currentText():
            self.device_changed.emit(self.combo_device.currentText())

    def emit_settings(self):
        self.settings_changed.emit(
            self.cb_top.isChecked(),
            self.cb_ignore.isChecked(),
        )

    def emit_audio_params(self):
        self.audio_params_changed.emit(
            self.spin_bars.value(),
            self.spin_sens.value(),
            self.spin_fps.value(),
        )

    def update_audio_stats(self, actual_fps, output_bands, nonempty_bands):
        self.audio_stats.setText(
            f"Actual: {actual_fps:.1f} FPS | Bands: {nonempty_bands}/{output_bands}"
        )


class HUDCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.audio_bands = [0] * 100
        self.style = default_style()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update)
        self.clock_timer.start(1000)

    def apply_style(self, style):
        self.style.update(style)
        self.update()

    def set_audio_bands(self, bands):
        self.audio_bands = bands if bands else [0] * max(1, len(self.audio_bands))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        def draw_clock():
            if not self.style.get("clock_enabled", True):
                return
            fmt = "%H:%M:%S" if self.style.get("clock_24h", True) else "%I:%M:%S %p"
            clock_text = datetime.datetime.now().strftime(fmt)
            clock_color = QColor(self.style["clock_color"])
            clock_font = QFont(self.style["clock_font_family"], self.style["clock_font_size"], QFont.Weight.Bold)
            painter.setFont(clock_font)
            clock_x = self.style["clock_x"]
            clock_y = self.style["clock_y"] + painter.fontMetrics().ascent()
            clock_opacity = max(0.1, min(1.0, self.style.get("clock_opacity", 1.0)))
            clock_color.setAlpha(round(255 * clock_opacity))
            painter.setPen(clock_color)
            painter.drawText(clock_x, clock_y, clock_text)

        def draw_bars():
            bands = self.audio_bands
            if not bands: return
            mirror_v = self.style.get("bar_mirror_vertical", False)
            mirror_h = self.style.get("bar_mirror_horizontal", False)
            mirror_both = self.style.get("bar_mirror_both", False)
            columns = 2 if (mirror_h or mirror_both) else 1
            rows = 2 if (mirror_v or mirror_both) else 1
            base_x = self.style["bar_x"]
            base_y = self.style["bar_y"]
            quadrant_width = self.style["bar_total_width"] / columns
            quadrant_height = self.style["bar_height"] / rows
            bar_width, gap = compute_bar_dimensions(quadrant_width, len(bands))
            bar_color = QColor(self.style["bar_color"])
            def draw_quadrant(col, row, flip_x, flip_y):
                quad_x = base_x + col * quadrant_width
                quad_y = base_y + row * quadrant_height
                for index, band in enumerate(bands):
                    value = max(0, min(100, band))
                    bar_height = quadrant_height * value / 100
                    slot = index * (bar_width + gap)
                    x = quad_x + (quadrant_width - slot - bar_width) if flip_x else quad_x + slot
                    y = quad_y if flip_y else quad_y + quadrant_height - bar_height
                    color = QColor(bar_color)
                    color.setAlpha(round(255 * self.style["bar_opacity"] * min(1, value / 100 + 0.4)))
                    painter.fillRect(round(x), round(y), max(1, round(bar_width)), round(bar_height), color)

            draw_quadrant(columns - 1, 0, False, False)
            if mirror_h:
                draw_quadrant(0, 0, True, False)
            if mirror_v:
                draw_quadrant(columns - 1, rows - 1, False, True)
            if mirror_both:
                draw_quadrant(0, rows - 1, True, True)

        layers = sorted(
            ((self.style.get("clock_z", 0), draw_clock), (self.style.get("bar_z", 0), draw_bars)),
            key=lambda layer: layer[0],
        )
        for _, draw in layers:
            draw()


class HUDWindow(QMainWindow):
    def __init__(self, settings_window):
        super().__init__()
        self.settings_window = settings_window
        self.setWindowTitle("Transparent HUD")
        self.base_flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.canvas = HUDCanvas()
        self.setCentralWidget(self.canvas)
        self.resize(800, 600)
        self.apply_flags(always_on_top=True, ignore_inputs=False)

    def apply_flags(self, always_on_top, ignore_inputs):
        flags = self.base_flags
        if always_on_top: flags |= Qt.WindowType.WindowStaysOnTopHint
        if ignore_inputs: flags |= Qt.WindowType.WindowTransparentForInput
        self.hide()
        self.setWindowFlags(flags)
        self.show()
        if self.settings_window.isVisible():
            self.settings_window.raise_()
            self.settings_window.activateWindow()

    def changeEvent(self, event):
        if event.type() == event.Type.ActivationChange:
            if self.isActiveWindow() and self.settings_window.isVisible():
                self.settings_window.raise_()
        super().changeEvent(event)

    def handle_action(self, action):
        if action == "toggle_maximize":
            if self.isMaximized(): self.showNormal()
            else: self.showMaximized()
            return
        if action in ("center_window_x", "center_window_y"):
            self.center_window(action)
            return
        if action in ("center_clock_x", "center_clock_y", "center_bars_x", "center_bars_y"):
            self.center_content(action)
            return
        if self.isMaximized(): self.showNormal()
        rect = self.geometry()
        if action == "move_up": rect.translate(0, -1)
        elif action == "move_down": rect.translate(0, 1)
        elif action == "move_left": rect.translate(-1, 0)
        elif action == "move_right": rect.translate(1, 0)
        elif action == "grow_top": rect.setTop(rect.top() - 1)
        elif action == "grow_bottom": rect.setBottom(rect.bottom() + 1)
        elif action == "grow_left": rect.setLeft(rect.left() - 1)
        elif action == "grow_right": rect.setRight(rect.right() + 1)
        elif action == "shrink_top": rect.setTop(rect.top() + 1)
        elif action == "shrink_bottom": rect.setBottom(rect.bottom() - 1)
        elif action == "shrink_left": rect.setLeft(rect.left() + 1)
        elif action == "shrink_right": rect.setRight(rect.right() - 1)
        self.setGeometry(rect)

    def center_window(self, action):
        screen = QApplication.primaryScreen().availableGeometry()
        rect = self.geometry()
        if action == "center_window_x": rect.moveLeft(screen.x() + (screen.width() - rect.width()) // 2)
        else: rect.moveTop(screen.y() + (screen.height() - rect.height()) // 2)
        self.setGeometry(rect)

    def center_content(self, action):
        style = self.settings_window.get_style()
        canvas_width = self.canvas.width()
        canvas_height = self.canvas.height()
        if action in ("center_clock_x", "center_clock_y"):
            font = QFont(style["clock_font_family"], style["clock_font_size"], QFont.Weight.Bold)
            metrics = QFontMetrics(font)
            fmt = "%H:%M:%S" if style.get("clock_24h", True) else "%I:%M:%S %p"
            text = datetime.datetime.now().strftime(fmt)
            if action == "center_clock_x": self.settings_window.clock_x.setValue(round((canvas_width - metrics.horizontalAdvance(text)) / 2))
            else: self.settings_window.clock_y.setValue(round((canvas_height - metrics.height()) / 2))
        else:
            if action == "center_bars_x": self.settings_window.bar_x.setValue(round((canvas_width - style["bar_total_width"]) / 2))
            else: self.settings_window.bar_y.setValue(round((canvas_height - style["bar_height"]) / 2))

    def update_audio_ram(self, bands):
        self.canvas.set_audio_bands(bands)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    settings = SettingsWindow()
    hud = HUDWindow(settings)
    hud.canvas.apply_style(settings.get_style())
    audio_thread = None
    settings.action_requested.connect(hud.handle_action)
    settings.settings_changed.connect(lambda top, ignore: hud.apply_flags(top, ignore))
    settings.style_changed.connect(hud.canvas.apply_style)

    def on_audio_toggled(enabled):
        global audio_thread
        settings.set_audio_controls_enabled(enabled)
        if enabled:
            settings.audio_stats.setText("Waiting for audio...")
            import audio_module
            bars = settings.spin_bars.value()
            sens = settings.spin_sens.value()
            fps = settings.spin_fps.value()
            audio_thread = audio_module.AudioThread(num_bars=bars, sensitivity=sens, fps=fps)
            audio_thread.audio_data_ready.connect(hud.update_audio_ram)
            audio_thread.devices_ready.connect(settings.populate_devices)
            audio_thread.stats_ready.connect(settings.update_audio_stats)
            if settings.combo_device.currentText():
                audio_thread.set_device(settings.combo_device.currentText())
            audio_thread.start()
        else:
            if audio_thread:
                audio_thread.stop()
                audio_thread = None
            settings.audio_stats.setText("Audio off")
            hud.update_audio_ram([0] * settings.spin_bars.value())

    def on_device_changed(device_name):
        if audio_thread and device_name:
            audio_thread.set_device(device_name)

    def on_audio_params_changed(bars, sens, fps):
        if audio_thread:
            audio_thread.update_parameters(bars, sens, fps)

    settings.audio_toggled.connect(on_audio_toggled)
    settings.device_changed.connect(on_device_changed)
    settings.audio_params_changed.connect(on_audio_params_changed)
    hotkey_thread = HotkeyThread()
    hotkey_thread.hotkey_pressed.connect(lambda: (settings.show(), settings.raise_(), settings.activateWindow()))
    hotkey_thread.start()
    hud.show()
    settings.show()
    exit_code = app.exec()
    if audio_thread:
        audio_thread.stop()
        audio_thread = None
    if hotkey_thread:
        hotkey_thread.stop()
        hotkey_thread = None
    sys.exit(exit_code)