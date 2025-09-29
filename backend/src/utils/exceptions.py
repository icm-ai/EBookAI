"""
Custom exception classes for the EBookAI application.
"""
from typing import Any, Dict, Optional


class EBookAIException(Exception):
    """Base exception for all EBookAI errors"""

    def __init__(
        self,
        message: str,
        error_code: str = "GENERAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.original_error = original_error
        super().__init__(self.message)


class ValidationError(EBookAIException):
    """Raised when input validation fails"""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        error_details = details or {}
        if field:
            error_details["field"] = field
        if value is not None:
            error_details["value"] = value

        super().__init__(
            message=message, error_code="VALIDATION_ERROR", details=error_details
        )


class FileProcessingError(EBookAIException):
    """Raised when file processing fails"""

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        file_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        error_details = details or {}
        if file_path:
            error_details["file_path"] = file_path
        if file_type:
            error_details["file_type"] = file_type

        super().__init__(
            message=message,
            error_code="FILE_PROCESSING_ERROR",
            details=error_details,
            original_error=original_error,
        )


class ConversionError(EBookAIException):
    """Raised when format conversion fails"""

    def __init__(
        self,
        message: str,
        source_format: Optional[str] = None,
        target_format: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        error_details = details or {}
        if source_format:
            error_details["source_format"] = source_format
        if target_format:
            error_details["target_format"] = target_format

        super().__init__(
            message=message,
            error_code="CONVERSION_ERROR",
            details=error_details,
            original_error=original_error,
        )


class ConversionTimeoutError(ConversionError):
    """Raised when conversion times out"""

    def __init__(
        self,
        timeout_seconds: int,
        source_format: Optional[str] = None,
        target_format: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        error_details = details or {}
        error_details["timeout_seconds"] = timeout_seconds

        super().__init__(
            message=f"Conversion timed out after {timeout_seconds} seconds",
            source_format=source_format,
            target_format=target_format,
            details=error_details,
        )
        self.error_code = "CONVERSION_TIMEOUT"


class AIServiceError(EBookAIException):
    """Raised when AI service calls fail"""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        api_error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        error_details = details or {}
        if provider:
            error_details["provider"] = provider
        if api_error_code:
            error_details["api_error_code"] = api_error_code

        super().__init__(
            message=message,
            error_code="AI_SERVICE_ERROR",
            details=error_details,
            original_error=original_error,
        )


class ConfigurationError(EBookAIException):
    """Raised when configuration is invalid or missing"""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        error_details = details or {}
        if config_key:
            error_details["config_key"] = config_key

        super().__init__(
            message=message, error_code="CONFIGURATION_ERROR", details=error_details
        )


class ResourceNotFoundError(EBookAIException):
    """Raised when requested resource is not found"""

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        error_details = details or {}
        if resource_type:
            error_details["resource_type"] = resource_type
        if resource_id:
            error_details["resource_id"] = resource_id

        super().__init__(
            message=message, error_code="RESOURCE_NOT_FOUND", details=error_details
        )


class SecurityError(EBookAIException):
    """Raised when security violations occur"""

    def __init__(
        self,
        message: str,
        violation_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        error_details = details or {}
        if violation_type:
            error_details["violation_type"] = violation_type

        super().__init__(
            message=message, error_code="SECURITY_ERROR", details=error_details
        )
