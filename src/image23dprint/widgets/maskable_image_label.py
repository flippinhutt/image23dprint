"""
MaskableImageLabel widget for interactive image masking.

Supports freehand drawing, rectangle selection (GrabCut), scaling lines,
and AI-powered background removal.
"""

from typing import Optional, List, Tuple, Callable
import numpy as np
import cv2
from PySide6.QtWidgets import QLabel, QFileDialog, QInputDialog, QWidget
from PySide6.QtCore import Qt, QPoint, QRect, QTimer
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QMouseEvent


class MaskableImageLabel(QLabel):
    """
    Interactive QLabel widget for image masking and editing.

    Provides multiple masking tools including AI-powered background removal,
    GrabCut selection, edge detection, freehand drawing, and scaling calibration.
    Supports undo/redo functionality and real-time visual feedback.

    Attributes:
        title: Display name for this image view
        image: Loaded QPixmap for display
        mask: Binary QImage mask (Format_Mono)
        drawing: Flag indicating active freehand drawing
        last_point: Previous mouse position during drawing
        brush_mode: Drawing mode (1=Remove background, 0=Keep foreground)
        grabcut_mode: Flag for GrabCut rectangle selection mode
        scale_mode: Flag for scaling line measurement mode
        scale_line: Tuple of start/end points for scale measurement
        rect_start: Rectangle selection start point
        rect_end: Rectangle selection end point
        history: Stack of previous mask states for undo
        quality_warnings: List of quality warning messages
    """
    # Class-level session cache for rembg AI model
    _rembg_session: Optional[object] = None

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the maskable image label widget.

        Args:
            title: Display name for this image view (e.g., "Front View")
            parent: Optional parent widget for proper cleanup
        """
        super().__init__(parent)
        self.title: str = title
        self.setText(f"Click to Load {title}")
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(300, 300)
        self.setStyleSheet("border: 2px dashed #aaa;")
        self.image: Optional[QPixmap] = None
        self.mask: Optional[QImage] = None
        self.drawing: bool = False
        self.last_point: Optional[QPoint] = None
        self.brush_mode: int = 1  # 1=Remove, 0=Keep
        self.grabcut_mode: bool = False
        self.scale_mode: bool = False
        self.scale_line: Optional[Tuple[QPoint, QPoint]] = None
        self.rect_start: Optional[QPoint] = None
        self.rect_end: Optional[QPoint] = None
        self.history: List[QImage] = []
        self.quality_warnings: List[str] = []

    def save_state(self) -> None:
        """
        Save current mask state to the undo history stack.

        Maintains up to 10 previous mask states for undo functionality.
        Automatically removes oldest state when limit is exceeded.
        """
        if self.mask:
            self.history.append(self.mask.copy())
            if len(self.history) > 10:
                self.history.pop(0)

    def undo(self) -> None:
        """
        Revert the mask to its previous state from the history stack.

        Pops the most recent mask from history and updates the display.
        Does nothing if history is empty.
        """
        if self.history:
            self.mask = self.history.pop()
            self.update_display()

    def set_quality_warnings(self, warnings: Optional[List[str]]) -> None:
        """
        Set quality warnings and update visual indicators.

        Args:
            warnings: List of warning messages, or None to clear warnings
        """
        self.quality_warnings = warnings if warnings else []
        self.update_border_style()

    def update_border_style(self) -> None:
        """
        Update the border style based on quality warnings.

        Changes border color and tooltip to reflect image quality status:
        - Orange border with warning icon if issues exist
        - Green border if image loaded successfully
        - Dashed gray border if no image loaded
        """
        if self.quality_warnings:
            self.setStyleSheet("border: 3px solid #ff9800; background-color: #fff3e0;")
            self.setToolTip("⚠️ Quality Issues:\n" + "\n".join(f"• {w}" for w in self.quality_warnings))
        elif self.image:
            self.setStyleSheet("border: 2px solid #4caf50;")
            self.setToolTip("")
        else:
            self.setStyleSheet("border: 2px dashed #aaa;")
            self.setToolTip("")
    def _map_to_image(self, pos: QPoint) -> Optional[QPoint]:
        """
        Maps a mouse position on the QLabel to its corresponding pixel in the underlying image.

        Accounts for image scaling and centering within the label bounds.

        Args:
            pos: Mouse position in label coordinates

        Returns:
            QPoint in image coordinates if within bounds, None otherwise
        """
        if self.image is None:
            return None
        lw, lh = self.width(), self.height()
        iw, ih = self.image.width(), self.image.height()
        ox, oy = (lw - iw) // 2, (lh - ih) // 2
        ip = pos - QPoint(ox, oy)
        return ip if 0 <= ip.x() < iw and 0 <= ip.y() < ih else None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handles mouse press for drawing, GrabCut initiation, or scaling tool.

        Behavior depends on current mode:
        - No image: Triggers load_image() dialog
        - GrabCut mode: Starts rectangle selection
        - Scale mode: Starts scale line drawing
        - Default: Initiates freehand drawing

        Args:
            event: Mouse press event with position and button information
        """
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

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        Handles mouse move for real-time drawing and visual guides.

        Updates display in real-time for:
        - GrabCut rectangle selection
        - Scale line measurement
        - Freehand mask drawing

        Args:
            event: Mouse move event with updated position
        """
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

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        Commits the current interactive operation (GrabCut or Scale line).

        Finalizes user actions initiated in mousePressEvent:
        - GrabCut: Executes segmentation on selected rectangle
        - Scale: Prompts for real-world measurement
        - Drawing: Stops freehand drawing mode

        Args:
            event: Mouse release event indicating end of interaction
        """
        if event.button() == Qt.LeftButton:
            if self.grabcut_mode and self.rect_start:
                self.run_grabcut()
                self.rect_start = self.rect_end = None
            elif self.scale_mode and self.scale_line:
                self.finish_scale_line()
            self.drawing = False
            self.update_display()

    def finish_scale_line(self) -> None:
        """
        Prompts for real-world length and sets the global scale factor.

        Calculates pixel-to-millimeter ratio based on user-drawn line and
        real-world measurement input. Updates parent window's calibration scale.
        """
        len_mm, ok = QInputDialog.getDouble(self, "Scale", "Length (mm):", 50.0, 0.1, 1000.0, 1)
        if ok and self.scale_line:
            p1, p2 = self.scale_line
            px_len = np.sqrt((p1.x()-p2.x())**2 + (p1.y()-p2.y())**2)
            if px_len > 0:
                self.window().set_calibration_scale(len_mm / px_len, self.title)
        self.scale_line = None
        self.update_display()

    def load_image(self) -> None:
        """
        Prompts user to select an image from disk and initializes the mask.

        Opens file dialog for image selection, scales image to fit widget,
        creates initial white mask (all foreground), and optionally triggers
        AI analysis if parent window supports it.
        """
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
            except Exception: # nosec B110
                # Silently ignore errors - analysis is optional
                pass

    def update_display(self) -> None:
        """
        Renders the image with the semi-transparent red mask overlay and UI guides.

        Composites the base image with:
        - Semi-transparent red overlay for masked (background) regions
        - Green dashed rectangle during GrabCut selection
        - Yellow line during scale measurement
        - Warning triangle icon if quality issues detected
        """
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

    def ai_mask(self, progress_callback: Optional[Callable[[int, str], None]] = None) -> None:
        """
        Uses rembg (AI) to automatically isolate the foreground object.

        Employs the ISNet model for high-quality background removal.
        Falls back to threshold-based masking on error. Caches the rembg
        session for improved performance across multiple invocations.

        Args:
            progress_callback: Optional callback function(percent: int, message: str)
                for progress updates during processing
        """
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
                progress_callback(25, "Loading AI background removal model...")

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

    def auto_mask(self) -> None:
        """
        Fallback threshold-based mask generation using OpenCV.

        Applies Gaussian blur, Otsu's automatic thresholding, and morphological
        closing to generate a simple mask. Used as fallback when AI masking fails
        or for simpler images that don't require AI processing.
        """
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

    def edge_mask(self) -> None:
        """
        Generates a mask using Canny edge detection and hole filling.

        Applies edge detection, dilation to connect edges, morphological closing,
        and flood fill to create a solid mask of the foreground object. Works best
        for images with clear object boundaries.
        """
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

    def run_grabcut(self) -> None:
        """
        Applies OpenCV GrabCut algorithm within the selected bounding box.

        Uses iterative graph-cut segmentation to separate foreground from
        background within the user-selected rectangle. Runs 5 iterations
        for refined boundary detection.
        """
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

    def get_mask_array(self) -> Optional[np.ndarray]:
        """
        Returns the current mask as a boolean NumPy array.

        Returns:
            Boolean array where True = foreground, False = background,
            or None if no mask exists
        """
        if not self.mask:
            return None
        g = self.mask.convertToFormat(QImage.Format_Grayscale8)
        a = np.frombuffer(g.bits(), dtype=np.uint8).reshape((g.height(), g.bytesPerLine()))
        return a[:, :g.width()] > 128

    def refine(self) -> None:
        """
        Applies morphological operations to clean up mask noise and fill holes.

        Uses a 7x7 kernel to perform:
        1. Opening: Removes small noise and thin protrusions
        2. Closing: Fills small holes and connects nearby regions

        Useful for smoothing mask boundaries after manual editing or
        automated masking operations.
        """
        if not self.mask:
            return
        self.save_state()
        q = self.mask.convertToFormat(QImage.Format_Grayscale8)
        a = np.frombuffer(q.bits(), dtype=np.uint8).reshape((q.height(), q.bytesPerLine()))[:, :q.width()]
        k = np.ones((7, 7), np.uint8)
        a = cv2.morphologyEx(a, cv2.MORPH_OPEN, k, iterations=2)
        a = cv2.morphologyEx(a, cv2.MORPH_CLOSE, k, iterations=2)
        self.mask = QImage(a.data, a.shape[1], a.shape[0], a.strides[0], QImage.Format_Grayscale8).convertToFormat(QImage.Format_Mono).copy()
        self.update_display()
