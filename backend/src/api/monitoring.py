"""
Monitoring and metrics API endpoints.
"""
from typing import Dict, Any

from fastapi import APIRouter, HTTPException

from utils.monitoring import get_performance_stats
from utils.logging_config import get_logger

router = APIRouter(tags=["monitoring"])
logger = get_logger("monitoring_api")


@router.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """Get performance metrics and statistics"""
    try:
        stats = get_performance_stats()
        logger.info("Metrics requested", extra={"stats": stats})
        return {
            "status": "success",
            "metrics": stats,
        }
    except Exception as e:
        logger.error(f"Failed to get metrics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


@router.get("/health/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check with performance metrics"""
    try:
        stats = get_performance_stats()

        # Determine health status based on metrics
        health_status = "healthy"
        issues = []

        # Check error rate
        if stats["error_rate"] > 0.1:  # More than 10% error rate
            health_status = "degraded"
            issues.append(f"High error rate: {stats['error_rate']:.2%}")

        # Check active requests (potential overload)
        if stats["active_requests"] > 50:
            health_status = "degraded"
            issues.append(f"High active requests: {stats['active_requests']}")

        # Check average response times
        for endpoint, times in stats["response_times"].items():
            if times["avg"] > 30:  # More than 30 seconds average
                health_status = "degraded"
                issues.append(f"Slow endpoint {endpoint}: {times['avg']:.2f}s avg")

        return {
            "status": health_status,
            "timestamp": stats.get("timestamp"),
            "metrics": stats,
            "issues": issues,
        }

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e),
        }