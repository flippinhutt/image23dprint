"""Ollama LLM Vision integration for AI-assisted photo analysis."""

import base64
from pathlib import Path
from typing import Optional, Dict, Any


class OllamaClient:
    """Client for interacting with local Ollama instance for vision analysis."""

    _instance: Optional['OllamaClient'] = None
    _available: Optional[bool] = None

    def __init__(self):
        """Initialize Ollama client with default settings."""
        self.base_url = "http://localhost:11434"
        self.timeout = 5  # seconds

    def is_available(self) -> bool:
        """Check if Ollama is installed and running.

        Returns:
            True if Ollama API is accessible, False otherwise.
        """
        if OllamaClient._available is not None:
            return OllamaClient._available

        try:
            import requests
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=self.timeout
            )
            OllamaClient._available = response.status_code == 200
            if OllamaClient._available:
                print("Ollama detected and running")
            return OllamaClient._available
        except (ImportError, Exception):
            OllamaClient._available = False
            return False

    def _encode_image(self, image_path: str) -> Optional[str]:
        """Encode image file to base64 for Ollama API.

        Args:
            image_path: Path to image file.

        Returns:
            Base64 encoded image string, or None on error.
        """
        try:
            path = Path(image_path)
            if not path.exists():
                return None
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception:
            return None

    def detect_orientation(self, image_path: str) -> Dict[str, Any]:
        """Detect the orientation/viewpoint of an object in the image.

        Args:
            image_path: Path to image file.

        Returns:
            Dictionary containing:
                - orientation (str): One of 'front', 'side', 'top', or 'unknown'.
                - confidence (float): Confidence score from 0.0 to 1.0.
                - error (str, optional): Error message if detection failed.
        """
        if not self.is_available():
            return {"orientation": "unknown", "confidence": 0.0, "error": "Ollama not available"}

        image_b64 = self._encode_image(image_path)
        if not image_b64:
            return {"orientation": "unknown", "confidence": 0.0, "error": "Failed to encode image"}

        try:
            import requests
            prompt = (
                "You are analyzing a photo of an object for 3D reconstruction. "
                "Identify the camera viewpoint/orientation. Respond with ONLY one word: "
                "front, side, top, or unknown. Nothing else."
            )

            payload = {
                "model": "llava",
                "prompt": prompt,
                "images": [image_b64],
                "stream": False
            }

            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=30
            )

            if response.status_code != 200:
                return {"orientation": "unknown", "confidence": 0.0, "error": f"API error: {response.status_code}"}

            result = response.json()
            response_text = result.get("response", "").strip().lower()

            # Parse orientation from response
            orientation = "unknown"
            for keyword in ["front", "side", "top"]:
                if keyword in response_text:
                    orientation = keyword
                    break

            # Simple confidence heuristic based on response clarity
            confidence = 0.8 if orientation != "unknown" else 0.1

            return {
                "orientation": orientation,
                "confidence": confidence
            }

        except Exception as e:
            return {"orientation": "unknown", "confidence": 0.0, "error": str(e)}

    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """Comprehensive AI analysis of image for 3D reconstruction quality.

        Performs viewpoint detection and checks for common image quality issues
        that could affect reconstruction results.

        Args:
            image_path: Path to image file.

        Returns:
            Dictionary containing:
                - orientation (str): Detected viewpoint ('front', 'side', 'top', 'unknown').
                - confidence (float): Confidence score (0.0-1.0).
                - quality_warnings (list): List of strings (e.g., 'blur', 'reflection').
                - suggestions (str): Natural language guidance for the user.
                - error (str, optional): Error message if analysis failed.
        """
        if not self.is_available():
            return {
                "orientation": "unknown",
                "confidence": 0.0,
                "quality_warnings": [],
                "suggestions": "Ollama not available. Install from ollama.ai and run 'ollama pull llava'",
                "error": "Ollama not available"
            }

        image_b64 = self._encode_image(image_path)
        if not image_b64:
            return {
                "orientation": "unknown",
                "confidence": 0.0,
                "quality_warnings": [],
                "suggestions": "Failed to load image",
                "error": "Failed to encode image"
            }

        try:
            import requests
            prompt = (
                "You are analyzing a photo for 3D reconstruction from silhouettes. "
                "Provide a brief analysis covering:\n"
                "1. Camera viewpoint (front/side/top)\n"
                "2. Image quality issues (blur, reflections, low contrast, transparency)\n"
                "3. Suggestions for better results\n\n"
                "Keep response under 100 words, conversational and helpful."
            )

            payload = {
                "model": "llava",
                "prompt": prompt,
                "images": [image_b64],
                "stream": False
            }

            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=30
            )

            if response.status_code != 200:
                return {
                    "orientation": "unknown",
                    "confidence": 0.0,
                    "quality_warnings": [],
                    "suggestions": f"API error: {response.status_code}",
                    "error": f"API error: {response.status_code}"
                }

            result = response.json()
            response_text = result.get("response", "").strip()

            # Parse orientation
            orientation = "unknown"
            for keyword in ["front", "side", "top"]:
                if keyword in response_text.lower():
                    orientation = keyword
                    break

            # Extract quality warnings from response text
            quality_warnings = []
            warning_keywords = {
                "blur": "blur",
                "reflection": "reflection",
                "contrast": "low contrast",
                "transparent": "transparency"
            }
            for key, warning in warning_keywords.items():
                if key in response_text.lower():
                    quality_warnings.append(warning)

            confidence = 0.7 if orientation != "unknown" else 0.3

            return {
                "orientation": orientation,
                "confidence": confidence,
                "quality_warnings": quality_warnings,
                "suggestions": response_text
            }

        except Exception as e:
            return {
                "orientation": "unknown",
                "confidence": 0.0,
                "quality_warnings": [],
                "suggestions": f"Analysis failed: {str(e)}",
                "error": str(e)
            }
