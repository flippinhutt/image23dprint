#!/usr/bin/env python3
"""
E2E Test Script for Ollama Integration
This script performs automated verification of the Ollama integration features.
"""

import sys
import os
import tempfile

# Add src to path
sys.path.insert(0, 'src')

def create_test_image(filename, text="TEST", color=(128, 128, 128)):
    """Create a simple test image with text overlay."""
    try:
        import numpy as np
        import cv2

        # Create a 300x300 test image
        img = np.full((300, 300, 3), color, dtype=np.uint8)

        # Add text
        cv2.putText(img, text, (50, 150), cv2.FONT_HERSHEY_SIMPLEX,
                   2, (255, 255, 255), 3)

        # Save image
        cv2.imwrite(filename, img)
        print(f"✅ Created test image: {filename}")
        return True
    except Exception as e:
        print(f"❌ Failed to create test image: {e}")
        return False

def test_ollama_connection():
    """Test connection to Ollama service."""
    print("\n" + "="*60)
    print("TEST 1: Ollama Connection")
    print("="*60)

    try:
        from image23dprint.ollama_vision import OllamaClient

        ollama = OllamaClient()
        if ollama.is_available():
            print("✅ Ollama is running and accessible")
            return True
        else:
            print("❌ Ollama is not available")
            print("   Please install: https://ollama.ai")
            print("   Then run: ollama pull llava")
            return False
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def test_image_analysis():
    """Test image analysis functionality."""
    print("\n" + "="*60)
    print("TEST 2: Image Analysis")
    print("="*60)

    try:
        from image23dprint.ollama_vision import OllamaClient
        import tempfile

        ollama = OllamaClient()

        # Create a test image
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            test_image_path = f.name

        if not create_test_image(test_image_path, "FRONT VIEW", (100, 150, 200)):
            return False

        try:
            print("📊 Analyzing test image (this may take 5-10 seconds)...")
            result = ollama.analyze_image(test_image_path)

            print("✅ Analysis completed successfully")
            print(f"   Orientation: {result.get('orientation', 'N/A')}")
            print(f"   Confidence: {result.get('confidence', 0):.1%}")

            if result.get('quality_warnings'):
                print(f"   Warnings: {', '.join(result['quality_warnings'])}")
            else:
                print("   Warnings: None")

            if result.get('suggestions'):
                print(f"   Suggestions: {result['suggestions'][:100]}...")

            return True
        finally:
            # Clean up test image
            if os.path.exists(test_image_path):
                os.unlink(test_image_path)

    except Exception as e:
        print(f"❌ Analysis test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_orientation_detection():
    """Test orientation detection specifically."""
    print("\n" + "="*60)
    print("TEST 3: Orientation Detection")
    print("="*60)

    try:
        from image23dprint.ollama_vision import OllamaClient

        ollama = OllamaClient()

        # Create test images for different orientations
        test_cases = [
            ("FRONT", (100, 150, 200)),
            ("SIDE", (200, 100, 150)),
            ("TOP", (150, 200, 100))
        ]

        for view_name, color in test_cases:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                test_image_path = f.name

            if not create_test_image(test_image_path, view_name, color):
                continue

            try:
                print(f"\n📊 Testing {view_name} view detection...")
                result = ollama.detect_orientation(test_image_path)

                orientation = result.get('orientation', 'unknown')
                confidence = result.get('confidence', 0)

                print(f"   Detected: {orientation} ({confidence:.1%} confidence)")

            finally:
                if os.path.exists(test_image_path):
                    os.unlink(test_image_path)

        print("\n✅ Orientation detection test completed")
        return True

    except Exception as e:
        print(f"❌ Orientation detection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_gui_integration_check():
    """Verify GUI has proper Ollama integration (without launching GUI)."""
    print("\n" + "="*60)
    print("TEST 4: GUI Integration Check")
    print("="*60)

    try:
        from image23dprint.gui import Image23DPrintGUI
        from image23dprint.widgets import MaskableImageLabel

        # Check class-level attributes and methods
        checks = [
            (hasattr(Image23DPrintGUI, 'analyze_with_llm'),
             "Image23DPrintGUI.analyze_with_llm method"),
            (hasattr(MaskableImageLabel, 'set_quality_warnings'),
             "MaskableImageLabel.set_quality_warnings method"),
            (hasattr(MaskableImageLabel, 'update_border_style'),
             "MaskableImageLabel.update_border_style method"),
        ]

        all_passed = True
        for check, description in checks:
            if check:
                print(f"✅ {description} exists")
            else:
                print(f"❌ {description} missing")
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"❌ GUI integration check failed: {e}")
        return False

def main():
    """Run all E2E tests."""
    print("=" * 60)
    print("OLLAMA INTEGRATION - E2E TEST SUITE")
    print("=" * 60)

    results = []

    # Test 1: Connection
    results.append(("Ollama Connection", test_ollama_connection()))

    if not results[0][1]:
        print("\n⚠️  Skipping remaining tests - Ollama not available")
        print("   Install Ollama from https://ollama.ai")
        print("   Run: ollama pull llava")
        return 1

    # Test 2: Image Analysis
    results.append(("Image Analysis", test_image_analysis()))

    # Test 3: Orientation Detection
    results.append(("Orientation Detection", test_orientation_detection()))

    # Test 4: GUI Integration
    results.append(("GUI Integration Check", test_gui_integration_check()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")

    print("\n" + "=" * 60)

    if all(result[1] for result in results):
        print("✅ ALL TESTS PASSED")
        print("\nNext Steps:")
        print("  1. Launch GUI: PYTHONPATH=src uv run python -m image23dprint")
        print("  2. Perform manual testing:")
        print("     - Load test images")
        print("     - Verify automatic analysis")
        print("     - Test 'Analyze with AI' button")
        print("     - Check quality warning indicators")
        print("  3. Update integration_test_results.md with findings")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        failed = [name for name, passed in results if not passed]
        print(f"   Failed tests: {', '.join(failed)}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
