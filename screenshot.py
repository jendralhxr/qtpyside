import sys
import mss
import numpy as np
import cv2
from PIL import Image
from pyzbar.pyzbar import decode
import pytesseract

from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import (
    QPainter, QColor, QPen, QPixmap, QImage, QMouseEvent, QKeySequence, QShortcut
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QFileDialog, QMessageBox,
    QVBoxLayout, QHBoxLayout, QPushButton, QColorDialog,
    QSpinBox, QTextEdit
)

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
            monitor = sct.monitors[0]  # Primary screen
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

    # annotated editor invoked
    def handle_selection(self):
        rect = QRect(self.start, self.end).normalized()
        left = rect.left() + self.capture_offset_x
        top = rect.top() + self.capture_offset_y
        right = rect.right() + self.capture_offset_x
        bottom = rect.bottom() + self.capture_offset_y
    
        cropped = self.full_image_pil.crop((left, top, right, bottom))
    
        self.editor = AnnotationEditor(cropped)
        self.editor.show()

 
class AnnotationEditor(QWidget):
    def __init__(self, pil_image):
        super().__init__()
        self.setWindowTitle("Annotate Screenshot")
        self.setCursor(Qt.CrossCursor)

        # Convert PIL image to QPixmap
        self.pil_image = pil_image.convert("RGBA")
        self.qimage = self.pil_to_qimage(self.pil_image)
        self.canvas = QPixmap.fromImage(self.qimage)
        self.temp_canvas = QPixmap(self.canvas.size())
        self.base_canvas = self.canvas.copy()

        # Drawing settingsdetect_qr_code
        self.drawing = False
        self.last_point = QPoint()
        self.pen_color = QColor("yellow")
        self.pen_width = 2

        self.cursor_visible = True
        self.current_pos = QPoint()
        self.setMouseTracking(True)  # Required to get mouseMoveEvent without pressing

        # Layout
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Drawing area
        self.label = QLabel()
        self.label.setPixmap(self.canvas)
        layout.addWidget(self.label)

        # Tools
        tool_layout = QHBoxLayout()
        self.color_btn = QPushButton("🎨 Color")
        self.color_btn.clicked.connect(self.choose_color)
        tool_layout.addWidget(self.color_btn)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 50)
        self.width_spin.setValue(self.pen_width)
        self.width_spin.valueChanged.connect(self.change_pen_width)
        tool_layout.addWidget(self.width_spin)

        self.clear_btn = QPushButton("🧼 Clear")
        self.clear_btn.clicked.connect(self.clear_canvas)
        tool_layout.addWidget(self.clear_btn)

        self.copy_btn = QPushButton("📋 Copy")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        tool_layout.addWidget(self.copy_btn)

        self.save_btn = QPushButton("💾 Save")
        self.save_btn.clicked.connect(self.save_image)
        tool_layout.addWidget(self.save_btn)

        self.qr_btn = QPushButton("📷 Detect QR")
        self.qr_btn.clicked.connect(self.detect_qr_code)
        tool_layout.addWidget(self.qr_btn)

        self.ocr_btn = QPushButton("🔤 OCR Text")
        self.ocr_btn.clicked.connect(self.detect_text)
        tool_layout.addWidget(self.ocr_btn)

        self.cancel_btn = QPushButton("❌ Cancel")
        self.cancel_btn.clicked.connect(self.close)
        tool_layout.addWidget(self.cancel_btn)

        layout.addLayout(tool_layout)
        self.resize(self.canvas.width(), self.canvas.height() + 40)

    def pil_to_qimage(self, image):
        data = image.tobytes("raw", "RGBA")
        qimage = QImage(data, image.width, image.height, QImage.Format_RGBA8888)
        return qimage

    def clear_canvas(self):
        self.canvas = self.base_canvas.copy()
        self.label.setPixmap(self.canvas)
        self.update()
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.drawing = True
        if event.button() == Qt.RightButton:
            self.clear_canvas()
            
    def mouseMoveEvent(self, event: QMouseEvent):
        if self.drawing:
            painter = QPainter(self.canvas)
            pen = QPen(self.pen_color, self.pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            current_point = event.position().toPoint() + QPoint(-8, -8)
            painter.drawPoint(current_point)
            self.label.setPixmap(self.canvas)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.drawing = False

    def choose_color(self):
        color = QColorDialog.getColor(self.pen_color, self, "Choose Pen Color")
        if color.isValid():
            self.pen_color = color

    def change_pen_width(self, width):
        self.pen_width = width

    def copy_to_clipboard(self):
        qimage = self.canvas.toImage().convertToFormat(QImage.Format_RGB888)
        QApplication.clipboard().setImage(qimage)
        QMessageBox.information(self, "Copied", "Image copied to clipboard.")

    def save_image(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Annotated Image", "screenshot.png", "PNG Files (*.png)")
        if path:
            self.canvas.toImage().save(path)
            QMessageBox.information(self, "Saved", f"Image saved to: {path}")

    def detect_qr_code(self):
        qimage = self.canvas.toImage().convertToFormat(QImage.Format_Grayscale8)
        ptr = qimage.bits()
        arr = np.array(ptr).reshape((qimage.height(), qimage.bytesPerLine()))
        # Slice to image width to remove padded bytes
        arr = arr[:, :qimage.width()]
        barcodes = decode(arr)

        if barcodes:
            texts = [obj.data.decode("utf-8") for obj in barcodes]
            result = "\n".join(texts)
            self.show_detected_text(result)
        else:
            QMessageBox.information(self, "QR/Barcode", "No QR or barcode detected.")

    def detect_text(self):
        qimage = self.canvas.toImage().convertToFormat(QImage.Format_Grayscale8)
        ptr = qimage.bits()
        arr = np.array(ptr).reshape((qimage.height(), qimage.bytesPerLine()))
        # Slice to image width to remove padded bytes
        arr = arr[:, :qimage.width()]
        
        th = cv2.threshold(arr, 0, 255, cv2.THRESH_OTSU)[1]
        textocr = pytesseract.image_to_string(th, config="--psm 6")
        print(textocr)

        if textocr:
            self.show_detected_text(textocr)
        else:
            QMessageBox.information(self, "OCR", "No text detected.")

    def show_detected_text(self, text):
        dialog = QWidget(self)
        dialog.setWindowTitle("QR/Barcode Result")
        layout = QVBoxLayout()
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(text)
        layout.addWidget(text_edit)
        dialog.setLayout(layout)
        dialog.resize(500, 200)
        dialog.show()
        self.result_window = dialog  # keep alive
        QShortcut(QKeySequence(Qt.Key_Escape), dialog, activated=dialog.close)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            QApplication.quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    grabber = ScreenGrabber()
    sys.exit(app.exec())
