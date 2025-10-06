import sys
import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPen, QImage, QPixmap
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QMainWindow
from scipy.ndimage import zoom
import matplotlib.pyplot as plt

class HeatmapWidget(QWidget):
    def __init__(self, Z, parent=None):
        super().__init__(parent)
        self.Z = Z
        self.h, self.w = Z.shape

        # Convert to image (colormap)
        norm = plt.Normalize(vmin=Z.min(), vmax=Z.max())
        rgb = plt.cm.jet_r(norm(Z))[:, :, :3]
        rgb = (rgb * 255).astype(np.uint8)
        rgb = np.ascontiguousarray(rgb)
        bytes_per_line = 3 * self.w
        qimg = QImage(rgb.data, self.w, self.h, bytes_per_line, QImage.Format_RGB888).copy()
        self.pixmap = QPixmap.fromImage(qimg)

        # Animation vars
        self.i = 0
        self.j = 0
        self.step_count = 0
        self.max_val = float("-inf")
        self.rect_color = Qt.green
        self.pause_timer = None

        # External readouts
        self.counter_display = None
        self.max_display = None

        # Main animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.next_step)
        self.timer.start(30)

    def next_step(self):
        if self.i >= self.h:
            self.timer.stop()
            return

        val = self.Z[self.i, self.j]
        self.step_count += 1

        # Update readouts
        if self.counter_display:
            self.counter_display.setText(str(self.step_count))

        if val > self.max_val:
            self.max_val = val
            if self.max_display:
                self.max_display.setText(f"{self.max_val:.3f}")

            # Turn red briefly when a new maximum is found
            self.rect_color = Qt.red
            self.update()
            self.timer.stop()

            # Short pause (e.g. 200 ms)
            self.pause_timer = QTimer.singleShot(200, self.resume_after_pause)
            return

        self.rect_color = Qt.green
        self.advance_indices()
        self.update()

    def resume_after_pause(self):
        self.advance_indices()
        self.rect_color = Qt.green
        self.update()
        self.timer.start(30)

    def advance_indices(self):
        self.j += 1
        if self.j >= self.w:
            self.j = 0
            self.i += 1

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.pixmap)

        if self.i < self.h and self.j < self.w:
            painter.setPen(QPen(self.rect_color, 4))
            rect_w = self.width() / self.w
            rect_h = self.height() / self.h
            painter.drawRect(self.j * rect_w, self.i * rect_h, rect_w, rect_h)


class MainWindow(QMainWindow):
    def __init__(self, Z):
        super().__init__()
        self.setWindowTitle("Z Clip Animation")

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Heatmap
        self.heatmap = HeatmapWidget(Z)
        layout.addWidget(self.heatmap)

        # Info bar
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel("Steps:"))
        self.steps_edit = QLineEdit()
        self.steps_edit.setReadOnly(True)
        info_layout.addWidget(self.steps_edit)

        info_layout.addWidget(QLabel("Current Max:"))
        self.max_edit = QLineEdit()
        self.max_edit.setReadOnly(True)
        info_layout.addWidget(self.max_edit)

        layout.addLayout(info_layout)
        self.setCentralWidget(widget)

        # Connect displays
        self.heatmap.counter_display = self.steps_edit
        self.heatmap.max_display = self.max_edit


def main():
    app = QApplication(sys.argv)

    # Example: load from CSV and resize
    Z = np.loadtxt("Z_clip.csv", delimiter=",")
    target_size = (40, 40)
    zoom_y = target_size[0] / Z.shape[0]
    zoom_x = target_size[1] / Z.shape[1]
    Z_small = zoom(Z, (zoom_y, zoom_x), order=3)

    window = MainWindow(Z_small)
    window.resize(600, 600)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
