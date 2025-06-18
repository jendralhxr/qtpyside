import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QFileDialog, QSpinBox, QHBoxLayout
)
from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtGui import QFont, QPalette, QColor


class TimerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dual Timer Alarm")
        self.setGeometry(100, 100, 800, 600)

        self.init_ui()

        self.timer1_duration = 0
        self.timer2_duration = 0
        self.time_remaining = 0
        self.phase = 1  # 1 = first timer, 2 = second timer

        self.qtimer = QTimer()
        self.qtimer.timeout.connect(self.update_timer)

        self.audio_output = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)

        # Load audio from runtime arguments, if provided
        self.audio1 = None
        self.audio2 = None
        if len(sys.argv) > 2:
            self.audio1 = QUrl.fromLocalFile(sys.argv[1])
            self.audio2 = QUrl.fromLocalFile(sys.argv[2])
            self.audio1_button.setDisabled(True)
            self.audio2_button.setDisabled(True)

    def init_ui(self):
        layout = QVBoxLayout()

        self.timer_label = QLabel("00:00")
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setFont(QFont("Arial", 72))
        layout.addWidget(self.timer_label)

        # Timer duration controls
        control_layout = QHBoxLayout()

        self.spin1 = QSpinBox()
        self.spin1.setRange(1, 3600)
        self.spin1.setValue(5)
        control_layout.addWidget(QLabel("Timer 1 (s):"))
        control_layout.addWidget(self.spin1)

        self.spin2 = QSpinBox()
        self.spin2.setRange(1, 3600)
        self.spin2.setValue(3)
        control_layout.addWidget(QLabel("Timer 2 (s):"))
        control_layout.addWidget(self.spin2)

        layout.addLayout(control_layout)

        # Audio file selection
        audio_layout = QHBoxLayout()

        self.audio1_button = QPushButton("Select Audio 1")
        self.audio1_button.clicked.connect(self.select_audio1)
        audio_layout.addWidget(self.audio1_button)

        self.audio2_button = QPushButton("Select Audio 2")
        self.audio2_button.clicked.connect(self.select_audio2)
        audio_layout.addWidget(self.audio2_button)

        layout.addLayout(audio_layout)

        # Start button
        self.start_button = QPushButton("Start Timer")
        self.start_button.clicked.connect(self.start_timers)
        layout.addWidget(self.start_button)

        self.setLayout(layout)

    def select_audio1(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Audio File 1")
        if file:
            self.audio1 = QUrl.fromLocalFile(file)

    def select_audio2(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Audio File 2")
        if file:
            self.audio2 = QUrl.fromLocalFile(file)

    def start_timers(self):
        self.timer1_duration = self.spin1.value()
        self.timer2_duration = self.spin2.value()
        self.time_remaining = self.timer1_duration
        self.phase = 1
        self.set_label_color("blue")
        self.qtimer.start(1000)

    def update_timer(self):
        if self.time_remaining > 0:
            self.time_remaining -= 1
            self.update_display()
        else:
            self.qtimer.stop()
            if self.phase == 1:
                self.play_audio(self.audio1)
                self.phase = 2
                self.time_remaining = self.timer2_duration
                self.set_label_color("red")
                self.qtimer.start(1000)
            else:
                self.play_audio(self.audio2)

    def play_audio(self, audio_url):
        if audio_url:
            self.player.setSource(audio_url)
            self.player.play()

    def update_display(self):
        mins, secs = divmod(self.time_remaining, 60)
        self.timer_label.setText(f"{mins:02}:{secs:02}")

    def set_label_color(self, color_name):
        palette = self.timer_label.palette()
        palette.setColor(QPalette.WindowText, QColor(color_name))
        self.timer_label.setPalette(palette)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = TimerApp()
    win.showMaximized()
    sys.exit(app.exec())
