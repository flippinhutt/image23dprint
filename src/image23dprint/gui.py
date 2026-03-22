"""
Image23DPrint GUI application.

This module provides the main entry point for the GUI application.
The actual implementation has been modularized into separate packages:
- widgets: Reusable UI components (MaskableImageLabel)
- ui: Main application window (Image23DPrintGUI)
"""
import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

# Import modular components
from .widgets import MaskableImageLabel
from .ui import Image23DPrintGUI

# Re-export for backward compatibility
__all__ = ['MaskableImageLabel', 'Image23DPrintGUI', 'main', 'show_mesh_process']


def show_mesh_process(mesh):
    """Entry point for parallel 3D viewer process to prevent main UI blocking."""
    mesh.show(resolution=(800, 600))


def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    w = Image23DPrintGUI()
    w.show()
    sys.exit(app.exec())
