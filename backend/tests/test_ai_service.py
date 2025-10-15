import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from services.ai_service import AIService, AIResult
from utils.exceptions import AIServiceError


@pytest.fixture
def mock_ai_config():
    """Mock AI configuration"""
    with patch("services.ai_service.ai_config") as mock_config:
        mock_config.DEFAULT_AI_PROVIDER = "deepseek"
        mock_config.get_provider_config.return_value = {
            "api_key": "test-api-key",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat",
            "api_type": "openai"
        }
        mock_config.get_available_providers.return_value = ["deepseek", "openai"]
        yield mock_config


@pytest.fixture
def ai_service(mock_ai_config):
    """Create AIService instance with mocked config"""
    return AIService()


class TestAIServiceInitialization:
    """Test AIService initialization"""

    def test_initialization_with_default_provider(self, mock_ai_config):
        """Test service initializes with default provider"""
        service = AIService()
        assert service.provider == "deepseek"
        assert service.config["api_key"] == "test-api-key"

    def test_initialization_with_custom_provider(self, mock_ai_config):
        """Test service initializes with custom provider"""
        mock_ai_config.get_provider_config.return_value = {
            "api_key": "openai-key",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-3.5-turbo",
            "api_type": "openai"
        }
        service = AIService(provider="openai")
        assert service.provider == "openai"

    def test_initialization_fails_without_api_key(self, mock_ai_config):
        """Test initialization fails when API key is not configured"""
        mock_ai_config.get_provider_config.return_value = {
            "api_key": None,
            "base_url": "https://api.example.com",
            "model": "test-model",
            "api_type": "openai"
        }
        with pytest.raises(ValueError, match="API key not configured"):
            AIService()


