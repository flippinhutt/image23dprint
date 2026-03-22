# Architecture Overview: image23dprint

## High-Level Design
The system follows a modular pipeline approach:
1. **Ingestion**: Reading various image formats.
2. **Preprocessing**: Grayscale conversion, noise reduction, and optional edge detection.
3. **Heightmap Generation**: Mapping pixel intensity or depth estimation to Z-axis values.
4. **Mesh Construction**: triangulation of the heightmap into STL/OBJ.
5. **Post-processing**: Smoothing, decimation, and manifold checking.

## Key Components
- `image_processor`: Handles all 2D manipulations.
- `mesh_generator`: Logic for converting spatial data to 3D meshes.
- `exporter`: Formats the data for 3D printing (e.g., binary STL).

## External Integrations
- `trimesh`: For mesh processing and validation.
- `opencv-python`: For image analysis.
