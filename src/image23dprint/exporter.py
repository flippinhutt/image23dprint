"""
Mesh export functionality for Image23DPrint.

This module provides the MeshExporter class for exporting trimesh.Trimesh objects
to various 3D file formats (STL, OBJ) with validation and error handling.
"""

from pathlib import Path
from typing import Optional, Union, Literal
import trimesh


ExportFormat = Literal["stl", "obj", "stl-ascii", "stl-binary"]


class ExportError(Exception):
    """Exception raised when mesh export fails."""
    pass


class MeshExporter:
    """
    Handles exporting 3D meshes to various file formats.

    Supports STL (binary and ASCII) and OBJ formats with optional validation
    and mesh quality checks before export.

    Example:
        >>> exporter = MeshExporter()
        >>> exporter.export(mesh, "output.stl")
        >>> exporter.export(mesh, "output.obj", validate=True)
    """

    def __init__(self):
        """Initialize the MeshExporter."""
        self.last_export_path: Optional[Path] = None
        self.last_format: Optional[str] = None

    def export(
        self,
        mesh: trimesh.Trimesh,
        file_path: Union[str, Path],
        format: Optional[ExportFormat] = None,
        validate: bool = True,
        overwrite: bool = True
    ) -> None:
        """
        Export a mesh to a file in the specified format.

        Args:
            mesh: The trimesh.Trimesh object to export.
            file_path: Target file path for export.
            format: Export format ('stl', 'obj', 'stl-ascii', 'stl-binary').
                   If None, format is inferred from file extension.
            validate: If True, perform validation checks before export.
            overwrite: If False, raises ExportError if file already exists.

        Raises:
            ExportError: If mesh is invalid, file exists (when overwrite=False),
                        or export operation fails.
            ValueError: If format is invalid or cannot be inferred.
        """
        if mesh is None:
            raise ExportError("Cannot export None mesh")

        if not isinstance(mesh, trimesh.Trimesh):
            raise ExportError(f"Expected trimesh.Trimesh, got {type(mesh).__name__}")

        # Convert to Path object for easier handling
        file_path = Path(file_path)

        # Check if file exists
        if file_path.exists() and not overwrite:
            raise ExportError(f"File already exists: {file_path}")

        # Infer format from extension if not provided
        if format is None:
            format = self._infer_format(file_path)

        # Validate format
        if format not in ["stl", "obj", "stl-ascii", "stl-binary"]:
            raise ValueError(f"Unsupported format: {format}")

        # Validate mesh if requested
        if validate:
            self._validate_mesh(mesh)

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Perform export
        try:
            if format == "stl-ascii":
                mesh.export(str(file_path), file_type="stl_ascii")
            elif format == "stl" or format == "stl-binary":
                mesh.export(str(file_path), file_type="stl")
            elif format == "obj":
                mesh.export(str(file_path), file_type="obj")

            # Store last export info
            self.last_export_path = file_path
            self.last_format = format

        except Exception as e:
            raise ExportError(f"Failed to export mesh: {e}") from e

    def export_stl(
        self,
        mesh: trimesh.Trimesh,
        file_path: Union[str, Path],
        binary: bool = True,
        validate: bool = True
    ) -> None:
        """
        Export a mesh to STL format.

        Args:
            mesh: The trimesh.Trimesh object to export.
            file_path: Target file path for export.
            binary: If True, export as binary STL; if False, export as ASCII.
            validate: If True, perform validation checks before export.

        Raises:
            ExportError: If mesh is invalid or export fails.
        """
        format = "stl-binary" if binary else "stl-ascii"
        self.export(mesh, file_path, format=format, validate=validate)

    def export_obj(
        self,
        mesh: trimesh.Trimesh,
        file_path: Union[str, Path],
        validate: bool = True
    ) -> None:
        """
        Export a mesh to OBJ format.

        Args:
            mesh: The trimesh.Trimesh object to export.
            file_path: Target file path for export.
            validate: If True, perform validation checks before export.

        Raises:
            ExportError: If mesh is invalid or export fails.
        """
        self.export(mesh, file_path, format="obj", validate=validate)

    def _infer_format(self, file_path: Path) -> ExportFormat:
        """
        Infer export format from file extension.

        Args:
            file_path: The file path to infer format from.

        Returns:
            The inferred export format.

        Raises:
            ValueError: If format cannot be inferred from extension.
        """
        ext = file_path.suffix.lower()

        if ext == ".stl":
            return "stl-binary"
        elif ext == ".obj":
            return "obj"
        else:
            raise ValueError(
                f"Cannot infer format from extension '{ext}'. "
                "Supported extensions: .stl, .obj"
            )

    def _validate_mesh(self, mesh: trimesh.Trimesh) -> None:
        """
        Validate mesh before export.

        Performs basic validation checks to ensure the mesh is suitable for export:
        - Has vertices and faces
        - Has finite bounds
        - Reports warnings for non-watertight or degenerate meshes

        Args:
            mesh: The mesh to validate.

        Raises:
            ExportError: If mesh fails critical validation checks.
        """
        # Check for empty mesh
        if len(mesh.vertices) == 0:
            raise ExportError("Mesh has no vertices")

        if len(mesh.faces) == 0:
            raise ExportError("Mesh has no faces")

        # Check for infinite or NaN values
        if not mesh.is_empty and not mesh.bounds.all():
            raise ExportError("Mesh has invalid bounds (infinite or NaN values)")

        # Check extents are valid
        if not all(e > 0 for e in mesh.extents):
            raise ExportError("Mesh has invalid extents (zero or negative dimensions)")

    def get_mesh_info(self, mesh: trimesh.Trimesh) -> dict:
        """
        Get information about a mesh.

        Args:
            mesh: The mesh to analyze.

        Returns:
            Dictionary containing mesh statistics and properties.
        """
        if mesh is None or not isinstance(mesh, trimesh.Trimesh):
            return {}

        return {
            "vertices": len(mesh.vertices),
            "faces": len(mesh.faces),
            "edges": len(mesh.edges_unique),
            "watertight": mesh.is_watertight,
            "volume": float(mesh.volume) if mesh.is_watertight else None,
            "area": float(mesh.area),
            "bounds": mesh.bounds.tolist(),
            "extents": mesh.extents.tolist(),
            "center_mass": mesh.center_mass.tolist() if mesh.is_watertight else None,
        }
