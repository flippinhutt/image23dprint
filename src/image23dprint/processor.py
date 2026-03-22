"""
Processing pipeline for Image23DPrint.

This module provides the core processing pipeline that orchestrates the complete
workflow from input images through mask generation, space carving, and mesh
generation. It coordinates the various processing stages and provides progress
reporting and error handling.
"""

import numpy as np
from typing import Dict, Optional, Tuple, Callable, Any
from dataclasses import dataclass

from .mesh import SpaceCarver, CancelledException


@dataclass
class PipelineConfig:
    """
    Configuration for the processing pipeline.

    Attributes:
        resolution: Voxel resolution for the longest dimension (higher = more detail)
        dimensions: Target real-world dimensions (width, depth, height) in mm
        smooth_mesh: Apply Laplacian smoothing to reduce voxel artifacts
        decimate_mesh: Reduce triangle count for print efficiency
        align_to_bed: Translate mesh so its bottom rests at Z=0
        thin_3d_thickness: Thickness in mm for 2D→thin 3D extrusion mode
        scale_factor: Pixels-to-mm conversion factor for thin 3D mode
    """
    resolution: int = 128
    dimensions: Tuple[float, float, float] = (100.0, 100.0, 100.0)
    smooth_mesh: bool = True
    decimate_mesh: bool = True
    align_to_bed: bool = True
    thin_3d_thickness: float = 2.0
    scale_factor: float = 1.0


