#!/usr/bin/env python3
"""Integration test verification script for Ollama integration."""

import sys
import os

# Add src to path
sys.path.insert(0, 'src')

def test_ollama_client_import():
    """Test that OllamaClient can be imported."""
    try:
        from image23dprint.ollama_vision import OllamaClient
        print("✅ OllamaClient import: OK")
        return True
    except Exception as e:
        print(f"❌ OllamaClient import FAILED: {e}")
        return False

def test_ollama_availability():
    """Test Ollama availability check."""
    try:
        from image23dprint.ollama_vision import OllamaClient
        ollama = OllamaClient()
        available = ollama.is_available()
        if available:
            print("✅ Ollama is available and running")
        else:
            print("⚠️  Ollama is not available (expected if not installed)")
        return True
    except Exception as e:
        print(f"❌ Ollama availability check FAILED: {e}")
        return False

def test_gui_import():
    """Test that GUI can be imported."""
    try:
        from image23dprint.gui import Image23DPrintGUI
        print("✅ GUI import: OK")
        return True
    except Exception as e:
        print(f"❌ GUI import FAILED: {e}")
        return False

def test_gui_has_ollama_methods():
    """Test that GUI has the expected Ollama-related methods."""
    try:
        from image23dprint.gui import Image23DPrintGUI

        # Check if the class has the expected method
        if hasattr(Image23DPrintGUI, 'analyze_with_llm'):
            print("✅ GUI has analyze_with_llm method")
        else:
            print("❌ GUI missing analyze_with_llm method")
            return False

        return True
    except Exception as e:
        print(f"❌ GUI method check FAILED: {e}")
        return False

def test_maskable_label_warnings():
    """Test that MaskableImageLabel has quality warnings support."""
    try:
        from image23dprint.gui import MaskableImageLabel

        # Check if the class has the expected methods (no instantiation needed)
        if hasattr(MaskableImageLabel, 'set_quality_warnings'):
            print("✅ MaskableImageLabel has set_quality_warnings method")
        else:
            print("❌ MaskableImageLabel missing set_quality_warnings method")
            return False

        if hasattr(MaskableImageLabel, 'update_border_style'):
            print("✅ MaskableImageLabel has update_border_style method")
        else:
            print("❌ MaskableImageLabel missing update_border_style method")
            return False

        return True
    except Exception as e:
        print(f"❌ MaskableImageLabel check FAILED: {e}")
        return False

def main():
    """Run all integration verification tests."""
    print("=" * 60)
    print("Ollama Integration - Pre-Launch Verification")
    print("=" * 60)
    print()

    results = []

    print("1. Testing OllamaClient module...")
    results.append(test_ollama_client_import())
    print()

    print("2. Testing Ollama availability...")
    results.append(test_ollama_availability())
    print()

    print("3. Testing GUI import...")
    results.append(test_gui_import())
    print()

    print("4. Testing GUI Ollama integration...")
    results.append(test_gui_has_ollama_methods())
    print()

    print("5. Testing visual warning indicators...")
    results.append(test_maskable_label_warnings())
    print()

    print("=" * 60)
    if all(results):
        print("✅ All pre-launch verification tests PASSED")
        print()
        print("Ready for manual E2E testing:")
        print("  1. Install Ollama: https://ollama.ai")
        print("  2. Pull vision model: ollama pull llava")
        print("  3. Launch app: PYTHONPATH=src uv run python -m image23dprint")
        print("  4. Follow test plan in integration_test_results.md")
        return 0
    else:
        print("❌ Some verification tests FAILED")
        print("Fix issues before proceeding to E2E testing")
        return 1

if __name__ == '__main__':
    sys.exit(main())
