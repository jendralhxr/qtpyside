import sys
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class TimestampTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Dictionary to store the timestamp of every single keystroke
        self.keystroke_log = []

        # Track the timestamp of the last valid alphanumeric key pressed
        self.last_alphanumeric_timestamp = None
        # Flag to wait for the next alphanumeric key after Tab is pressed
        self.waiting_for_next_after_tab = False

    def keyPressEvent(self, event):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        key = event.key()
        text = event.text()

        # 1. Record the timestamp of EVERY keystroke universally
        self.keystroke_log.append(
            {"key": event.text() or f"KeyC_{key}", "time": current_time}
        )

        # 2. Handle 'Tab' key logic
        if key == Qt.Key_Tab:
            # Print the timestamp of the *last* alphanumeric key pressed
            last_ts_str = (
                self.last_alphanumeric_timestamp
                if self.last_alphanumeric_timestamp
                else "None"
            )
            self.insertPlainText(f"\n[lap end: {last_ts_str}]\n")

            # Set flag to capture the *next* alphanumeric key's timestamp
            self.waiting_for_next_after_tab = True
            return  # Prevent default Tab behavior (indentation)

        # 3. Handle 'Backspace' key logic
        if key == Qt.Key_Backspace:
            self.insertPlainText("-")
            return  # Prevent default Backspace behavior (deleting text)

        # 4. Handle alphanumeric keys (a-z, 0-9)
        if len(text) == 1 and text.isalnum():
            # If we were waiting for this key because of a prior Tab press
            if self.waiting_for_next_after_tab:
                self.insertPlainText(f"[lab start: {current_time}]\n")
                self.waiting_for_next_after_tab = False

            # Update the last alphanumeric tracker
            self.last_alphanumeric_timestamp = current_time

            # Print the character directly
            self.insertPlainText(text)
        else:
            # For any other keys, let PySide handle it normally
            super().keyPressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Timestamp Text Editor")
        self.resize(600, 450)

        # Main Layout
        layout = QVBoxLayout()

        # Text Editor
        self.editor = TimestampTextEdit()
        layout.addWidget(self.editor)

        # Save Button
        self.save_button = QPushButton("Save File")
        # Connect the button click to our save method
        self.save_button.clicked.connect(self.save_file)
        layout.addWidget(self.save_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def save_file(self):
        # Open a native OS save file dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Document", "", "Text Files (*.txt);;All Files (*)"
        )

        # If the user selected a path and didn't cancel the dialog
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as file:
                    # Retrieve the raw text inside the editor and write it
                    file.write(self.editor.toPlainText())
            except Exception as e:
                print(f"Error saving file: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
