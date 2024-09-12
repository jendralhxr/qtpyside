import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTextEdit
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtCore import Qt
import math

APP_WIDTH= 640
APP_HEIGHT= 480
chaincode=''


PHI= 1.6180339887498948482 # ppl says this is a beautiful number :)
def freeman(x, y):
    if (y==0):
        y=1e-9 # so that we escape the divby0 exception
    if (x==0):
        x=-1e-9 # biased to the left as the text progresses leftward
    if (abs(x/y)<pow(PHI,2)) and (abs(y/x)<pow(PHI,2)): # corner angles
        if   (x>0) and (y>0):
            return(1)
        elif (x<0) and (y>0):
            return(3)
        elif (x<0) and (y<0):
            return(5)
        elif (x>0) and (y<0):
            return(7)
    else: # square angles
        if   (x>0) and (abs(x)>abs(y)):
            return(int(0))
        elif (y>0) and (abs(y)>abs(x)):
            return(2)
        elif (x<0) and (abs(x)>abs(y)):
            return(4)
        elif (y<0) and (abs(y)>abs(x)):
            return(6)

def pdistance(point1, point2):
    x1, y1 = point1
    x2, y2 = point2
    distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    return distance

class CustomTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)  # Make the text edit read-only
        self.setMaximumHeight(40)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Q:
            QApplication.quit()  # Quit when 'Q' is pressed
        elif event.key() == Qt.Key_C:
            global chaincode
            chaincode=''
            self.setText('')
        else:
            super().keyPressEvent(event)  # Default behavior for other keys

class MouseTracker(QWidget):
    def __init__(self):
        super().__init__()
        self.prev_pos= (-1,-1)
        self.current_pos= (-1,-1)
        
        self.setWindowTitle("Mouse Position Tracker with Text Editor")
        self.setGeometry(100, 100, APP_WIDTH, APP_HEIGHT)
        self.setMouseTracking(True)
        self.mouse_position = (0, 0)
        
        # Create the layout and add widgets
        self.layout = QVBoxLayout(self)

        # Create a placeholder widget for mouse tracking
        self.tracking_area = QWidget(self)
        self.tracking_area.setMinimumHeight(200)

        # Create the text editor
        self.text_edit = CustomTextEdit(self)
        self.text_edit.setPlaceholderText("Freeman chain code goes here")

        # Add widgets to the layout
        self.layout.addWidget(self.tracking_area)
        self.layout.addWidget(self.text_edit)

        # Set the layout for the main widget
        self.setLayout(self.layout)

    def mouseMoveEvent(self, event):
        # Get mouse position and store it
        self.mouse_position = (event.x(), event.y())
        #print(f"Mouse Position: {self.mouse_position}")
        if self.prev_pos==(-1,-1):
            self.prev_pos= self.mouse_position
        self.current_pos= self.mouse_position
        
            # draw the line
    def drawLine(self, painter):
        if pdistance(self.current_pos, self.prev_pos)>20:
            code= str(freeman(self.current_pos[0]-self.prev_pos[0], self.prev_pos[1]-self.current_pos[1]))
            #self.text_edit.setText(f"Mouse Position: {self.mouse_position[0]}, {self.mouse_position[1]}")
            global chaincode 
            chaincode += code
            print(f"from {self.prev_pos} to {self.current_pos}: {chaincode}")
            self.text_edit.setText(chaincode)
            painter = QPainter(self)
            painter.setPen(QPen(Qt.yellow, 10, Qt.SolidLine))  # Black color, 2 pixels width
            painter.drawLine(self.prev_pos[0], self.prev_pos[1], self.current_pos[0], self.current_pos[1])
            self.prev_pos= self.current_pos

    def drawPos(self, painter):
        # Draw the current mouse position
        painter = QPainter(self)
        painter.setPen(QPen(Qt.green, 5, Qt.SolidLine))
        painter.drawText(self.mouse_position[0], self.mouse_position[1], f"({self.mouse_position[0]}, {self.mouse_position[1]})")
    
    def paintEvent(self, event):
        painter = QPainter(self)
        self.drawLine(painter)
        self.drawPos(painter)
        self.update()  # Trigger a redraw of the widget

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Q:
            QApplication.quit()
        elif event.key() == Qt.Key_C:
            global chaincode 
            chaincode='a'
            self.text_edit.setText('')
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MouseTracker()
    window.show()
    sys.exit(app.exec())
