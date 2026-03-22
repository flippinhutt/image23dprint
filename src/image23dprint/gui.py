import sys
import os
import re
import numpy as np
import cv2
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QFileDialog,
                             QSlider, QGroupBox, QInputDialog, QLineEdit, QRadioButton,
                             QProgressBar)
from PySide6.QtCore import Qt, QPoint, QRect, QTimer
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QIcon

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
            progress_callback(0, f"Starting AI mask for {self.title}...")

        try:
            from rembg import remove, new_session
            from PIL import Image

            if progress_callback:
                progress_callback(25, f"Loading AI model...")

            if MaskableImageLabel._rembg_session is None:
                MaskableImageLabel._rembg_session = new_session("isnet-general-use")

            if progress_callback:
                progress_callback(40, f"Processing {self.title} image...")

            qimg = self.image.toImage().convertToFormat(QImage.Format_RGBA8888)
            ptr = qimg.bits()
            arr = np.frombuffer(ptr, dtype=np.uint8).reshape((qimg.height(), qimg.bytesPerLine() // 4, 4))[:, :qimg.width()].copy()
            img = Image.fromarray(arr)

            if progress_callback:
                progress_callback(60, f"Running AI detection on {self.title}...")

            output = remove(img, session=MaskableImageLabel._rembg_session)

            if progress_callback:
                progress_callback(80, f"Generating mask for {self.title}...")

            mask_v = (np.array(output)[:, :, 3] > 127).astype(np.uint8) * 255
            self.mask = QImage(mask_v.data, mask_v.shape[1], mask_v.shape[0], mask_v.strides[0], QImage.Format_Grayscale8).convertToFormat(QImage.Format_Mono).copy()
            bg_pct = np.sum(mask_v==0)/mask_v.size
            print(f"AI Success: {bg_pct:.1%} background removed")
            if bg_pct > 0.99:
                print("Warning: AI might have missed the object. Try 'Smart Outline'!")

            if progress_callback:
                progress_callback(100, f"Completed {self.title}")
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

def show_mesh_process(mesh):
    """Entry point for parallel 3D viewer process to prevent main UI blocking."""
    mesh.show(resolution=(800, 600))

class Image23DPrintGUI(QMainWindow):
    """Main application window for Image23DPrint."""
    _ollama_client = None

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image23DPrint - Space Carving")
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.carver = None
        self.current_mesh = None
        self.setup_ui()

    def setup_ui(self):
        """Initializes the UI layout, sliders, buttons, and image labels."""
        cw = QWidget()
        self.setCentralWidget(cw)
        ml = QVBoxLayout(cw)
        il = QHBoxLayout()
        self.view_front = MaskableImageLabel("Front")
        self.view_side = MaskableImageLabel("Side")
        self.view_top = MaskableImageLabel("Top")
        for v in [self.view_front, self.view_side, self.view_top]:
            il.addWidget(v)
        ml.addLayout(il)
        cg = QGroupBox("Controls")
        cl = QVBoxLayout(cg)
        ml.addWidget(cg)
        rl = QHBoxLayout()
        cl.addLayout(rl)
        rl.addWidget(QLabel("Res:"))
        self.res_slider = QSlider(Qt.Horizontal)
        self.res_slider.setRange(32, 256)
        self.res_slider.setValue(64)
        rl.addWidget(self.res_slider)
        self.res_label = QLabel("64")
        rl.addWidget(self.res_label)
        self.res_slider.valueChanged.connect(lambda v: self.res_label.setText(str(v)))
        mg = QGroupBox("Target Dimensions (mm)")
        mgl = QHBoxLayout(mg)
        cl.addWidget(mg)
        self.edit_w, self.edit_h, self.edit_d = QLineEdit(), QLineEdit(), QLineEdit()
        for e, label_text in [(self.edit_w, "W:"), (self.edit_h, "H:"), (self.edit_d, "D:")]:
            mgl.addWidget(QLabel(label_text))
            mgl.addWidget(e)
        bl = QHBoxLayout()
        cl.addLayout(bl)
        self.btn_ai = QPushButton("AI Auto-Mask")
        self.btn_ai.clicked.connect(self.ai_mask_all)
        self.btn_analyze = QPushButton("Analyze with AI")
        self.btn_analyze.clicked.connect(self.analyze_with_llm)
        self.btn_edge = QPushButton("Edge Mask")
        self.btn_edge.setToolTip("Use Canny Edge Detection for high-contrast objects")
        self.btn_edge.clicked.connect(self.edge_mask_all)
        self.btn_smart = QPushButton("Smart Outline")
        self.btn_smart.clicked.connect(lambda: self.set_mode('smart'))
        self.btn_scale = QPushButton("Scale Tool")
        self.btn_scale.clicked.connect(lambda: self.set_mode('scale'))
        self.btn_undo = QPushButton("Undo")
        self.btn_undo.clicked.connect(self.undo_all)
        self.btn_refine = QPushButton("Refine Mask")
        self.btn_refine.clicked.connect(self.refine_masks)
        self.btn_clr = QPushButton("Clear")
        self.btn_clr.clicked.connect(self.clear_all_masks)
        self.btn_gen = QPushButton("Generate STL")
        self.btn_gen.clicked.connect(self.generate_stl)
        self.btn_2d3d = QPushButton("2D to 3D")
        self.btn_2d3d.setToolTip("Generate a thin 3D model from a single 2D mask (Front)")
        self.btn_2d3d.clicked.connect(self.generate_2d3d)
        self.btn_pre = QPushButton("Preview 3D")
        self.btn_pre.clicked.connect(self.preview_3d)
        self.btn_pre.setVisible(False)
        for b in [self.btn_ai, self.btn_analyze, self.btn_edge, self.btn_smart, self.btn_refine, self.btn_scale, self.btn_undo, self.btn_clr, self.btn_gen, self.btn_2d3d, self.btn_pre]:
            bl.addWidget(b)
        gl = QHBoxLayout()
        cl.addLayout(gl)
        self.radio_remove = QRadioButton("Remove (Red)")
        self.radio_keep = QRadioButton("Keep (Orig)")
        self.radio_remove.setChecked(True)
        self.radio_remove.toggled.connect(self.update_brush_mode)
        self.radio_keep.toggled.connect(self.update_brush_mode)
        gl.addWidget(self.radio_remove)
        gl.addWidget(self.radio_keep)

        ag = QGroupBox("AI Analysis")
        al = QVBoxLayout(ag)
        ml.addWidget(ag)
        self.llm_feedback_label = QLabel("No analysis yet.")
        self.llm_feedback_label.setWordWrap(True)
        self.llm_feedback_label.setStyleSheet("padding: 10px; background-color: #f5f5f5;")
        al.addWidget(self.llm_feedback_label)

        # Progress UI components
        pg = QGroupBox("Processing")
        pgl = QVBoxLayout(pg)
        ml.addWidget(pg)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        pgl.addWidget(self.progress_bar)
        pbl = QHBoxLayout()
        pgl.addLayout(pbl)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setVisible(False)
        pbl.addWidget(self.btn_cancel)

        self.st = QLabel("Load Images -> AI Mask -> Generate")
        ml.addWidget(self.st)
        self.update_brush_mode()

    def set_mode(self, mode):
        """Toggles between 'Smart Outline' and 'Scale Tool' interaction modes."""
        smart = (mode == 'smart' and not self.view_front.grabcut_mode)
        scale = (mode == 'scale' and not self.view_front.scale_mode)
        for v in [self.view_front, self.view_side, self.view_top]:
            v.grabcut_mode = smart
            v.scale_mode = scale
        self.btn_smart.setStyleSheet("background-color: lightgreen;" if smart else "")
        self.btn_scale.setStyleSheet("background-color: yellow; color: black;" if scale else "")

    def set_calibration_scale(self, factor, title):
        """Calculates world dimensions for all axes based on a single measured reference line."""
        v = None
        if title == "Front":
            v = self.view_front
        elif title == "Side":
            v = self.view_side
        elif title == "Top":
            v = self.view_top
        if not v:
            return
        
        mask = v.get_mask_array()
        if mask is not None and np.any(mask):
            coords = np.argwhere(mask)
            y0, x0 = coords.min(axis=0)
            y1, x1 = coords.max(axis=0) + 1
            obj_h_px = y1 - y0
            obj_w_px = x1 - x0
        else:
            obj_h_px = v.image.height()
            obj_w_px = v.image.width()

        if title == "Front":
            self.edit_w.setText(f"{obj_w_px * factor:.2f}")
            self.edit_h.setText(f"{obj_h_px * factor:.2f}")
        elif title == "Side":
            self.edit_d.setText(f"{obj_w_px * factor:.2f}")
            self.edit_h.setText(f"{obj_h_px * factor:.2f}")
        elif title == "Top":
            self.edit_w.setText(f"{obj_w_px * factor:.2f}")
            self.edit_d.setText(f"{obj_h_px * factor:.2f}")

    def update_brush_mode(self):
        """Synchronizes the brush interaction based on the radio button state."""
        m = 0 if self.radio_keep.isChecked() else 1
        for v in [self.view_front, self.view_side, self.view_top]:
            v.brush_mode = m
        self.st.setText(f"Active Brush: {'KEEP (No Red)' if m==0 else 'REMOVE (Red)'}")

    def analyze_with_llm(self):
        """Analyzes loaded images using Ollama LLM vision and displays feedback."""
        if Image23DPrintGUI._ollama_client is None:
            try:
                from .ollama_vision import OllamaClient
                Image23DPrintGUI._ollama_client = OllamaClient()
            except Exception as e:
                self.llm_feedback_label.setText(f"Error loading Ollama client: {e}")
                return

        client = Image23DPrintGUI._ollama_client
        if not client.is_available():
            self.llm_feedback_label.setText("Ollama not available. Install from ollama.ai and run 'ollama pull llava'")
            return

        self.llm_feedback_label.setText("Analyzing images...")

        views = [
            (self.view_front, "Front"),
            (self.view_side, "Side"),
            (self.view_top, "Top")
        ]

        results = []
        import tempfile
        for view, name in views:
            if view.image is None:
                continue

            temp_path = os.path.join(tempfile.gettempdir(), f"image23dprint_{name.lower()}.png")
            try:
                view.image.save(temp_path)
                analysis = client.analyze_image(temp_path)

                if "error" not in analysis:
                    orientation = analysis.get("orientation", "unknown")
                    confidence = analysis.get("confidence", 0.0)
                    suggestions = analysis.get("suggestions", "")
                    warnings = analysis.get("quality_warnings", [])

                    # Update visual indicators on the view
                    view.set_quality_warnings(warnings)

                    result_text = f"**{name}**: {suggestions}"
                    if warnings:
                        result_text += f"\n  Warnings: {', '.join(warnings)}"
                    results.append(result_text)
                else:
                    view.set_quality_warnings([])
                    results.append(f"**{name}**: {analysis.get('suggestions', 'Analysis failed')}")
            except Exception as e:
                view.set_quality_warnings([])
                results.append(f"**{name}**: Error - {str(e)}")

        if results:
            self.llm_feedback_label.setText("\n\n".join(results))
        else:
            self.llm_feedback_label.setText("No images loaded. Load images first.")

    def ai_mask_all(self):
        """Triggers AI background removal for all three image views."""
        views = [self.view_front, self.view_side, self.view_top]
        total_views = sum(1 for v in views if v.image is not None)

        if total_views == 0:
            self.st.setText("No images loaded to mask")
            return

        # Show progress UI
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.btn_cancel.setVisible(True)

        current_view_idx = [0]  # Use list to allow modification in nested function

        def update_progress(percent, message):
            """Update progress bar based on current view and its progress."""
            # Calculate overall progress across all views
            view_progress = (current_view_idx[0] * 100 + percent) / total_views
            self.progress_bar.setValue(int(view_progress))
            self.st.setText(message)
            QApplication.processEvents()  # Keep UI responsive

        # Process each view sequentially
        for v in views:
            if v.image is not None:
                v.ai_mask(progress_callback=update_progress)
                current_view_idx[0] += 1

        # Hide progress UI
        self.progress_bar.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.st.setText("AI masking complete")

    def edge_mask_all(self):
        """Triggers local edge detection (Canny) for all three image views."""
        for v in [self.view_front, self.view_side, self.view_top]:
            v.edge_mask()

    def refine_masks(self):
        """Triggers mask refinement (morphology) for all three image views."""
        for v in [self.view_front, self.view_side, self.view_top]:
            v.refine()

    def clear_all_masks(self):
        """Clears masks for all three image views."""
        for v in [self.view_front, self.view_side, self.view_top]:
            v.clear_mask()

    def undo_all(self):
        """Triggers undo for all three image views."""
        for v in [self.view_front, self.view_side, self.view_top]:
            v.undo()

    def get_dim(self, text):
        """Extracts numerical value from dimension input strings using regular expressions."""
        m = re.search(r"[-+]?\d*\.\d+|\d+", text)
        return float(m.group()) if m else 1.0

    def generate_stl(self):
        """Orchestrates the 3D carving process and mesh generation."""
        from .mesh import SpaceCarver
        w, h, d = self.get_dim(self.edit_w.text()), self.get_dim(self.edit_h.text()), self.get_dim(self.edit_d.text())
        print(f"Generating for dims: {w}x{h}x{d}")
        self.carver = SpaceCarver(res=self.res_slider.value(), dims=(w, d, h))
        masks = {'front': self.view_front.get_mask_array(), 'side': self.view_side.get_mask_array(), 'top': self.view_top.get_mask_array()}
        for a, m in masks.items():
            if m is not None:
                self.carver.apply_mask(m, axis=a)
        self.current_mesh = self.carver.generate_mesh(smooth=True)
        if self.current_mesh:
            ex = self.current_mesh.extents
            if ex[0] > 0 and ex[1] > 0 and ex[2] > 0:
                sx, sy, sz = w / ex[0], d / ex[1], h / ex[2]
                self.current_mesh.apply_scale([sx, sy, sz])
            self.btn_pre.setVisible(True)
            self.btn_gen.setText("Export STL")
            self.btn_gen.clicked.disconnect()
            self.btn_gen.clicked.connect(self.export_stl)
            self.st.setText("Generated! Scale applies to export.")
        else:
            self.st.setText("No mesh.")

    def export_stl(self):
        """Prompt for file save and export the generated mesh to STL format."""
        if not self.current_mesh:
            return
        p, _ = QFileDialog.getSaveFileName(self, "Save STL", "", "*.stl")
        if p:
            self.current_mesh.export(p)
            self.st.setText(f"Saved to {p}")
            self.btn_gen.setText("Generate STL")
            self.btn_gen.clicked.disconnect()
            self.btn_gen.clicked.connect(self.generate_stl)

    def generate_2d3d(self):
        """Generates a thin 3D mesh from the front mask."""
        from .mesh import SpaceCarver
        m = self.view_front.get_mask_array()
        if m is None:
            self.st.setText("Error: Load 'Front' image and mask it first!")
            return

        # Determine scale factor (mm per pixel)
        # Use the width dimension if set, else default to 1mm/px
        w_mm = self.get_dim(self.edit_w.text())
        coords = np.argwhere(m)
        if coords.size > 0:
            px_w = coords.max(axis=0)[1] - coords.min(axis=0)[1]
            scale = w_mm / px_w if px_w > 0 else 1.0
        else:
            scale = 1.0

        carver = SpaceCarver(res=64) # Dummy carver to access the method
        self.current_mesh = carver.generate_thin_3d(m, thickness_mm=2.5, scale_factor=scale)

        if self.current_mesh:
            self.btn_pre.setVisible(True)
            self.btn_gen.setText("Export STL")
            try:
                self.btn_gen.clicked.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.btn_gen.clicked.connect(self.export_stl)
            self.st.setText("Thin 3D Generated!")
        else:
            self.st.setText("Failed to generate Thin 3D.")

    def preview_3d(self):
        """Opens a 3D preview window for the generated mesh in a separate process."""
        if self.current_mesh:
            import multiprocessing
            p = multiprocessing.Process(target=show_mesh_process, args=(self.current_mesh,))
            p.start()
        else:
            self.st.setText("No mesh to preview.")

def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    w = Image23DPrintGUI()
    w.show()
    sys.exit(app.exec())
