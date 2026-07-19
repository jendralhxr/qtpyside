import sys
from datetime import datetime
import pyttsx3
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)
from PySide6.QtGui import QKeySequence
from PySide6.QtGui import QShortcut

class TimestampTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.keystroke_log = []
        self.last_alphanumeric_timestamp = None
        self.waiting_for_next_after_tab = False
        
        # State tracking for the narrator toggle
        self.narrator_enabled = True

        # Initialize the lightweight offline TTS engine
        self.tts_engine = pyttsx3.init(driverName="espeak")
        self.tts_engine.setProperty("rate", 175)
        
        # Set language to Indonesian if available on the system
        self._set_indonesian_voice()

    def _set_indonesian_voice(self):
        """Scans the system for an Indonesian voice profile and applies it."""
        voices = self.tts_engine.getProperty("voices")
        indonesian_voice_id = None

        for voice in voices:
            # Check voice details (lowercased) for 'id' locale tags or 'indonesian' name
            voice_id_lower = voice.id.lower()
            voice_name_lower = voice.name.lower()
            
            # Match standard OS naming formats (e.g., id-ID, MSTTS_V110_idID, com.apple...id-ID)
            if "id_id" in voice_id_lower or "id-id" in voice_id_lower or "indonesian" in voice_name_lower:
                indonesian_voice_id = voice.id
                break
        
        if indonesian_voice_id:
            self.tts_engine.setProperty("voice", indonesian_voice_id)
            print(f"Successfully configured Indonesian voice: {indonesian_voice_id}")
        else:
            print("Warning: Indonesian voice package not detected on this system. Falling back to default system voice.")

    def speak_last_word(self):
        # Guard clause: do nothing if narrator is disabled
        if not self.narrator_enabled:
            return

        full_text = self.toPlainText()
        words = full_text.split()
        
        if words:
            last_word = words[-1]
            # Clean up trailing non-alphanumeric characters (like hyphens from backspaces)
            cleaned_word = "".join(c for c in last_word if c.isalnum())
            
            if cleaned_word:
                self.tts_engine.say(cleaned_word)
                self.tts_engine.runAndWait()

    def keyPressEvent(self, event):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        key = event.key()
        text = event.text()

        self.keystroke_log.append(
            {"key": event.text() or f"KeyC_{key}", "time": current_time}
        )

        # tab is the 'lap' timer
        if key == Qt.Key_Tab:
            last_ts_str = (
                self.last_alphanumeric_timestamp
                if self.last_alphanumeric_timestamp
                else "None"
            )
            self.insertPlainText(f"\n[lap end: {last_ts_str}]\n")
            self.waiting_for_next_after_tab = True
            return

        # 3. 'Backspace' dont delete, it just prints delay mark
        if key == Qt.Key_Backspace:
            self.insertPlainText("-")
            return

        # tilde/backquote resets the buffer
        if key == Qt.Key_QuoteLeft:
            self.setText("");
            return

        # space, return or key speak the last word
        if key == Qt.Key_Space or key == Qt.Key_Return:
            super().keyPressEvent(event)
            self.speak_last_word()
            return

        # 5. Handle alphanumeric keys (a-z, 0-9)
        if len(text) == 1 and text.isalnum():
            if self.waiting_for_next_after_tab:
                self.insertPlainText(f"[lap start: {current_time}]\n")
                self.waiting_for_next_after_tab = False

            self.last_alphanumeric_timestamp = current_time
            self.insertPlainText(text)
        else:
            super().keyPressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lantunkan Kibor")
        #self.resize(600, 450)
        self.save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)

        # Main Layout
        layout = QVBoxLayout()

        # Text Editor
        self.editor = TimestampTextEdit()
        layout.addWidget(self.editor)

        # Bottom Button Row layout (Horizontal)
        button_layout = QHBoxLayout()

        # Toggle Narrator Button
        self.toggle_button = QPushButton("Narrator: ENABLED")
        self.toggle_button.clicked.connect(self.toggle_narrator)
        button_layout.addWidget(self.toggle_button)

        # Save Button
        self.save_button = QPushButton("Save File")
        self.save_button.clicked.connect(self.save_file)
        button_layout.addWidget(self.save_button)
        self.save_shortcut.activated.connect(self.save_file)
        
        # Add button layout to main window layout
        layout.addLayout(button_layout)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def toggle_narrator(self):
        # Invert boolean state in the text editor tracker
        self.editor.narrator_enabled = not self.editor.narrator_enabled
        
        # Adjust text based on the current state
        if self.editor.narrator_enabled:
            self.toggle_button.setText("Narrator: ENABLED")
        else:
            self.toggle_button.setText("Narrator: DISABLED")

    def save_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Document", "", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(self.editor.toPlainText())
            except Exception as e:
                print(f"Error saving file: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
