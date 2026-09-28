"""Native Sigstore/Cosign bundle signing and verification.

Unlike the generic detached-signature adapter, this module preserves Cosign's
native bundle bytes so certificates, timestamps, and transparency-log evidence
remain available to independent verifiers.
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


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@dataclass(frozen=True)
class SigstoreBundleEvidence:
    """Non-lossy summary of evidence retained in a native Sigstore bundle."""

    media_type: str = ""
    verification_material: str = ""
    transparency_log_entries: int = 0
    timestamp_entries: int = 0
    raw_top_level_keys: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "media_type": self.media_type,
            "verification_material": self.verification_material,
            "transparency_log_entries": self.transparency_log_entries,
            "timestamp_entries": self.timestamp_entries,
            "raw_top_level_keys": list(self.raw_top_level_keys),
        }


@dataclass(frozen=True)
class SigstoreVerificationResult:
    """Normalized trust result while preserving the native bundle separately."""

    available: bool
    executed: bool
    cryptographically_valid: Optional[bool]
    trusted: bool
    identity: str = ""
    issuer: str = ""
    mode: str = ""
    cosign_version: str = ""
    evidence: SigstoreBundleEvidence = field(default_factory=SigstoreBundleEvidence)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": "sigstore",
            "signed": True,
            "available": self.available,
            "executed": self.executed,
            "cryptographically_valid": self.cryptographically_valid,
            "trusted": self.trusted,
            "identity": self.identity,
            "issuer": self.issuer,
            "mode": self.mode,
            "cosign_version": self.cosign_version,
            "evidence": self.evidence.to_dict(),
            "error": self.error,
        }


class SigstoreBundleInspector:
    """Inspect stable evidence categories without rewriting the native bundle."""

    @staticmethod
    def inspect(bundle_path: Path) -> SigstoreBundleEvidence:
        bundle_path = Path(bundle_path)
        try:
            payload = json.loads(bundle_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return SigstoreBundleEvidence()

        if not isinstance(payload, dict):
            return SigstoreBundleEvidence()

        verification = payload.get("verificationMaterial", {})
        if not isinstance(verification, dict):
            verification = {}

        if isinstance(verification.get("certificate"), dict):
            material = "certificate"
        elif isinstance(verification.get("publicKey"), dict):
            material = "public_key"
        elif isinstance(verification.get("x509CertificateChain"), dict):
            material = "certificate_chain"
        else:
            material = ""

        tlog_entries = verification.get("tlogEntries", [])
        if not isinstance(tlog_entries, list):
            tlog_entries = []

        timestamp_data = payload.get("verificationMaterial", {}).get(
            "timestampVerificationData",
            {},
        )
        if not isinstance(timestamp_data, dict):
            timestamp_data = {}
        timestamps = timestamp_data.get("rfc3161Timestamps", [])
        if not isinstance(timestamps, list):
            timestamps = []

        return SigstoreBundleEvidence(
            media_type=str(payload.get("mediaType", "")),
            verification_material=material,
            transparency_log_entries=len(tlog_entries),
            timestamp_entries=len(timestamps),
            raw_top_level_keys=sorted(str(key) for key in payload),
        )


class _CosignCommand:
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

        configured = os.environ.get("EBOOKAI_COSIGN_COMMAND", "").strip()
        if configured:
            parsed = shlex.split(configured)
            return parsed or None

        executable = shutil.which("cosign")
        return [executable] if executable else None

    def version(self) -> str:
        command = self.resolve_command()
        if not command:
            return ""
        try:
            completed = subprocess.run(
                [*command, "version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=min(self.timeout_seconds, 15),
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        if completed.returncode != 0:
            return ""
        for line in completed.stdout.splitlines():
            if "GitVersion" in line and ":" in line:
                return line.split(":", 1)[1].strip()
        return completed.stdout.strip().splitlines()[0] if completed.stdout.strip() else ""


class SigstoreBundleSigner(_CosignCommand):
    """Create a native Cosign bundle for the exact release manifest."""

    algorithm = "sigstore-bundle"

    def __init__(
        self,
        command: Optional[Sequence[str]] = None,
        *,
        key: Optional[str] = None,
        keyless: Optional[bool] = None,
        timeout_seconds: int = 120,
    ) -> None:
        super().__init__(command, timeout_seconds=timeout_seconds)
        self.key = key
        self.keyless = keyless

    def resolve_key(self) -> str:
        return (self.key or os.environ.get("EBOOKAI_SIGSTORE_SIGN_KEY", "")).strip()

    def is_keyless(self) -> bool:
        if self.keyless is not None:
            return self.keyless
        return _env_flag("EBOOKAI_SIGSTORE_KEYLESS")

    def available(self) -> bool:
        return bool(
            self.resolve_command()
            and (self.resolve_key() or self.is_keyless())
        )

    def identity_hint(self) -> str:
        return os.environ.get("EBOOKAI_SIGSTORE_IDENTITY_HINT", "").strip()

    def sign(self, payload_path: Path, bundle_path: Path) -> SigstoreBundleEvidence:
        payload_path = Path(payload_path)
        bundle_path = Path(bundle_path)
        if not payload_path.is_file():
            raise FileNotFoundError(payload_path)

        command = self.resolve_command()
        if not command:
            raise RuntimeError("Cosign is not installed or configured")

        key = self.resolve_key()
        if not key and not self.is_keyless():
            raise RuntimeError(
                "Sigstore signing requires EBOOKAI_SIGSTORE_SIGN_KEY or "
                "EBOOKAI_SIGSTORE_KEYLESS=true"
            )

        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        args = [
            *command,
            "sign-blob",
            "--yes",
            "--bundle",
            str(bundle_path),
        ]
        if key:
            args.extend(["--key", key])
        args.append(str(payload_path))

        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(detail or "Cosign sign-blob failed")
        if not bundle_path.is_file() or bundle_path.stat().st_size == 0:
            raise RuntimeError("Cosign did not produce a native Sigstore bundle")

        return SigstoreBundleInspector.inspect(bundle_path)


class SigstoreBundleVerifier(_CosignCommand):
    """Verify a native Cosign bundle under explicit identity/key trust policy."""

    def __init__(
        self,
        command: Optional[Sequence[str]] = None,
        *,
        key: Optional[str] = None,
        certificate_identity: Optional[str] = None,
        certificate_identity_regexp: Optional[str] = None,
        certificate_oidc_issuer: Optional[str] = None,
        certificate_oidc_issuer_regexp: Optional[str] = None,
        timeout_seconds: int = 120,
    ) -> None:
        super().__init__(command, timeout_seconds=timeout_seconds)
        self.key = key
        self.certificate_identity = certificate_identity
        self.certificate_identity_regexp = certificate_identity_regexp
        self.certificate_oidc_issuer = certificate_oidc_issuer
        self.certificate_oidc_issuer_regexp = certificate_oidc_issuer_regexp

    def _policy(self) -> Dict[str, str]:
        return {
            "key": (
                self.key
                or os.environ.get("EBOOKAI_SIGSTORE_VERIFY_KEY", "")
            ).strip(),
            "identity": (
                self.certificate_identity
                or os.environ.get("EBOOKAI_SIGSTORE_CERT_IDENTITY", "")
            ).strip(),
            "identity_regexp": (
                self.certificate_identity_regexp
                or os.environ.get("EBOOKAI_SIGSTORE_CERT_IDENTITY_REGEXP", "")
            ).strip(),
            "issuer": (
                self.certificate_oidc_issuer
                or os.environ.get("EBOOKAI_SIGSTORE_CERT_ISSUER", "")
            ).strip(),
            "issuer_regexp": (
                self.certificate_oidc_issuer_regexp
                or os.environ.get("EBOOKAI_SIGSTORE_CERT_ISSUER_REGEXP", "")
            ).strip(),
        }

    def verify(
        self,
        payload_path: Path,
        bundle_path: Path,
    ) -> SigstoreVerificationResult:
        payload_path = Path(payload_path)
        bundle_path = Path(bundle_path)
        evidence = SigstoreBundleInspector.inspect(bundle_path)
        command = self.resolve_command()
        if not command:
            return SigstoreVerificationResult(
                available=False,
                executed=False,
                cryptographically_valid=None,
                trusted=False,
                evidence=evidence,
                error="Cosign is not installed or configured",
            )

        policy = self._policy()
        key = policy["key"]
        identity = policy["identity"] or policy["identity_regexp"]
        issuer = policy["issuer"] or policy["issuer_regexp"]

        args = [
            *command,
            "verify-blob",
            str(payload_path),
            "--bundle",
            str(bundle_path),
        ]
        mode = ""
        if key:
            mode = "key"
            args.extend(["--key", key])
        else:
            mode = "keyless"
            if policy["identity"]:
                args.extend(["--certificate-identity", policy["identity"]])
            elif policy["identity_regexp"]:
                args.extend(
                    [
                        "--certificate-identity-regexp",
                        policy["identity_regexp"],
                    ]
                )
            else:
                return SigstoreVerificationResult(
                    available=True,
                    executed=False,
                    cryptographically_valid=None,
                    trusted=False,
                    mode=mode,
                    cosign_version=self.version(),
                    evidence=evidence,
                    error="Sigstore keyless verification requires certificate identity policy",
                )

            if policy["issuer"]:
                args.extend(["--certificate-oidc-issuer", policy["issuer"]])
            elif policy["issuer_regexp"]:
                args.extend(
                    [
                        "--certificate-oidc-issuer-regexp",
                        policy["issuer_regexp"],
                    ]
                )
            else:
                return SigstoreVerificationResult(
                    available=True,
                    executed=False,
                    cryptographically_valid=None,
                    trusted=False,
                    identity=identity,
                    mode=mode,
                    cosign_version=self.version(),
                    evidence=evidence,
                    error="Sigstore keyless verification requires OIDC issuer policy",
                )

        try:
            completed = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return SigstoreVerificationResult(
                available=True,
                executed=False,
                cryptographically_valid=None,
                trusted=False,
                identity=identity,
                issuer=issuer,
                mode=mode,
                cosign_version=self.version(),
                evidence=evidence,
                error=str(exc),
            )

        valid = completed.returncode == 0
        detail = ""
        if not valid:
            detail = completed.stderr.strip() or completed.stdout.strip()
            detail = detail or "Cosign verify-blob failed"

        return SigstoreVerificationResult(
            available=True,
            executed=True,
            cryptographically_valid=valid,
            trusted=valid,
            identity=identity,
            issuer=issuer,
            mode=mode,
            cosign_version=self.version(),
            evidence=evidence,
            error=detail,
        )
