import sys
import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)
from superqt import QRangeSlider


class ColorTrackerApp(QMainWindow):
    def __init__(self, camera_index: int = 0):
        super().__init__()
        self.setWindowTitle("Real-Time Color Object Tracker (RGB / HSV)")
        self.resize(1280, 720)

        # Initialize USB Camera
        self.cap = cv2.VideoCapture(camera_index)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open USB camera at index {camera_index}")

        self.color_space = "HSV"
        self.channel_labels = []
        self.sliders = []
        self.value_labels = []

        self._init_ui()

        # Timer for ~30 FPS video loop
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Top Bar: Color Space Selector ---
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("<b>Color Space:</b>"))

        self.space_selector = QComboBox()
        self.space_selector.addItems(["HSV", "RGB"])
        self.space_selector.currentTextChanged.connect(self.on_color_space_changed)
        top_bar.addWidget(self.space_selector)
        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        # --- Middle Area: Side-by-Side Video Feeds ---
        video_layout = QHBoxLayout()

        self.input_label = QLabel("Waiting for camera...")
        self.input_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_label.setStyleSheet("background-color: #1e1e1e; color: white;")
        self.input_label.setMinimumSize(480, 360)

        self.output_label = QLabel("Processed Output")
        self.output_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.output_label.setStyleSheet("background-color: #1e1e1e; color: white;")
        self.output_label.setMinimumSize(480, 360)

        video_layout.addWidget(self.input_label, stretch=1)
        video_layout.addWidget(self.output_label, stretch=1)
        main_layout.addLayout(video_layout, stretch=1)

        # --- Bottom Area: Three Two-Handle Range Sliders (0-255) ---
        sliders_layout = QVBoxLayout()
        initial_names = ["H (Hue)", "S (Sat)", "V (Val)"]

        for i in range(3):
            row = QHBoxLayout()

            name_lbl = QLabel(initial_names[i])
            name_lbl.setFixedWidth(90)
            self.channel_labels.append(name_lbl)

            slider = QRangeSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 255)
            slider.setValue((0, 255))
            slider.valueChanged.connect(lambda val, idx=i: self.on_slider_changed(idx, val))
            self.sliders.append(slider)

            val_lbl = QLabel("0 - 255")
            val_lbl.setFixedWidth(80)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.value_labels.append(val_lbl)

            row.addWidget(name_lbl)
            row.addWidget(slider)
            row.addWidget(val_lbl)
            sliders_layout.addLayout(row)

        main_layout.addLayout(sliders_layout)

    def on_color_space_changed(self, space: str):
        self.color_space = space
        if space == "HSV":
            names = ["H (Hue)", "S (Sat)", "V (Val)"]
        else:
            names = ["R (Red)", "G (Green)", "B (Blue)"]

        for lbl, name in zip(self.channel_labels, names):
            lbl.setText(name)

    def on_slider_changed(self, idx: int, val: tuple[int, int]):
        self.value_labels[idx].setText(f"{val[0]} - {val[1]}")

    def update_frame(self):
        ret, frame_bgr = self.cap.read()
        if not ret:
            return

        # 1. Convert frame to selected color space for thresholding
        if self.color_space == "HSV":
            converted = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        else:
            converted = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        # 2. Gather slider thresholds
        c0_min, c0_max = self.sliders[0].value()
        c1_min, c1_max = self.sliders[1].value()
        c2_min, c2_max = self.sliders[2].value()

        lower_bound = np.array([c0_min, c1_min, c2_min], dtype=np.uint8)
        upper_bound = np.array([c0_max, c1_max, c2_max], dtype=np.uint8)

        # 3. Create binary mask & apply bitwise AND to input image
        mask = cv2.inRange(converted, lower_bound, upper_bound)
        masked_bgr = cv2.bitwise_and(frame_bgr, frame_bgr, mask=mask)

        # 4. Calculate Image Moments & Draw Centroid
        moments = cv2.moments(mask)
        if moments["m00"] > 0:
            cx = int(moments["m10"] / moments["m00"])
            cy = int(moments["m01"] / moments["m00"])

            cv2.circle(masked_bgr, (cx, cy), 8, (0, 0, 255), -1)
            cv2.circle(masked_bgr, (cx, cy), 14, (0, 255, 0), 2)
            cv2.putText(
                masked_bgr,
                f"({cx}, {cy})",
                (cx + 18, cy + 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )

        # 5. Render side-by-side QLabels
        self._display_image(frame_bgr, self.input_label)
        self._display_image(masked_bgr, self.output_label)

    def _display_image(self, frame_bgr: np.ndarray, label: QLabel):
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        q_img = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img).scaled(
            label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        label.setPixmap(pixmap)

    def closeEvent(self, event):
        self.timer.stop()
        if self.cap.isOpened():
            self.cap.release()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ColorTrackerApp(camera_index=0)
    window.show()
    sys.exit(app.exec())