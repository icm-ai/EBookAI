import asyncio
import httpx
from typing import Dict, List, Optional
from dataclasses import dataclass

from config import ai_config
from utils.logging_config import get_logger
from utils.exceptions import AIServiceError


@dataclass
class AIResult:
    """Result from AI processing"""
    content: str
    provider: str
    model: str
    processing_time: float
    token_usage: Optional[Dict] = None


class AIService:
    """Handle AI text processing using multiple providers"""

    def __init__(self, provider: str = None):
        self.logger = get_logger("ai_service")
        self.provider = provider or ai_config.DEFAULT_AI_PROVIDER
        self.config = ai_config.get_provider_config(self.provider)

        if not self.config["api_key"]:
            raise ValueError(f"{self.provider} API key not configured")

    async def generate_summary(
        self, text: str, max_length: int = 300, provider: str = None
    ) -> AIResult:
        """Generate text summary using specified or default provider"""
        import time
        start_time = time.time()

        provider = provider or self.provider
        config = ai_config.get_provider_config(provider)

        if not config["api_key"]:
            raise AIServiceError(
                message=f"{provider} API key not configured",
                provider=provider
            )

        prompt = f"""
        请为以下文本生成一个简洁的摘要，长度约为{max_length}字符：

        {text[:2000]}
        """

        try:
            api_type = config.get("api_type", "openai")
            if api_type == "openai":
                content, token_usage = await self._call_openai_compatible_api(
                    config, prompt, max_length
                )
            elif api_type == "anthropic":
                content, token_usage = await self._call_anthropic_api(config, prompt, max_length)
            else:
                raise ValueError(f"Unsupported api_type: {api_type}")

            processing_time = time.time() - start_time

            self.logger.info(
                f"AI summary generated successfully",
                extra={
                    "provider": provider,
                    "processing_time": processing_time,
                    "input_length": len(text),
                    "output_length": len(content)
                }
            )

            return AIResult(
                content=content,
                provider=provider,
                model=config["model"],
                processing_time=processing_time,
                token_usage=token_usage
            )

        except Exception as e:
            self.logger.error(f"AI processing failed: {e}", extra={"provider": provider})
            raise AIServiceError(
                message=f"AI processing failed: {str(e)}",
                provider=provider,
                original_error=e
            )

    async def enhance_text(
        self, text: str, enhancement_type: str = "improve_readability", provider: str = None
    ) -> AIResult:
        """Enhance text with various AI improvements"""
        import time
        start_time = time.time()

        provider = provider or self.provider
        config = ai_config.get_provider_config(provider)

        enhancement_prompts = {
            "improve_readability": "请改善以下文本的可读性，使其更易于理解，保持原意：",
            "fix_grammar": "请修正以下文本中的语法错误和拼写错误：",
            "translate_to_chinese": "请将以下文本翻译成中文：",
            "translate_to_english": "请将以下文本翻译成英文：",
            "format_content": "请对以下文本进行格式化，添加适当的段落分隔和标点符号："
        }

        if enhancement_type not in enhancement_prompts:
            raise AIServiceError(
                message=f"Unsupported enhancement type: {enhancement_type}",
                provider=provider
            )

        prompt = f"{enhancement_prompts[enhancement_type]}\n\n{text[:3000]}"

        try:
            api_type = config.get("api_type", "openai")
            if api_type == "openai":
                content, token_usage = await self._call_openai_compatible_api(
                    config, prompt, max_tokens=1000
                )
            elif api_type == "anthropic":
                content, token_usage = await self._call_anthropic_api(config, prompt, max_tokens=1000)
            else:
                raise ValueError(f"Unsupported api_type: {api_type}")

            processing_time = time.time() - start_time

            return AIResult(
                content=content,
                provider=provider,
                model=config["model"],
                processing_time=processing_time,
                token_usage=token_usage
            )

        except Exception as e:
            raise AIServiceError(
                message=f"Text enhancement failed: {str(e)}",
                provider=provider,
                original_error=e
            )

    async def batch_process_texts(
        self, texts: List[str], operation: str = "summary", **kwargs
    ) -> List[AIResult]:
        """Process multiple texts in parallel with rate limiting"""
        semaphore = asyncio.Semaphore(3)  # Limit concurrent requests

        async def process_single_text(text: str) -> AIResult:
            async with semaphore:
                if operation == "summary":
                    return await self.generate_summary(text, **kwargs)
                elif operation == "enhance":
                    return await self.enhance_text(text, **kwargs)
                else:
                    raise ValueError(f"Unsupported operation: {operation}")

        return await asyncio.gather(
            *[process_single_text(text) for text in texts],
            return_exceptions=True
        )

    async def _call_openai_compatible_api(
        self, config: dict, prompt: str, max_tokens: int = None, max_length: int = None
    ) -> tuple[str, Optional[Dict]]:
        """Call OpenAI-compatible API (OpenAI, DeepSeek)"""

        # Handle backward compatibility
        if max_tokens is None:
            max_tokens = (max_length // 3) if max_length else 300

        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": config["model"],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{config['base_url']}/chat/completions", headers=headers, json=payload
                )

                if response.status_code != 200:
                    error_detail = f"HTTP {response.status_code}"
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            error_detail += f": {error_data['error'].get('message', 'Unknown error')}"
                    except:
                        error_detail += f": {response.text[:200]}"

                    raise Exception(error_detail)

                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()

                # Extract token usage if available
                token_usage = result.get("usage", {})

                return content, token_usage

        except httpx.TimeoutException:
            raise Exception("API request timed out")
        except httpx.ConnectError:
            raise Exception("Failed to connect to API")
        except Exception as e:
            if "API request failed" in str(e) or "timed out" in str(e) or "connect" in str(e):
                raise
            raise Exception(f"Unexpected API error: {str(e)}")

    async def _call_anthropic_api(
        self, config: dict, prompt: str, max_tokens: int = None, max_length: int = None
    ) -> tuple[str, Optional[Dict]]:
        """Call Anthropic API (Claude and compatible APIs)"""

        # Handle backward compatibility
        if max_tokens is None:
            max_tokens = (max_length // 3) if max_length else 300

        headers = {
            "x-api-key": config["api_key"],
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": config["model"],
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{config['base_url']}/v1/messages", headers=headers, json=payload
                )

                if response.status_code != 200:
                    error_detail = f"HTTP {response.status_code}"
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            error_detail += f": {error_data['error'].get('message', 'Unknown error')}"
                    except:
                        error_detail += f": {response.text[:200]}"

                    raise Exception(error_detail)

                result = response.json()
                content = result["content"][0]["text"].strip()

                # Extract token usage if available
                token_usage = result.get("usage", {})

                return content, token_usage

        except httpx.TimeoutException:
            raise Exception("API request timed out")
        except httpx.ConnectError:
            raise Exception("Failed to connect to API")
        except Exception as e:
            if "API request failed" in str(e) or "timed out" in str(e) or "connect" in str(e):
                raise
            raise Exception(f"Unexpected API error: {str(e)}")

    def get_available_providers(self) -> list:
        """Get list of available AI providers with configured API keys"""
        return ai_config.get_available_providers()

    async def extract_text_from_epub(self, epub_path: str) -> str:
        """Extract text content from EPUB file (placeholder)"""
        # This would use a library like ebooklib to extract text
        # For MVP, we'll implement a simple version
        return "Text extraction from EPUB - to be implemented"
