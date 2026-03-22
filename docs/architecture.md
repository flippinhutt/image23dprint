# Architecture Overview: Image23DPrint

## High-Level Design
Image23DPrint uses a **Volumetric Space Carving** approach to reconstruct 3D geometry from 2D silhouettes:

1.  **AI Masking**: Input images (Front, Side, Top) are processed using `rembg` (ISNet) to isolate the foreground object.
2.  **Voxel Initialization**: A dense 3D grid (Voxels) is initialized matching the real-world proportions provided by the user.
3.  **Projection Carving**: Each 2D mask is projected through the voxel volume. Any voxel falling outside the silhouette is "carved" away.
4.  **Mesh Extraction**: The `skimage.measure.marching_cubes` algorithm extracts a surface mesh from the remaining voxels.
5.  **Refinement**: The resulting mesh undergoes Laplacian smoothing and Quadratic Decimation using `fast-simplification`.
6.  **Alignment**: The mesh is automatically translated to sit at Z=0 for immediate 3D printing.
7.  **Thin 3D Extrusion**: A specialized mode that bypasses voxel carving from multiple views, instead extruding a single 2D silhouette into a specific millimeter thickness.

## Modular Architecture

The codebase follows a clean modular structure separating concerns across focused packages and modules:

### GUI Layer (`src/image23dprint/ui/`)
- **`main_window.py`**: Main application window (Image23DPrintGUI)
  - Orchestrates the complete user workflow
  - Manages image loading, mask editing, and processing controls
  - Coordinates worker threads for long-running operations
  - Handles progress reporting and user interaction
  - Integrates ProcessingPipeline and MeshExporter

### Widget Components (`src/image23dprint/widgets/`)
- **`maskable_image_label.py`**: Interactive masking widget (MaskableImageLabel)
  - AI-powered background removal using rembg (ISNet)
  - GrabCut rectangle selection for semi-automatic masking
  - Freehand drawing tools with undo/redo history
  - Edge detection and quality validation
  - Scaling calibration for physical measurements

### Processing Pipeline (`src/image23dprint/processor.py`)
- **`ProcessingPipeline`**: Core 3D reconstruction workflow orchestration
  - `process_full_3d()`: Multi-view space carving from front/side/top masks
  - `process_thin_3d()`: 2D silhouette extrusion to specified thickness
  - Progress reporting with cancellation support
  - Voxel statistics tracking
- **`PipelineConfig`**: Configuration dataclass for all pipeline parameters
  - Resolution, dimensions, smoothing, decimation, alignment settings
  - Thin 3D mode parameters (thickness, scale factor)

### Export Layer (`src/image23dprint/exporter.py`)
- **`MeshExporter`**: Mesh export with validation and error handling
  - `export()`: Auto-detect format from file extension
  - `export_stl()`: STL export (binary/ASCII)
  - `export_obj()`: OBJ export
  - `get_mesh_info()`: Mesh statistics and quality analysis
  - Pre-export validation (manifold check, watertight verification)

### Core Engine (`src/image23dprint/mesh.py`)
- **`SpaceCarver`**: Low-level volumetric operations
  - Voxel grid initialization and projection
  - Marching cubes mesh extraction
  - Post-processing (smoothing, decimation, alignment)
  - Cancellation support for long operations

### Entry Point (`src/image23dprint/gui.py`)
- Minimal entry point (19 lines)
- `main()`: Application startup function
- Re-exports for backward compatibility

## Data Flow

```
User Input (Images)
    ↓
MaskableImageLabel (Interactive Masking)
    ↓
PipelineConfig (User Settings)
    ↓
ProcessingPipeline
    ├─→ process_full_3d() → SpaceCarver → Mesh
    └─→ process_thin_3d() → SpaceCarver → Mesh
    ↓
MeshExporter (STL/OBJ)
    ↓
3D Printable File
```

## Physical Constraints
The system relies on user-provided height/width measurements to set the aspect ratio of the voxel grid, ensuring that a "100mm candle" in the photo results in a "100mm candle" in the STL file.

## Design Principles
- **Separation of Concerns**: UI, processing, and export logic are isolated in dedicated modules
- **Type Safety**: Comprehensive type hints throughout all public APIs
- **Cancellation Support**: Long-running operations can be interrupted cleanly
- **Progress Reporting**: Real-time feedback during processing via callbacks
- **Error Handling**: Dedicated exception types (ExportError, CancelledException)
- **Testability**: Modular architecture enables focused unit testing
