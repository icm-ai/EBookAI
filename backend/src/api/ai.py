from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.ai_service import AIService
from utils.logging_config import get_logger

router = APIRouter(prefix="/ai", tags=["ai-processing"])
logger = get_logger("ai_api")


class SummaryRequest(BaseModel):
    text: str
    max_length: int = 300
    provider: Optional[str] = None


class EnhanceRequest(BaseModel):
    text: str
    enhancement_type: str = "improve_readability"
    provider: Optional[str] = None


class BatchProcessRequest(BaseModel):
    texts: List[str]
    operation: str = "summary"
    max_length: Optional[int] = 300
    enhancement_type: Optional[str] = "improve_readability"
    provider: Optional[str] = None


@router.post("/summary")
async def generate_summary(request: SummaryRequest):
    """Generate text summary using AI"""
    try:
        ai_service = AIService(provider=request.provider)
        result = await ai_service.generate_summary(
            text=request.text, max_length=request.max_length, provider=request.provider
        )

        return {
            "summary": result.content,
            "original_length": len(request.text),
            "summary_length": len(result.content),
            "provider": result.provider,
            "model": result.model,
            "processing_time": result.processing_time,
            "token_usage": result.token_usage,
        }

    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)}")


@router.post("/enhance")
async def enhance_text(request: EnhanceRequest):
    """Enhance text using AI"""
    try:
        ai_service = AIService(provider=request.provider)
        result = await ai_service.enhance_text(
            text=request.text,
            enhancement_type=request.enhancement_type,
            provider=request.provider
        )

        return {
            "enhanced_text": result.content,
            "original_length": len(request.text),
            "enhanced_length": len(result.content),
            "enhancement_type": request.enhancement_type,
            "provider": result.provider,
            "model": result.model,
            "processing_time": result.processing_time,
            "token_usage": result.token_usage,
        }

    except Exception as e:
        logger.error(f"Text enhancement failed: {e}")
        raise HTTPException(status_code=500, detail=f"Text enhancement failed: {str(e)}")


@router.post("/batch-process")
async def batch_process_texts(request: BatchProcessRequest):
    """Process multiple texts in parallel"""
    try:
        ai_service = AIService(provider=request.provider)

        kwargs = {}
        if request.operation == "summary":
            kwargs["max_length"] = request.max_length
        elif request.operation == "enhance":
            kwargs["enhancement_type"] = request.enhancement_type

        if request.provider:
            kwargs["provider"] = request.provider

        results = await ai_service.batch_process_texts(
            texts=request.texts,
            operation=request.operation,
            **kwargs
        )

        # Process results and handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "index": i,
                    "success": False,
                    "error": str(result)
                })
            else:
                processed_results.append({
                    "index": i,
                    "success": True,
                    "content": result.content,
                    "provider": result.provider,
                    "model": result.model,
                    "processing_time": result.processing_time,
                    "token_usage": result.token_usage,
                })

        successful_count = sum(1 for r in processed_results if r["success"])
        total_processing_time = sum(
            r.get("processing_time", 0) for r in processed_results if r["success"]
        )

        return {
            "results": processed_results,
            "summary": {
                "total_texts": len(request.texts),
                "successful": successful_count,
                "failed": len(request.texts) - successful_count,
                "total_processing_time": total_processing_time,
                "operation": request.operation
            }
        }

    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")


@router.get("/enhancement-types")
async def get_enhancement_types():
    """Get available text enhancement types"""
    return {
        "enhancement_types": [
            {
                "key": "improve_readability",
                "name": "改善可读性",
                "description": "改善文本的可读性，使其更易于理解"
            },
            {
                "key": "fix_grammar",
                "name": "修正语法",
                "description": "修正语法错误和拼写错误"
            },
            {
                "key": "translate_to_chinese",
                "name": "翻译成中文",
                "description": "将文本翻译成中文"
            },
            {
                "key": "translate_to_english",
                "name": "翻译成英文",
                "description": "将文本翻译成英文"
            },
            {
                "key": "format_content",
                "name": "格式化内容",
                "description": "对文本进行格式化，添加适当的段落分隔和标点符号"
            }
        ]
    }


@router.get("/providers")
async def get_available_providers():
    """Get list of available AI providers"""
    try:
        ai_service = AIService()
        providers = ai_service.get_available_providers()

        return {"providers": providers, "default": ai_service.provider}

    except Exception as e:
        logger.error(f"Failed to get providers: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get providers: {str(e)}"
        )


@router.get("/providers/{provider}/test")
async def test_provider(provider: str):
    """Test if a specific AI provider is working"""
    try:
        ai_service = AIService(provider=provider)
        test_text = "这是一个用于测试API连接的消息。"

        result = await ai_service.generate_summary(
            text=test_text, max_length=50, provider=provider
        )

        return {
            "provider": provider,
            "status": "working",
            "test_summary": result.content,
            "model": result.model,
            "processing_time": result.processing_time
        }

    except Exception as e:
        logger.warning(f"Provider {provider} test failed: {e}")
        return {"provider": provider, "status": "error", "error": str(e)}
