"""Optional external EPUBCheck integration.

The runner is intentionally process-based so EBookAI does not vendor EPUBCheck
or its Java dependencies. It consumes EPUBCheck's JSON report and normalizes
only stable validation data for release manifests.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class EpubCheckMessage:
    """Normalized EPUBCheck message."""

    id: str
    severity: str
    message: str
    locations: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity,
            "message": self.message,
            "locations": self.locations,
        }


@dataclass(frozen=True)
class EpubCheckResult:
    """Stable external-validation result suitable for persistence and hashing."""

    available: bool
    executed: bool
    valid: Optional[bool]
    version: str = ""
    exit_code: Optional[int] = None
    counts: Dict[str, int] = field(default_factory=dict)
    messages: List[EpubCheckMessage] = field(default_factory=list)
    error: str = ""

    @property
    def status(self) -> str:
        if not self.available:
            return "unavailable"
        if not self.executed:
            return "error"
        return "passed" if self.valid else "failed"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "executed": self.executed,
            "valid": self.valid,
            "status": self.status,
            "version": self.version,
            "exit_code": self.exit_code,
            "counts": dict(self.counts),
            "messages": [message.to_dict() for message in self.messages],
            "error": self.error,
        }


class ExternalEpubCheckRunner:
    """Discover and execute an EPUBCheck CLI without shell interpolation."""

    def __init__(
        self,
        command: Optional[Sequence[str]] = None,
        *,
        timeout_seconds: int = 120,
    ) -> None:
        self.command = list(command) if command else None
        self.timeout_seconds = timeout_seconds

    def resolve_command(self) -> Optional[List[str]]:
        if self.command:
            return list(self.command)

        configured = os.environ.get("EPUBCHECK_COMMAND", "").strip()
        if configured:
            parsed = shlex.split(configured)
            return parsed or None

        executable = shutil.which("epubcheck")
        if executable:
            return [executable]

        jar = os.environ.get("EPUBCHECK_JAR", "").strip()
        java = shutil.which("java")
        if jar and java and Path(jar).is_file():
            return [java, "-jar", jar]

        return None

    def run(self, epub_path: Path) -> EpubCheckResult:
        epub_path = Path(epub_path)
        if not epub_path.is_file():
            raise FileNotFoundError(epub_path)

        command = self.resolve_command()
        if not command:
            return EpubCheckResult(
                available=False,
                executed=False,
                valid=None,
                error="EPUBCheck executable or jar was not found",
            )

        args = [*command, "--json", "-", str(epub_path)]
        try:
            completed = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return EpubCheckResult(
                available=True,
                executed=False,
                valid=None,
                error=str(exc),
            )

        try:
            payload = self._parse_json_stdout(completed.stdout)
        except ValueError as exc:
            detail = completed.stderr.strip()
            message = str(exc)
            if detail:
                message = f"{message}: {detail}"
            return EpubCheckResult(
                available=True,
                executed=False,
                valid=None,
                exit_code=completed.returncode,
                error=message,
            )

        checker = payload.get("checker", {})
        if not isinstance(checker, dict):
            checker = {}

        messages = self._messages(payload.get("messages", []))
        counts = {
            "fatal": self._count(checker, "nFatal", messages, "FATAL"),
            "error": self._count(checker, "nError", messages, "ERROR"),
            "warning": self._count(checker, "nWarning", messages, "WARNING"),
            "usage": self._count(checker, "nUsage", messages, "USAGE"),
            "info": self._count(checker, "nInfo", messages, "INFO"),
        }
        valid = (
            completed.returncode == 0
            and counts["fatal"] == 0
            and counts["error"] == 0
        )
        return EpubCheckResult(
            available=True,
            executed=True,
            valid=valid,
            version=str(checker.get("checkerVersion", "")),
            exit_code=completed.returncode,
            counts=counts,
            messages=messages,
        )

    @staticmethod
    def _parse_json_stdout(stdout: str) -> Dict[str, Any]:
        text = stdout.strip()
        if not text:
            raise ValueError("EPUBCheck produced no JSON report")

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("EPUBCheck output did not contain a JSON object")
            try:
                payload = json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                raise ValueError("EPUBCheck JSON report could not be parsed") from exc

        if not isinstance(payload, dict):
            raise ValueError("EPUBCheck JSON report root must be an object")
        return payload

    @staticmethod
    def _messages(value: Any) -> List[EpubCheckMessage]:
        if not isinstance(value, list):
            return []

        result: List[EpubCheckMessage] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            locations: List[Dict[str, Any]] = []
            raw_locations = item.get("locations", [])
            if isinstance(raw_locations, list):
                for location in raw_locations:
                    if not isinstance(location, dict):
                        continue
                    locations.append(
                        {
                            "path": str(location.get("path", "")),
                            "line": int(location.get("line", -1) or -1),
                            "column": int(location.get("column", -1) or -1),
                            "context": location.get("context"),
                        }
                    )
            result.append(
                EpubCheckMessage(
                    id=str(item.get("ID", "")),
                    severity=str(item.get("severity", "")).upper(),
                    message=str(item.get("message", "")),
                    locations=locations,
                )
            )
        return result

    @staticmethod
    def _count(
        checker: Dict[str, Any],
        key: str,
        messages: List[EpubCheckMessage],
        severity: str,
    ) -> int:
        value = checker.get(key)
        if isinstance(value, int):
            return value
        return sum(1 for message in messages if message.severity == severity)
