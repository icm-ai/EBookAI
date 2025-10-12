from fastapi import APIRouter
from typing import Dict, Any
import time
import asyncio
from datetime import datetime

from services.conversion_service import ConversionService
from services.ai_service import AIService
from services.batch_conversion_service import batch_conversion_service
from utils.logging_config import get_logger
from config import ai_config

router = APIRouter(prefix="/health", tags=["health"])
logger = get_logger("health_api")


@router.get("")
async def health_check() -> Dict[str, Any]:
    """基础健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "EBookAI",
        "version": "1.0.0"
    }


@router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """详细健康检查，包含所有服务状态"""
    start_time = time.time()

    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "EBookAI",
        "version": "1.0.0",
        "components": {},
        "check_duration": 0
    }

    # 检查转换服务
    try:
        conversion_service = ConversionService()
        health_status["components"]["conversion_service"] = {
            "status": "healthy",
            "message": "Conversion service is operational"
        }
    except Exception as e:
        health_status["components"]["conversion_service"] = {
            "status": "unhealthy",
            "message": f"Conversion service error: {str(e)}"
        }
        health_status["status"] = "degraded"

    # 检查批量转换服务
    try:
        batch_count = len(batch_conversion_service.active_batches)
        health_status["components"]["batch_conversion_service"] = {
            "status": "healthy",
            "message": "Batch conversion service is operational",
            "active_batches": batch_count
        }
    except Exception as e:
        health_status["components"]["batch_conversion_service"] = {
            "status": "unhealthy",
            "message": f"Batch conversion service error: {str(e)}"
        }
        health_status["status"] = "degraded"

    # 检查AI服务配置
    try:
        available_providers = ai_config.get_available_providers()
        if available_providers:
            health_status["components"]["ai_service"] = {
                "status": "healthy",
                "message": "AI service configured",
                "available_providers": available_providers,
                "default_provider": ai_config.DEFAULT_AI_PROVIDER
            }
        else:
            health_status["components"]["ai_service"] = {
                "status": "degraded",
                "message": "No AI providers configured",
                "available_providers": [],
                "default_provider": ai_config.DEFAULT_AI_PROVIDER
            }
    except Exception as e:
        health_status["components"]["ai_service"] = {
            "status": "unhealthy",
            "message": f"AI service error: {str(e)}"
        }
        health_status["status"] = "degraded"

    health_status["check_duration"] = round(time.time() - start_time, 3)

    logger.info(
        f"Health check completed",
        extra={
            "status": health_status["status"],
            "duration": health_status["check_duration"],
            "components_count": len(health_status["components"])
        }
    )

    return health_status


@router.get("/metrics")
async def get_system_metrics() -> Dict[str, Any]:
    """获取系统指标"""
    try:
        # 批量转换指标
        batch_metrics = {
            "active_batches": len(batch_conversion_service.active_batches),
            "total_batches_processed": 0,  # 可以从日志或数据库获取
            "average_processing_time": 0   # 可以从历史数据计算
        }

        # AI服务指标
        ai_metrics = {
            "configured_providers": len(ai_config.get_available_providers()),
            "default_provider": ai_config.DEFAULT_AI_PROVIDER,
            "total_requests": 0,  # 可以从监控系统获取
            "success_rate": 0     # 可以从监控系统计算
        }

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "batch_conversion": batch_metrics,
            "ai_service": ai_metrics,
            "system": {
                "uptime": "N/A",  # 可以跟踪服务启动时间
                "memory_usage": "N/A",  # 可以使用psutil获取
                "cpu_usage": "N/A"      # 可以使用psutil获取
            }
        }

    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        return {
            "error": "Failed to retrieve system metrics",
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/readiness")
async def readiness_check() -> Dict[str, Any]:
    """就绪检查 - 检查服务是否准备好接收请求"""
    try:
        # 检查关键服务是否可用
        conversion_service = ConversionService()

        # 检查是否有可用的AI提供商
        available_providers = ai_config.get_available_providers()

        if len(available_providers) > 0:
            return {
                "status": "ready",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Service is ready to accept requests"
            }
        else:
            return {
                "status": "not_ready",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "No AI providers configured"
            }

    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {
            "status": "not_ready",
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Service not ready: {str(e)}"
        }


@router.get("/liveness")
async def liveness_check() -> Dict[str, Any]:
    """存活检查 - 检查服务是否仍在运行"""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Service is alive"
    }