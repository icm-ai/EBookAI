"""Standalone release-bundle verification without server/review dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Sequence

from book.publication.attestation import ExternalManifestVerifier
from book.publication.release import ReleasePipeline
from book.publication.sigstore import SigstoreBundleVerifier


@dataclass(frozen=True)
class ReleaseVerificationPolicy:
    """Portable trust requirements for verifying a release bundle."""

    require_signature: bool = False
    trusted_key_ids: Sequence[str] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "require_signature": self.require_signature,
            "trusted_key_ids": list(self.trusted_key_ids),
        }


class StandaloneReleaseVerifier:
    """Verify bundle integrity/authenticity without FastAPI or review-session state."""

    def __init__(
        self,
        *,
        external_verifier: ExternalManifestVerifier | None = None,
        sigstore_verifier: SigstoreBundleVerifier | None = None,
    ) -> None:
        self.external_verifier = external_verifier or ExternalManifestVerifier()
        self.sigstore_verifier = sigstore_verifier or SigstoreBundleVerifier()

    def verify(
        self,
        bundle_path: Path,
        *,
        policy: ReleaseVerificationPolicy | None = None,
    ) -> Dict[str, Any]:
        policy = policy or ReleaseVerificationPolicy()
        pipeline = ReleasePipeline(
            verifier=self.external_verifier,
            sigstore_verifier=self.sigstore_verifier,
        )
        result = pipeline.verify_bundle(
            Path(bundle_path),
            require_signature=policy.require_signature,
            trusted_key_ids=tuple(policy.trusted_key_ids),
        )
        result["policy"] = policy.to_dict()
        return result
