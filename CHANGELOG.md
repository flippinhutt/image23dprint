# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **2D-to-Thin-3D Feature**: New capability to generate constant-thickness 3D models from a single image.
- **Edge Masking**: Integrated Canny edge detection into the GUI for high-contrast object isolation.
- **Pull Request Template**: Standardized `.github/PULL_REQUEST_TEMPLATE.md` to improve repository governance.
- **Automated Binary Releases**: GitHub Action (`release.yml`) for cross-platform PyInstaller builds on tags.
- **Pytest Configuration**: Integrated `pythonpath` in `pyproject.toml` for easier test execution.

### Changed
- Updated GitHub Actions to use Node 24 runners (Node 20 deprecation fix).
- Improved CI workflow with `pip-audit` and updated tool versions.

## [0.1.0] - 2026-03-21

### Added
- Initial project setup with core source code.
- Volumetric Space Carving engine (`SpaceCarver`).
- PySide6 GUI for image management and masking.
- AI Masking integration using `rembg` (ISNet).
- Interactive refinement tools (Brush, GrabCut).
- CI workflow with `ruff`, `bandit`, and geometry validation tests.
- CODEOWNERS and initial documentation (Architecture, API, Governance).
- MIT License.
