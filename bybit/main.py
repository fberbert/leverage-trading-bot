#!/usr/bin/env python3

import sys
import os
from PyQt5.QtWidgets import QApplication
from ui import MainWindow

os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
