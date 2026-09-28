"""Command-line verifier for EBookAI release bundles.

Example:
    PYTHONPATH=backend/src python -m book.publication.verify_cli \
        book.release.zip --json
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Optional, Sequence

from book.publication.attestation import ExternalManifestVerifier
from book.publication.sigstore import SigstoreBundleVerifier
from book.publication.verification import (
    ReleaseVerificationPolicy,
    StandaloneReleaseVerifier,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ebookai-verify",
        description=(
            "Verify EBookAI release integrity, detached signatures, "
            "and native Sigstore bundles."
        ),
    )
    parser.add_argument("bundle", type=Path, help="Path to release-bundle.zip")
    parser.add_argument(
        "--require-signature",
        action="store_true",
        help="Reject unsigned releases even when the manifest allows them.",
    )
    parser.add_argument(
        "--trusted-key-id",
        action="append",
        default=[],
        help="Trusted generic external-signature key id; repeat as needed.",
    )
    parser.add_argument(
        "--verify-command",
        help=(
            "Generic detached-signature verification command. "
            "Equivalent to EBOOKAI_VERIFY_COMMAND."
        ),
    )
    parser.add_argument(
        "--cosign",
        help="Cosign executable/command; defaults to EBOOKAI_COSIGN_COMMAND or PATH.",
    )
    parser.add_argument(
        "--sigstore-key",
        help="Public key/KMS URI for key-based Sigstore verification.",
    )
    parser.add_argument(
        "--certificate-identity",
        help="Expected identity for keyless Sigstore verification.",
    )
    parser.add_argument(
        "--certificate-identity-regexp",
        help="Expected identity regexp for keyless Sigstore verification.",
    )
    parser.add_argument(
        "--certificate-oidc-issuer",
        help="Expected OIDC issuer for keyless Sigstore verification.",
    )
    parser.add_argument(
        "--certificate-oidc-issuer-regexp",
        help="Expected OIDC issuer regexp for keyless Sigstore verification.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit machine-readable JSON.",
    )
    return parser


def _command(value: Optional[str]) -> Optional[Sequence[str]]:
    if not value:
        return None
    parsed = shlex.split(value)
    if not parsed:
        raise ValueError("Command must not be empty")
    return parsed


def _human(result: dict) -> str:
    lines = [
        f"Release: {result.get('release_id') or 'unknown'}",
        f"Valid: {'yes' if result.get('valid') else 'no'}",
    ]
    signature = result.get("signature", {})
    if isinstance(signature, dict):
        lines.append(f"Signature provider: {signature.get('provider', 'none')}")
        if signature.get("signed"):
            lines.append(
                "Signature valid: "
                + (
                    "yes"
                    if signature.get("cryptographically_valid") is True
                    else "no"
                    if signature.get("cryptographically_valid") is False
                    else "not verified"
                )
            )
            lines.append(
                f"Trusted: {'yes' if signature.get('trusted') else 'no'}"
            )
            if signature.get("identity"):
                lines.append(f"Identity: {signature['identity']}")
            if signature.get("issuer"):
                lines.append(f"Issuer: {signature['issuer']}")
            evidence = signature.get("evidence")
            if isinstance(evidence, dict):
                lines.append(
                    "Transparency-log entries: "
                    f"{evidence.get('transparency_log_entries', 0)}"
                )
    errors = result.get("errors", [])
    if errors:
        lines.append("Errors:")
        lines.extend(f"  - {item}" for item in errors)
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)

    try:
        external = ExternalManifestVerifier(
            command=_command(args.verify_command),
        )
        sigstore = SigstoreBundleVerifier(
            command=_command(args.cosign),
            key=args.sigstore_key,
            certificate_identity=args.certificate_identity,
            certificate_identity_regexp=args.certificate_identity_regexp,
            certificate_oidc_issuer=args.certificate_oidc_issuer,
            certificate_oidc_issuer_regexp=args.certificate_oidc_issuer_regexp,
        )
        verifier = StandaloneReleaseVerifier(
            external_verifier=external,
            sigstore_verifier=sigstore,
        )
        result = verifier.verify(
            args.bundle,
            policy=ReleaseVerificationPolicy(
                require_signature=args.require_signature,
                trusted_key_ids=tuple(args.trusted_key_id),
            ),
        )
    except (OSError, ValueError) as exc:
        result = {
            "valid": False,
            "release_id": "",
            "signature": {
                "provider": "none",
                "signed": False,
                "cryptographically_valid": None,
                "trusted": False,
            },
            "errors": [str(exc)],
        }

    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(_human(result))
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    sys.exit(main())
