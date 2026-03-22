import base64
import pytest
from unittest.mock import Mock, patch
from image23dprint.ollama_vision import OllamaClient


@pytest.fixture
def client():
    """Create a fresh OllamaClient for each test."""
    # Reset class-level cache
    OllamaClient._available = None
    return OllamaClient()


def test_ollama_client_init(client):
    """Test OllamaClient initialization with default settings."""
    assert client.base_url == "http://localhost:11434"
    assert client.timeout == 5


def test_is_available_when_ollama_running(client):
    """Test is_available returns True when Ollama API is accessible."""
    mock_response = Mock()
    mock_response.status_code = 200

    with patch('requests.get', return_value=mock_response):
        assert client.is_available() is True
        assert OllamaClient._available is True


def test_is_available_when_ollama_not_running(client):
    """Test is_available returns False when Ollama is not accessible."""
    with patch('requests.get', side_effect=Exception("Connection refused")):
        assert client.is_available() is False
        assert OllamaClient._available is False


def test_is_available_uses_cache(client):
    """Test is_available uses cached result on subsequent calls."""
    # First call sets cache
    OllamaClient._available = True

    # Second call should not make HTTP request
    with patch('requests.get') as mock_get:
        result = client.is_available()
        assert result is True
        mock_get.assert_not_called()


def test_encode_image_success(client, tmp_path):
    """Test _encode_image successfully encodes an image file."""
    # Create a temporary test image
    test_file = tmp_path / "test.jpg"
    test_content = b"fake image content"
    test_file.write_bytes(test_content)

    result = client._encode_image(str(test_file))
    expected = base64.b64encode(test_content).decode('utf-8')

    assert result == expected


def test_encode_image_nonexistent_file(client):
    """Test _encode_image returns None for nonexistent file."""
    result = client._encode_image("/nonexistent/path/image.jpg")
    assert result is None


def test_detect_orientation_ollama_unavailable(client):
    """Test detect_orientation when Ollama is not available."""
    with patch.object(client, 'is_available', return_value=False):
        result = client.detect_orientation("test.jpg")

        assert result["orientation"] == "unknown"
        assert result["confidence"] == 0.0
        assert "error" in result


def test_detect_orientation_image_encoding_fails(client):
    """Test detect_orientation when image encoding fails."""
    with patch.object(client, 'is_available', return_value=True):
        with patch.object(client, '_encode_image', return_value=None):
            result = client.detect_orientation("test.jpg")

            assert result["orientation"] == "unknown"
            assert result["confidence"] == 0.0
            assert "error" in result


def test_detect_orientation_front_view(client):
    """Test detect_orientation correctly identifies front view."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "front"}

    with patch.object(client, 'is_available', return_value=True):
        with patch.object(client, '_encode_image', return_value="fake_base64"):
            with patch('requests.post', return_value=mock_response):
                result = client.detect_orientation("test.jpg")

                assert result["orientation"] == "front"
                assert result["confidence"] == 0.8


def test_detect_orientation_side_view(client):
    """Test detect_orientation correctly identifies side view."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "side"}

    with patch.object(client, 'is_available', return_value=True):
        with patch.object(client, '_encode_image', return_value="fake_base64"):
            with patch('requests.post', return_value=mock_response):
                result = client.detect_orientation("test.jpg")

                assert result["orientation"] == "side"
                assert result["confidence"] == 0.8


def test_detect_orientation_top_view(client):
    """Test detect_orientation correctly identifies top view."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "top"}

    with patch.object(client, 'is_available', return_value=True):
        with patch.object(client, '_encode_image', return_value="fake_base64"):
            with patch('requests.post', return_value=mock_response):
                result = client.detect_orientation("test.jpg")

                assert result["orientation"] == "top"
                assert result["confidence"] == 0.8


def test_detect_orientation_unknown(client):
    """Test detect_orientation handles ambiguous responses."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "unclear angle"}

    with patch.object(client, 'is_available', return_value=True):
        with patch.object(client, '_encode_image', return_value="fake_base64"):
            with patch('requests.post', return_value=mock_response):
                result = client.detect_orientation("test.jpg")

                assert result["orientation"] == "unknown"
                assert result["confidence"] == 0.1


def test_detect_orientation_api_error(client):
    """Test detect_orientation handles API errors gracefully."""
    mock_response = Mock()
    mock_response.status_code = 500

    with patch.object(client, 'is_available', return_value=True):
        with patch.object(client, '_encode_image', return_value="fake_base64"):
            with patch('requests.post', return_value=mock_response):
                result = client.detect_orientation("test.jpg")

                assert result["orientation"] == "unknown"
                assert result["confidence"] == 0.0
                assert "error" in result


def test_analyze_image_ollama_unavailable(client):
    """Test analyze_image when Ollama is not available."""
    with patch.object(client, 'is_available', return_value=False):
        result = client.analyze_image("test.jpg")

        assert result["orientation"] == "unknown"
        assert result["confidence"] == 0.0
        assert result["quality_warnings"] == []
        assert "Ollama not available" in result["suggestions"]
        assert "error" in result


def test_analyze_image_success_with_warnings(client):
    """Test analyze_image detects quality warnings."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": "This is a front view. The image has some blur and reflections. Try better lighting."
    }

    with patch.object(client, 'is_available', return_value=True):
        with patch.object(client, '_encode_image', return_value="fake_base64"):
            with patch('requests.post', return_value=mock_response):
                result = client.analyze_image("test.jpg")

                assert result["orientation"] == "front"
                assert result["confidence"] == 0.7
                assert "blur" in result["quality_warnings"]
                assert "reflection" in result["quality_warnings"]
                assert "front view" in result["suggestions"].lower()


def test_analyze_image_no_warnings(client):
    """Test analyze_image with clean image (no quality issues)."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": "Clear side view, good quality photo."
    }

    with patch.object(client, 'is_available', return_value=True):
        with patch.object(client, '_encode_image', return_value="fake_base64"):
            with patch('requests.post', return_value=mock_response):
                result = client.analyze_image("test.jpg")

                assert result["orientation"] == "side"
                assert result["confidence"] == 0.7
                assert result["quality_warnings"] == []


def test_analyze_image_low_contrast_warning(client):
    """Test analyze_image detects low contrast issues."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": "The image has low contrast which may affect masking."
    }

    with patch.object(client, 'is_available', return_value=True):
        with patch.object(client, '_encode_image', return_value="fake_base64"):
            with patch('requests.post', return_value=mock_response):
                result = client.analyze_image("test.jpg")

                assert "low contrast" in result["quality_warnings"]


def test_analyze_image_transparency_warning(client):
    """Test analyze_image detects transparency issues."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": "Object appears transparent in some areas."
    }

    with patch.object(client, 'is_available', return_value=True):
        with patch.object(client, '_encode_image', return_value="fake_base64"):
            with patch('requests.post', return_value=mock_response):
                result = client.analyze_image("test.jpg")

                assert "transparency" in result["quality_warnings"]


def test_analyze_image_request_exception(client):
    """Test analyze_image handles network exceptions gracefully."""
    with patch.object(client, 'is_available', return_value=True):
        with patch.object(client, '_encode_image', return_value="fake_base64"):
            with patch('requests.post', side_effect=Exception("Network error")):
                result = client.analyze_image("test.jpg")

                assert result["orientation"] == "unknown"
                assert result["confidence"] == 0.0
                assert result["quality_warnings"] == []
                assert "error" in result
                assert "Network error" in result["error"]
