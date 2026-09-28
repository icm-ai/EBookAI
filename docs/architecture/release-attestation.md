# Release Attestation

Milestone 10 adds provenance and optional detached signatures to EBookAI's
content-addressed release bundles.

## Threat model

Milestone 9 proves that the bytes in a bundle match the release manifest.
Milestone 10 adds a separate question: **who or what authorized this manifest?**

The two checks are deliberately separate:

- integrity: artifact SHA-256 values and `release_id`
- authenticity: detached signature over the exact canonical `manifest.json`
- trust: verifier policy decides whether the signing `key_id` is accepted

A cryptographically valid signature from an unknown key is not automatically a
trusted release.

## Bundle layout

A signed bundle contains:

    release-bundle.zip
    ├── manifest.json
    ├── attestation.json
    ├── source/source.pdf
    ├── book/bookir.json
    ├── publication/book.epub
    ├── provenance/toolchain.json
    └── reports/
        ├── publication-qa.json
        └── epubcheck.json

`provenance/toolchain.json` is a normal integrity-protected release artifact.
`attestation.json` is detached because embedding a signature inside the
manifest it signs would create a circular dependency.

## Toolchain provenance

The provenance record contains only non-secret, reproducible information:

- Python and available parser/AI package versions
- optional `EBOOKAI_BUILD_REVISION`
- selected/attempted parser names from orchestration metadata
- BookIR/reconstruction identity
- accepted/rejected AI repair provider/model/input-mode records
- EPUB compiler identity and target format
- external EPUBCheck status/version

Runtime paths, API keys, prompts containing credentials, signing commands,
private keys, tokens, wall-clock timestamps, and temporary paths are excluded.

## Signing contract

Signing is optional unless the release request sets `require_signature=true`.

Configure an external signer with:

    EBOOKAI_SIGN_COMMAND="..."
    EBOOKAI_SIGN_KEY_ID="public-key-identifier"

The signer receives the canonical manifest bytes on stdin and must return raw
signature bytes on stdout. EBookAI persists only:

- algorithm
- public/non-secret key identifier
- base64 signature
- SHA-256 of the signed manifest bytes

Private signing material remains owned by the external tool, KMS, agent, HSM,
or operating-system key store.

If signing is required but no signer/key id is configured, release creation is
rejected. If a configured signer fails, the release build fails rather than
silently producing an unsigned bundle.

## Verification and trust policy

Configure an external verifier with:

    EBOOKAI_VERIFY_COMMAND="..."
    EBOOKAI_TRUSTED_KEY_IDS="key-a,key-b"

Verifier commands may use `{payload}` and `{signature}` placeholders. If no
placeholders are present, EBookAI appends the payload and signature paths.

Verification checks, in order:

1. manifest structure
2. every artifact size and SHA-256
3. deterministic `release_id`
4. attestation key id/algorithm matches the manifest declaration
5. attested manifest SHA-256 matches the exact manifest bytes
6. detached cryptographic signature
7. optional trusted-key allowlist

A release requiring a signature cannot pass verification when no verifier is
configured.

## OpenSSL example

The generic command contract can be backed by OpenSSL, GPG, SSH signing, a KMS
wrapper, or another external signer. CI exercises a real ephemeral Ed25519 key
through OpenSSL; no long-lived private key is committed to the repository.

## Sigstore direction

The generic detached-signature contract intentionally leaves room for a
Sigstore-specific adapter. Sigstore/Cosign supports signing ordinary blobs and
recommends a bundle that can carry the signature, certificate, timestamp, and
transparency-log evidence. A future adapter can preserve that native bundle
instead of flattening it into the generic raw-signature envelope.

The current milestone does not claim Sigstore/Rekor verification until that
adapter exists.
