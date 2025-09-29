import json
import os
from pathlib import Path
from typing import Any, Dict

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
CONFIG_DIR = BASE_DIR / "config"

# Create directories if they don't exist
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
CONFIG_DIR.mkdir(exist_ok=True)


# AI Provider Configuration
class AIConfig:
    def __init__(self):
        self.providers = {}
        self.load_config()

    def load_config(self):
        # Load default providers
        self._load_default_providers()

        # Load from config file if exists
        config_file = CONFIG_DIR / "ai_config.json"
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    file_config = json.load(f)
                    self._load_custom_providers(file_config)
            except Exception as e:
                print(f"Warning: Could not load config file: {e}")

        # Set default provider
        self.DEFAULT_AI_PROVIDER = os.getenv("DEFAULT_AI_PROVIDER", "openai")

    def _load_default_providers(self):
        """Load default OpenAI-compatible and Anthropic providers"""
        # OpenAI-compatible providers
        openai_providers = {
            "openai": {
                "api_key": os.getenv("OPENAI_API_KEY", ""),
                "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                "model": os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                "api_type": "openai",
            },
            "deepseek": {
                "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
                "base_url": os.getenv(
                    "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"
                ),
                "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                "api_type": "openai",
            },
        }

        # Anthropic providers
        anthropic_providers = {
            "claude": {
                "api_key": os.getenv("CLAUDE_API_KEY", ""),
                "base_url": os.getenv("CLAUDE_BASE_URL", "https://api.anthropic.com"),
                "model": os.getenv("CLAUDE_MODEL", "claude-3-sonnet-20240229"),
                "api_type": "anthropic",
            }
        }

        # Auto-discover providers from environment variables
        self._discover_providers_from_env()

        self.providers.update(openai_providers)
        self.providers.update(anthropic_providers)

    def _discover_providers_from_env(self):
        """Auto-discover providers from environment variables"""
        # Get all environment variables
        env_vars = os.environ

        # Pattern: {PROVIDER}_API_KEY
        discovered = {}
        for key, value in env_vars.items():
            if key.endswith("_API_KEY") and value:
                provider_name = key[:-8].lower()  # Remove '_API_KEY' suffix

                # Skip if already defined as built-in
                if provider_name in ["openai", "deepseek", "claude"]:
                    continue

                # Auto-detect provider configuration
                base_url_key = f"{provider_name.upper()}_BASE_URL"
                model_key = f"{provider_name.upper()}_MODEL"
                api_type_key = f"{provider_name.upper()}_API_TYPE"

                base_url = os.getenv(base_url_key, "")
                model = os.getenv(model_key, "")
                api_type = os.getenv(
                    api_type_key, "openai"
                )  # Default to openai-compatible

                if base_url and model:
                    discovered[provider_name] = {
                        "api_key": value,
                        "base_url": base_url,
                        "model": model,
                        "api_type": api_type,
                    }

        self.providers.update(discovered)

    def _load_custom_providers(self, config: Dict[str, Any]):
        """Load custom providers from config file"""
        if "providers" in config:
            for name, provider_config in config["providers"].items():
                # Only add if required fields are present
                if self._validate_provider_config(provider_config):
                    # Override env variables with config file values if env not set
                    final_config = {}
                    for key, value in provider_config.items():
                        env_key = f"{name.upper()}_{key.upper()}"
                        final_config[key] = os.getenv(env_key, value)

                    self.providers[name] = final_config

    def _validate_provider_config(self, config: Dict[str, Any]) -> bool:
        """Validate provider configuration"""
        required_fields = ["api_key", "base_url", "model", "api_type"]
        return all(field in config for field in required_fields)

    def add_provider(
        self,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        api_type: str = "openai",
    ):
        """Dynamically add a new provider"""
        if api_type not in ["openai", "anthropic"]:
            raise ValueError(
                f"Unsupported api_type: {api_type}. Must be 'openai' or 'anthropic'"
            )

        self.providers[name] = {
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
            "api_type": api_type,
        }

    def get_available_providers(self) -> list:
        """Get list of providers with valid API keys"""
        return [
            name for name, config in self.providers.items() if config.get("api_key")
        ]

    def _update_from_dict(self, config_dict: Dict[str, Any]):
        """Update configuration from dictionary (only if env var not set)"""
        for key, value in config_dict.items():
            attr_name = key.upper()
            if hasattr(self, attr_name) and not os.getenv(key.upper()):
                setattr(self, attr_name, value)

    def get_provider_config(self, provider: str = None) -> Dict[str, str]:
        """Get configuration for specific AI provider"""
        provider = provider or self.DEFAULT_AI_PROVIDER

        if provider not in self.providers:
            raise ValueError(f"Unsupported AI provider: {provider}")

        config = self.providers[provider]
        if not config.get("api_key"):
            raise ValueError(f"API key not configured for provider: {provider}")

        return config


# Initialize AI configuration
ai_config = AIConfig()

# File settings
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {".epub", ".pdf", ".txt"}

# Conversion settings
CONVERSION_TIMEOUT = 300  # 5 minutes
