# Architecture Overview: Image23DPrint

## High-Level Design
Image23DPrint uses a **Volumetric Space Carving** approach to reconstruct 3D geometry from 2D silhouettes:

1.  **AI Masking**: Input images (Front, Side, Top) are processed using `rembg` (ISNet) to isolate the foreground object.
2.  **Voxel Initialization**: A dense 3D grid (Voxels) is initialized matching the real-world proportions provided by the user.
3.  **Projection Carving**: Each 2D mask is projected through the voxel volume. Any voxel falling outside the silhouette is "carved" away.
4.  **Mesh Extraction**: The `skimage.measure.marching_cubes` algorithm extracts a surface mesh from the remaining voxels.
5.  **Refinement**: The resulting mesh undergoes Laplacian smoothing and Quadratic Decimation using `fast-simplification`.
6.  **Alignment**: The mesh is automatically translated to sit at Z=0 for immediate 3D printing.

## Key Components
- `gui.py`: PySide6 interface for image management, interactive masking (GrabCut), and real-time undo history.
- `mesh.py`: The `SpaceCarver` class handling the volumetric operations and CAD export.
- `trimesh`: Used for mesh post-processing, bounding box calculations, and STL/OBJ encoding.

## Physical Constraints
The system relies on user-provided height/width measurements to set the aspect ratio of the voxel grid, ensuring that a "100mm candle" in the photo results in a "100mm candle" in the STL file.
