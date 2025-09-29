"""
Performance monitoring and metrics collection for EBookAI.
"""
import time
import uuid
from typing import Dict, Any, Optional
from functools import wraps
from contextlib import asynccontextmanager

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from utils.logging_config import get_logger


class PerformanceMetrics:
    """Collect and store performance metrics"""

    def __init__(self):
        self.logger = get_logger("metrics")
        self.request_count = 0
        self.error_count = 0
        self.response_times: Dict[str, list] = {}
        self.active_requests: Dict[str, Dict[str, Any]] = {}

    def record_request_start(self, request_id: str, method: str, path: str) -> None:
        """Record the start of a request"""
        self.request_count += 1
        self.active_requests[request_id] = {
            "method": method,
            "path": path,
            "start_time": time.time(),
            "request_id": request_id,
        }

        self.logger.info(
            f"Request started: {method} {path}",
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "active_requests_count": len(self.active_requests),
            },
        )

    def record_request_end(
        self,
        request_id: str,
        status_code: int,
        response_size: Optional[int] = None,
    ) -> None:
        """Record the end of a request"""
        if request_id not in self.active_requests:
            return

        request_info = self.active_requests.pop(request_id)
        duration = time.time() - request_info["start_time"]

        # Track response times by endpoint
        endpoint = f"{request_info['method']} {request_info['path']}"
        if endpoint not in self.response_times:
            self.response_times[endpoint] = []
        self.response_times[endpoint].append(duration)

        # Keep only last 100 response times per endpoint
        if len(self.response_times[endpoint]) > 100:
            self.response_times[endpoint] = self.response_times[endpoint][-100:]

        # Count errors
        if status_code >= 400:
            self.error_count += 1

        self.logger.info(
            f"Request completed: {request_info['method']} {request_info['path']}",
            extra={
                "request_id": request_id,
                "method": request_info["method"],
                "path": request_info["path"],
                "duration": duration,
                "status_code": status_code,
                "response_size": response_size,
                "active_requests_count": len(self.active_requests),
            },
        )

    def record_error(self, request_id: str, error_type: str, error_message: str) -> None:
        """Record an error occurrence"""
        self.error_count += 1

        self.logger.error(
            f"Error occurred: {error_type}",
            extra={
                "request_id": request_id,
                "error_type": error_type,
                "error_message": error_message,
                "total_errors": self.error_count,
            },
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        stats = {
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "active_requests": len(self.active_requests),
            "error_rate": (
                self.error_count / self.request_count if self.request_count > 0 else 0
            ),
            "response_times": {},
        }

        # Calculate average response times
        for endpoint, times in self.response_times.items():
            if times:
                stats["response_times"][endpoint] = {
                    "avg": sum(times) / len(times),
                    "min": min(times),
                    "max": max(times),
                    "count": len(times),
                }

        return stats


# Global metrics instance
metrics = PerformanceMetrics()


class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware for tracking request performance"""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Record request start
        metrics.record_request_start(
            request_id, request.method, str(request.url.path)
        )

        try:
            # Process request
            response = await call_next(request)

            # Record successful completion
            response_size = response.headers.get("content-length")
            if response_size:
                response_size = int(response_size)

            metrics.record_request_end(
                request_id, response.status_code, response_size
            )

            # Add request ID to response headers for debugging
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Record error
            metrics.record_error(
                request_id, type(e).__name__, str(e)
            )

            # Re-raise the exception to be handled by global error handler
            raise


def track_operation(operation_name: str):
    """Decorator to track the performance of specific operations"""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = str(uuid.uuid4())
            logger = get_logger("operation_tracker")

            logger.info(
                f"Operation started: {operation_name}",
                extra={
                    "operation": operation_name,
                    "operation_id": operation_id,
                },
            )

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                logger.info(
                    f"Operation completed: {operation_name}",
                    extra={
                        "operation": operation_name,
                        "operation_id": operation_id,
                        "duration": duration,
                        "status": "success",
                    },
                )

                return result

            except Exception as e:
                duration = time.time() - start_time

                logger.error(
                    f"Operation failed: {operation_name}",
                    extra={
                        "operation": operation_name,
                        "operation_id": operation_id,
                        "duration": duration,
                        "status": "error",
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    exc_info=True,
                )

                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = str(uuid.uuid4())
            logger = get_logger("operation_tracker")

            logger.info(
                f"Operation started: {operation_name}",
                extra={
                    "operation": operation_name,
                    "operation_id": operation_id,
                },
            )

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                logger.info(
                    f"Operation completed: {operation_name}",
                    extra={
                        "operation": operation_name,
                        "operation_id": operation_id,
                        "duration": duration,
                        "status": "success",
                    },
                )

                return result

            except Exception as e:
                duration = time.time() - start_time

                logger.error(
                    f"Operation failed: {operation_name}",
                    extra={
                        "operation": operation_name,
                        "operation_id": operation_id,
                        "duration": duration,
                        "status": "error",
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    exc_info=True,
                )

                raise

        # Return appropriate wrapper based on function type
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


@asynccontextmanager
async def track_async_operation(operation_name: str, **context):
    """Context manager for tracking async operations with additional context"""
    start_time = time.time()
    operation_id = str(uuid.uuid4())
    logger = get_logger("operation_tracker")

    logger.info(
        f"Async operation started: {operation_name}",
        extra={
            "operation": operation_name,
            "operation_id": operation_id,
            **context,
        },
    )

    try:
        yield operation_id

        duration = time.time() - start_time
        logger.info(
            f"Async operation completed: {operation_name}",
            extra={
                "operation": operation_name,
                "operation_id": operation_id,
                "duration": duration,
                "status": "success",
                **context,
            },
        )

    except Exception as e:
        duration = time.time() - start_time

        logger.error(
            f"Async operation failed: {operation_name}",
            extra={
                "operation": operation_name,
                "operation_id": operation_id,
                "duration": duration,
                "status": "error",
                "error_type": type(e).__name__,
                "error_message": str(e),
                **context,
            },
            exc_info=True,
        )

        raise


def get_performance_stats() -> Dict[str, Any]:
    """Get current performance statistics"""
    return metrics.get_stats()


def reset_metrics() -> None:
    """Reset all metrics (useful for testing)"""
    global metrics
    metrics = PerformanceMetrics()