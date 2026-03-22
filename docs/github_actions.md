# GitHub Actions Guide for Image23DPrint 🛠️

To transform **Image23DPrint** into a professional, production-ready repository, the following GitHub Actions workflows are implemented:

## 1. Automated Quality Control (`ci.yml`)
Runs on every push or Pull Request to ensure the code remains stable and clean.
- **Linting**: Use `ruff` for lightning-fast Python linting and formatting. It catches bugs and enforces PEP 8 instantly.
- **Security Scanning**: Use `bandit` or `CodeQL` to scan for security vulnerabilities in your Python code.
- **Unit Tests**: Use `pytest` to run the geometry validation tests (e.g., verifying `SpaceCarver` projections) across Python versions (3.9, 3.10, 3.11, 3.12).
- **Environment**: Updated to run on Node 24 following the Node 20 deprecation.

## 2. Multi-Platform Binary Releases (`release.yml`) 🚀
Since this is a GUI application, most users won't want to install Python and `uv`.
- **PyInstaller Bundling**: Automatically build a `.app` (macOS), `.exe` (Windows), and an AppImage (Linux) whenever you create a new GitHub Tag. This creates a portable, standalone experience.
- **GitHub Releases**: Automatically upload these binaries to a new Release page so users can just download and run the app.

## 3. Dependency Management (Scheduled) 📦
- **Dependabot**: Automatically creates PRs to update your `pyproject.toml` dependencies when new versions or security patches are released.
- **Vulnerability Audit**: Runs `uv run pip-audit` as part of the CI to ensure no known CVEs are in your local environment.

## 4. Documentation Deployment (`docs.yml`) 📚
- **GitHub Pages**: If you expand your documentation into a site (using `MkDocs` or `Sphinx`), this action will automatically deploy it to `flippinhutt.github.io/image23dprint` whenever you update the `docs/` folder.

---

## 5. Active Workflows ⚡
To ensure stability and ease of distribution, the following workflows are currently active:
- **`ci.yml`**: Runs on Node 24. Performs linting (`ruff`), security scans (`bandit`), and dependency audits (`pip-audit`) on every push and PR.
- **`release.yml`**: Runs on version tags (`v*`). Automatically builds standalone binaries for Windows, macOS, and Linux using PyInstaller and uploads them to GitHub Releases.
