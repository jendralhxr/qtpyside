import sys
import cv2
import numpy as np
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QPushButton, QWidget
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage, QPixmap

ROI_SIZE= 192

class SNRApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aplikasi Wajah Mirip")
        
        # --- ROI Configuration ---
        self.roi_size = ROI_SIZE
        self.half_roi = int(ROI_SIZE / 2)
        
        # Initialize Camera
        self.cap = cv2.VideoCapture(0)
        
        # Get actual hardware resolution
        self.cam_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.cam_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Data storage
        self.img1_data = None
        self.img2_data = None
        self.current_frame = None
        
        # Drawing states
        self.show_roi1 = False
        self.show_roi2 = False
        self.roi1_pos = (0, 0)
        self.roi2_pos = (0, 0)
        
        self.setup_ui()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(10, 10, 10, 10)

        instr_text = "Klik kiri: Merah | Klik kanan: Hijau"
        self.label_instr = QLabel(instr_text)
        self.label_instr.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.label_instr)

        # Match Label size exactly to Camera size
        self.video_label = QLabel()
        self.video_label.setFixedSize(self.cam_width, self.cam_height)
        self.video_label.setStyleSheet("border: 1px solid #555; background-color: black;") 
        self.layout.addWidget(self.video_label)

        self.btn_calc = QPushButton("Hitung Kemiripan")
        self.btn_calc.setFixedHeight(40)
        self.btn_calc.clicked.connect(self.calculate_snr)
        self.layout.addWidget(self.btn_calc)

        self.result_label = QLabel("Skor Kemiripan: (belum dihitung)")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.result_label)

        self.adjustSize()

    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            self.current_frame = frame.copy()
            display_frame = frame.copy()

            # Draw ROI 1 (Red)
            if self.show_roi1:
                x, y = self.roi1_pos
                cv2.rectangle(display_frame, 
                              (x - self.half_roi, y - self.half_roi), 
                              (x + self.half_roi, y + self.half_roi), 
                              (0, 0, 255), 2)

            # Draw ROI 2 (Green)
            if self.show_roi2:
                x, y = self.roi2_pos
                cv2.rectangle(display_frame, 
                              (x - self.half_roi, y - self.half_roi), 
                              (x + self.half_roi, y + self.half_roi), 
                              (0, 255, 0), 2)

            # Convert to RGB for PySide
            rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            qt_img = QImage(rgb_frame.data, self.cam_width, self.cam_height, 
                            self.cam_width * 3, QImage.Format_RGB888)
            self.video_label.setPixmap(QPixmap.fromImage(qt_img))

    def mousePressEvent(self, event):
        # Map click to video_label coordinates
        pos = self.video_label.mapFromParent(event.position().toPoint())
        x, y = pos.x(), pos.y()

        # Boundary check: Ensure the ROI box doesn't go outside the frame
        if (x < self.half_roi or x > self.cam_width - self.half_roi or 
            y < self.half_roi or y > self.cam_height - self.half_roi):
            print("Click too close to edge for the selected ROI size.")
            return

        # Define the slice coordinates
        y_start, y_end = y - self.half_roi, y + self.half_roi
        x_start, x_end = x - self.half_roi, x + self.half_roi

        # Extract ROI and convert to grayscale float
        roi = self.current_frame[y_start:y_end, x_start:x_end]
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)

        if event.button() == Qt.LeftButton:
            self.img1_data = gray_roi
            self.roi1_pos = (x, y)
            self.show_roi1 = True
            print(f"Captured Image 1 at {x}, {y}")
            
        elif event.button() == Qt.RightButton:
            self.img2_data = gray_roi
            self.roi2_pos = (x, y)
            self.show_roi2 = True
            print(f"Captured Image 2 at {x}, {y}")

    def calculate_snr(self):
        if self.img1_data is None or self.img2_data is None:
            self.result_label.setText("Error: Please capture both ROIs first!")
            return

        # 1. Calculate the absolute difference (Noise Map)
        diff = np.abs(self.img1_data - self.img2_data)
        
        # 2. Add epsilon to avoid division by zero at the pixel level
        # We use 1e-6 as the floor for the noise
        diff_safe = np.where(diff == 0, 1e-6, diff)

        # 3. Element-wise division: Image / Difference
        # Logic: SNR = Mean(Image_pixel / Noise_pixel)
        snr1_map = self.img1_data / diff_safe
        snr2_map = self.img2_data / diff_safe

        # 4. Calculate the mean of the resulting SNR maps
        snr1 = np.mean(snr1_map) / ROI_SIZE**2
        snr2 = np.mean(snr2_map) / ROI_SIZE**2
        avg_snr = (snr1 + snr2) / 2
        
        self.result_label.setText(f"Skor Kemiripan: {avg_snr:.2f}")

    def closeEvent(self, event):
        self.cap.release()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SNRApp()
    window.show()
    sys.exit(app.exec())