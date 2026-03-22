# Image23DPrint 📸 ➡️ 🧊

**Image23DPrint** is a professional-grade 3D reconstruction tool that transforms 2D photographs into print-ready 3D models (STL) using advanced **Space Carving** (Voxel Carving) algorithms and AI-powered background removal.

Designed for hobbyists, engineers, and creators, it allows you to generate a 3D model from as few as three photos (Front, Side, Top) with precise real-world scaling.

---

## ✨ Key Features

- 🧠 **AI-Powered Masking**: Utilizes `rembg` (ISNet) to automatically isolate objects from complex backgrounds.
- 📐 **Precision Scaling**: Built-in calibration tool to set real-world dimensions (mm) from a simple reference line.
- 🖼️ **2D-to-Thin-3D**: Instantly generate a constant-thickness 3D layer from a single image (perfect for signs and lithophanes).
- 🖥️ **Interactive Refinement**: Manual brush tools, "Edge Mask" (Canny), "Smart Outline" (GrabCut), and morphological refinement to perfect your masks.
- 🧊 **Proportional Carving**: Supports non-cubic voxel grids to ensure tall or wide objects aren't distorted.
- ⚡ **Optimized Mesh**: Automatic Laplacian smoothing and Quadric Decimation for clean, lightweight STL files.
- 🖨️ **Print Ready**: Auto-bed alignment ensures the generated model's base sits perfectly at Z=0.

---

## 🚀 Quick Start

### 1. Installation
Ensure you have Python 3.13+ and `uv` (recommended) or `pip` installed.

```bash
# Clone the repository
git clone https://github.com/flippinhutt/image23dprint.git
cd image23dprint

# Install dependencies
uv sync
```

### 2. Launch
```bash
PYTHONPATH=src uv run python -m image23dprint
```

### 3. Usage
1. **Load Images**: Click the three boxes to load **Front**, **Side**, and **Top** photos of your object.
2. **AI Mask**: Click **AI Auto-Mask** to let the vision model isolate the object.
3. **Calibrate**: Use the **Scale Tool** to draw a line on an object (e.g., its height) and input the real-world mm.
4. **Generate**: Set your desired resolution (32-256) and click **Generate STL**.
5. **Export**: Preview the 3D model and click **Export** to save your print-ready file.

---

## 🏗️ Architecture

```mermaid
graph TD
    A[Photos: Front, Side, Top] --> B{AI Masking - rembg}
    B --> C[Binary Masks]
    C --> D[Refinement Tools: Brush/GrabCut]
    D --> E[Voxel Grid Construction]
    E --> F[Space Carving - Projections]
    F --> G[Marching Cubes]
    G --> H[Post-Processing: Smooth/Decimate]
    H --> I[STL Export]
```

---

## 🛠️ Technical Details

- **Language**: Python 3.13
- **UI Framework**: PySide6 (Qt)
- **Computer Vision**: OpenCV, rembg (ONNX)
- **3D Geometry**: trimesh, scikit-image (Marching Cubes)
- **Package Manager**: uv

---

## 📚 Documentation
- [Architecture](docs/architecture.md): Technical deep-dive into space carving.
- [API Reference](docs/API.md): Class and method documentation.
- [Governance](docs/governance.md): Contribution and review guidelines.
- [GitHub Actions](docs/github_actions.md): CI/CD pipeline details.

---

## 🗺️ Roadmap / TODO

We are actively developing and looking for contributors!
- [ ] **Ollama Support**: Integrate local LLM vision for scene analysis and prompt-based mesh generation.
- [ ] **Extended AI Support**: Support for additional vision models (Segment Anything, etc.).
- [ ] **Improved Image Recognition**: Enhanced edge detection for fine-grained object features.
- [x] **2D-to-Thin-3D**: Allow generating a 3D layer with adjustable thickness from a single 2D image.
- [ ] **Poisson Surface Reconstruction**: For perfectly watertight, high-poly 3D models.

---

## 🤝 Contributing
This is an active research project. Contributions are welcome!
1. Fork the repo.
2. Create your feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

---

## 📜 License
Distributed under the MIT License. See `LICENSE` for more information.

---
*Created with ❤️ by [flippinhutt](https://github.com/flippinhutt)*
