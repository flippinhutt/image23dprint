# image23dprint

Convert images into 3D printable meshes (STL/OBJ).

## Project Overview
This tool aims to simplify the process of creating 3D printable objects from 2D images, potentially using depth estimation or edge detection to generate heightmaps and meshes.

## Tech Stack
- **Language**: Python 3.12+
- **Package Manager**: `uv`
- **Libraries**: (Planned) `opencv-python`, `trimesh`, `numpy`, `scipy`

## Repository Layout
- `src/`: Core logic for image processing and mesh generation.
- `docs/`: Architectural diagrams, ADRs, and runbooks.
- `tools/`: Utility scripts and localized prompts.
- `.claude/`: Claude-specific settings and assistant skills.

## Coding Conventions
- Follow PEP 8 styles.
- Use `pytest` for all functional tests.
- Prefer explicit type hinging.

## Claude Behavior
- Keep diffs small and focused.
- Ensure all logic has corresponding tests.
- Update `docs/architecture.md` when adding major components.

[Architecture](file:///Users/ryanhutto/projects/image23dprint/docs/architecture.md)
