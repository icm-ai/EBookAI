# Standalone Release Verification and Native Sigstore

Milestone 11 makes release verification portable outside the EBookAI server and
adds a native Cosign/Sigstore bundle path.

## Standalone verifier

The verifier is available as both a Python library and a CLI.

Library:

    from book.publication import (
        ReleaseVerificationPolicy,
        StandaloneReleaseVerifier,
    )

    result = StandaloneReleaseVerifier().verify(
        "book.release.zip",
        policy=ReleaseVerificationPolicy(require_signature=True),
    )

CLI:

    PYTHONPATH=backend/src python -m book.publication.verify_cli \
      book.release.zip --json

The CLI exits with code 0 only when the release passes the requested policy.
It does not require FastAPI, review-session storage, parsers, reconstruction,
AI providers, or access to the original server that produced the release.

Generic detached-signature trust can be supplied with:

    --verify-command "..."
    --trusted-key-id release-key-2026

Native Sigstore verification supports:

    --cosign /path/to/cosign
    --sigstore-key cosign.pub

or keyless identity policy:

    --certificate-identity <expected identity>
    --certificate-oidc-issuer <expected issuer>

Regular-expression variants are also available, as is:

    --trusted-root trusted-root.json

for private/custom Sigstore infrastructure.

## Native Sigstore bundle

When release creation selects `signature_provider=sigstore`, EBookAI invokes
Cosign `sign-blob --bundle` on the canonical `manifest.json` and stores the
result without translating or flattening it:

    sigstore/manifest.sigstore.json

This preserves Cosign/Sigstore verification material such as the signature,
certificate or public-key hint, signed timestamps, and transparency-log
evidence when present.

The release manifest records only the provider boundary:

    "attestation": {
      "signed": true,
      "provider": "sigstore",
      "key_id": "... optional identity hint ...",
      "algorithm": "sigstore-bundle"
    }

The native Sigstore bundle is deliberately not placed in the release artifact
hash list because it signs `manifest.json`; including it in the manifest would
create a circular dependency. The content-addressed `release_id` therefore
identifies the release content/policy, while the native Sigstore bundle
authenticates that exact manifest.

Unsigned M9-style bundles remain byte-reproducible. Signed bundles are not
required to be byte-identical across signing runs because certificates,
timestamps, transparency-log proofs, and some signature mechanisms can contain
fresh evidence. The stable reproducibility boundary is the publication
artifacts, canonical manifest, and `release_id`; attestation is an external
evidence layer over that stable identity.

## Signing modes

Sigstore signing is explicitly configured; merely having Cosign on PATH does not
cause EBookAI to start keyless signing.

Key/KMS-style signing:

    EBOOKAI_SIGSTORE_SIGN_KEY=/path/to/cosign.key

Keyless signing:

    EBOOKAI_SIGSTORE_KEYLESS=true

The latter delegates identity acquisition to Cosign, so CI can use ambient
GitHub OIDC and interactive developer environments can use Cosign's normal
Fulcio authentication flow.

## Verification modes

Key-based verification:

    EBOOKAI_SIGSTORE_VERIFY_KEY=/path/to/cosign.pub

Keyless verification requires an explicit identity and issuer policy:

    EBOOKAI_SIGSTORE_CERT_IDENTITY=...
    EBOOKAI_SIGSTORE_CERT_ISSUER=https://token.actions.githubusercontent.com

or regexp forms:

    EBOOKAI_SIGSTORE_CERT_IDENTITY_REGEXP=...
    EBOOKAI_SIGSTORE_CERT_ISSUER_REGEXP=...

A keyless bundle is not treated as trusted if the verifier has no identity
policy. EBookAI does not use a permissive wildcard by default.

## Evidence reporting

The verifier returns the normalized trust verdict plus a summary of evidence
that remains in the untouched Sigstore bundle:

- bundle media type
- certificate / certificate-chain / public-key verification material
- number of transparency-log entries
- number of RFC3161 timestamp entries
- Cosign version used for verification

The raw Sigstore bundle remains the authoritative verification evidence.

## Compatibility

Standalone verification preserves the historical release-id rules:

- manifest 0.1: Milestone 9, no signature policy
- manifest 0.2: Milestone 10 generic detached signatures
- manifest 0.3: Milestone 11 signature-provider binding

This lets a current verifier validate old M9/M10 release bundles without
rewriting or republishing them.

## CI strategy

The lightweight BookIR test job uses a fake Cosign protocol fixture to test
provider routing, identity-policy fail-closed behavior, native bundle
preservation, CLI parity, and historical compatibility.

A separate Native Sigstore Release Gate installs pinned Cosign 3.1.3 and creates
an ephemeral local key pair. It performs real `sign-blob --bundle` and
`verify-blob --bundle` operations. For this local-key fixture the gate creates
a Cosign v3 signing configuration with no Fulcio, OIDC, Rekor, or TSA services,
avoiding public transparency-log noise while still testing the native bundle
format and Cosign verification path. Verification in that isolated local-key
gate explicitly uses `--insecure-ignore-tlog`; production keyless verification
does not set this flag and continues to require its transparency-log evidence.

Keyless public-Fulcio/Rekor signing remains supported by the adapter but is not
performed on every pull-request CI run, because that would create a public
transparency-log entry for each test execution.
