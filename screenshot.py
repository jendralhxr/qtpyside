import sys
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QGuiApplication, QPixmap
from PySide6.QtCore import Qt, QRect, QPoint
import mss
import mss.tools
from PIL import Image

class ScreenGrabber(QWidget):
    def __init__(self):
        super().__init__()
        self.start = QPoint()
        self.end = QPoint()

        # Take screenshot immediately before showing overlay
        self.screenshot_path = "_screen_background.png"
        self.take_background_screenshot()

        # Load screenshot as background
        self.background = QPixmap(self.screenshot_path)

        # Set up full-screen transparent window
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setWindowState(Qt.WindowFullScreen)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.show()

    def take_background_screenshot(self):
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # primary screen
            img = sct.grab(monitor)
            mss.tools.to_png(img.rgb, img.size, output=self.screenshot_path)

            # Store values for cropping later
            self.capture_offset_x = monitor["left"]
            self.capture_offset_y = monitor["top"]

    def paintEvent(self, event):
        painter = QPainter(self)

        # Draw captured screen as background
        painter.drawPixmap(0, 0, self.background)

        # Draw transparent dimming
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        # Draw selection rectangle
        if not self.start.isNull() and not self.end.isNull():
            pen = QPen(QColor(255, 0, 0), 2)
            painter.setPen(pen)
            painter.setBrush(QColor(255, 0, 0, 50))
            rect = QRect(self.start, self.end)
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        self.start = event.pos()
        self.end = self.start
        self.update()

    def mouseMoveEvent(self, event):
        self.end = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        self.end = event.pos()
        self.update()
        self.extract_selected_region()
        self.close()

    def extract_selected_region(self):
        # Normalize rectangle
        rect = QRect(self.start, self.end).normalized()

        # Crop from the previously captured background image
        image = Image.open(self.screenshot_path)
        left = rect.left() + self.capture_offset_x
        top = rect.top() + self.capture_offset_y
        right = rect.right() + self.capture_offset_x
        bottom = rect.bottom() + self.capture_offset_y

        cropped = image.crop((left, top, right, bottom))
        cropped.save("selected_region.png")
        print("Saved: selected_region.png")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    grabber = ScreenGrabber()
    sys.exit(app.exec())
