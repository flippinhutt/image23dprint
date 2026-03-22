# API Reference - Image23DPrint 🛠️

This document provides a comprehensive reference for the core classes and methods in `Image23DPrint`.

## 📦 `image23dprint.processor`

The primary interface for orchestrating the 3D reconstruction workflow.

### `class ProcessingPipeline`
Coordinates masks, carving, and mesh generation.

| Method | Parameters | Description |
|---|---|---|
| `__init__` | `config` | Initializes the pipeline with a `PipelineConfig`. |
| `set_mask` | `axis`, `mask` | Sets a binary mask for 'front', 'side', or 'top'. |
| `process_full_3d`| `progress_callback` | Executes the full space carving workflow and returns a `trimesh.Trimesh`. |
| `process_thin_3d`| `mask`, `callback` | Generates a constant-thickness mesh from a single mask. |
| `cancel` | - | Requests cancellation of the current long-running operation. |

### `class PipelineConfig`
Configuration dataclass for reconstruction parameters.

| Attribute | Type | Default | Description |
|---|---|---|---|
| `resolution` | `int` | `128` | Voxel resolution for the longest dimension. |
| `dimensions` | `tuple` | `(100,100,100)` | Real-world dimensions (W, D, H) in mm. |
| `smooth_mesh` | `bool` | `True` | Apply Laplacian smoothing. |
| `decimate_mesh`| `bool` | `True` | Reduce triangle count for performance. |
| `thin_3d_thickness` | `float` | `2.0` | Target thickness for 2D→3D mode. |

---

## 📦 `image23dprint.mesh`

### `class SpaceCarver`
The core engine for volumetric 3D reconstruction.

| Method | Description |
|---|---|
| `apply_mask` | Projects a 2D mask into the 3D grid and carves away voxels. |
| `generate_mesh`| Extracts the surface using Marching Cubes. |
| `generate_thin_3d` | Specialized extrusion logic for single-mask 3D objects. |

---

## 📦 `image23dprint.ollama_vision`

### `class OllamaClient`
Integration with local LLM for image analysis.

| Method | Description |
|---|---|
| `is_available` | Checks if the Ollama API is reachable. |
| `analyze_image`| Returns a comprehensive analysis (orientation, quality warnings). |
| `detect_orientation` | Specifically identifies if an image is Front, Side, or Top. |

---

## 📦 `image23dprint.exporter`

### `class MeshExporter`
Handles saving meshes to various file formats.

| Method | Description |
|---|---|
| `export` | Saves mesh to file (auto-detects .stl, .obj). |
| `export_stl` | Direct STL export with ASCII/Binary options. |
| `get_mesh_info`| Returns a dictionary of mesh stats (vertices, faces, volume). |
