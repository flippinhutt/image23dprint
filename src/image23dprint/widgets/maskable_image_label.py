"""
MaskableImageLabel widget for interactive image masking.

Supports freehand drawing, rectangle selection (GrabCut), scaling lines,
and AI-powered background removal.
"""

import numpy as np
import cv2
from PySide6.QtWidgets import QLabel, QFileDialog, QInputDialog
from PySide6.QtCore import Qt, QPoint, QRect, QTimer
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor


class MaskableImageLabel(QLabel):
    """
    Subclass of QLabel for interactive image masking.
    Supports freehand drawing, rectangle selection (GrabCut), scaling lines,
    and AI-powered background removal.
    """
    _rembg_session = None

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.setText(f"Click to Load {title}")
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(300, 300)
        self.setStyleSheet("border: 2px dashed #aaa;")
        self.image = None
        self.mask = None
        self.drawing = False
        self.last_point = None
        self.brush_mode = 1 # 1=Remove, 0=Keep
        self.grabcut_mode = False
        self.scale_mode = False
        self.scale_line = None
        self.rect_start = self.rect_end = None
        self.history = []
        self.quality_warnings = []

    def save_state(self):
        """Save current mask state to the undo history stack."""
        if self.mask:
            self.history.append(self.mask.copy())
            if len(self.history) > 10:
                self.history.pop(0)

    def undo(self):
        """Revert the mask to its previous state from the history stack."""
        if self.history:
            self.mask = self.history.pop()
            self.update_display()

    def set_quality_warnings(self, warnings):
        """Set quality warnings and update visual indicators."""
        self.quality_warnings = warnings if warnings else []
        self.update_border_style()

    def update_border_style(self):
        """Update the border style based on quality warnings."""
        if self.quality_warnings:
            self.setStyleSheet("border: 3px solid #ff9800; background-color: #fff3e0;")
            self.setToolTip(f"⚠️ Quality Issues:\n" + "\n".join(f"• {w}" for w in self.quality_warnings))
        elif self.image:
            self.setStyleSheet("border: 2px solid #4caf50;")
            self.setToolTip("")
        else:
            self.setStyleSheet("border: 2px dashed #aaa;")
            self.setToolTip("")
    def _map_to_image(self, pos):
        """Maps a mouse position on the QLabel to its corresponding pixel in the underlying image."""
        if self.image is None:
            return None
        lw, lh = self.width(), self.height()
        iw, ih = self.image.width(), self.image.height()
        ox, oy = (lw - iw) // 2, (lh - ih) // 2
        ip = pos - QPoint(ox, oy)
        return ip if 0 <= ip.x() < iw and 0 <= ip.y() < ih else None

    def mousePressEvent(self, event):
        """Handles mouse press for drawing, GrabCut initiation, or scaling tool."""
        if self.image is None:
            self.load_image()
        elif event.button() == Qt.LeftButton:
            p = self._map_to_image(event.position().toPoint())
            if p:
                if self.grabcut_mode:
                    self.rect_start = self.rect_end = p
                elif self.scale_mode:
                    self.scale_line = (p, p)
                else:
                    self.save_state()
                    self.drawing = True
                    self.last_point = p

    def mouseMoveEvent(self, event):
        """Handles mouse move for real-time drawing and visual guides."""
        p = self._map_to_image(event.position().toPoint())
        if not p:
            return
        if self.grabcut_mode and self.rect_start:
            self.rect_end = p
            self.update_display()
        elif self.scale_mode and self.scale_line:
            self.scale_line = (self.scale_line[0], p)
            self.update_display()
        elif self.drawing and self.mask:
            painter = QPainter(self.mask)
            color = Qt.color1 if self.brush_mode == 1 else Qt.color0
            painter.setPen(QPen(color, 20, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(self.last_point, p)
            self.last_point = p
            self.update_display()

    def mouseReleaseEvent(self, event):
        """Commits the current interactive operation (GrabCut or Scale line)."""
        if event.button() == Qt.LeftButton:
            if self.grabcut_mode and self.rect_start:
                self.run_grabcut()
                self.rect_start = self.rect_end = None
            elif self.scale_mode and self.scale_line:
                self.finish_scale_line()
            self.drawing = False
            self.update_display()

    def finish_scale_line(self):
        """Prompts for real-world length and sets the global scale factor."""
        len_mm, ok = QInputDialog.getDouble(self, "Scale", "Length (mm):", 50.0, 0.1, 1000.0, 1)
        if ok and self.scale_line:
            p1, p2 = self.scale_line
            px_len = np.sqrt((p1.x()-p2.x())**2 + (p1.y()-p2.y())**2)
            if px_len > 0:
                self.window().set_calibration_scale(len_mm / px_len, self.title)
        self.scale_line = None
        self.update_display()

    def load_image(self):
        """Prompts user to select an image from disk and initializes the mask."""
        path, _ = QFileDialog.getOpenFileName(self, f"Open {self.title}", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            pix = QPixmap(path)
            self.image = pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.mask = QImage(self.image.size(), QImage.Format_Mono)
            self.mask.fill(Qt.color1)
            self.quality_warnings = []
            self.update_border_style()
            self.update_display()

            # Trigger automatic AI analysis (non-blocking, optional)
            try:
                parent = self.window()
                if hasattr(parent, 'analyze_with_llm'):
                    # Schedule analysis to run after UI updates (non-blocking)
                    QTimer.singleShot(100, parent.analyze_with_llm)
            except Exception as e:
                # Silently ignore errors - analysis is optional
                pass

    def update_display(self):
        """Renders the image with the semi-transparent red mask overlay and UI guides."""
        if not self.image or not self.mask:
            return
        display = self.image.copy()
        w, h = self.mask.width(), self.mask.height()

        gray = self.mask.convertToFormat(QImage.Format_Grayscale8)
        mask_arr = np.frombuffer(gray.bits(), dtype=np.uint8).reshape((h, gray.bytesPerLine()))[:, :w]

        overlay = QImage(w, h, QImage.Format_ARGB32)
        overlay.fill(0)
        arr = np.frombuffer(overlay.bits(), dtype=np.uint8).reshape((h, overlay.bytesPerLine() // 4, 4))
        arr[mask_arr == 0, 2] = 255 # Red
        arr[mask_arr == 0, 3] = 120 # Semi-transparent Alpha

        painter = QPainter(display)
        painter.drawImage(0, 0, overlay)
        if self.grabcut_mode and self.rect_start and self.rect_end:
            painter.setPen(QPen(QColor(0, 255, 0), 2, Qt.DashLine))
            painter.drawRect(QRect(self.rect_start, self.rect_end).normalized())
        if self.scale_line:
            painter.setPen(QPen(QColor(255, 255, 0), 2, Qt.SolidLine))
            painter.drawLine(self.scale_line[0], self.scale_line[1])

        # Draw warning icon if quality warnings exist
        if self.quality_warnings:
            icon_size = 32
            x_pos = w - icon_size - 5
            y_pos = 5

            # Draw warning triangle background
            painter.setBrush(QColor(255, 152, 0))
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            points = [
                QPoint(x_pos + icon_size // 2, y_pos),
                QPoint(x_pos, y_pos + icon_size),
                QPoint(x_pos + icon_size, y_pos + icon_size)
            ]
            painter.drawPolygon(points)

            # Draw exclamation mark
            painter.setPen(QPen(QColor(255, 255, 255), 3, Qt.SolidLine))
            painter.drawLine(x_pos + icon_size // 2, y_pos + 8, x_pos + icon_size // 2, y_pos + 18)
            painter.drawPoint(x_pos + icon_size // 2, y_pos + 22)

        painter.end()
        self.setPixmap(display)

    def ai_mask(self, progress_callback=None):
        """Uses rembg (AI) to automatically isolate the foreground object."""
        if not self.image:
            return
        self.save_state()
        print(f"AI Masking {self.title} with ISNet...")

        if progress_callback:
            progress_callback(0, f"Preparing {self.title} for background removal...")

        try:
            from rembg import remove, new_session
            from PIL import Image

            if progress_callback:
                progress_callback(25, f"Loading AI background removal model...")

            if MaskableImageLabel._rembg_session is None:
                MaskableImageLabel._rembg_session = new_session("isnet-general-use")

            if progress_callback:
                progress_callback(40, f"Analyzing {self.title} image...")

            qimg = self.image.toImage().convertToFormat(QImage.Format_RGBA8888)
            ptr = qimg.bits()
            arr = np.frombuffer(ptr, dtype=np.uint8).reshape((qimg.height(), qimg.bytesPerLine() // 4, 4))[:, :qimg.width()].copy()
            img = Image.fromarray(arr)

            if progress_callback:
                progress_callback(60, f"Removing background from {self.title}...")

            output = remove(img, session=MaskableImageLabel._rembg_session)

            if progress_callback:
                progress_callback(80, f"Creating mask for {self.title}...")

            mask_v = (np.array(output)[:, :, 3] > 127).astype(np.uint8) * 255
            self.mask = QImage(mask_v.data, mask_v.shape[1], mask_v.shape[0], mask_v.strides[0], QImage.Format_Grayscale8).convertToFormat(QImage.Format_Mono).copy()
            bg_pct = np.sum(mask_v==0)/mask_v.size
            print(f"AI Success: {bg_pct:.1%} background removed")
            if bg_pct > 0.99:
                print("Warning: AI might have missed the object. Try 'Smart Outline'!")

            if progress_callback:
                progress_callback(100, f"Background removal complete for {self.title}")
        except Exception as e:
            print(f"AI Error: {e}")
            if progress_callback:
                progress_callback(50, f"AI failed, using fallback for {self.title}...")
            self.auto_mask()
            if progress_callback:
                progress_callback(100, f"Fallback completed for {self.title}")
        self.update_display()

    def auto_mask(self):
        """Fallback threshold-based mask generation using OpenCV."""
        if not self.image:
            return
        self.save_state()
        q = self.image.toImage().convertToFormat(QImage.Format_Grayscale8)
        a = np.frombuffer(q.bits(), dtype=np.uint8).reshape((q.height(), q.bytesPerLine()))[:, :q.width()]
        b = cv2.GaussianBlur(a, (5, 5), 0)
        _, m = cv2.threshold(b, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2)
        self.mask = QImage(m.data, m.shape[1], m.shape[0], m.strides[0], QImage.Format_Grayscale8).convertToFormat(QImage.Format_Mono).copy()
        self.update_display()

    def edge_mask(self):
        """Generates a mask using Canny edge detection and hole filling."""
        if not self.image:
            return
        self.save_state()
        print(f"Edge Masking {self.title} with Canny...")
        q = self.image.toImage().convertToFormat(QImage.Format_Grayscale8)
        a = np.frombuffer(q.bits(), dtype=np.uint8).reshape((q.height(), q.bytesPerLine()))[:, :q.width()]

        # 1. Blur and Canny
        b = cv2.GaussianBlur(a, (5, 5), 0)
        edges = cv2.Canny(b, 50, 150)

        # 2. Dilate to connect edges
        k = np.ones((5, 5), np.uint8)
        m = cv2.dilate(edges, k, iterations=2)

        # 3. Fill holes using morphology
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=3)

        # 4. Optional: floodFill to fill inner areas if the object container is closed
        h, w = m.shape
        mask_flood = np.zeros((h+2, w+2), np.uint8)
        # We assume edges are NOT at the very boundary for floodFill to work from origin
        # (Though this isn't always true, it's a common heuristic for object isolated photos)
        m_filled = m.copy()
        cv2.floodFill(m_filled, mask_flood, (0, 0), 255)
        m_filled = cv2.bitwise_not(m_filled)
        m = cv2.bitwise_or(m, m_filled)

        self.mask = QImage(m.data, m.shape[1], m.shape[0], m.strides[0], QImage.Format_Grayscale8).convertToFormat(QImage.Format_Mono).copy()
        self.update_display()

    def run_grabcut(self):
        """Applies OpenCV GrabCut algorithm within the selected bounding box."""
        if not self.image or not self.rect_start:
            return
        self.save_state()
        q = self.image.toImage().convertToFormat(QImage.Format_RGB888)
        s, w, h = q.bytesPerLine(), q.width(), q.height()
        a = np.frombuffer(q.bits(), dtype=np.uint8).reshape((h, s))[:, :w*3].reshape((h, w, 3)).copy()
        r = (QRect(self.rect_start, self.rect_end).normalized().x(), QRect(self.rect_start, self.rect_end).normalized().y(), QRect(self.rect_start, self.rect_end).normalized().width(), QRect(self.rect_start, self.rect_end).normalized().height())
        m = np.zeros(a.shape[:2], np.uint8)
        cv2.grabCut(a, m, r, np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64), 5, cv2.GC_INIT_WITH_RECT)
        mv = np.where((m == 2) | (m == 0), 0, 255).astype('uint8')
        self.mask = QImage(mv.data, w, h, mv.strides[0], QImage.Format_Grayscale8).convertToFormat(QImage.Format_Mono).copy()
        self.update_display()

    def get_mask_array(self):
        """Returns the current mask as a boolean NumPy array."""
        if not self.mask:
            return None
        g = self.mask.convertToFormat(QImage.Format_Grayscale8)
        a = np.frombuffer(g.bits(), dtype=np.uint8).reshape((g.height(), g.bytesPerLine()))
        return a[:, :g.width()] > 128

        if self.mask:
            self.save_state()
            self.mask.fill(Qt.color1)
            self.update_display()

    def refine(self):
        """Applies morphological operations to clean up mask noise and fill holes."""
        if not self.mask:
            return
        self.save_state()
        q = self.mask.convertToFormat(QImage.Format_Grayscale8)
        a = np.frombuffer(q.bits(), dtype=np.uint8).reshape((q.height(), q.bytesPerLine()))[:, :q.width()]
        k = np.ones((7,7), np.uint8)
        a = cv2.morphologyEx(a, cv2.MORPH_OPEN, k, iterations=2)
        a = cv2.morphologyEx(a, cv2.MORPH_CLOSE, k, iterations=2)
        self.mask = QImage(a.data, a.shape[1], a.shape[0], a.strides[0], QImage.Format_Grayscale8).convertToFormat(QImage.Format_Mono).copy()
        self.update_display()
