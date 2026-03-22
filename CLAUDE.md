# Image23DPrint

Convert images into 3D printable meshes (STL/OBJ) using Volumetric Space Carving.

## Project Overview
This tool focuses on high-accuracy reconstruction from 2D silhouettes. It uses specialized masking (AI + GrabCut) and volumetric carving to generate manifold 3D meshes ready for printing.

## Tech Stack
- **Language**: Python 3.13+
- **Package Manager**: `uv`
- **Gui Framework**: `PySide6`
- **3D Engine**: `trimesh`, `skimage`, `fast-simplification`
- **AI Vision**: `rembg` (ISNet)

## Repository Layout
- `src/image23dprint/`: Core logic and GUI.
- `src/image23dprint/assets/`: UI resources (Icons, images).
- `docs/`: Architecture, API, and Governance documentation.
- `tests/`: Pytest suite for carving and mesh logic.

## Coding Conventions
- Follow PEP 8 styles (enforced by `ruff`).
- Use `pytest` for all functional tests.
- Maintain comprehensive docstrings for all public classes and methods.

## Claude Behavior
- Keep diffs small and focused.
- Ensure all logic has corresponding tests.
- Update `docs/architecture.md` when adding major components.

[Architecture](file:///Users/ryanhutto/projects/image23dprint/docs/architecture.md)
