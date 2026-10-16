"""
Tests for API Key discovery, validation, and persistence.
"""

from unittest.mock import MagicMock, patch
import pytest

from multi_agent_coder.common.auth import (
    ensure_api_key,
    find_configured_api_key,
    persist_api_key,
    validate_gemini_api_key,
    _VALIDATED_KEYS,
)


def test_rejects_empty_and_whitespace_keys():
    is_valid, msg = validate_gemini_api_key("")
    assert not is_valid
    assert "empty" in msg.lower()

    is_valid, msg = validate_gemini_api_key("   ")
    assert not is_valid
    assert "empty" in msg.lower()


def test_rejects_oauth_aq_session_token():
    is_valid, msg = validate_gemini_api_key("AQ.Ab8RN6somethingdummytoken")
    assert not is_valid
    assert "AQ." in msg
    assert "Google AI Studio" in msg


def test_validation_caching():
    _VALIDATED_KEYS.clear()
    dummy_key = "AIzaSy_mock_valid_key_for_caching_test"

    with patch("multi_agent_coder.common.auth.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "pong"
        mock_instance.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_instance

        # 1. First call touches API
        is_valid, msg = validate_gemini_api_key(dummy_key, bypass_cache=False)
        assert is_valid
        assert mock_instance.models.generate_content.call_count == 1

        # 2. Second call uses cache
        is_valid2, msg2 = validate_gemini_api_key(dummy_key, bypass_cache=False)
        assert is_valid2
        assert "cached" in msg2.lower()
        assert mock_instance.models.generate_content.call_count == 1  # Not called again


def test_validation_handles_google_errors():
    dummy_key = "AIzaSy_invalid_key"
    with patch("multi_agent_coder.common.auth.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.models.generate_content.side_effect = Exception("400 API_KEY_INVALID: Key not found")
        mock_client_cls.return_value = mock_instance

        is_valid, msg = validate_gemini_api_key(dummy_key, bypass_cache=True)
        assert not is_valid
        assert "API_KEY_INVALID" in msg


def test_find_configured_api_key_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy_test_from_env")
    assert find_configured_api_key() == "AIzaSy_test_from_env"
