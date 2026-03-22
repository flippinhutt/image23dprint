"""Ollama LLM Vision integration for AI-assisted photo analysis."""

from typing import Optional


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
            bool: True if Ollama API is accessible, False otherwise.
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
        except (ImportError, Exception) as e:
            OllamaClient._available = False
            return False
