#!/usr/bin/env python3
import sys
import numpy as np
import tifffile
import zarr
import imageio.v3 as iio
from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QLineEdit, QGraphicsView, 
    QGraphicsScene, QGraphicsPixmapItem, QRubberBand
)
from PySide6.QtGui import QImage, QPixmap


class ImageCanvas(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        
        # UI configuration
        self.setMouseTracking(True)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        # Drag selection state
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self.origin = QPoint()
        self.is_selecting = False

        # Main window reference callback for cursor tracking
        self.main_window = parent

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.origin = event.pos()
            self.rubber_band.setGeometry(QRect(self.origin, self.origin).normalized())
            self.rubber_band.show()
            self.is_selecting = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # Update rubberband rect if dragging
        if self.is_selecting:
            self.rubber_band.setGeometry(QRect(self.origin, event.pos()).normalized())

        # Update pixel values in main window based on scene coordinates
        scene_pos = self.mapToScene(event.pos())
        self.main_window.update_pixel_info(scene_pos.x(), scene_pos.y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.is_selecting = False
            self.rubber_band.hide()
            
            # Map rubberband geometry to scene coordinates
            rect = self.rubber_band.geometry()
            top_left = self.mapToScene(rect.topLeft())
            bottom_right = self.mapToScene(rect.bottomRight())
            
            x1, y1 = int(top_left.x()), int(top_left.y())
            x2, y2 = int(bottom_right.x()), int(bottom_right.y())
            
            w = abs(x2 - x1)
            h = abs(y2 - y1)

            # Trigger ROI update if a valid area was dragged (minimum 5x5 px)
            if w > 5 and h > 5:
                x = min(x1, x2)
                y = min(y1, y2)
                self.main_window.display_roi(x, y, w, h)
                
        super().mouseReleaseEvent(event)


class ImageViewer(QMainWindow):
    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath
        self.is_tiff = filepath.lower().endswith(('.tif', '.tiff'))
        
        self.tiff_store = None
        self.z_array = None
        self.non_tiff_arr = None
        self.img_w = 0
        self.img_h = 0
        
        # Render display scale state (tracks ratio between original full-res and current display)
        self.current_display_scale = 1.0
        
        # Target viewport offset tracking for ROI calculation
        self.current_roi_offset = (0, 0)

        self.init_ui()
        self.load_image()

    def init_ui(self):
        self.setWindowTitle("Pure Python Cross-Platform Viewer (tifffile + PySide)")
        
        # Central Layout
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        
        # Canvas
        self.canvas = ImageCanvas(self)
        layout.addWidget(self.canvas)

        # Status Panel (Bottom)
        status_layout = QHBoxLayout()
        status_label = QLabel("Pixel Value:")
        self.val_textbox = QLineEdit()
        self.val_textbox.setReadOnly(True)
        
        status_layout.addWidget(status_label)
        status_layout.addWidget(self.val_textbox)
        layout.addLayout(status_layout)

        self.setCentralWidget(central_widget)

    def load_image(self):
        screen = QApplication.primaryScreen().size()
        max_w = screen.width() * 0.62
        max_h = screen.height() * 0.62

        if self.is_tiff:
            # Memory-map the TIFF with zero-copy via tifffile + zarr
            self.tiff_store = tifffile.imread(self.filepath, aszarr=True)
            self.z_array = zarr.open(self.tiff_store, mode='r')
            
            # Standardize shape tracking (Handle 2D, 3D, multi-channel arrays)
            shape = self.z_array.shape
            self.img_h, self.img_w = shape[0], shape[1]

            # Downsample check
            if self.img_w > max_w or self.img_h > max_h:
                self.current_display_scale = 0.5
                # Slice with step 2 for memory-efficient 2x downsampling
                display_slice = self.z_array[::2, ::2]
            else:
                self.current_display_scale = 1.0
                display_slice = self.z_array[:]

            self.render_array_to_canvas(display_slice)

        else:
            # Universal non-TIFF reader (PNG, JPEG, WebP, etc.)
            self.non_tiff_arr = iio.imread(self.filepath)
            self.img_h, self.img_w = self.non_tiff_arr.shape[0], self.non_tiff_arr.shape[1]

            if self.img_w > max_w or self.img_h > max_h:
                self.current_display_scale = 0.5
                display_slice = self.non_tiff_arr[::2, ::2]
            else:
                self.current_display_scale = 1.0
                display_slice = self.non_tiff_arr

            self.render_array_to_canvas(display_slice)

    def render_array_to_canvas(self, arr):
        """Safely normalizes 32-bit floats/ints to 8-bit UI canvas rendering."""
        # Convert zarr array slice to numpy array if required
        if not isinstance(arr, np.ndarray):
            arr = np.array(arr)

        # Normalize 32-bit/16-bit array to 8-bit range for GUI display
        if arr.dtype != np.uint8:
            arr_min, arr_max = arr.min(), arr.max()
            if arr_max > arr_min:
                norm_arr = ((arr - arr_min) / (arr_max - arr_min) * 255).astype(np.uint8)
            else:
                norm_arr = np.zeros_like(arr, dtype=np.uint8)
        else:
            norm_arr = arr

        # Handle grayscale vs multichannel
        if norm_arr.ndim == 2:
            height, width = norm_arr.shape
            bytes_per_line = width
            qfmt = QImage.Format_Grayscale8
        elif norm_arr.ndim == 3:
            height, width, channels = norm_arr.shape
            bytes_per_line = width * channels
            if channels == 3:
                qfmt = QImage.Format_RGB888
            elif channels == 4:
                qfmt = QImage.Format_RGBA8888
            else:
                # Spectral/multi-channel fallback (render 1st channel as grayscale)
                norm_arr = norm_arr[:, :, 0]
                bytes_per_line = width
                qfmt = QImage.Format_Grayscale8

        # Copy data buffer to QImage safely
        qimg = QImage(norm_arr.data, width, height, bytes_per_line, qfmt).copy()
        pixmap = QPixmap.fromQImage(qimg)
        
        self.canvas.pixmap_item.setPixmap(pixmap)
        self.canvas.scene.setSceneRect(pixmap.rect())

    def display_roi(self, display_x, display_y, display_w, display_h):
        """Extracts ROI directly from the zero-copy array store."""
        orig_x = int((display_x + self.current_roi_offset[0]) / self.current_display_scale)
        orig_y = int((display_y + self.current_roi_offset[1]) / self.current_display_scale)
        orig_w = int(display_w / self.current_display_scale)
        orig_h = int(display_h / self.current_display_scale)

        # Bounds check
        crop_x = max(0, min(orig_x, self.img_w - 1))
        crop_y = max(0, min(orig_y, self.img_h - 1))
        crop_w = min(orig_w, self.img_w - crop_x)
        crop_h = min(orig_h, self.img_h - crop_y)

        if self.is_tiff:
            # Memory-mapped slice extraction from disk
            roi_slice = self.z_array[crop_y:crop_y + crop_h, crop_x:crop_x + crop_w]
        else:
            roi_slice = self.non_tiff_arr[crop_y:crop_y + crop_h, crop_x:crop_x + crop_w]

        self.current_roi_offset = (crop_x, crop_y)
        self.current_display_scale = 1.0  # Reset scale to 100% full detail for cropped region
        self.render_array_to_canvas(roi_slice)

    def update_pixel_info(self, scene_x, scene_y):
        """Direct 32-bit pixel value peeking."""
        abs_x = int((scene_x / self.current_display_scale) + self.current_roi_offset[0])
        abs_y = int((scene_y / self.current_display_scale) + self.current_roi_offset[1])

        if 0 <= abs_x < self.img_w and 0 <= abs_y < self.img_h:
            if self.is_tiff:
                # Zero-copy disk lookup of exact 32-bit sample values
                val = self.z_array[abs_y, abs_x]
            else:
                val = self.non_tiff_arr[abs_y, abs_x]

            if isinstance(val, (np.ndarray, list)):
                val_str = ", ".join([f"{v:.4f}" if isinstance(v, (float, np.floating)) else str(v) for v in val])
            elif isinstance(val, (float, np.floating)):
                val_str = f"{val:.4f}"
            else:
                val_str = str(val)

            self.val_textbox.setText(f"X: {abs_x}, Y: {abs_y} | Values: {val_str}")
        else:
            self.val_textbox.setText("Out of Bounds")

    def closeEvent(self, event):
        """Cleanup store context on exit."""
        if hasattr(self.tiff_store, 'close'):
            self.tiff_store.close()
        super().closeEvent(event)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python viewer.py <path_to_image>")
        sys.exit(1)

    app = QApplication(sys.argv)
    viewer = ImageViewer(sys.argv[1])
    viewer.resize(800, 600)
    viewer.show()
    sys.exit(app.exec())
