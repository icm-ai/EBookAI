import httpx

from config import ai_config


class AIService:
    """Handle AI text processing using multiple providers"""

    def __init__(self, provider: str = None):
        self.provider = provider or ai_config.DEFAULT_AI_PROVIDER
        self.config = ai_config.get_provider_config(self.provider)

        if not self.config["api_key"]:
            raise ValueError(f"{self.provider} API key not configured")

    async def generate_summary(
        self, text: str, max_length: int = 300, provider: str = None
    ) -> str:
        """Generate text summary using specified or default provider"""

        provider = provider or self.provider
        config = ai_config.get_provider_config(provider)

        if not config["api_key"]:
            raise ValueError(f"{provider} API key not configured")

        prompt = f"""
        Provide a concise summary of the text in approximately {max_length} chars:

        {text[:2000]}
        """

        try:
            api_type = config.get("api_type", "openai")
            if api_type == "openai":
                return await self._call_openai_compatible_api(
                    config, prompt, max_length
                )
            elif api_type == "anthropic":
                return await self._call_anthropic_api(config, prompt, max_length)
            else:
                raise ValueError(f"Unsupported api_type: {api_type}")

        except Exception as e:
            raise Exception(f"{provider} API error: {str(e)}")

    async def _call_openai_compatible_api(
        self, config: dict, prompt: str, max_length: int
    ) -> str:
        """Call OpenAI-compatible API (OpenAI, DeepSeek)"""

        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": config["model"],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_length // 3,
            "temperature": 0.3,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{config['base_url']}/chat/completions", headers=headers, json=payload
            )

            if response.status_code != 200:
                raise Exception(
                    f"API request failed: {response.status_code} {response.text}"
                )

            result = response.json()
            return result["choices"][0]["message"]["content"].strip()

    async def _call_anthropic_api(
        self, config: dict, prompt: str, max_length: int
    ) -> str:
        """Call Anthropic API (Claude and compatible APIs)"""

        headers = {
            "x-api-key": config["api_key"],
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": config["model"],
            "max_tokens": max_length // 3,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{config['base_url']}/v1/messages", headers=headers, json=payload
            )

            if response.status_code != 200:
                msg = f"Anthropic API failed: {response.status_code} {response.text}"
                raise Exception(msg)

            result = response.json()
            return result["content"][0]["text"].strip()

    def get_available_providers(self) -> list:
        """Get list of available AI providers with configured API keys"""
        return ai_config.get_available_providers()

    async def extract_text_from_epub(self, epub_path: str) -> str:
        """Extract text content from EPUB file (placeholder)"""
        # This would use a library like ebooklib to extract text
        # For MVP, we'll implement a simple version
        return "Text extraction from EPUB - to be implemented"
