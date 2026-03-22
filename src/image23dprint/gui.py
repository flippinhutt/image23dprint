"""Image23DPrint GUI application entry point."""
import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from .ui import Image23DPrintGUI


def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    w = Image23DPrintGUI()
    w.show()
    sys.exit(app.exec())
