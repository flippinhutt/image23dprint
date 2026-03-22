"""
Worker classes for asynchronous processing in Image23DPrint.

This module provides base worker classes using PySide6's QThread for
non-blocking background operations with progress reporting and error handling.
"""

import numpy as np
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QImage


class CancelledException(Exception):
    """Exception raised when an operation is cancelled by the user."""
    pass


class BaseWorker(QThread):
    """
    Base worker class for asynchronous background operations.

    Provides standard signals for progress tracking, completion notification,
    and error handling. Subclasses should override the run() method to implement
    specific background tasks.

    Signals:
        progress: Emitted during task execution with (current, total, message) tuple
        finished: Emitted when task completes successfully with optional result data
        error: Emitted when task fails with error message string
    """

    # Signal emitted during task execution: (current: int, total: int, message: str)
    progress = Signal(int, int, str)

    # Signal emitted on successful completion: (result: object)
    finished = Signal(object)

    # Signal emitted on error: (error_message: str)
    error = Signal(str)

    def __init__(self, parent=None):
        """
        Initialize the base worker.

        Args:
            parent: Optional parent QObject for proper cleanup
        """
        super().__init__(parent)
        self._is_running = False
        self._should_stop = False

    def run(self):
        """
        Main execution method - override this in subclasses.

        Subclasses should:
        1. Set self._is_running = True at start
        2. Check self._should_stop periodically for cancellation
        3. Emit progress signals during execution
        4. Emit finished signal with result on success
        5. Emit error signal on failure
        6. Set self._is_running = False in finally block
        """
        self._is_running = True
        try:
            # Subclass implementation goes here
            self.finished.emit(None)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._is_running = False

    def stop(self):
        """
        Request the worker to stop execution gracefully.

        Sets the stop flag - the worker's run() method should check
        self._should_stop periodically and exit cleanly when True.
        """
        self._should_stop = True

    def is_running(self):
        """
        Check if the worker is currently executing.

        Returns:
            bool: True if worker is running, False otherwise
        """
        return self._is_running


