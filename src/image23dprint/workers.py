"""
Worker classes for asynchronous processing in Image23DPrint.

This module provides base worker classes using PySide6's QThread for
non-blocking background operations with progress reporting and error handling.
"""

import numpy as np
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QImage


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
