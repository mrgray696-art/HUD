import sys,json,keyboard
from datetime import datetime
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QCheckBox, QPushButton, QGridLayout, QGroupBox, QLabel, QComboBox, QSpinBox, QDoubleSpinBox)

class HotkeyThread(QThread):
    hotkey_pressed = pyqtSignal()
    def run(self):
        keyboard.add_hotkey('ctrl+shift+h', self.hotkey_pressed.emit)
        keyboard.wait()
    def stop(self):
        keyboard.unhook_all_hotkeys()
        self.quit()
        self.wait()

class SettingsWindow(QWidget):
    settings_changed = pyqtSignal(bool, bool)
    action_requested = pyqtSignal(str)
    audio_toggled = pyqtSignal(bool)
    device_changed = pyqtSignal(str)
    audio_params_changed = pyqtSignal(int, float, int)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HUD Settings")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        layout = QVBoxLayout()
        self.cb_top = QCheckBox("Always on Top (HUD)")
        self.cb_top.setChecked(True)
        self.cb_top.stateChanged.connect(self.emit_settings)
        layout.addWidget(self.cb_top)
        self.cb_ignore = QCheckBox("Ignore Inputs / Click-through (HUD)")
        self.cb_ignore.setChecked(False)
        self.cb_ignore.stateChanged.connect(self.emit_settings)
        layout.addWidget(self.cb_ignore)
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
        self.spin_bars.setValue(250)
        self.spin_bars.valueChanged.connect(self.emit_audio_params)
        param_layout.addWidget(self.spin_bars, 0, 1)
        param_layout.addWidget(QLabel("Sensitivity:"), 1, 0)
        self.spin_sens = QDoubleSpinBox()
        self.spin_sens.setRange(0.0001, 1000.0)
        self.spin_sens.setSingleStep(0.0001)
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
        layout.addWidget(audio_group)
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
        layout.addWidget(control_group)
        btn_quit = QPushButton("Quit Application")
        btn_quit.clicked.connect(QApplication.instance().quit)
        layout.addWidget(btn_quit)
        self.setLayout(layout)
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
        self.settings_changed.emit(self.cb_top.isChecked(), self.cb_ignore.isChecked())
    def emit_audio_params(self):
        self.audio_params_changed.emit(
            self.spin_bars.value(),
            self.spin_sens.value(),
            self.spin_fps.value()
        )
    def update_audio_stats(self, actual_fps, output_bands, nonempty_bands):
        self.audio_stats.setText(
            f"Actual: {actual_fps:.1f} FPS | Bands: {nonempty_bands}/{output_bands}"
        )

class HUDCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.audio_bands = [0] * 100
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update)
        self.clock_timer.start(1000)
    def set_audio_bands(self, bands):
        self.audio_bands = bands
        self.update()
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        accent = QColor(200, 0, 200)
        clock_font = QFont("Courier New", 32, QFont.Weight.Bold)
        painter.setFont(clock_font)
        clock_y = self.height() - 30
        clock_text = datetime.now().strftime("%H:%M:%S")
        for offset, alpha in ((-2, 28), (-1, 56), (1, 56), (2, 28)):
            glow = QColor(accent)
            glow.setAlpha(alpha)
            painter.setPen(glow)
            painter.drawText(20 + offset, clock_y, clock_text)
        painter.setPen(accent)
        painter.drawText(20, clock_y, clock_text)
        bands = self.audio_bands
        if not bands:
            return
        visualizer_height = 250
        visualizer_bottom = self.height() - 80
        visualizer_top = visualizer_bottom - visualizer_height
        gap = 2
        bar_width = max(0, (self.width() - gap * (len(bands) - 1)) / len(bands))
        for index, band in enumerate(bands):
            value = max(0, min(100, band))
            bar_height = visualizer_height * value / 100
            color = QColor(accent)
            color.setAlpha(round(255 * min(1, value / 100 + 0.4)))
            painter.fillRect(
                round(index * (bar_width + gap)),
                round(visualizer_top + visualizer_height - bar_height),
                max(1, round(bar_width)),
                round(bar_height),
                color,
            )

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
        if always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        if ignore_inputs:
            flags |= Qt.WindowType.WindowTransparentForInput
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
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()
            return
        if self.isMaximized():
            self.showNormal()
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
    def update_audio_ram(self, json_bands):
        self.canvas.set_audio_bands(json.loads(json_bands))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    settings = SettingsWindow()
    hud = HUDWindow(settings)
    audio_thread = None
    settings.action_requested.connect(hud.handle_action)
    settings.settings_changed.connect(lambda top, ignore: hud.apply_flags(top, ignore))
    def on_audio_toggled(enabled):
        global audio_thread
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
            settings.combo_device.setEnabled(True)
        else:
            if audio_thread:
                audio_thread.stop()
                audio_thread = None
            settings.combo_device.setEnabled(False)
            settings.audio_stats.setText("Audio off")
            hud.update_audio_ram(json.dumps([0] * settings.spin_bars.value()))
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