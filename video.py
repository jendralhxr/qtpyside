import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QVBoxLayout, QWidget,
    QPushButton, QSlider, QHBoxLayout
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtCore import QUrl, Qt, QTimer

class VideoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Player")

        # Set up the central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        # QVideoWidget to display the video
        self.video_widget = QVideoWidget()
        self.layout.addWidget(self.video_widget)

        # Media controls layout
        self.controls_layout = QHBoxLayout()
        self.layout.addLayout(self.controls_layout)

        # Play button
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.play_video)
        self.controls_layout.addWidget(self.play_button)

        # Pause button
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.pause_video)
        self.controls_layout.addWidget(self.pause_button)

        # Slider for seeking
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.set_position)
        self.layout.addWidget(self.slider)

        # Load button
        self.load_button = QPushButton("Load Video")
        self.load_button.clicked.connect(self.load_video)
        self.layout.addWidget(self.load_button)

        # QMediaPlayer to handle the video playback
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)

        # Connect media player signals to update the slider
        self.media_player.durationChanged.connect(self.update_duration)
        self.media_player.positionChanged.connect(self.update_position)

        # Timer to update the play/pause button states
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_play_pause_buttons)
        self.timer.start(100)  # Check every 100 ms

        # Set the video widget size to a fraction of the screen size
        self.video_widget.setFixedSize(320, 240)  # Example size, adjust as needed

    def load_video(self):
        # Open a file dialog to select a video file
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Video File", "", "Videos (*.mp4 *.avi *.mkv *.mov)")
        if file_name:
            self.media_player.setSource(QUrl.fromLocalFile(file_name))
            self.play_video()

    def play_video(self):
        if self.media_player.mediaStatus() != QMediaPlayer.NoMedia:
            self.media_player.play()

    def pause_video(self):
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.media_player.pause()

    def update_duration(self, duration):
        # Update the slider's range to the new video's duration
        self.slider.setRange(0, duration)

    def update_position(self, position):
        # Update the slider's position as the video plays
        self.slider.setValue(position)

    def set_position(self, position):
        # Seek to the position when the slider is moved
        self.media_player.setPosition(position)

    def update_play_pause_buttons(self):
        # Update button text based on media player state
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.play_button.setEnabled(False)
            self.pause_button.setEnabled(True)
        elif self.media_player.playbackState() == QMediaPlayer.PausedState:
            self.play_button.setEnabled(True)
            self.pause_button.setEnabled(False)
        else:
            self.play_button.setEnabled(True)
            self.pause_button.setEnabled(False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoWindow()
    window.show()
    sys.exit(app.exec())
