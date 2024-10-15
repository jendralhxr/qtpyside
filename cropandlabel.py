import sys
import os
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QRadioButton, QLabel, QGridLayout
from PySide6.QtGui import QPixmap, QPainter, QColor, QImage
from PySide6.QtCore import Qt, QRect
import cv2
import numpy as np

HURF_SIZE= 48
HURF_COUNTER= 0
imagename= ''
filenametosave= ''
chosen_hurf= int(0)

hurf = [''] * 40
hurf[1] = 'ا'
hurf[2] = 'ب'
hurf[3] = 'ت'
hurf[4] = 'ة'
hurf[5] = 'ث'
hurf[6] = 'ج'
hurf[7] = 'چ'
hurf[8] = 'ح'
hurf[9] = 'خ'
hurf[10] = 'د'
hurf[11] = 'ذ'
hurf[12] = 'ر'
hurf[13] = 'ز'
hurf[14] = 'س'
hurf[15] = 'ش'
hurf[16] = 'ص'
hurf[17] = 'ض'
hurf[18] = 'ط'
hurf[19] = 'ظ'
hurf[20] = 'ع'
hurf[21] = 'غ'
hurf[22] = 'ڠ'
hurf[23] = 'ف'
hurf[24] = 'ڤ'
hurf[25] = 'ق'
hurf[26] = 'ک'
hurf[27] = 'ݢ'
hurf[28] = 'ل'
hurf[29] = 'م'
hurf[30] = 'ن'
hurf[31] = 'و'
hurf[32] = 'ۏ'
hurf[33] = 'ه'
hurf[34] = 'ء'
hurf[35] = 'ي'
hurf[36] = 'ی'
hurf[37] = 'ڽ'

x_crop= [0, 0]
y_crop= [0, 0]
resized_image = np.empty((0, 0, 1), dtype=np.uint8)

