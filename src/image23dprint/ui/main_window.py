import sys
import os
import re
import time
from typing import Optional, Callable, Dict, Tuple
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QFileDialog,
                             QSlider, QGroupBox, QInputDialog, QLineEdit, QRadioButton,
                             QProgressBar)
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QIcon
from ..widgets.maskable_image_label import MaskableImageLabel
from ..workers import MeshGenerationWorker, Thin3DWorker
from ..exporter import MeshExporter, ExportError


def show_mesh_process(mesh) -> None:
    """
    Entry point for parallel 3D viewer process to prevent main UI blocking.

    Args:
        mesh: trimesh.Trimesh object to display
    """
    mesh.show(resolution=(800, 600))


class Image23DPrintGUI(QMainWindow):
    """
    Main application window for Image23DPrint.

    Provides the primary user interface for loading images, masking, and
    generating 3D printable meshes using space carving or thin 3D extrusion.
    """
    _ollama_client: Optional[object] = None

    def __init__(self) -> None:
        """Initialize the main application window and set up the UI."""
        super().__init__()
        self.setWindowTitle("Image23DPrint - Space Carving")
        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.carver: Optional[object] = None
        self.current_mesh: Optional[object] = None
        self.mesh_worker: Optional[MeshGenerationWorker] = None
        self.thin3d_worker: Optional[Thin3DWorker] = None
        self.pending_dims: Optional[Tuple[float, float, float]] = None
        self.operation_start_time: Optional[float] = None
        self.exporter: MeshExporter = MeshExporter()
        self.setup_ui()

    def setup_ui(self) -> None:
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
        self.btn_cancel.clicked.connect(self.cancel_operation)
        pbl.addWidget(self.btn_cancel)

        self.st = QLabel("Load Images -> AI Mask -> Generate")
        ml.addWidget(self.st)
        self.update_brush_mode()

    def set_mode(self, mode: str) -> None:
        """
        Toggles between 'Smart Outline' and 'Scale Tool' interaction modes.

        Args:
            mode: Mode to activate ('smart' for Smart Outline, 'scale' for Scale Tool)
        """
        smart = (mode == 'smart' and not self.view_front.grabcut_mode)
        scale = (mode == 'scale' and not self.view_front.scale_mode)
        for v in [self.view_front, self.view_side, self.view_top]:
            v.grabcut_mode = smart
            v.scale_mode = scale
        self.btn_smart.setStyleSheet("background-color: lightgreen;" if smart else "")
        self.btn_scale.setStyleSheet("background-color: yellow; color: black;" if scale else "")

    def set_calibration_scale(self, factor: float, title: str) -> None:
        """
        Calculates world dimensions for all axes based on a single measured reference line.

        Args:
            factor: Millimeters per pixel conversion factor
            title: View name ('Front', 'Side', or 'Top') that was calibrated
        """
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

    def update_brush_mode(self) -> None:
        """Synchronizes the brush interaction based on the radio button state."""
        m = 0 if self.radio_keep.isChecked() else 1
        for v in [self.view_front, self.view_side, self.view_top]:
            v.brush_mode = m
        self.st.setText(f"Active Brush: {'KEEP (No Red)' if m==0 else 'REMOVE (Red)'}")

    def analyze_with_llm(self) -> None:
        """Analyzes loaded images using Ollama LLM vision and displays feedback."""
        if Image23DPrintGUI._ollama_client is None:
            try:
                from ..ollama_vision import OllamaClient
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

    def ai_mask_all(self) -> None:
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

    def edge_mask_all(self) -> None:
        """Triggers local edge detection (Canny) for all three image views."""
        for v in [self.view_front, self.view_side, self.view_top]:
            v.edge_mask()

    def refine_masks(self) -> None:
        """Triggers mask refinement (morphology) for all three image views."""
        for v in [self.view_front, self.view_side, self.view_top]:
            v.refine()

    def clear_all_masks(self) -> None:
        """Clears masks for all three image views."""
        for v in [self.view_front, self.view_side, self.view_top]:
            v.clear_mask()

    def undo_all(self) -> None:
        """Triggers undo for all three image views."""
        for v in [self.view_front, self.view_side, self.view_top]:
            v.undo()

    def get_dim(self, text: str) -> float:
        """
        Extracts numerical value from dimension input strings using regular expressions.

        Args:
            text: Input string potentially containing a numerical value

        Returns:
            float: Extracted numerical value, or 1.0 if no number found
        """
        m = re.search(r"[-+]?\d*\.\d+|\d+", text)
        return float(m.group()) if m else 1.0

    def generate_stl(self) -> None:
        """Orchestrates the 3D carving process and mesh generation using async worker."""
        # Get dimensions
        w, h, d = self.get_dim(self.edit_w.text()), self.get_dim(self.edit_h.text()), self.get_dim(self.edit_d.text())

        # Prepare masks in the format MeshGenerationWorker expects
        # Dictionary mapping names to (mask_qimage, axis) tuples
        masks = {}

        # Front view
        front_mask_arr = self.view_front.get_mask_array()
        if front_mask_arr is not None:
            # Convert numpy array back to QImage
            front_mask_uint8 = (front_mask_arr > 0).astype(np.uint8) * 255
            front_qimage = QImage(
                front_mask_uint8.data,
                front_mask_uint8.shape[1],
                front_mask_uint8.shape[0],
                front_mask_uint8.strides[0],
                QImage.Format_Grayscale8
            ).copy()
            masks['front'] = (front_qimage, 'front')

        # Side view
        side_mask_arr = self.view_side.get_mask_array()
        if side_mask_arr is not None:
            side_mask_uint8 = (side_mask_arr > 0).astype(np.uint8) * 255
            side_qimage = QImage(
                side_mask_uint8.data,
                side_mask_uint8.shape[1],
                side_mask_uint8.shape[0],
                side_mask_uint8.strides[0],
                QImage.Format_Grayscale8
            ).copy()
            masks['side'] = (side_qimage, 'side')

        # Top view
        top_mask_arr = self.view_top.get_mask_array()
        if top_mask_arr is not None:
            top_mask_uint8 = (top_mask_arr > 0).astype(np.uint8) * 255
            top_qimage = QImage(
                top_mask_uint8.data,
                top_mask_uint8.shape[1],
                top_mask_uint8.shape[0],
                top_mask_uint8.strides[0],
                QImage.Format_Grayscale8
            ).copy()
            masks['top'] = (top_qimage, 'top')

        if not masks:
            self.st.setText("Error: No masks available. Please load and mask images first.")
            return

        # Show progress UI
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.btn_cancel.setVisible(True)
        self.st.setText("Starting mesh generation...")

        # Store dimensions for scaling after generation
        self.pending_dims = (w, h, d)

        # Create worker
        self.mesh_worker = MeshGenerationWorker(
            masks=masks,
            dims=(w, d, h),  # (width, depth, height)
            voxel_res=self.res_slider.value(),
            smooth=True,
            decimate=True
        )

        # Connect signals
        self.mesh_worker.progress.connect(self.on_mesh_progress)
        self.mesh_worker.finished.connect(self.on_mesh_finished)
        self.mesh_worker.error.connect(self.on_mesh_error)

        # Track start time for ETA calculation
        self.operation_start_time = time.time()

        # Start worker
        self.mesh_worker.start()

    def on_mesh_progress(self, current: int, total: int, message: str) -> None:
        """
        Handle progress updates from mesh generation worker.

        Args:
            current: Current progress value
            total: Total progress value
            message: Status message describing current operation
        """
        self.progress_bar.setValue(current)

        # Calculate and display ETA
        if self.operation_start_time is not None and current > 0 and total > 0:
            elapsed = time.time() - self.operation_start_time
            progress_percent = current / total
            if progress_percent > 0.01:  # Only show ETA after 1% progress
                estimated_total_time = elapsed / progress_percent
                remaining = estimated_total_time - elapsed
                if remaining > 0:
                    message = f"{message} (~{int(remaining)}s remaining)"

        self.st.setText(message)

    def on_mesh_finished(self, mesh: object) -> None:
        """
        Handle successful mesh generation completion.

        Args:
            mesh: Generated trimesh.Trimesh object or None if generation failed
        """
        # Hide progress UI
        self.progress_bar.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.operation_start_time = None

        # Store the mesh
        self.current_mesh = mesh

        if self.current_mesh:
            # Apply scaling to match real-world dimensions
            w, h, d = self.pending_dims
            ex = self.current_mesh.extents
            if ex[0] > 0 and ex[1] > 0 and ex[2] > 0:
                sx, sy, sz = w / ex[0], d / ex[1], h / ex[2]
                self.current_mesh.apply_scale([sx, sy, sz])

            # Update UI
            self.btn_pre.setVisible(True)
            self.btn_gen.setText("Export STL")
            try:
                self.btn_gen.clicked.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.btn_gen.clicked.connect(self.export_stl)
            self.st.setText("Generated! Scale applies to export.")
        else:
            self.st.setText("No mesh generated.")

        # Clean up worker
        if hasattr(self, 'mesh_worker') and self.mesh_worker:
            self.mesh_worker.deleteLater()
            self.mesh_worker = None

    def on_mesh_error(self, error_message: str) -> None:
        """
        Handle mesh generation errors.

        Args:
            error_message: Error message string describing what went wrong
        """
        # Hide progress UI
        self.progress_bar.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.operation_start_time = None

        # Show error
        self.st.setText(f"Error: {error_message}")

        # Clean up worker
        if hasattr(self, 'mesh_worker') and self.mesh_worker:
            self.mesh_worker.deleteLater()
            self.mesh_worker = None

    def cancel_operation(self) -> None:
        """Cancel any running worker operation and return UI to ready state."""
        cancelled = False

        # Try to stop mesh worker
        if hasattr(self, 'mesh_worker') and self.mesh_worker and self.mesh_worker.is_running():
            self.mesh_worker.stop()
            self.mesh_worker.deleteLater()
            self.mesh_worker = None
            cancelled = True

        # Try to stop thin 3D worker
        if hasattr(self, 'thin3d_worker') and self.thin3d_worker and self.thin3d_worker.is_running():
            self.thin3d_worker.stop()
            self.thin3d_worker.deleteLater()
            self.thin3d_worker = None
            cancelled = True

        # Return UI to ready state if something was cancelled
        if cancelled:
            # Hide progress UI
            self.progress_bar.setVisible(False)
            self.btn_cancel.setVisible(False)
            self.operation_start_time = None

            # Reset generate button to initial state
            self.btn_gen.setText("Generate STL")
            try:
                self.btn_gen.clicked.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.btn_gen.clicked.connect(self.generate_stl)

            # Update status text
            self.st.setText("Operation cancelled")

    def export_stl(self) -> None:
        """Prompt for file save and export the generated mesh to STL format."""
        if not self.current_mesh:
            return
        p, _ = QFileDialog.getSaveFileName(self, "Save STL", "", "STL Files (*.stl);;OBJ Files (*.obj)")
        if p:
            try:
                self.exporter.export(self.current_mesh, p, validate=True)
                self.st.setText(f"Saved to {p}")
                self.btn_gen.setText("Generate STL")
                self.btn_gen.clicked.disconnect()
                self.btn_gen.clicked.connect(self.generate_stl)
            except ExportError as e:
                self.st.setText(f"Export failed: {e}")
            except Exception as e:
                self.st.setText(f"Unexpected error during export: {e}")

    def generate_2d3d(self) -> None:
        """Generates a thin 3D mesh from the front mask using async worker."""
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

        # Show progress UI
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.btn_cancel.setVisible(True)
        self.st.setText("Starting thin 3D generation...")

        # Create worker
        self.thin3d_worker = Thin3DWorker(
            mask_array=m,
            thickness_mm=2.5,
            scale_factor=scale
        )

        # Connect signals
        self.thin3d_worker.progress.connect(self.on_thin3d_progress)
        self.thin3d_worker.finished.connect(self.on_thin3d_finished)
        self.thin3d_worker.error.connect(self.on_thin3d_error)

        # Track start time for ETA calculation
        self.operation_start_time = time.time()

        # Start worker
        self.thin3d_worker.start()

    def on_thin3d_progress(self, current: int, total: int, message: str) -> None:
        """
        Handle progress updates from thin 3D generation worker.

        Args:
            current: Current progress value
            total: Total progress value
            message: Status message describing current operation
        """
        self.progress_bar.setValue(current)

        # Calculate and display ETA
        if self.operation_start_time is not None and current > 0 and total > 0:
            elapsed = time.time() - self.operation_start_time
            progress_percent = current / total
            if progress_percent > 0.01:  # Only show ETA after 1% progress
                estimated_total_time = elapsed / progress_percent
                remaining = estimated_total_time - elapsed
                if remaining > 0:
                    message = f"{message} (~{int(remaining)}s remaining)"

        self.st.setText(message)

    def on_thin3d_finished(self, mesh: object) -> None:
        """
        Handle successful thin 3D generation completion.

        Args:
            mesh: Generated trimesh.Trimesh object or None if generation failed
        """
        # Hide progress UI
        self.progress_bar.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.operation_start_time = None

        # Store the mesh
        self.current_mesh = mesh

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

        # Clean up worker
        if hasattr(self, 'thin3d_worker') and self.thin3d_worker:
            self.thin3d_worker.deleteLater()
            self.thin3d_worker = None

    def on_thin3d_error(self, error_message: str) -> None:
        """
        Handle thin 3D generation errors.

        Args:
            error_message: Error message string describing what went wrong
        """
        # Hide progress UI
        self.progress_bar.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.operation_start_time = None

        # Show error message
        self.st.setText(f"Error: {error_message}")

        # Clean up worker
        if hasattr(self, 'thin3d_worker') and self.thin3d_worker:
            self.thin3d_worker.deleteLater()
            self.thin3d_worker = None

    def preview_3d(self) -> None:
        """Opens a 3D preview window for the generated mesh in a separate process."""
        if self.current_mesh:
            import multiprocessing
            p = multiprocessing.Process(target=show_mesh_process, args=(self.current_mesh,))
            p.start()
        else:
            self.st.setText("No mesh to preview.")