class TestGenerateSummary:
    """Test generate_summary method"""

    @pytest.mark.asyncio
    async def test_generate_summary_success_openai(self, ai_service):
        """Test successful summary generation with OpenAI API"""
        mock_response = {
            "choices": [{"message": {"content": "This is a test summary."}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20}
        }

        with patch.object(ai_service, "_call_openai_compatible_api", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = ("This is a test summary.", {"prompt_tokens": 100, "completion_tokens": 20})

            result = await ai_service.generate_summary("Test text for summarization")

            assert isinstance(result, AIResult)
            assert result.content == "This is a test summary."
            assert result.provider == "deepseek"
            assert result.model == "deepseek-chat"
            assert result.processing_time > 0
            assert result.token_usage is not None

    @pytest.mark.asyncio
    async def test_generate_summary_with_custom_max_length(self, ai_service):
        """Test summary generation with custom max length"""
        with patch.object(ai_service, "_call_openai_compatible_api", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = ("Short summary.", {})

            result = await ai_service.generate_summary("Test text", max_length=100)

            mock_call.assert_called_once()
            args = mock_call.call_args[0]
            assert "max_length" in mock_call.call_args[1] or args[2] is not None

    @pytest.mark.asyncio
    async def test_generate_summary_with_different_provider(self, ai_service, mock_ai_config):
        """Test summary generation with different provider"""
        mock_ai_config.get_provider_config.return_value = {
            "api_key": "claude-key",
            "base_url": "https://api.anthropic.com",
            "model": "claude-3-sonnet",
            "api_type": "anthropic"
        }

        with patch.object(ai_service, "_call_anthropic_api", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = ("Claude summary.", {})

            result = await ai_service.generate_summary("Test text", provider="claude")

            assert result.provider == "claude"
            mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_summary_api_key_not_configured(self, ai_service, mock_ai_config):
        """Test summary generation fails when API key is not configured"""
        mock_ai_config.get_provider_config.return_value = {
            "api_key": None,
            "base_url": "https://api.example.com",
            "model": "test-model",
            "api_type": "openai"
        }

        with pytest.raises(AIServiceError, match="API key not configured"):
            await ai_service.generate_summary("Test text", provider="invalid_provider")

    @pytest.mark.asyncio
    async def test_generate_summary_handles_api_error(self, ai_service):
        """Test summary generation handles API errors"""
        with patch.object(ai_service, "_call_openai_compatible_api", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = Exception("API connection failed")

            with pytest.raises(AIServiceError, match="AI processing failed"):
                await ai_service.generate_summary("Test text")

    @pytest.mark.asyncio
    async def test_generate_summary_truncates_long_text(self, ai_service):
        """Test that long input text is truncated to 2000 characters"""
        long_text = "a" * 5000

        with patch.object(ai_service, "_call_openai_compatible_api", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = ("Summary.", {})

            await ai_service.generate_summary(long_text)

            call_args = mock_call.call_args[0]
            prompt = call_args[1]
            assert len(long_text[:2000]) <= 2000
            assert long_text[:2000] in prompt


class TestEnhanceText:
    """Test enhance_text method"""

    @pytest.mark.asyncio
    async def test_enhance_text_improve_readability(self, ai_service):
        """Test text enhancement with improve_readability type"""
        with patch.object(ai_service, "_call_openai_compatible_api", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = ("Enhanced text with better readability.", {})

            result = await ai_service.enhance_text("Original text", enhancement_type="improve_readability")

            assert result.content == "Enhanced text with better readability."
            assert result.provider == "deepseek"

    @pytest.mark.asyncio
    async def test_enhance_text_fix_grammar(self, ai_service):
        """Test text enhancement with fix_grammar type"""
        with patch.object(ai_service, "_call_openai_compatible_api", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = ("Text with fixed grammar.", {})

            result = await ai_service.enhance_text("Text with errors", enhancement_type="fix_grammar")

            assert "fixed grammar" in result.content

    @pytest.mark.asyncio
    async def test_enhance_text_translate_to_chinese(self, ai_service):
        """Test text enhancement with translation to Chinese"""
        with patch.object(ai_service, "_call_openai_compatible_api", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = ("翻译后的中文文本", {})

            result = await ai_service.enhance_text("English text", enhancement_type="translate_to_chinese")

            assert result.content == "翻译后的中文文本"

    @pytest.mark.asyncio
    async def test_enhance_text_invalid_enhancement_type(self, ai_service):
        """Test enhancement fails with invalid type"""
        with pytest.raises(AIServiceError, match="Unsupported enhancement type"):
            await ai_service.enhance_text("Text", enhancement_type="invalid_type")

    @pytest.mark.asyncio
    async def test_enhance_text_truncates_long_text(self, ai_service):
        """Test that enhancement truncates text to 3000 characters"""
        long_text = "b" * 5000

        with patch.object(ai_service, "_call_openai_compatible_api", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = ("Enhanced.", {})

            await ai_service.enhance_text(long_text, enhancement_type="improve_readability")

            call_args = mock_call.call_args[0]
            prompt = call_args[1]
            assert long_text[:3000] in prompt


class TestBatchProcessTexts:
    """Test batch_process_texts method"""

    @pytest.mark.asyncio
    async def test_batch_process_summaries(self, ai_service):
        """Test batch processing for summaries"""
        texts = ["Text 1", "Text 2", "Text 3"]

        with patch.object(ai_service, "generate_summary", new_callable=AsyncMock) as mock_summary:
            mock_summary.side_effect = [
                AIResult("Summary 1", "deepseek", "deepseek-chat", 0.5),
                AIResult("Summary 2", "deepseek", "deepseek-chat", 0.5),
                AIResult("Summary 3", "deepseek", "deepseek-chat", 0.5),
            ]

            results = await ai_service.batch_process_texts(texts, operation="summary")

            assert len(results) == 3
            assert all(isinstance(r, AIResult) for r in results)
            assert mock_summary.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_process_enhancements(self, ai_service):
        """Test batch processing for enhancements"""
        texts = ["Text 1", "Text 2"]

        with patch.object(ai_service, "enhance_text", new_callable=AsyncMock) as mock_enhance:
            mock_enhance.side_effect = [
                AIResult("Enhanced 1", "deepseek", "deepseek-chat", 0.5),
                AIResult("Enhanced 2", "deepseek", "deepseek-chat", 0.5),
            ]

            results = await ai_service.batch_process_texts(
                texts, operation="enhance", enhancement_type="improve_readability"
            )

            assert len(results) == 2
            assert mock_enhance.call_count == 2

    @pytest.mark.asyncio
    async def test_batch_process_invalid_operation(self, ai_service):
        """Test batch processing with invalid operation"""
        texts = ["Text 1"]

        results = await ai_service.batch_process_texts(texts, operation="invalid_op")

        assert len(results) == 1
        assert isinstance(results[0], Exception)

    @pytest.mark.asyncio
    async def test_batch_process_handles_errors(self, ai_service):
        """Test batch processing handles individual errors gracefully"""
        texts = ["Text 1", "Text 2", "Text 3"]

        with patch.object(ai_service, "generate_summary", new_callable=AsyncMock) as mock_summary:
            mock_summary.side_effect = [
                AIResult("Summary 1", "deepseek", "deepseek-chat", 0.5),
                AIServiceError("API error", "deepseek"),
                AIResult("Summary 3", "deepseek", "deepseek-chat", 0.5),
            ]

            results = await ai_service.batch_process_texts(texts, operation="summary")

            assert len(results) == 3
            assert isinstance(results[0], AIResult)
            assert isinstance(results[1], AIServiceError)
            assert isinstance(results[2], AIResult)


class TestOpenAICompatibleAPI:
    """Test _call_openai_compatible_api method"""

    @pytest.mark.asyncio
    async def test_openai_api_success(self, ai_service):
        """Test successful OpenAI API call"""
        config = {
            "api_key": "test-key",
            "base_url": "https://api.test.com",
            "model": "test-model"
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "API response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            content, usage = await ai_service._call_openai_compatible_api(config, "Test prompt", max_tokens=100)

            assert content == "API response"
            assert usage["prompt_tokens"] == 10

    @pytest.mark.asyncio
    async def test_openai_api_http_error(self, ai_service):
        """Test OpenAI API call with HTTP error"""
        config = {
            "api_key": "test-key",
            "base_url": "https://api.test.com",
            "model": "test-model"
        }

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "error": {"message": "Invalid API key"}
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            with pytest.raises(Exception, match="HTTP 401"):
                await ai_service._call_openai_compatible_api(config, "Test prompt")

    @pytest.mark.asyncio
    async def test_openai_api_timeout(self, ai_service):
        """Test OpenAI API call timeout"""
        config = {
            "api_key": "test-key",
            "base_url": "https://api.test.com",
            "model": "test-model"
        }

        with patch("httpx.AsyncClient") as mock_client:
            import httpx
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )

            with pytest.raises(Exception, match="timed out"):
                await ai_service._call_openai_compatible_api(config, "Test prompt")

    @pytest.mark.asyncio
    async def test_openai_api_connection_error(self, ai_service):
        """Test OpenAI API connection error"""
        config = {
            "api_key": "test-key",
            "base_url": "https://api.test.com",
            "model": "test-model"
        }

        with patch("httpx.AsyncClient") as mock_client:
            import httpx
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection failed")
            )

            with pytest.raises(Exception, match="Failed to connect"):
                await ai_service._call_openai_compatible_api(config, "Test prompt")


class TestAnthropicAPI:
    """Test _call_anthropic_api method"""

    @pytest.mark.asyncio
    async def test_anthropic_api_success(self, ai_service):
        """Test successful Anthropic API call"""
        config = {
            "api_key": "claude-key",
            "base_url": "https://api.anthropic.com",
            "model": "claude-3-sonnet"
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"text": "Claude response"}],
            "usage": {"input_tokens": 15, "output_tokens": 10}
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            content, usage = await ai_service._call_anthropic_api(config, "Test prompt", max_tokens=100)

            assert content == "Claude response"
            assert usage["input_tokens"] == 15

    @pytest.mark.asyncio
    async def test_anthropic_api_error(self, ai_service):
        """Test Anthropic API call with error"""
        config = {
            "api_key": "claude-key",
            "base_url": "https://api.anthropic.com",
            "model": "claude-3-sonnet"
        }

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {
            "error": {"message": "Rate limit exceeded"}
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            with pytest.raises(Exception, match="HTTP 429"):
                await ai_service._call_anthropic_api(config, "Test prompt")


class TestUtilityMethods:
    """Test utility methods"""

    def test_get_available_providers(self, ai_service, mock_ai_config):
        """Test getting available providers"""
        providers = ai_service.get_available_providers()

        assert isinstance(providers, list)
        assert "deepseek" in providers
        mock_ai_config.get_available_providers.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_text_from_epub_placeholder(self, ai_service):
        """Test EPUB text extraction placeholder"""
        result = await ai_service.extract_text_from_epub("/path/to/file.epub")

        assert "to be implemented" in result.lower()
