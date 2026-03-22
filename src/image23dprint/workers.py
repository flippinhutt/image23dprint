"""
Worker classes for asynchronous processing in Image23DPrint.

This module provides base worker classes using PySide6's QThread for
non-blocking background operations with progress reporting and error handling.
"""

from PySide6.QtCore import QThread, Signal


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
