#!/usr/bin/env python3
import sys
import numpy as np
import cv2
from pyzbar.pyzbar import decode
import pytesseract

from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import (
    QPainter, QColor, QPen, QPixmap, QImage, QMouseEvent, QKeySequence,
    QShortcut, QCursor, QGuiApplication
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
        self.background = None
        # Ratio between the grabbed pixmap's pixel size and the widget's
        # logical size on this screen. Normally 1:1 since both come from
        # the same QScreen, but kept as a safety net in case a platform
        # ever returns a differently-scaled grab.
        self.scale_x = 1.0
        self.scale_y = 1.0

        self.take_background_screenshot()

        # Overlay setup
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        # Position the overlay using Qt's own geometry for the screen under
        # the cursor, so it lines up exactly with the grabbed content and
        # with the mouse coordinates Qt reports for that screen.
        self.setGeometry(self.screen_geometry)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.showFullScreen()

    def get_screen_under_cursor(self):
        """Return the QScreen that currently contains the mouse cursor."""
        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos)
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        return screen

    def take_background_screenshot(self):
        screen = self.get_screen_under_cursor()
        self.screen_geometry = screen.geometry()

        # grabWindow(0) on a specific QScreen captures just that screen,
        # in that screen's own local coordinates (its top-left is (0, 0)).
        # No manual monitor offset/matching needed, unlike mss.
        self.background = screen.grabWindow(0)

        # Guard against the (unusual) case where the grabbed pixmap's pixel
        # size doesn't match the screen's logical size 1:1.
        if self.screen_geometry.width() and self.screen_geometry.height():
            self.scale_x = self.background.width() / self.screen_geometry.width()
            self.scale_y = self.background.height() / self.screen_geometry.height()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.background, self.background.rect())
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
        # self.start/self.end are in the widget's local (logical) pixel
        # space, which is also the background pixmap's coordinate space
        # since both come from the same QScreen. scale_x/scale_y are 1.0
        # in the normal case.
        left = round(rect.left() * self.scale_x)
        top = round(rect.top() * self.scale_y)
        right = round(rect.right() * self.scale_x)
        bottom = round(rect.bottom() * self.scale_y)

        cropped = self.background.copy(QRect(QPoint(left, top), QPoint(right, bottom)))

        self.editor = AnnotationEditor(cropped)
        self.editor.show()

 
class AnnotationEditor(QWidget):
    def __init__(self, pixmap):
        super().__init__()
        self.setWindowTitle("Annotate Screenshot")
        self.setCursor(Qt.CrossCursor)

        self.canvas = QPixmap(pixmap)
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

        self.clear_btn = QPushButton("🧼 Cl&ear")
        self.clear_btn.clicked.connect(self.clear_canvas)
        tool_layout.addWidget(self.clear_btn)

        self.copy_btn = QPushButton("📋 &Copy")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        tool_layout.addWidget(self.copy_btn)

        self.save_btn = QPushButton("💾 &Save")
        self.save_btn.clicked.connect(self.save_image)
        tool_layout.addWidget(self.save_btn)

        self.qr_btn = QPushButton("📷 Detect &QR")
        self.qr_btn.clicked.connect(self.detect_qr_code)
        tool_layout.addWidget(self.qr_btn)

        self.ocr_btn = QPushButton("🔤 OCR &Text")
        self.ocr_btn.clicked.connect(self.detect_text)
        tool_layout.addWidget(self.ocr_btn)

        self.cancel_btn = QPushButton("❌ Cancel")
        self.cancel_btn.clicked.connect(self.close)
        tool_layout.addWidget(self.cancel_btn)

        layout.addLayout(tool_layout)
        #self.resize(self.canvas.width(), self.canvas.height() + 40)

        # Drawing area
        self.label = QLabel()
        self.label.setPixmap(self.canvas)
        layout.addWidget(self.label)

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
            current_point = event.position().toPoint() + QPoint(-8, -48)
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
        threshold = arr.mean()
        th = np.where(arr > threshold, 255, 0).astype(np.uint8)
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
        actions = {
        Qt.Key_C: self.copy_to_clipboard,
        Qt.Key_S: self.save_image,
        Qt.Key_Q: self.detect_qr_code,
        Qt.Key_T: self.detect_text,
        Qt.Key_E: self.clear_canvas,
        Qt.Key_Escape: QApplication.quit,
            }
    
        action = actions.get(event.key())
        if action:
            action()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    grabber = ScreenGrabber()
    sys.exit(app.exec())