class ImageWidget(QWidget):
    def __init__(self, image_path):
        super().__init__()
        self.rectangle = QRect(50, 50, HURF_SIZE, HURF_SIZE)  # Initial rectangle position and size
        
        # Initialize the QPixmap and rectangle
        image = cv2.imread(image_path)
        inverted_image = cv2.bitwise_not(image)
        gray_image = cv2.cvtColor(inverted_image, cv2.COLOR_BGR2GRAY)
        _, thresholded_image = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        height, width = thresholded_image.shape[:2]
        global resized_image
        resized_image = cv2.resize(thresholded_image, (width*2, height*2), interpolation=cv2.INTER_CUBIC)

        # Convert the thresholded image back to QPixmap
        height, width = resized_image.shape
        bytes_per_line = width
        q_image = QImage(resized_image.data, width, height, bytes_per_line, QImage.Format_Grayscale8)

        # Convert QImage to QPixmap
        self.original_pixmap = QPixmap.fromImage(q_image)
        
        # Initialize rectangle color
        self.rectangle_color = QColor(0, 255, 0, 40)  # Default color 

        # Create QLabel to hold the pixmap
        self.image_label = QLabel()
        self.image_label.setFixedSize(self.original_pixmap.size())  # Set fixed size to match pixmap

        # Layout for radio buttons
        self.layout = QVBoxLayout()
        
        # # Create radio buttons for color selection
        # self.red_button = QRadioButton("Red")
        # self.green_button = QRadioButton("Green")
        # self.blue_button = QRadioButton("Blue")
        # self.red_button.setChecked(True)  # Set default checked button

        # # Connect radio buttons to change color
        # self.red_button.toggled.connect(self.update_color)
        # self.green_button.toggled.connect(self.update_color)
        # self.blue_button.toggled.connect(self.update_color)

        # # Add radio buttons to layout
        # self.layout.addWidget(QLabel("Select Rectangle Color:"))
        # self.layout.addWidget(self.red_button)
        # self.layout.addWidget(self.green_button)
        # self.layout.addWidget(self.blue_button)

        # Add the image label to the layout
        self.layout.addWidget(self.image_label)

        self.setLayout(self.layout)
        
        radio_layout = QGridLayout()

        # List to store radio buttons
        self.radio_buttons = []
        
        for i in range(1, 38):
            radio_button = QRadioButton(hurf[i])  # Adjust index for zero-based list
            # Use a default argument in the lambda to capture the current index
            radio_button.toggled.connect(lambda checked, idx=i: self.radio_selected(idx, checked))
            self.radio_buttons.append(radio_button)
            radio_layout.addWidget(radio_button, (i-1) // 19, (i - 1) % 19)  # You can adjust layout as needed

        self.layout.addLayout(radio_layout)
        self.setWindowTitle("yuk dikotakin dan ditulisin hurufnya")
        #self.setFixedSize(self.original_pixmap.size().width(), self.original_pixmap.size().height() + 100)  # Adjust height for buttons

        # Initialize the displayed pixmap with the original pixmap
        self.displayed_pixmap = self.original_pixmap.copy()
        self.image_label.setPixmap(self.displayed_pixmap)
    
    def radio_selected(self, idx, checked):
        global filenametosave
        if checked:
            global chosen_hurf
            chosen_hurf= idx
            filenametosave= f"{imagename}_n{HURF_COUNTER:04d}_label{chosen_hurf:02d}.png"
            #print(f"gonna save to {filenametosave}")  # Access original option
        # else:
        #     print(f"Radio button {idx} deselected: {hurf[idx - 1]}.")   
    
    def paint_rect(self):
        # Create a new pixmap to draw the rectangle on
        pixmap_with_rect = self.original_pixmap.copy()  # Copy original pixmap for drawing
        painter = QPainter(pixmap_with_rect)
        # Set color and draw the rectangle on the new pixmap
        painter.setPen(self.rectangle_color)
        painter.setBrush(self.rectangle_color)
        painter.drawRect(self.rectangle)
        painter.end()  # End painting

        # Update the displayed pixmap
        self.image_label.setPixmap(pixmap_with_rect)

    # def update_color(self):
    #     # Update rectangle color based on selected radio button
    #     if self.red_button.isChecked():
    #         self.rectangle_color = QColor(255, 0, 0)
    #     elif self.green_button.isChecked():
    #         self.rectangle_color = QColor(0, 255, 0)
    #     elif self.blue_button.isChecked():
    #         self.rectangle_color = QColor(0, 0, 255)

    #     self.paint_rect()  # Call to paint the rectangle with new color

    def mousePressEvent(self, event):
        # Update rectangle position based on mouse click
        if event.button() == Qt.LeftButton:
            pos = self.image_label.mapFromGlobal(event.globalPos())
            self.rectangle.moveTo(pos.x() - self.rectangle.width() // 2,
                                  pos.y() - self.rectangle.height() // 2)
            self.paint_rect()  # Call to paint the rectangle at new position
            global x_crop, y_crop
            x_crop[0]= int (pos.x() - HURF_SIZE/2)
            y_crop[0]= int (pos.y() - HURF_SIZE/2)
            x_crop[1]= int (x_crop[0] + HURF_SIZE)
            y_crop[1]= int (y_crop[0] + HURF_SIZE)
            #print(f"update {x_crop[0]}:{x_crop[1]} {y_crop[0]}:{y_crop[1]}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Q:
            QApplication.quit()
        elif event.key() == Qt.Key_C:
            global filenametosave
            global HURF_COUNTER, chosen_hurf
            global resized_image
            global y_crop, x_crop
            #print(f"mau cetak {HURF_COUNTER} {x_crop[0]}:{x_crop[1]} {y_crop[0]}:{y_crop[1]}")
            cropped= resized_image[int(y_crop[0]):int(y_crop[1]), int(x_crop[0]):int(x_crop[1])]
            cv2.imwrite(filenametosave, cropped)
            print(f"menyimpan ke: {filenametosave}")
            HURF_COUNTER += 1
            filenametosave= f"{imagename}_n{HURF_COUNTER:04d}_label{chosen_hurf:02d}.png"

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Replace 'path_to_image.jpg' with the path to your image file
    image_path = sys.argv[1]
    imagename, ext= os.path.splitext(image_path)
    print(imagename)
    widget = ImageWidget(image_path)
    widget.show()

    sys.exit(app.exec())
