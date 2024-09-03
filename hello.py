import random
import sys

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (QApplication, QLabel, QPushButton,
                               QVBoxLayout, QWidget)
from __feature__ import snake_case, true_property


class MyWidget(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        self.hello = [
"Hello, World! (English)", "Hola, Mundo! (Spanish)", "Bonjour, le Monde! (French)", "Hallo, Welt! (German)", "Ciao, Mondo! (Italian)", "こんにちは、世界！(Japanese)", "안녕하세요, 세계! (Korean)", "你好，世界！(Chinese)", "Привет, мир! (Russian)", "Olá, Mundo! (Portuguese)", "سلام دنیا! (Persian)", "नमस्ते, दुनिया! (Hindi)", "வணக்கம், உலகம்! (Tamil)", "ಹಲೋ, ಪ್ರಪಂಚ! (Kannada)", "ഹലോ, ലോകം! (Malayalam)", "হ্যালো, বিশ্ব! (Bengali)", "ਸਤ ਸ੍ਰੀ ਅਕਾਲ, ਦੁਨਿਆ! (Punjabi)", "සුභ දවසක්, ලෝකය! (Sinhala)", "မင်္ဂလာပါ, ကမ္ဘာ! (Burmese)", "สวัสดี, โลก! (Thai)", "សួស្តី​ពិភពលោក! (Khmer)", "Chào, Thế Giới! (Vietnamese)", "ສະບາຍດີ, ທ່ານໂລກ! (Lao)", "Mabuhay, Mundo! (Filipino)", "Salam, Dunia! (Malay/Indonesian)", "Walay, Kalibutan! (Cebuano)", "Naha, Dunya! (Sundanese)", "Halo, Jagad! (Javanese)", "Aloha, Donyo! (Balinese)", "Helo, Dunia! (Madurese)", "Tabea, Alam! (Minangkabau)", "Salamaik, Dunia! (Lampung)"        ]

        self.button = QPushButton("Click me!")
        self.message = QLabel("Hello World")
        self.message.alignment = Qt.AlignCenter

        self.layout = QVBoxLayout(self)
        self.layout.add_widget(self.message)
        self.layout.add_widget(self.button)

        # Connecting the signal
        self.button.clicked.connect(self.magic)

    @Slot()
    def magic(self):
        self.message.text = random.choice(self.hello)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    widget = MyWidget()
    widget.show()

    sys.exit(app.exec_())
