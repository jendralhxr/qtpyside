import sys
import cv2
import numpy as np
from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QPen, QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QDoubleSpinBox,
    QGroupBox,
    QFormLayout,
    QFrame,
)


class RegionSnipper(QWidget):
    """Full-screen transparent overlay to select a region of the screen."""
    region_selected = Signal(QPixmap)

    def __init__(self, full_pixmap: QPixmap):
        super().__init__()
        self.full_pixmap = full_pixmap
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.start_pos = None
        self.end_pos = None

    def paintEvent(self, event):
        painter = QPainter(self)
        # Draw captured screen
        painter.drawPixmap(0, 0, self.full_pixmap)
        # Dim background
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110))

        if self.start_pos and self.end_pos:
            rect = QRect(self.start_pos, self.end_pos).normalized()
            # Reveal bright selected area
            painter.drawPixmap(rect, self.full_pixmap, rect)
            # Draw selection border
            pen = QPen(QColor(0, 255, 128), 2)
            painter.setPen(pen)
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = event.position().toPoint()
            self.end_pos = self.start_pos
            self.update()

    def mouseMoveEvent(self, event):
        if self.start_pos:
            self.end_pos = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.start_pos:
            rect = QRect(self.start_pos, self.end_pos).normalized()
            self.close()
            if rect.width() > 5 and rect.height() > 5:
                # Account for high-DPI scaling
                dpr = self.full_pixmap.devicePixelRatio()
                scaled_rect = QRect(
                    int(rect.x() * dpr),
                    int(rect.y() * dpr),
                    int(rect.width() * dpr),
                    int(rect.height() * dpr),
                )
                cropped = self.full_pixmap.copy(scaled_rect)
                self.region_selected.emit(cropped)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()


