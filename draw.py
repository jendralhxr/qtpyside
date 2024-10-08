import sys
import math
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QTextEdit, QSpinBox
from PySide6.QtGui import QPainter, QPen, QPixmap, QColor, QFont
from PySide6.QtCore import Qt, QPoint, Signal, Slot
import random
import pandas as pd

APP_WIDTH = 640
APP_HEIGHT = 480
ARC_DISTANCE = 12
chaincode = ''

PHI = 1.6180339887498948482  # Golden ratio

df= pd.read_csv(sys.argv[1])
row_indices = df.index[1:]  # from row 1 to the last row
column_indices = [1, 4]  # B:isolated, C:initial, D:medial, E:final
random_col=0
random_row=0
random_form= 0

def update_arc(value):
    global ARC_DISTANCE
    ARC_DISTANCE = value
    #print(f"Global variable updated to: {global_variable}")

def freeman(x, y):
    if (y == 0):
        y = 1e-9
    if (x == 0):
        x = -1e-9
    if (abs(x / y) < pow(PHI, 2)) and (abs(y / x) < pow(PHI, 2)):  # Corner angles
        if x > 0 and y > 0:
            return 1
        elif x < 0 and y > 0:
            return 3
        elif x < 0 and y < 0:
            return 5
        elif x > 0 and y < 0:
            return 7
    else:  # Square angles
        if x > 0 and abs(x) > abs(y):
            return int(0)
        elif y > 0 and abs(y) > abs(x):
            return 2
        elif x < 0 and abs(x) > abs(y):
            return 4
        elif y < 0 and abs(y) > abs(x):
            return 6

def pdistance(point1, point2):
    x1, y1 = point1
    x2, y2 = point2
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

class TextEditChain(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumHeight(40)
        self.setPlaceholderText("Freeman code chain goes here")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Q:
            QApplication.quit()
        elif event.key() == Qt.Key_C:
            global chaincode
            chaincode = ''
            self.setText('')
        else:
            super().keyPressEvent(event)

    @Slot(str)
    def updateText(self, text):
        self.setText(text)

class Canvas(QWidget):
    # Define a custom signal with a string argument
    customSignal = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_StaticContents)
        self.setStyleSheet("background-color: white;")
        self.prev_pos = None
        self.prev_pos_bitmap = (-1, -1)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedSize(APP_WIDTH, APP_HEIGHT)
        self.pixmap = QPixmap(self.size())
        self.pixmap.fill(QColor(200, 200, 200))
        
        self.color_map = [
            Qt.red,
            QColor(200, 160, 0),  # Orange
            Qt.yellow,
            Qt.green,
            Qt.blue,
            Qt.cyan,
            Qt.magenta,
            QColor(40, 40, 40)  # Gray
        ]

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.prev_pos = event.position()
            self.prev_pos_bitmap = (self.prev_pos.x(), self.prev_pos.y())

    def mouseMoveEvent(self, event):
        if self.prev_pos is not None:
            current_pos = (event.position().x(), event.position().y())
            if pdistance(current_pos, self.prev_pos_bitmap) > ARC_DISTANCE:
                code = freeman(current_pos[0] - self.prev_pos_bitmap[0], self.prev_pos_bitmap[1] - current_pos[1])
                global chaincode 
                chaincode += str(code)
                self.emitCustomSignal()  # Emit the signal with updated chaincode
                #print(f"from {self.prev_pos_bitmap} to {current_pos}: {chaincode}")
                self.drawLine(self.prev_pos_bitmap, current_pos, self.color_map[code])
                self.prev_pos_bitmap = current_pos
                self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.prev_pos = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.pixmap)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Q:
            QApplication.quit()
        elif event.key() == Qt.Key_C:
            global chaincode
            self.pixmap.fill(QColor(200, 200, 200))
            self.drawLetter()
            self.update()
            self.emitCustomSignal()
            global random_row, random_col, random_form
            print(f"{df.iat[random_row,0]}, pos:{random_col}, code:{chaincode}")
            chaincode = ''
            
    
    def emitCustomSignal(self):
        global chaincode 
        self.customSignal.emit(chaincode)

    @Slot()
    def drawLine(self, start, stop, color):
        painter = QPainter(self.pixmap)
        painter.setPen(QPen(color, 6, Qt.SolidLine))
        painter.drawLine(QPoint(*start), QPoint(*stop))
        painter.end()
    
    def drawLetter(self):
        #ranges = [
        #    (0x0600, 0x06FF),  # Basic Arabic
        #    (0x0700, 0x074F),  # Arabic Supplement
        #    (0x0750, 0x077F),  # Arabic Extended-A
        #    (0x08A0, 0x08FF),  # Arabic Extended-B
        #    (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
        #    (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
        #    (0x1EE00, 0x1EEFF) # Arabic Mathematical Alphabetic Symbols
        #]
        #selected_range = random.choice(ranges)
        #random_form = chr(random.randint(selected_range[0], selected_range[1]))
        #random_form = chr(random.randint(0xFE70, 0xFEFC))
        global random_row, random_col, row_indices, random_form
        random_row = random.choice(row_indices)
        random_col = random.randint(1,4) 
        #print(f"{df.iat[random_row,0]}, pos:{random_col}")
        random_form = chr(int(df.iat[random_row, random_col].replace('U+', ''), 16))
        painter = QPainter(self.pixmap)
        font = QFont("Arial", 320)  # Choose a font and size that supports Arabic
        painter.setFont(font)
        painter.setPen(QColor(160, 160, 160))
        painter.drawText(int(APP_WIDTH*.2), int(APP_HEIGHT*.8), random_form)
        painter.end()
        
        
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("tracing Arabic letters")
        
        # Create the drawing widget and text edit widget
        self.canvas = Canvas()
        self.textedit = TextEditChain()
        
        # Create a SpinBox for ARC_DISTANCE
        self.spinbox = QSpinBox()
        self.spinbox.setRange(1, 100)
        self.spinbox.setValue(ARC_DISTANCE)
        self.spinbox.valueChanged.connect(self.setArcDistance)
        
        # Set up the layout
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        layout.addWidget(self.textedit)
        layout.addWidget(self.spinbox)
        
        # Create a central widget and set the layout
        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Connect the canvas's custom signal to the text edit's updateText slot
        self.canvas.customSignal.connect(self.textedit.updateText)

    def setArcDistance(self, value):
        global ARC_DISTANCE
        print(f"set arc to {ARC_DISTANCE}")
        ARC_DISTANCE = value
        

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
