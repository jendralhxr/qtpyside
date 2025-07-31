import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QFileDialog, QMessageBox,
    QVBoxLayout, QPushButton, QDialog, QTextEdit
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QGuiApplication, QPixmap, QImage, QClipboard, QCursor
)
from PySide6.QtCore import Qt, QRect, QPoint
import mss
from PIL import Image
import cv2
import numpy as np
from pyzbar.pyzbar import decode


class ActionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose an Action")
        layout = QVBoxLayout()

        self.copy_btn = QPushButton("📋 Copy to Clipboard")
        self.save_btn = QPushButton("💾 Save as PNG")
        self.qr_btn = QPushButton("📷 Detect QR/Barcode")
        self.cancel_btn = QPushButton("❌ Cancel")

        self.copy_btn.clicked.connect(lambda: self.done(1))
        self.save_btn.clicked.connect(lambda: self.done(2))
        self.qr_btn.clicked.connect(lambda: self.done(3))
        self.cancel_btn.clicked.connect(lambda: self.done(0))

        layout.addWidget(self.copy_btn)
        layout.addWidget(self.save_btn)
        layout.addWidget(self.qr_btn)
        layout.addWidget(self.cancel_btn)

        self.setLayout(layout)


class ScreenGrabber(QWidget):
    def __init__(self):
        super().__init__()
        self.start = QPoint()
        self.end = QPoint()
        self.capture_offset_x = 0
        self.capture_offset_y = 0
        self.full_image_pil = None
        self.background = None

        self.take_background_screenshot()

        # Overlay setup
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setWindowState(Qt.WindowFullScreen)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.show()

    def take_background_screenshot(self):
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Primary screen
            img = sct.grab(monitor)

            # Store PIL image for cropping
            self.full_image_pil = Image.frombytes("RGB", img.size, img.rgb)
            self.capture_offset_x = monitor["left"]
            self.capture_offset_y = monitor["top"]

            # For drawing in background
            qimage = QImage(img.rgb, img.width, img.height, QImage.Format_RGB888)
            self.background = QPixmap.fromImage(qimage)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.background)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        if not self.start.isNull() and not self.end.isNull():
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.setBrush(QColor(255, 0, 0, 50))
            painter.drawRect(QRect(self.start, self.end))

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
        self.handle_selection()
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            # print("Selection cancelled by Esc key.")
            QApplication.quit()

    def handle_selection(self):
        rect = QRect(self.start, self.end).normalized()
        left = rect.left() + self.capture_offset_x
        top = rect.top() + self.capture_offset_y
        right = rect.right() + self.capture_offset_x
        bottom = rect.bottom() + self.capture_offset_y

        cropped = self.full_image_pil.crop((left, top, right, bottom))

        dialog = ActionDialog()
        result = dialog.exec()

        if result == 1:
            self.copy_to_clipboard(cropped)
        elif result == 2:
            self.save_image(cropped)
        elif result == 3:
            self.detect_qr_code(cropped)
        else:
            print("Action canceled.")

    def copy_to_clipboard(self, pil_image):
        rgb_image = pil_image.convert("RGB")
        data = rgb_image.tobytes("raw", "RGB")
        qimage = QImage(data, rgb_image.width, rgb_image.height, QImage.Format_RGB888)
        QApplication.clipboard().setImage(qimage)
        QMessageBox.information(self, "Clipboard", "Image copied to clipboard.")

    def save_image(self, pil_image):
        path, _ = QFileDialog.getSaveFileName(self, "Save Screenshot", "screenshot.png", "PNG Files (*.png)")
        if path:
            pil_image.save(path)
            QMessageBox.information(self, "Saved", f"Image saved to: {path}")

    def detect_qr_code(self, pil_image):
        np_img = np.array(pil_image.convert("RGB"))
        gray = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)
        barcodes = decode(gray)

        if barcodes:
            texts = [obj.data.decode("utf-8") for obj in barcodes]
            result = "\n".join(texts)
            self.show_detected_text(result)
        else:
            QMessageBox.information(self, "QR/Barcode", "No QR or barcode detected.")

    def show_detected_text(self, text):
        window = QWidget()
        window.setWindowTitle("QR/Barcode Result")
        layout = QVBoxLayout()

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(text)
        layout.addWidget(text_edit)

        window.setLayout(layout)
        window.resize(500, 200)
        window.show()
        self.detected_text_window = window  # keep window alive


if __name__ == "__main__":
    app = QApplication(sys.argv)
    grabber = ScreenGrabber()
    sys.exit(app.exec())
