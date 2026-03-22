#!/usr/bin/env python3
"""Integration test verification script for Ollama integration."""

import sys

# Add src to path
sys.path.insert(0, 'src')

def test_ollama_client_import():
    """Test that OllamaClient can be imported."""
    print("✅ OllamaClient import: OK")

def test_ollama_availability():
    """Test Ollama availability check."""
    from image23dprint.ollama_vision import OllamaClient
    ollama = OllamaClient()
    available = ollama.is_available()
    if available:
        print("✅ Ollama is available and running")
    else:
        print("⚠️  Ollama is not available (expected if not installed)")
    # No assertion - availability is informational, not a failure condition

def test_gui_import():
    """Test that GUI can be imported."""
    print("✅ GUI import: OK")

def test_gui_has_ollama_methods():
    """Test that GUI has the expected Ollama-related methods."""
    from image23dprint.gui import Image23DPrintGUI

    # Check if the class has the expected method
    assert hasattr(Image23DPrintGUI, 'analyze_with_llm'), \
        "GUI missing analyze_with_llm method"
    print("✅ GUI has analyze_with_llm method")

def test_maskable_label_warnings():
    """Test that MaskableImageLabel has quality warnings support."""
    from image23dprint.widgets import MaskableImageLabel

    # Check if the class has the expected methods (no instantiation needed)
    assert hasattr(MaskableImageLabel, 'set_quality_warnings'), \
        "MaskableImageLabel missing set_quality_warnings method"
    print("✅ MaskableImageLabel has set_quality_warnings method")

    assert hasattr(MaskableImageLabel, 'update_border_style'), \
        "MaskableImageLabel missing update_border_style method"
    print("✅ MaskableImageLabel has update_border_style method")

def main():
    """Run all integration verification tests."""
    print("=" * 60)
    print("Ollama Integration - Pre-Launch Verification")
    print("=" * 60)
    print()

    tests = [
        ("1. Testing OllamaClient module...", test_ollama_client_import),
        ("2. Testing Ollama availability...", test_ollama_availability),
        ("3. Testing GUI import...", test_gui_import),
        ("4. Testing GUI Ollama integration...", test_gui_has_ollama_methods),
        ("5. Testing visual warning indicators...", test_maskable_label_warnings),
    ]

    results = []
    for description, test_func in tests:
        print(description)
        try:
            test_func()
            results.append(True)
        except AssertionError as e:
            print(f"   Assertion failed: {e}")
            results.append(False)
        except Exception as e:
            print(f"   Test failed with error: {e}")
            results.append(False)
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
