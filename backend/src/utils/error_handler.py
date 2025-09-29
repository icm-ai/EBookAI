"""
Global error handler for FastAPI application.
"""
import traceback
import uuid
from typing import Union

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_503_SERVICE_UNAVAILABLE,
)

from utils.exceptions import (
    EBookAIException,
    ValidationError,
    FileProcessingError,
    ConversionError,
    ConversionTimeoutError,
    AIServiceError,
    ConfigurationError,
    ResourceNotFoundError,
    SecurityError,
)
from utils.logging_config import get_logger
from utils.user_messages import create_user_friendly_error

logger = get_logger("error")


class ErrorResponse:
    """Standardized error response format"""

    def __init__(
        self,
        error_code: str,
        message: str,
        details: dict = None,
        request_id: str = None,
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.request_id = request_id or str(uuid.uuid4())

    def to_dict(self) -> dict:
        response = {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "request_id": self.request_id,
            }
        }
        if self.details:
            response["error"]["details"] = self.details
        return response


def get_http_status_from_error(error: Exception) -> int:
    """Map exceptions to HTTP status codes"""
    if isinstance(error, ValidationError):
        return HTTP_422_UNPROCESSABLE_ENTITY
    elif isinstance(error, ResourceNotFoundError):
        return HTTP_404_NOT_FOUND
    elif isinstance(error, SecurityError):
        return HTTP_403_FORBIDDEN
    elif isinstance(error, FileProcessingError):
        return HTTP_400_BAD_REQUEST
    elif isinstance(error, ConversionTimeoutError):
        return HTTP_503_SERVICE_UNAVAILABLE
    elif isinstance(error, (ConversionError, AIServiceError)):
        return HTTP_500_INTERNAL_SERVER_ERROR
    elif isinstance(error, ConfigurationError):
        return HTTP_500_INTERNAL_SERVER_ERROR
    elif isinstance(error, HTTPException):
        return error.status_code
    else:
        return HTTP_500_INTERNAL_SERVER_ERROR


def create_error_response(
    error: Exception, request_id: str = None
) -> tuple[JSONResponse, int]:
    """Create standardized error response"""
    request_id = request_id or str(uuid.uuid4())

    if isinstance(error, EBookAIException):
        # Handle custom exceptions
        error_response = ErrorResponse(
            error_code=error.error_code,
            message=error.message,
            details=error.details,
            request_id=request_id,
        )
        status_code = get_http_status_from_error(error)

        # Log the error with context
        logger.error(
            f"Application error: {error.message}",
            extra={
                "request_id": request_id,
                "error_code": error.error_code,
                "details": error.details,
                "operation": getattr(error, "operation", "unknown"),
            },
            exc_info=error.original_error if error.original_error else True,
        )

    elif isinstance(error, HTTPException):
        # Handle FastAPI HTTP exceptions
        error_response = ErrorResponse(
            error_code="HTTP_ERROR",
            message=error.detail,
            request_id=request_id,
        )
        status_code = error.status_code

        logger.warning(
            f"HTTP error: {error.detail}",
            extra={"request_id": request_id, "status_code": error.status_code},
        )

    elif isinstance(error, ValueError):
        # Handle validation errors
        error_response = ErrorResponse(
            error_code="VALIDATION_ERROR",
            message=str(error),
            request_id=request_id,
        )
        status_code = HTTP_400_BAD_REQUEST

        logger.warning(
            f"Validation error: {str(error)}",
            extra={"request_id": request_id},
        )

    elif isinstance(error, FileNotFoundError):
        # Handle file not found errors
        error_response = ErrorResponse(
            error_code="FILE_NOT_FOUND",
            message="Requested file was not found",
            details={"original_error": str(error)},
            request_id=request_id,
        )
        status_code = HTTP_404_NOT_FOUND

        logger.warning(
            f"File not found: {str(error)}",
            extra={"request_id": request_id},
        )

    elif isinstance(error, PermissionError):
        # Handle permission errors
        error_response = ErrorResponse(
            error_code="PERMISSION_DENIED",
            message="Access denied",
            request_id=request_id,
        )
        status_code = HTTP_403_FORBIDDEN

        logger.warning(
            f"Permission denied: {str(error)}",
            extra={"request_id": request_id},
        )

    else:
        # Handle unexpected errors
        error_response = ErrorResponse(
            error_code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            details={"type": type(error).__name__} if error else {},
            request_id=request_id,
        )
        status_code = HTTP_500_INTERNAL_SERVER_ERROR

        logger.error(
            f"Unexpected error: {str(error)}",
            extra={
                "request_id": request_id,
                "error_type": type(error).__name__,
                "traceback": traceback.format_exc(),
            },
            exc_info=True,
        )

    # Create user-friendly response
    user_friendly_response = create_user_friendly_error(
        error=error,
        request_id=request_id,
        include_technical=False  # Set to True in development
    )

    return JSONResponse(
        status_code=status_code,
        content=user_friendly_response,
    ), status_code


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for FastAPI"""
    request_id = str(uuid.uuid4())

    # Add request context to logs
    logger.error(
        f"Unhandled exception in {request.method} {request.url}",
        extra={
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "client": request.client.host if request.client else "unknown",
        },
    )

    response, _ = create_error_response(exc, request_id)
    return response


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions"""
    request_id = str(uuid.uuid4())

    logger.warning(
        f"HTTP exception in {request.method} {request.url}: {exc.detail}",
        extra={
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "status_code": exc.status_code,
        },
    )

    response, _ = create_error_response(exc, request_id)
    return response


def handle_service_error(
    operation: str, error: Exception, **context
) -> EBookAIException:
    """Convert service-level exceptions to application exceptions"""
    request_id = context.get("request_id", str(uuid.uuid4()))

    if isinstance(error, EBookAIException):
        return error

    elif isinstance(error, FileNotFoundError):
        return ResourceNotFoundError(
            message="Requested file was not found",
            resource_type="file",
            resource_id=context.get("file_path"),
            details={"operation": operation, "original_error": str(error)},
        )

    elif isinstance(error, PermissionError):
        return SecurityError(
            message="Access denied",
            violation_type="file_access",
            details={"operation": operation, "original_error": str(error)},
        )

    elif isinstance(error, ValueError):
        return ValidationError(
            message=str(error),
            details={"operation": operation},
        )

    elif "timeout" in str(error).lower():
        return ConversionTimeoutError(
            timeout_seconds=context.get("timeout", 300),
            source_format=context.get("source_format"),
            target_format=context.get("target_format"),
            details={"operation": operation, "original_error": str(error)},
        )

    else:
        # Generic error handling
        if "conversion" in operation.lower():
            return ConversionError(
                message=f"Conversion failed: {str(error)}",
                source_format=context.get("source_format"),
                target_format=context.get("target_format"),
                details={"operation": operation},
                original_error=error,
            )
        elif "ai" in operation.lower():
            return AIServiceError(
                message=f"AI service error: {str(error)}",
                provider=context.get("provider"),
                details={"operation": operation},
                original_error=error,
            )
        else:
            return EBookAIException(
                message=f"Operation failed: {str(error)}",
                error_code="OPERATION_ERROR",
                details={"operation": operation},
                original_error=error,
            )