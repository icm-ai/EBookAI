import pytest
import os
from unittest.mock import patch, mock_open
from config import AIConfig


class TestAIConfig:
    """Test AI configuration functionality"""

    def test_default_providers_loading(self):
        """Test that default providers are loaded correctly"""
        config = AIConfig()

        # Should have default providers
        assert "openai" in config.providers
        assert "deepseek" in config.providers
        assert "claude" in config.providers

        # Check structure
        assert "api_type" in config.providers["openai"]
        assert config.providers["openai"]["api_type"] == "openai"
        assert config.providers["claude"]["api_type"] == "anthropic"

    @patch.dict(os.environ, {
        'MOONSHOT_API_KEY': 'test_key',
        'MOONSHOT_BASE_URL': 'https://api.moonshot.cn/v1',
        'MOONSHOT_MODEL': 'moonshot-v1-8k'
    })
    def test_auto_discovery(self):
        """Test auto-discovery of providers from environment"""
        config = AIConfig()

        assert "moonshot" in config.providers
        assert config.providers["moonshot"]["api_key"] == "test_key"
        assert config.providers["moonshot"]["api_type"] == "openai"

    def test_get_provider_config_success(self):
        """Test successful provider config retrieval"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            config = AIConfig()
            provider_config = config.get_provider_config("openai")

            assert provider_config["api_key"] == "test_key"
            assert provider_config["api_type"] == "openai"

    @patch.dict(os.environ, {}, clear=True)
    def test_get_provider_config_missing_key(self):
        """Test error when API key is missing"""
        config = AIConfig()

        with pytest.raises(ValueError, match="API key not configured"):
            config.get_provider_config("openai")

    def test_get_provider_config_invalid_provider(self):
        """Test error for invalid provider"""
        config = AIConfig()

        with pytest.raises(ValueError, match="Unsupported AI provider"):
            config.get_provider_config("invalid_provider")

    def test_add_provider(self):
        """Test adding a new provider dynamically"""
        config = AIConfig()

        config.add_provider(
            "custom",
            "test_key",
            "https://api.custom.com",
            "custom-model",
            "openai"
        )

        assert "custom" in config.providers
        assert config.providers["custom"]["api_key"] == "test_key"

    def test_add_provider_invalid_type(self):
        """Test error for invalid API type"""
        config = AIConfig()

        with pytest.raises(ValueError, match="Unsupported api_type"):
            config.add_provider(
                "custom",
                "test_key",
                "https://api.custom.com",
                "custom-model",
                "invalid_type"
            )

    def test_get_available_providers(self):
        """Test getting available providers with valid keys"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            config = AIConfig()
            available = config.get_available_providers()

            assert "openai" in available
            # Others without keys should not be in available
            assert len([p for p in available if p in ["deepseek", "claude"]]) == 0