class TrafficLightAnalyzer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Traffic Light & Stopping Distance Assistant")
        self.resize(620, 560)
        self.snipper = None
        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # 1. Capture Control
        self.btn_snip = QPushButton("Select Traffic Light Region (Snip)")
        self.btn_snip.setMinimumHeight(40)
        self.btn_snip.clicked.connect(self.start_snip)
        main_layout.addWidget(self.btn_snip)

        # 2. Vehicle & Physics Parameters
        params_group = QGroupBox("Vehicle Approach Parameters (Dilemma Zone Physics)")
        form_layout = QFormLayout(params_group)

        self.speed_input = QDoubleSpinBox()
        self.speed_input.setRange(0.0, 250.0)
        self.speed_input.setValue(65.0)
        self.speed_input.setSuffix(" km/h")

        self.distance_input = QDoubleSpinBox()
        self.distance_input.setRange(1.0, 500.0)
        self.distance_input.setValue(22.0)
        self.distance_input.setSuffix(" m")

        self.reaction_input = QDoubleSpinBox()
        self.reaction_input.setRange(0.1, 5.0)
        self.reaction_input.setValue(1.0)
        self.reaction_input.setSingleStep(0.1)
        self.reaction_input.setSuffix(" s")

        self.decel_input = QDoubleSpinBox()
        self.decel_input.setRange(1.0, 12.0)
        self.decel_input.setValue(6.0)
        self.decel_input.setSingleStep(0.5)
        self.decel_input.setSuffix(" m/s²")

        form_layout.addRow("Current Speed:", self.speed_input)
        form_layout.addRow("Distance to Stop Line:", self.distance_input)
        form_layout.addRow("Driver Reaction Time:", self.reaction_input)
        form_layout.addRow("Max Safe Deceleration:", self.decel_input)
        main_layout.addWidget(params_group)

        # 3. Captured Image Preview
        self.preview_label = QLabel("No screenshot captured yet.")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(200)
        self.preview_label.setFrameShape(QFrame.Shape.StyledPanel)
        self.preview_label.setStyleSheet("background-color: #1e1e1e; color: #aaaaaa;")
        main_layout.addWidget(self.preview_label)

        # 4. Detection Metrics & Decision Output
        self.metrics_label = QLabel("Color Pixel Counts — Red: 0 | Yellow: 0 | Green: 0")
        self.metrics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.metrics_label)

        self.decision_banner = QLabel("AWAITING CAPTURE")
        self.decision_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.decision_banner.setMinimumHeight(75)
        self.decision_banner.setWordWrap(True)
        self.decision_banner.setStyleSheet(
            "font-size: 16px; font-weight: bold; padding: 10px; "
            "background-color: #333333; color: white; border-radius: 6px;"
        )
        main_layout.addWidget(self.decision_banner)

    def start_snip(self):
        self.hide()
        QApplication.processEvents()
        QGuiApplication.sync()
        screen = QGuiApplication.primaryScreen()
        full_pixmap = screen.grabWindow(0)

        self.snipper = RegionSnipper(full_pixmap)
        self.snipper.region_selected.connect(self.on_region_captured)
        self.snipper.destroyed.connect(self.show)
        self.snipper.show()

    def on_region_captured(self, pixmap: QPixmap):
        self.show()
        self.process_pixmap(pixmap)

    def _pixmap_to_bgr(self, pixmap: QPixmap) -> np.ndarray:
        """Convert QPixmap to OpenCV BGR numpy array."""
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
        width = image.width()
        height = image.height()
        bytes_per_line = image.bytesPerLine()

        ptr = image.bits()
        arr = np.frombuffer(ptr, np.uint8).reshape((height, bytes_per_line))
        rgb = arr[:, : width * 3].reshape((height, width, 3))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    def detect_dominant_light(self, bgr_img: np.ndarray) -> tuple[str, dict]:
        """Detect prominent traffic light color using HSV color thresholds."""
        hsv = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)

        red_mask1 = cv2.inRange(hsv, np.array([0, 120, 120]), np.array([10, 255, 255]))
        red_mask2 = cv2.inRange(hsv, np.array([165, 120, 120]), np.array([180, 255, 255]))
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)

        yellow_mask = cv2.inRange(hsv, np.array([15, 120, 120]), np.array([35, 255, 255]))
        green_mask = cv2.inRange(hsv, np.array([40, 100, 100]), np.array([95, 255, 255]))

        counts = {
            "RED": int(cv2.countNonZero(red_mask)),
            "YELLOW": int(cv2.countNonZero(yellow_mask)),
            "GREEN": int(cv2.countNonZero(green_mask)),
        }

        dominant_color = max(counts, key=counts.get)
        if counts[dominant_color] < 15:
            return "NONE", counts
        return dominant_color, counts

    def compute_stopping_distance(self) -> float:
        """
        Calculate total safe stopping distance:
        d_total = (v * t_reaction) + (v^2 / (2 * a_decel))
        """
        v_ms = self.speed_input.value() / 3.6
        t_react = self.reaction_input.value()
        decel = self.decel_input.value()

        reaction_dist = v_ms * t_react
        braking_dist = (v_ms ** 2) / (2.0 * decel)
        return reaction_dist + braking_dist

    def evaluate_decision(self, light: str):
        speed_kmh = self.speed_input.value()
        dist_to_line = self.distance_input.value()
        required_stop_dist = self.compute_stopping_distance()
        unsafe_to_brake = required_stop_dist > dist_to_line

        if light == "NONE":
            self._set_banner(
                "NO TRAFFIC LIGHT DETECTED\nTry snipping closer to the signal bulbs.",
                "#555555",
            )
            return

        if light == "GREEN":
            self._set_banner(
                f"GREEN LIGHT — GO\nProceed normally ({speed_kmh:.0f} km/h).",
                "#1e7e34",
            )

        elif light == "YELLOW":
            if unsafe_to_brake:
                self._set_banner(
                    f"YELLOW LIGHT (OVERSPEED / DILEMMA ZONE) — ALLOWED TO GO\n"
                    f"Safe stopping distance ({required_stop_dist:.1f} m) exceeds distance to line ({dist_to_line:.1f} m). "
                    f"Hard braking is dangerous; clear the intersection safely.",
                    "#d97706",
                )
            else:
                self._set_banner(
                    f"YELLOW LIGHT — WAIT CAUTIOUSLY / PREPARE TO STOP\n"
                    f"Safe stopping distance ({required_stop_dist:.1f} m) is within available distance ({dist_to_line:.1f} m).",
                    "#b45309",
                )

        elif light == "RED":
            if unsafe_to_brake:
                self._set_banner(
                    f"RED LIGHT (EMERGENCY OVERRIDE) — ALLOWED TO GO TO AVOID CRASH\n"
                    f"Speed ({speed_kmh:.0f} km/h) requires {required_stop_dist:.1f} m to stop, but only {dist_to_line:.1f} m remain. "
                    f"Emergency braking would overshoot/skid.",
                    "#991b1b",
                )
            else:
                self._set_banner(
                    f"RED LIGHT — STOP\n"
                    f"Sufficient distance ({dist_to_line:.1f} m available vs {required_stop_dist:.1f} m needed) to stop safely.",
                    "#dc2626",
                )

    def _set_banner(self, text: str, bg_hex: str):
        self.decision_banner.setText(text)
        self.decision_banner.setStyleSheet(
            f"font-size: 14px; font-weight: bold; padding: 12px; "
            f"background-color: {bg_hex}; color: white; border-radius: 6px;"
        )

    def process_pixmap(self, pixmap: QPixmap):
        scaled = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

        bgr = self._pixmap_to_bgr(pixmap)
        dominant, counts = self.detect_dominant_light(bgr)

        self.metrics_label.setText(
            f"Detected Pixels — Red: {counts['RED']} | Yellow: {counts['YELLOW']} | Green: {counts['GREEN']}  "
            f"(Dominant: {dominant})"
        )
        self.evaluate_decision(dominant)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TrafficLightAnalyzer()
    window.show()
    sys.exit(app.exec())