class ProcessingPipeline:
    """
    Main processing pipeline for 3D reconstruction from 2D images.

    This class orchestrates the complete workflow:
    1. Accept input masks from multiple views (front, side, top)
    2. Apply space carving to generate a 3D voxel grid
    3. Extract a mesh using marching cubes
    4. Apply post-processing (smoothing, decimation, alignment)

    The pipeline supports both full 3D reconstruction from multiple views
    and thin 3D extrusion from a single 2D mask.
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        Initialize the processing pipeline.

        Args:
            config: Pipeline configuration options. If None, uses defaults.
        """
        self.config = config or PipelineConfig()
        self.carver: Optional[SpaceCarver] = None
        self.masks: Dict[str, np.ndarray] = {}
        self._should_stop = False

    def reset(self) -> None:
        """
        Reset the pipeline state, clearing all masks and the carver.

        Call this to start a fresh processing run.
        """
        self.carver = None
        self.masks = {}
        self._should_stop = False

    def set_mask(self, axis: str, mask: np.ndarray) -> None:
        """
        Set a mask for a specific projection axis.

        Args:
            axis: Projection axis ('front', 'side', or 'top')
            mask: Binary mask array (0 or 255, or boolean)

        Raises:
            ValueError: If axis is not valid
        """
        valid_axes = {'front', 'side', 'top'}
        if axis not in valid_axes:
            raise ValueError(f"Invalid axis '{axis}'. Must be one of {valid_axes}")

        # Ensure mask is in correct format (boolean or 0/255 uint8)
        if mask.dtype == bool:
            self.masks[axis] = mask.astype(np.uint8) * 255
        else:
            self.masks[axis] = mask

    def get_mask(self, axis: str) -> Optional[np.ndarray]:
        """
        Retrieve the mask for a specific projection axis.

        Args:
            axis: Projection axis ('front', 'side', or 'top')

        Returns:
            The mask array if set, None otherwise
        """
        return self.masks.get(axis)

    def has_masks(self) -> bool:
        """
        Check if any masks have been set.

        Returns:
            True if at least one mask is available, False otherwise
        """
        return len(self.masks) > 0

    def cancel(self) -> None:
        """
        Request cancellation of the current processing operation.

        Sets the cancellation flag that will be checked during processing.
        """
        self._should_stop = True

    def _check_cancelled(self) -> None:
        """
        Check if processing has been cancelled and raise exception if so.

        Raises:
            CancelledException: If cancel() has been called
        """
        if self._should_stop:
            raise CancelledException("Processing cancelled by user")

    def _progress_wrapper(
        self,
        callback: Optional[Callable[[int, int, str], None]],
        stage_start: int,
        stage_end: int
    ) -> Callable[[int, int, str], None]:
        """
        Create a progress callback wrapper that maps stage progress to overall progress.

        Args:
            callback: The original progress callback to wrap
            stage_start: Starting percentage for this stage (0-100)
            stage_end: Ending percentage for this stage (0-100)

        Returns:
            A wrapped progress callback that scales progress to the stage range
        """
        def wrapped_callback(current: int, total: int, message: str) -> None:
            if callback:
                # Check for cancellation
                self._check_cancelled()

                # Map stage progress to overall progress
                if total > 0:
                    stage_progress = (current / total)
                    overall_progress = int(stage_start + (stage_end - stage_start) * stage_progress)
                else:
                    overall_progress = stage_start

                callback(overall_progress, 100, message)

        return wrapped_callback

    def process_full_3d(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> object:
        """
        Execute full 3D reconstruction from multiple mask views.

        This method applies all configured masks to a voxel grid using space carving,
        then generates and post-processes a 3D mesh.

        Args:
            progress_callback: Optional callback function(current, total, message)
                             for progress reporting

        Returns:
            The generated trimesh.Trimesh object, or None if no masks are available

        Raises:
            CancelledException: If processing is cancelled
            ValueError: If no masks have been set
        """
        if not self.has_masks():
            raise ValueError("No masks available for processing")

        try:
            if progress_callback:
                progress_callback(0, 100, "Initializing space carver...")

            # Initialize the space carver with configured dimensions
            self.carver = SpaceCarver(
                res=self.config.resolution,
                dims=self.config.dimensions
            )

            self._check_cancelled()

            # Apply each mask to carve the voxel grid
            num_masks = len(self.masks)
            for idx, (axis, mask) in enumerate(self.masks.items()):
                # Calculate progress range for this carving stage
                stage_start = int((idx / num_masks) * 50)
                stage_end = int(((idx + 1) / num_masks) * 50)

                wrapped_callback = self._progress_wrapper(
                    progress_callback,
                    stage_start,
                    stage_end
                )

                self.carver.apply_mask(mask, axis=axis, progress_callback=wrapped_callback)
                self._check_cancelled()

            if progress_callback:
                progress_callback(50, 100, "Generating mesh from voxel grid...")

            # Generate the mesh from the carved voxel grid
            wrapped_mesh_callback = self._progress_wrapper(progress_callback, 50, 100)
            mesh = self.carver.generate_mesh(
                smooth=self.config.smooth_mesh,
                decimate=self.config.decimate_mesh,
                align_to_bed=self.config.align_to_bed,
                progress_callback=wrapped_mesh_callback
            )

            self._check_cancelled()

            if progress_callback:
                progress_callback(100, 100, "3D reconstruction complete")

            return mesh

        except CancelledException:
            if progress_callback:
                progress_callback(0, 100, "Processing cancelled")
            raise

    def process_thin_3d(
        self,
        mask: np.ndarray,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> object:
        """
        Generate a thin 3D mesh from a single 2D mask by extrusion.

        This is the '2D to Thin 3D' feature that creates a constant-thickness
        3D object from a single silhouette image.

        Args:
            mask: Binary mask array (0 or 255, or boolean) to extrude
            progress_callback: Optional callback function(current, total, message)
                             for progress reporting

        Returns:
            The generated trimesh.Trimesh object with constant thickness

        Raises:
            CancelledException: If processing is cancelled
            ValueError: If mask is empty or invalid
        """
        if mask is None or not np.any(mask):
            raise ValueError("Mask is empty or invalid")

        try:
            if progress_callback:
                progress_callback(0, 100, "Initializing thin 3D extrusion...")

            # Initialize a minimal carver (not used for thin 3D, but required for the method)
            self.carver = SpaceCarver(res=self.config.resolution, dims=self.config.dimensions)

            self._check_cancelled()

            # Generate the thin 3D mesh
            mesh = self.carver.generate_thin_3d(
                mask_img=mask,
                thickness_mm=self.config.thin_3d_thickness,
                scale_factor=self.config.scale_factor,
                progress_callback=progress_callback
            )

            self._check_cancelled()

            if progress_callback:
                progress_callback(100, 100, "Thin 3D generation complete")

            return mesh

        except CancelledException:
            if progress_callback:
                progress_callback(0, 100, "Processing cancelled")
            raise

    def get_voxel_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the current voxel grid state.

        Returns:
            Dictionary containing voxel statistics:
            - 'shape': Voxel grid dimensions (x, y, z)
            - 'total_voxels': Total number of voxels
            - 'filled_voxels': Number of occupied voxels
            - 'fill_percentage': Percentage of occupied voxels

        Raises:
            RuntimeError: If carver has not been initialized
        """
        if self.carver is None:
            raise RuntimeError("Carver not initialized. Process masks first.")

        total = np.prod(self.carver.shape)
        filled = np.sum(self.carver.voxels)

        return {
            'shape': self.carver.shape,
            'total_voxels': int(total),
            'filled_voxels': int(filled),
            'fill_percentage': float(filled / total * 100) if total > 0 else 0.0
        }


def create_default_pipeline() -> ProcessingPipeline:
    """
    Create a processing pipeline with default configuration.

    Returns:
        A new ProcessingPipeline instance with default settings
    """
    return ProcessingPipeline(PipelineConfig())
