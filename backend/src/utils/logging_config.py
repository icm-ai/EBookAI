"""
Centralized logging configuration for EBookAI.
"""
import json
import logging
import logging.config
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "task_id"):
            log_data["task_id"] = record.task_id
        if hasattr(record, "file_path"):
            log_data["file_path"] = record.file_path
        if hasattr(record, "operation"):
            log_data["operation"] = record.operation
        if hasattr(record, "duration"):
            log_data["duration"] = record.duration

        return json.dumps(log_data, ensure_ascii=False)


def get_logging_config(
    log_level: str = "INFO", log_dir: str = "logs"
) -> Dict[str, Any]:
    """Get logging configuration dictionary"""

    # Ensure log directory exists
    Path(log_dir).mkdir(exist_ok=True)

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": JSONFormatter,
            },
            "detailed": {
                "format": "{asctime} - {name} - {levelname} - {module}:{funcName}:{lineno} - {message}",
                "style": "{",
            },
            "simple": {
                "format": "{levelname} - {name} - {message}",
                "style": "{",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "detailed",
                "stream": sys.stdout,
            },
            "file_json": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": log_level,
                "formatter": "json",
                "filename": f"{log_dir}/app.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "json",
                "filename": f"{log_dir}/error.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
            "conversion_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "json",
                "filename": f"{log_dir}/conversion.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
            "ai_service_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "json",
                "filename": f"{log_dir}/ai_service.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
        },
        "loggers": {
            "ebook_ai": {
                "level": log_level,
                "handlers": ["console", "file_json"],
                "propagate": False,
            },
            "ebook_ai.conversion": {
                "level": log_level,
                "handlers": ["console", "conversion_file"],
                "propagate": False,
            },
            "ebook_ai.ai_service": {
                "level": log_level,
                "handlers": ["console", "ai_service_file"],
                "propagate": False,
            },
            "ebook_ai.error": {
                "level": "ERROR",
                "handlers": ["console", "error_file"],
                "propagate": False,
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "fastapi": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["console", "file_json"],
        },
    }


def setup_logging(log_level: str = "INFO", log_dir: str = "logs") -> None:
    """Setup logging configuration"""
    config = get_logging_config(log_level, log_dir)
    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name"""
    return logging.getLogger(f"ebook_ai.{name}")


def log_operation_start(logger: logging.Logger, operation: str, **kwargs) -> None:
    """Log the start of an operation with context"""
    logger.info(f"Starting {operation}", extra={"operation": operation, **kwargs})


def log_operation_end(
    logger: logging.Logger, operation: str, duration: float, **kwargs
) -> None:
    """Log the end of an operation with duration"""
    logger.info(
        f"Completed {operation} in {duration:.2f}s",
        extra={"operation": operation, "duration": duration, **kwargs},
    )


def log_operation_error(
    logger: logging.Logger, operation: str, error: Exception, **kwargs
) -> None:
    """Log an operation error with context"""
    logger.error(
        f"Failed {operation}: {str(error)}",
        extra={"operation": operation, **kwargs},
        exc_info=True,
    )
