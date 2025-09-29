from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.ai_service import AIService

router = APIRouter()


class SummaryRequest(BaseModel):
    text: str
    max_length: int = 300
    provider: Optional[str] = None


@router.post("/ai/summary")
async def generate_summary(request: SummaryRequest):
    """Generate text summary using AI"""
    try:
        ai_service = AIService(provider=request.provider)
        summary = await ai_service.generate_summary(
            text=request.text, max_length=request.max_length, provider=request.provider
        )

        return {
            "summary": summary,
            "original_length": len(request.text),
            "summary_length": len(summary),
            "provider": request.provider or ai_service.provider,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)}")


@router.get("/ai/providers")
async def get_available_providers():
    """Get list of available AI providers"""
    try:
        ai_service = AIService()
        providers = ai_service.get_available_providers()

        return {"providers": providers, "default": ai_service.provider}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get providers: {str(e)}"
        )


@router.get("/ai/providers/{provider}/test")
async def test_provider(provider: str):
    """Test if a specific AI provider is working"""
    try:
        ai_service = AIService(provider=provider)
        test_text = "This is a test message for API connectivity."

        summary = await ai_service.generate_summary(
            text=test_text, max_length=100, provider=provider
        )

        return {"provider": provider, "status": "working", "test_summary": summary}

    except Exception as e:
        return {"provider": provider, "status": "error", "error": str(e)}