class AIRemovalWorker(BaseWorker):
    """
    Worker for AI-powered background removal using rembg.

    Performs background removal on a QImage using the ISNet model from rembg,
    running in a background thread to keep the GUI responsive. The worker
    caches the rembg session for improved performance across multiple runs.

    Signals:
        progress: Emitted with (current, total, message) during processing
        finished: Emitted with resulting mask QImage on success
        error: Emitted with error message string on failure
    """

    # Class-level session cache shared across all instances
    _rembg_session = None

    def __init__(self, image, parent=None):
        """
        Initialize the AI removal worker.

        Args:
            image: QImage to process for background removal
            parent: Optional parent QObject for proper cleanup
        """
        super().__init__(parent)
        self.image = image

    def run(self):
        """
        Execute background removal using rembg.

        Converts the QImage to PIL format, runs rembg.remove() to isolate
        the foreground object, extracts the alpha channel as a mask, and
        returns the result as a QImage mask.
        """
        self._is_running = True
        try:
            # Emit initial progress
            self.progress.emit(0, 100, "Initializing AI model...")

            # Import rembg dependencies
            from rembg import remove, new_session
            from PIL import Image

            # Initialize session on first use (cached for subsequent calls)
            if AIRemovalWorker._rembg_session is None:
                self.progress.emit(10, 100, "Loading ISNet model...")
                AIRemovalWorker._rembg_session = new_session("isnet-general-use")

            # Check for cancellation
            if self._should_stop:
                return

            # Convert QImage to numpy array
            self.progress.emit(30, 100, "Converting image...")
            qimg = self.image.toImage().convertToFormat(QImage.Format_RGBA8888)
            ptr = qimg.bits()
            arr = np.frombuffer(ptr, dtype=np.uint8).reshape(
                (qimg.height(), qimg.bytesPerLine() // 4, 4)
            )[:, :qimg.width()].copy()

            # Convert to PIL Image
            img = Image.fromarray(arr)

            # Check for cancellation
            if self._should_stop:
                return

            # Run background removal
            self.progress.emit(50, 100, "Removing background with AI...")
            output = remove(img, session=AIRemovalWorker._rembg_session)

            # Check for cancellation
            if self._should_stop:
                return

            # Extract alpha channel and create mask
            self.progress.emit(80, 100, "Creating mask...")
            mask_values = (np.array(output)[:, :, 3] > 127).astype(np.uint8) * 255

            # Convert to QImage mask
            mask = QImage(
                mask_values.data,
                mask_values.shape[1],
                mask_values.shape[0],
                mask_values.strides[0],
                QImage.Format_Grayscale8
            ).convertToFormat(QImage.Format_Mono).copy()

            # Calculate statistics
            bg_pct = np.sum(mask_values == 0) / mask_values.size

            # Emit completion
            self.progress.emit(100, 100, f"AI complete: {bg_pct:.1%} background removed")
            self.finished.emit(mask)

        except Exception as e:
            self.error.emit(f"AI background removal failed: {str(e)}")
        finally:
            self._is_running = False


class MeshGenerationWorker(BaseWorker):
    """
    Worker for 3D mesh generation using space carving.

    Performs volumetric space carving from multiple 2D masks and generates
    a 3D mesh using marching cubes. Runs in a background thread to keep the
    GUI responsive during the potentially long mesh generation process.

    Signals:
        progress: Emitted with (current, total, message) during processing
        finished: Emitted with resulting trimesh.Trimesh object on success
        error: Emitted with error message string on failure
    """

    def __init__(self, masks, dims, voxel_res=128, smooth=True, decimate=True, parent=None):
        """
        Initialize the mesh generation worker.

        Args:
            masks: Dictionary mapping axis names to (QImage mask, axis string) tuples
                   e.g., {'front': (mask_qimage, 'front'), 'side': (mask_qimage, 'side')}
            dims: Tuple of real-world dimensions (width, depth, height) in mm
            voxel_res: Resolution of the longest voxel dimension (default: 128)
            smooth: Whether to apply Laplacian smoothing to the mesh
            decimate: Whether to decimate (simplify) the mesh
            parent: Optional parent QObject for proper cleanup
        """
        super().__init__(parent)
        self.masks = masks
        self.dims = dims
        self.voxel_res = voxel_res
        self.smooth = smooth
        self.decimate = decimate

    def run(self):
        """
        Execute space carving and mesh generation.

        Creates a SpaceCarver, applies each mask sequentially with progress
        updates, then generates the final mesh with smoothing and decimation.
        """
        self._is_running = True
        try:
            # Import dependencies
            from .mesh import SpaceCarver

            # Create a progress callback that checks for cancellation
            def progress_callback(current, total, message):
                if self._should_stop:
                    raise CancelledException("Operation cancelled by user")
                self.progress.emit(current, total, message)

            # Calculate total steps for progress tracking
            num_masks = len(self.masks)
            total_steps = num_masks + 3  # masks + marching_cubes + smooth + decimate

            # Step 1: Initialize space carver
            self.progress.emit(0, 100, "Initializing voxel grid...")
            carver = SpaceCarver(res=self.voxel_res, dims=self.dims)

            # Check for cancellation
            if self._should_stop:
                return

            # Step 2-N: Apply each mask
            for idx, (name, (mask_qimage, axis)) in enumerate(self.masks.items(), start=1):
                step_progress = int((idx / total_steps) * 100)
                self.progress.emit(step_progress, 100, f"Carving {name} view...")

                # Convert QImage mask to numpy array
                qimg = mask_qimage.convertToFormat(QImage.Format_Grayscale8)
                ptr = qimg.bits()
                mask_arr = np.frombuffer(ptr, dtype=np.uint8).reshape(
                    (qimg.height(), qimg.bytesPerLine())
                )[:, :qimg.width()].copy()

                # Check for cancellation
                if self._should_stop:
                    return

                # Apply mask to carver with cancellation-aware callback
                carver.apply_mask(mask_arr, axis=axis, progress_callback=progress_callback)

                # Check for cancellation
                if self._should_stop:
                    return

            # Step N+1: Generate mesh with marching cubes
            step_progress = int(((num_masks + 1) / total_steps) * 100)
            self.progress.emit(step_progress, 100, "Extracting surface mesh...")

            # Check for cancellation
            if self._should_stop:
                return

            # Generate the mesh (this calls marching cubes internally)
            mesh = carver.generate_mesh(
                smooth=self.smooth,
                decimate=self.decimate,
                align_to_bed=True,
                progress_callback=progress_callback
            )

            if mesh is None:
                self.error.emit("Mesh generation failed: no voxels remaining after carving")
                return

            # Check for cancellation
            if self._should_stop:
                return

            # Final progress update
            self.progress.emit(100, 100, f"Mesh complete: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
            self.finished.emit(mesh)

        except CancelledException:
            # Operation was cancelled - exit cleanly without error
            return
        except Exception as e:
            self.error.emit(f"Mesh generation failed: {str(e)}")
        finally:
            self._is_running = False


class Thin3DWorker(BaseWorker):
    """
    Worker for thin 3D mesh generation from a single 2D mask.

    Generates a constant-thickness 3D mesh by extruding a 2D binary mask.
    Runs in a background thread to keep the GUI responsive during mesh generation.

    Signals:
        progress: Emitted with (current, total, message) during processing
        finished: Emitted with resulting trimesh.Trimesh object on success
        error: Emitted with error message string on failure
    """

    def __init__(self, mask_array, thickness_mm=2.5, scale_factor=1.0, parent=None):
        """
        Initialize the thin 3D generation worker.

        Args:
            mask_array: Binary mask numpy array (True/False or 0/255)
            thickness_mm: The target extrusion thickness in real-world units (default: 2.5)
            scale_factor: Pixels-to-mm conversion factor (default: 1.0)
            parent: Optional parent QObject for proper cleanup
        """
        super().__init__(parent)
        self.mask_array = mask_array
        self.thickness_mm = thickness_mm
        self.scale_factor = scale_factor

    def run(self):
        """
        Execute thin 3D mesh generation.

        Creates a SpaceCarver and generates a thin 3D mesh by extruding
        the 2D mask to a constant thickness.
        """
        self._is_running = True
        try:
            # Import dependencies
            from .mesh import SpaceCarver

            # Create a progress callback that checks for cancellation
            def progress_callback(current, total, message):
                if self._should_stop:
                    raise CancelledException("Operation cancelled by user")
                self.progress.emit(current, total, message)

            # Create dummy carver to access the method
            carver = SpaceCarver(res=64)

            # Check for cancellation
            if self._should_stop:
                return

            # Generate the thin 3D mesh
            mesh = carver.generate_thin_3d(
                self.mask_array,
                thickness_mm=self.thickness_mm,
                scale_factor=self.scale_factor,
                progress_callback=progress_callback
            )

            if mesh is None:
                self.error.emit("Thin 3D generation failed: no mask to extrude")
                return

            # Check for cancellation
            if self._should_stop:
                return

            # Final progress update
            self.progress.emit(100, 100, f"Thin 3D complete: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
            self.finished.emit(mesh)

        except CancelledException:
            # Operation was cancelled - exit cleanly without error
            return
        except Exception as e:
            self.error.emit(f"Thin 3D generation failed: {str(e)}")
        finally:
            self._is_running = False
