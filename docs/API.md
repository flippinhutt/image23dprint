# API Reference - Image23DPrint 🛠️

This document outlines the core classes and functions within `Image23DPrint`.

## 📦 `image23dprint.mesh`

### `class SpaceCarver`
The core engine for 3D reconstruction using Voxel Carving.

| Method | Parameters | Description |
|---|---|---|
| `__init__` | `res`, `dims` | Initializes the voxel grid with target proportions. |
| `apply_mask` | `mask_img`, `axis` | Projects a 2D mask onto the grid and carves voxels. |
| `generate_mesh` | `smooth`, `decimate`, `align_to_bed` | Extracts an STL mesh using Marching Cubes. |
| `generate_thin_3d`| `mask_img`, `thickness_mm`, `scale_factor` | Generates a constant-thickness 3D mesh from a single 2D mask. |

---

## 🖥️ `image23dprint.gui`

### `class MaskableImageLabel`
Interactive QLabel for image masking and calibration.

| Method | Description |
|---|---|
| `ai_mask()` | Uses `rembg` (ISNet) to auto-generate a foreground mask. |
| `edge_mask()` | Uses Canny edge detection and hole filling for high-contrast objects. |
| `auto_mask()` | Fallback OpenCV threshold-based masking. |
| `run_grabcut()` | Applies GrabCut within a user-selected rectangle. |
| `undo()` | Reverts the last mask modification using a local history stack. |
| `refine()` | Cleans up noise and fills holes in the mask using morphology. |

### `class Image23DPrintGUI`
Main application window and orchestrator for the carving workflow.

| Method | Description |
|---|---|
| `generate_stl()` | Coordinates carving, extraction, and scaling. |
| `set_calibration_scale()` | Updates global scaling factors based on a known length. |
| `preview_3d()` | Spawns a separate process for the 3D viewer. |
| `export_stl()` | Saves the internal mesh object to disk. |

---

## 🧬 Data Flow

1. **Input**: `Front`, `Side`, `Top` images.
2. **Processing**: AI or manual masking produces `mask_img` (binary).
3. **Execution**: `SpaceCarver` projects masks to a boolean `voxels` array.
4. **Extraction**: `Marching Cubes` generates vertices/faces.
5. **Output**: `Trimesh` mesh is smoothed, decimated, and exported.
