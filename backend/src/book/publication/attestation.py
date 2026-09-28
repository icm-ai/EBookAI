"""Detached release-manifest signing and trust verification."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class ReleaseAttestation:
    """Detached signature metadata. Private key material is never persisted."""

    algorithm: str
    key_id: str
    signature: str
    payload_sha256: str
    signer: str = "external"

    def to_dict(self) -> Dict[str, str]:
        return {
            "schema_version": "0.1",
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "signature": self.signature,
            "payload_sha256": self.payload_sha256,
            "signer": self.signer,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ReleaseAttestation":
        return cls(
            algorithm=str(value["algorithm"]),
            key_id=str(value["key_id"]),
            signature=str(value["signature"]),
            payload_sha256=str(value["payload_sha256"]),
            signer=str(value.get("signer", "external")),
        )


@dataclass(frozen=True)
class SignatureVerification:
    """Trust-policy result for one detached release attestation."""

    signed: bool
    cryptographically_valid: Optional[bool]
    trusted: bool
    key_id: str = ""
    algorithm: str = ""
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signed": self.signed,
            "cryptographically_valid": self.cryptographically_valid,
            "trusted": self.trusted,
            "key_id": self.key_id,
            "algorithm": self.algorithm,
            "error": self.error,
        }


class ExternalManifestSigner:
    """Sign canonical manifest bytes using a caller-owned external command.

    Protocol: command receives payload bytes on stdin and must write raw signature
    bytes to stdout. The command/key reference itself is never persisted.
    """

    def __init__(
        self,
        command: Optional[Sequence[str]] = None,
        *,
        key_id: Optional[str] = None,
        algorithm: str = "external",
        timeout_seconds: int = 30,
    ) -> None:
        self.command = list(command) if command else None
        self.key_id = key_id
        self.algorithm = algorithm
        self.timeout_seconds = timeout_seconds

    def resolve_command(self) -> Optional[List[str]]:
        if self.command:
            return list(self.command)
        configured = os.environ.get("EBOOKAI_SIGN_COMMAND", "").strip()
        return shlex.split(configured) if configured else None

    def available(self) -> bool:
        return bool(self.resolve_command() and self.resolve_key_id())

    def resolve_key_id(self) -> str:
        return (self.key_id or os.environ.get("EBOOKAI_SIGN_KEY_ID", "")).strip()

    def sign(self, payload: bytes) -> ReleaseAttestation:
        command = self.resolve_command()
        key_id = self.resolve_key_id()
        if not command or not key_id:
            raise RuntimeError("Release signing command/key id is not configured")

        completed = subprocess.run(
            command,
            input=payload,
            capture_output=True,
            check=False,
            timeout=self.timeout_seconds,
        )
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(detail or "External release signer failed")
        if not completed.stdout:
            raise RuntimeError("External release signer returned an empty signature")

        return ReleaseAttestation(
            algorithm=self.algorithm,
            key_id=key_id,
            signature=base64.b64encode(completed.stdout).decode("ascii"),
            payload_sha256=hashlib.sha256(payload).hexdigest(),
        )


class ExternalManifestVerifier:
    """Verify detached signatures with a caller-owned external command.

    Protocol: command is invoked as COMMAND <payload-path> <signature-path> and
    returns zero only for a cryptographically valid signature. Public key/trust
    material stays outside the release bundle.
    """

    def __init__(
        self,
        command: Optional[Sequence[str]] = None,
        *,
        timeout_seconds: int = 30,
    ) -> None:
        self.command = list(command) if command else None
        self.timeout_seconds = timeout_seconds

    def resolve_command(self) -> Optional[List[str]]:
        if self.command:
            return list(self.command)
        configured = os.environ.get("EBOOKAI_VERIFY_COMMAND", "").strip()
        return shlex.split(configured) if configured else None

    def verify(
        self,
        payload: bytes,
        attestation: ReleaseAttestation,
        *,
        trusted_key_ids: Sequence[str] = (),
    ) -> SignatureVerification:
        if hashlib.sha256(payload).hexdigest() != attestation.payload_sha256:
            return SignatureVerification(
                signed=True,
                cryptographically_valid=False,
                trusted=False,
                key_id=attestation.key_id,
                algorithm=attestation.algorithm,
                error="Attested payload hash does not match manifest bytes",
            )

        command = self.resolve_command()
        if not command:
            return SignatureVerification(
                signed=True,
                cryptographically_valid=None,
                trusted=False,
                key_id=attestation.key_id,
                algorithm=attestation.algorithm,
                error="Signature verifier is not configured",
            )

        import tempfile

        try:
            signature = base64.b64decode(attestation.signature, validate=True)
        except ValueError:
            return SignatureVerification(
                signed=True,
                cryptographically_valid=False,
                trusted=False,
                key_id=attestation.key_id,
                algorithm=attestation.algorithm,
                error="Attestation signature is not valid base64",
            )

        with tempfile.TemporaryDirectory(prefix="ebookai-verify-") as temporary:
            root = Path(temporary)
            payload_path = root / "manifest.json"
            signature_path = root / "manifest.sig"
            payload_path.write_bytes(payload)
            signature_path.write_bytes(signature)
            completed = subprocess.run(
                [*command, str(payload_path), str(signature_path)],
                capture_output=True,
                check=False,
                timeout=self.timeout_seconds,
            )

        valid = completed.returncode == 0
        trusted = valid and (
            not trusted_key_ids or attestation.key_id in set(trusted_key_ids)
        )
        error = ""
        if not valid:
            error = completed.stderr.decode("utf-8", errors="replace").strip()
            error = error or "Detached signature verification failed"
        elif trusted_key_ids and not trusted:
            error = f"Signing key is not trusted: {attestation.key_id}"

        return SignatureVerification(
            signed=True,
            cryptographically_valid=valid,
            trusted=trusted,
            key_id=attestation.key_id,
            algorithm=attestation.algorithm,
            error=error,
        )


def load_trusted_key_ids(value: Optional[str] = None) -> List[str]:
    """Load an allowlist of non-secret public key identifiers."""

    raw = value if value is not None else os.environ.get("EBOOKAI_TRUSTED_KEY_IDS", "")
    return sorted({item.strip() for item in raw.split(",") if item.strip()})
