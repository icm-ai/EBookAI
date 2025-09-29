"""
User-friendly error messages and response formatting.
"""
from typing import Dict, Any, Optional
from enum import Enum

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


class MessageType(Enum):
    """Types of user messages"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    SUCCESS = "success"


class UserMessageFormatter:
    """Format error messages for user-friendly display"""

    # Error code to user-friendly message mapping
    ERROR_MESSAGES = {
        # File-related errors
        "FILE_NOT_FOUND": {
            "title": "文件未找到",
            "message": "您指定的文件不存在，请检查文件路径是否正确。",
            "suggestions": [
                "确认文件路径拼写正确",
                "检查文件是否已被移动或删除",
                "尝试重新上传文件"
            ]
        },
        "FILE_PROCESSING_ERROR": {
            "title": "文件处理失败",
            "message": "处理您的文件时出现问题，可能是文件格式不受支持或文件已损坏。",
            "suggestions": [
                "确认文件格式是否受支持（EPUB、PDF、TXT）",
                "检查文件是否完整且未损坏",
                "尝试使用其他文件"
            ]
        },

        # Validation errors
        "VALIDATION_ERROR": {
            "title": "输入验证失败",
            "message": "您提供的信息格式不正确，请检查输入内容。",
            "suggestions": [
                "检查必填字段是否完整",
                "确认数据格式符合要求",
                "参考API文档中的示例"
            ]
        },

        # Conversion errors
        "CONVERSION_ERROR": {
            "title": "格式转换失败",
            "message": "无法将文件转换为目标格式，请检查文件内容和格式要求。",
            "suggestions": [
                "确认源文件格式正确",
                "检查目标格式是否受支持",
                "如果是大文件，请稍后重试"
            ]
        },
        "CONVERSION_TIMEOUT": {
            "title": "转换超时",
            "message": "文件转换时间过长，可能是文件太大或服务器繁忙。",
            "suggestions": [
                "尝试转换较小的文件",
                "稍后重试",
                "联系技术支持获取帮助"
            ]
        },

        # AI service errors
        "AI_SERVICE_ERROR": {
            "title": "AI服务暂时不可用",
            "message": "AI处理服务遇到问题，请稍后再试。",
            "suggestions": [
                "等待几分钟后重试",
                "检查网络连接",
                "如问题持续存在，请联系支持团队"
            ]
        },

        # Configuration errors
        "CONFIGURATION_ERROR": {
            "title": "系统配置错误",
            "message": "服务配置有误，请联系管理员。",
            "suggestions": [
                "联系系统管理员",
                "稍后重试",
                "查看系统状态页面"
            ]
        },

        # Security errors
        "SECURITY_ERROR": {
            "title": "访问被拒绝",
            "message": "您没有权限执行此操作。",
            "suggestions": [
                "检查您的访问权限",
                "联系管理员获取权限",
                "确认您已正确登录"
            ]
        },

        # Generic errors
        "INTERNAL_ERROR": {
            "title": "系统内部错误",
            "message": "系统遇到了意外错误，我们正在调查此问题。",
            "suggestions": [
                "稍后重试",
                "如问题持续存在，请联系技术支持",
                "记录错误ID以便技术支持定位问题"
            ]
        },
        "HTTP_ERROR": {
            "title": "请求错误",
            "message": "您的请求格式不正确或包含无效数据。",
            "suggestions": [
                "检查请求参数",
                "参考API文档",
                "确认请求方法正确"
            ]
        }
    }

    @classmethod
    def format_error_response(
        cls,
        error: Exception,
        request_id: str = None,
        include_technical_details: bool = False
    ) -> Dict[str, Any]:
        """Format error for user-friendly response"""

        # Get error code and details
        if isinstance(error, EBookAIException):
            error_code = error.error_code
            details = error.details or {}
            original_message = error.message
        else:
            # Map standard exceptions to error codes
            error_code = cls._map_exception_to_code(error)
            details = {}
            original_message = str(error)

        # Get user-friendly message template
        message_template = cls.ERROR_MESSAGES.get(error_code, cls.ERROR_MESSAGES["INTERNAL_ERROR"])

        # Build user-friendly response
        user_response = {
            "error": {
                "type": "error",
                "code": error_code,
                "title": message_template["title"],
                "message": message_template["message"],
                "suggestions": message_template["suggestions"],
                "request_id": request_id,
            }
        }

        # Add specific details based on error type
        if isinstance(error, ValidationError):
            user_response["error"]["field"] = details.get("field")
            user_response["error"]["value"] = details.get("value")

        elif isinstance(error, ConversionError):
            user_response["error"]["source_format"] = details.get("source_format")
            user_response["error"]["target_format"] = details.get("target_format")

        elif isinstance(error, ConversionTimeoutError):
            timeout = details.get("timeout_seconds", 300)
            user_response["error"]["message"] = f"文件转换超时（{timeout}秒），请尝试较小的文件或稍后重试。"

        elif isinstance(error, FileProcessingError):
            user_response["error"]["file_type"] = details.get("file_type")

        elif isinstance(error, AIServiceError):
            provider = details.get("provider")
            if provider:
                user_response["error"]["message"] = f"{provider} AI服务暂时不可用，请稍后再试。"

        # Add technical details if requested (for debugging)
        if include_technical_details:
            user_response["error"]["technical"] = {
                "original_message": original_message,
                "exception_type": type(error).__name__,
                "details": details,
            }

        return user_response

    @classmethod
    def _map_exception_to_code(cls, error: Exception) -> str:
        """Map standard exceptions to error codes"""
        if isinstance(error, FileNotFoundError):
            return "FILE_NOT_FOUND"
        elif isinstance(error, PermissionError):
            return "SECURITY_ERROR"
        elif isinstance(error, ValueError):
            return "VALIDATION_ERROR"
        elif isinstance(error, TimeoutError):
            return "CONVERSION_TIMEOUT"
        else:
            return "INTERNAL_ERROR"

    @classmethod
    def format_success_response(
        cls,
        data: Any,
        message: str = "操作成功完成",
        message_type: MessageType = MessageType.SUCCESS
    ) -> Dict[str, Any]:
        """Format successful response with user-friendly message"""
        return {
            "success": True,
            "message": {
                "type": message_type.value,
                "text": message
            },
            "data": data
        }

    @classmethod
    def format_info_response(
        cls,
        message: str,
        data: Any = None,
        message_type: MessageType = MessageType.INFO
    ) -> Dict[str, Any]:
        """Format informational response"""
        response = {
            "message": {
                "type": message_type.value,
                "text": message
            }
        }

        if data is not None:
            response["data"] = data

        return response


def create_user_friendly_error(
    error: Exception,
    request_id: str = None,
    include_technical: bool = False
) -> Dict[str, Any]:
    """Convenience function to create user-friendly error response"""
    return UserMessageFormatter.format_error_response(
        error=error,
        request_id=request_id,
        include_technical_details=include_technical
    )


def create_success_message(
    data: Any,
    message: str = "操作成功完成"
) -> Dict[str, Any]:
    """Convenience function to create success response"""
    return UserMessageFormatter.format_success_response(
        data=data,
        message=message
    )


# Pre-defined common messages
COMMON_MESSAGES = {
    "conversion_started": "文件转换已开始，请稍候...",
    "conversion_completed": "文件转换成功完成！",
    "file_uploaded": "文件上传成功",
    "ai_processing_started": "AI处理已开始，这可能需要几分钟时间...",
    "ai_processing_completed": "AI处理完成",
}