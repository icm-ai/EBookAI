import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from book.domain.models import (
    Book,
    BookMetadata,
    BookNode,
    Confidence,
    NodeType,
    SourceRef,
)
from book.publication import (
    EpubCheckMessage,
    EpubCheckResult,
    ExternalEpubCheckRunner,
    ExternalManifestSigner,
    ExternalManifestVerifier,
    ReleasePipeline,
    ReleaseVerificationPolicy,
    SigstoreBundleSigner,
    SigstoreBundleVerifier,
    StandaloneReleaseVerifier,
)
from book.publication.verify_cli import main as verify_cli_main
from book.quality import QualityReport


def _book():
    return Book(
        metadata=BookMetadata(
            title="Release Fixture",
            author="EBookAI",
            language="en",
        ),
        nodes=[
            BookNode(
                id="p1",
                type=NodeType.PARAGRAPH,
                content="A reproducible publication.",
                source=[
                    SourceRef(
                        page_index=0,
                        bbox=(10.0, 20.0, 300.0, 80.0),
                        parser="fixture",
                        source_id="fixture-source",
                    )
                ],
                confidence=Confidence(0.99, 0.99, 0.99),
            )
        ],
    )


def _quality_report():
    return QualityReport(
        issues=[],
        score=1.0,
        node_count=1,
    )


class StaticRunner:
    def __init__(self, result):
        self.result = result

    def run(self, epub_path):
        assert Path(epub_path).is_file()
        return self.result


def _passed_epubcheck():
    return EpubCheckResult(
        available=True,
        executed=True,
        valid=True,
        version="5.4.0",
        exit_code=0,
        counts={
            "fatal": 0,
            "error": 0,
            "warning": 0,
            "usage": 0,
            "info": 0,
        },
    )


def test_release_pipeline_is_byte_reproducible_and_self_verifying(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    pipeline = ReleasePipeline(epubcheck_runner=StaticRunner(_passed_epubcheck()))

    first = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "release-one",
        require_epubcheck=True,
    )
    second = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "release-two",
        require_epubcheck=True,
    )

    assert first.manifest.release_ready is True
    assert first.manifest.release_id == second.manifest.release_id
    assert first.bundle_path.read_bytes() == second.bundle_path.read_bytes()
    verification = pipeline.verify_bundle(first.bundle_path)
    assert verification["valid"] is True
    assert verification["release_id"] == first.manifest.release_id
    assert verification["signature"]["signed"] is False
    assert verification["errors"] == []

    with zipfile.ZipFile(first.bundle_path) as archive:
        assert {
            "manifest.json",
            "source/source.pdf",
            "book/bookir.json",
            "publication/book.epub",
            "reports/publication-qa.json",
            "reports/epubcheck.json",
            "provenance/toolchain.json",
        }.issubset(set(archive.namelist()))


def test_release_pipeline_detects_tampered_artifact(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    pipeline = ReleasePipeline(epubcheck_runner=StaticRunner(_passed_epubcheck()))
    result = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "release",
    )

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(result.bundle_path) as original:
        entries = {name: original.read(name) for name in original.namelist()}
    entries["book/bookir.json"] += b"\n"
    with zipfile.ZipFile(tampered, "w") as archive:
        for name in sorted(entries):
            archive.writestr(name, entries[name])

    verification = pipeline.verify_bundle(tampered)

    assert verification["valid"] is False
    assert "SHA-256 mismatch: book/bookir.json" in verification["errors"]


def test_required_unavailable_epubcheck_blocks_release(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    unavailable = EpubCheckResult(
        available=False,
        executed=False,
        valid=None,
        error="not installed",
    )
    pipeline = ReleasePipeline(epubcheck_runner=StaticRunner(unavailable))

    optional = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "optional",
        require_epubcheck=False,
    )
    required = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "required",
        require_epubcheck=True,
    )

    assert optional.manifest.release_ready is True
    assert optional.manifest.epubcheck_status == "unavailable"
    assert required.manifest.release_ready is False


def test_available_but_failing_epubcheck_always_blocks_release(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    failed = EpubCheckResult(
        available=True,
        executed=True,
        valid=False,
        version="5.4.0",
        exit_code=1,
        counts={
            "fatal": 0,
            "error": 1,
            "warning": 0,
            "usage": 0,
            "info": 0,
        },
        messages=[
            EpubCheckMessage(
                id="RSC-001",
                severity="ERROR",
                message="Missing resource",
            )
        ],
    )
    pipeline = ReleasePipeline(epubcheck_runner=StaticRunner(failed))

    result = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "failed",
        require_epubcheck=False,
    )

    assert result.manifest.release_ready is False
    assert result.manifest.epubcheck_status == "failed"


def test_external_epubcheck_runner_consumes_json_report(tmp_path):
    epub = tmp_path / "book.epub"
    epub.write_bytes(b"fixture")
    script = tmp_path / "fake_epubcheck.py"
    script.write_text(
        """import json
print(json.dumps({
    "checker": {
        "checkerVersion": "5.4.0",
        "nFatal": 0,
        "nError": 0,
        "nWarning": 1,
        "nUsage": 0,
        "nInfo": 0
    },
    "messages": [{
        "ID": "ACC-001",
        "severity": "WARNING",
        "message": "Accessibility metadata recommended.",
        "locations": [{
            "path": "EPUB/package.opf",
            "line": 4,
            "column": 2,
            "context": None
        }]
    }]
}))
""",
        encoding="utf-8",
    )
    runner = ExternalEpubCheckRunner(command=[sys.executable, str(script)])

    result = runner.run(epub)

    assert result.status == "passed"
    assert result.valid is True
    assert result.version == "5.4.0"
    assert result.counts["warning"] == 1
    assert result.messages[0].id == "ACC-001"
    assert result.messages[0].locations[0]["path"] == "EPUB/package.opf"


@pytest.mark.skipif(
    ExternalEpubCheckRunner().resolve_command() is None,
    reason="External EPUBCheck runtime is not installed",
)
def test_real_epubcheck_accepts_compiler_release_epub(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    pipeline = ReleasePipeline()

    result = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "real",
        require_epubcheck=True,
    )

    assert result.epubcheck_result.available is True
    assert result.epubcheck_result.executed is True
    assert result.epubcheck_result.valid is True, json.dumps(
        result.epubcheck_result.to_dict(),
        ensure_ascii=False,
        indent=2,
    )
    assert result.manifest.release_ready is True


def _write_signature_fixture(tmp_path: Path):
    signer_script = tmp_path / "sign.py"
    signer_script.write_text(
        """import hashlib
import sys
payload = sys.stdin.buffer.read()
sys.stdout.buffer.write(hashlib.sha256(b"fixture-public-key" + payload).digest())
""",
        encoding="utf-8",
    )
    verifier_script = tmp_path / "verify.py"
    verifier_script.write_text(
        """import hashlib
import pathlib
import sys
payload = pathlib.Path(sys.argv[1]).read_bytes()
signature = pathlib.Path(sys.argv[2]).read_bytes()
expected = hashlib.sha256(b"fixture-public-key" + payload).digest()
raise SystemExit(0 if signature == expected else 1)
""",
        encoding="utf-8",
    )
    return signer_script, verifier_script


def test_signed_release_attestation_and_trust_policy(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    signer_script, verifier_script = _write_signature_fixture(tmp_path)
    pipeline = ReleasePipeline(
        epubcheck_runner=StaticRunner(_passed_epubcheck()),
        signer=ExternalManifestSigner(
            command=[sys.executable, str(signer_script)],
            key_id="fixture-key",
            algorithm="fixture-sha256",
        ),
        verifier=ExternalManifestVerifier(
            command=[sys.executable, str(verifier_script)]
        ),
    )

    result = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "signed",
        require_signature=True,
    )

    assert result.manifest.signed is True
    assert result.manifest.signing_key_id == "fixture-key"
    assert result.attestation is not None

    trusted = pipeline.verify_bundle(
        result.bundle_path,
        require_signature=True,
        trusted_key_ids=["fixture-key"],
    )
    assert trusted["valid"] is True
    assert trusted["signature"]["cryptographically_valid"] is True
    assert trusted["signature"]["trusted"] is True

    untrusted = pipeline.verify_bundle(
        result.bundle_path,
        require_signature=True,
        trusted_key_ids=["different-key"],
    )
    assert untrusted["valid"] is False
    assert untrusted["signature"]["cryptographically_valid"] is True
    assert untrusted["signature"]["trusted"] is False


def test_required_signature_without_signer_is_rejected(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    pipeline = ReleasePipeline(epubcheck_runner=StaticRunner(_passed_epubcheck()))

    with pytest.raises(ValueError, match="signature is required"):
        pipeline.build(
            source_path=source,
            source_filename="fixture.pdf",
            book=_book(),
            quality_report=_quality_report(),
            issue_resolutions={},
            output_dir=tmp_path / "unsigned",
            require_signature=True,
        )


def test_signed_manifest_tampering_invalidates_attestation(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    signer_script, verifier_script = _write_signature_fixture(tmp_path)
    pipeline = ReleasePipeline(
        epubcheck_runner=StaticRunner(_passed_epubcheck()),
        signer=ExternalManifestSigner(
            command=[sys.executable, str(signer_script)],
            key_id="fixture-key",
            algorithm="fixture-sha256",
        ),
        verifier=ExternalManifestVerifier(
            command=[sys.executable, str(verifier_script)]
        ),
    )
    result = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "signed",
    )

    tampered = tmp_path / "tampered-signed.zip"
    with zipfile.ZipFile(result.bundle_path) as original:
        entries = {name: original.read(name) for name in original.namelist()}
    manifest = json.loads(entries["manifest.json"])
    manifest["source_filename"] = "tampered.pdf"
    entries["manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    with zipfile.ZipFile(tampered, "w") as archive:
        for name in sorted(entries):
            archive.writestr(name, entries[name])

    verification = pipeline.verify_bundle(
        tampered,
        trusted_key_ids=["fixture-key"],
    )

    assert verification["valid"] is False
    assert verification["signature"]["cryptographically_valid"] is False


def test_toolchain_provenance_is_integrity_protected(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    pipeline = ReleasePipeline(epubcheck_runner=StaticRunner(_passed_epubcheck()))
    result = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "release",
    )

    with zipfile.ZipFile(result.bundle_path) as archive:
        provenance = json.loads(archive.read("provenance/toolchain.json"))
        manifest = json.loads(archive.read("manifest.json"))

    assert provenance["schema_version"] == "0.1"
    assert provenance["compiler"]["format"] == "EPUB3"
    assert provenance["external_validation"]["epubcheck"]["version"] == "5.4.0"
    artifact = next(
        item
        for item in manifest["artifacts"]
        if item["path"] == "provenance/toolchain.json"
    )
    assert artifact["sha256"]


def test_signing_command_material_is_not_persisted_in_release(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    signer_script, _ = _write_signature_fixture(tmp_path)
    secret_marker = "super-secret-signing-material"
    pipeline = ReleasePipeline(
        epubcheck_runner=StaticRunner(_passed_epubcheck()),
        signer=ExternalManifestSigner(
            command=[sys.executable, str(signer_script), secret_marker],
            key_id="public-key-id",
            algorithm="fixture-sha256",
        ),
    )

    result = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "signed",
    )

    assert secret_marker.encode("utf-8") not in result.bundle_path.read_bytes()
    assert b"public-key-id" in result.bundle_path.read_bytes()


def test_required_signature_verification_fails_without_verifier(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    signer_script, _ = _write_signature_fixture(tmp_path)
    pipeline = ReleasePipeline(
        epubcheck_runner=StaticRunner(_passed_epubcheck()),
        signer=ExternalManifestSigner(
            command=[sys.executable, str(signer_script)],
            key_id="fixture-key",
            algorithm="fixture-sha256",
        ),
    )
    result = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "signed",
        require_signature=True,
    )

    verification = pipeline.verify_bundle(result.bundle_path)

    assert verification["valid"] is False
    assert verification["signature"]["cryptographically_valid"] is None
    assert "verifier is not configured" in " ".join(verification["errors"])


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL is not installed")
def test_real_openssl_detached_release_signature(tmp_path):
    openssl = shutil.which("openssl")
    private_key = tmp_path / "private.pem"
    public_key = tmp_path / "public.pem"
    subprocess.run(
        [openssl, "genpkey", "-algorithm", "ED25519", "-out", str(private_key)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            openssl,
            "pkey",
            "-in",
            str(private_key),
            "-pubout",
            "-out",
            str(public_key),
        ],
        check=True,
        capture_output=True,
    )

    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    pipeline = ReleasePipeline(
        epubcheck_runner=StaticRunner(_passed_epubcheck()),
        signer=ExternalManifestSigner(
            command=[
                openssl,
                "pkeyutl",
                "-sign",
                "-inkey",
                str(private_key),
                "-rawin",
                "-in",
                "{payload}",
            ],
            key_id="openssl-ed25519-fixture",
            algorithm="ed25519",
        ),
        verifier=ExternalManifestVerifier(
            command=[
                openssl,
                "pkeyutl",
                "-verify",
                "-pubin",
                "-inkey",
                str(public_key),
                "-rawin",
                "-sigfile",
                "{signature}",
                "-in",
                "{payload}",
            ]
        ),
    )

    result = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "signed-openssl",
        require_signature=True,
    )
    verification = pipeline.verify_bundle(
        result.bundle_path,
        trusted_key_ids=["openssl-ed25519-fixture"],
    )

    assert verification["valid"] is True
    assert verification["signature"]["cryptographically_valid"] is True
    assert verification["signature"]["trusted"] is True


def _write_fake_cosign(tmp_path: Path) -> Path:
    script = tmp_path / "fake_cosign.py"
    script.write_text(
        """import hashlib
import json
import pathlib
import sys

args = sys.argv[1:]
if args and args[0] == "version":
    print("GitVersion: v3.1.3")
    raise SystemExit(0)

if args and args[0] == "sign-blob":
    bundle = pathlib.Path(args[args.index("--bundle") + 1])
    payload = pathlib.Path(args[-1]).read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    native = {
        "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
        "messageSignature": {
            "messageDigest": {
                "algorithm": "SHA2_256",
                "digest": digest,
            },
            "signature": "ZmFrZS1zaWduYXR1cmU=",
        },
        "verificationMaterial": {
            "certificate": {"rawBytes": "ZmFrZS1jZXJ0"},
            "tlogEntries": [
                {
                    "logIndex": "7",
                    "integratedTime": "123456789",
                    "inclusionPromise": {
                        "signedEntryTimestamp": "ZmFrZS1zZXQ="
                    },
                }
            ],
            "timestampVerificationData": {
                "rfc3161Timestamps": [{"signedTimestamp": "ZmFrZS10cw=="}]
            },
        },
    }
    bundle.parent.mkdir(parents=True, exist_ok=True)
    bundle.write_text(
        json.dumps(native, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    raise SystemExit(0)

if args and args[0] == "verify-blob":
    payload = pathlib.Path(args[1]).read_bytes()
    bundle = pathlib.Path(args[args.index("--bundle") + 1])
    native = json.loads(bundle.read_text(encoding="utf-8"))
    expected = hashlib.sha256(payload).hexdigest()
    actual = native["messageSignature"]["messageDigest"]["digest"]
    identity_ok = (
        "--certificate-identity" in args
        and args[args.index("--certificate-identity") + 1]
        == "https://github.com/icm-ai/EBookAI/.github/workflows/ci.yml@refs/heads/develop"
    )
    issuer_ok = (
        "--certificate-oidc-issuer" in args
        and args[args.index("--certificate-oidc-issuer") + 1]
        == "https://token.actions.githubusercontent.com"
    )
    raise SystemExit(0 if expected == actual and identity_ok and issuer_ok else 1)

raise SystemExit(2)
""",
        encoding="utf-8",
    )
    return script


def test_native_sigstore_bundle_is_preserved_and_verified(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    fake_cosign = _write_fake_cosign(tmp_path)
    command = [sys.executable, str(fake_cosign)]
    identity = (
        "https://github.com/icm-ai/EBookAI/.github/workflows/"
        "ci.yml@refs/heads/develop"
    )
    issuer = "https://token.actions.githubusercontent.com"
    pipeline = ReleasePipeline(
        epubcheck_runner=StaticRunner(_passed_epubcheck()),
        sigstore_signer=SigstoreBundleSigner(
            command=command,
            keyless=True,
        ),
        sigstore_verifier=SigstoreBundleVerifier(
            command=command,
            certificate_identity=identity,
            certificate_oidc_issuer=issuer,
        ),
    )

    result = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "sigstore-release",
        require_signature=True,
        signature_provider="sigstore",
    )

    assert result.manifest.signed is True
    assert result.manifest.signature_provider == "sigstore"
    assert result.manifest.signing_algorithm == "sigstore-bundle"

    with zipfile.ZipFile(result.bundle_path) as archive:
        names = set(archive.namelist())
        assert "sigstore/manifest.sigstore.json" in names
        assert "attestation.json" not in names
        native = archive.read("sigstore/manifest.sigstore.json")
        parsed = json.loads(native)
        assert parsed["mediaType"].startswith("application/vnd.dev.sigstore.bundle")
        assert len(parsed["verificationMaterial"]["tlogEntries"]) == 1

    verification = pipeline.verify_bundle(result.bundle_path)

    assert verification["valid"] is True
    assert verification["signature"]["provider"] == "sigstore"
    assert verification["signature"]["cryptographically_valid"] is True
    assert verification["signature"]["trusted"] is True
    assert verification["signature"]["identity"] == identity
    assert verification["signature"]["issuer"] == issuer
    assert verification["signature"]["evidence"]["transparency_log_entries"] == 1


def test_sigstore_keyless_verification_requires_identity_policy(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    fake_cosign = _write_fake_cosign(tmp_path)
    command = [sys.executable, str(fake_cosign)]
    pipeline = ReleasePipeline(
        epubcheck_runner=StaticRunner(_passed_epubcheck()),
        sigstore_signer=SigstoreBundleSigner(
            command=command,
            keyless=True,
        ),
        sigstore_verifier=SigstoreBundleVerifier(command=command),
    )
    result = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "sigstore-release",
        require_signature=True,
        signature_provider="sigstore",
    )

    verification = pipeline.verify_bundle(result.bundle_path)

    assert verification["valid"] is False
    assert verification["signature"]["cryptographically_valid"] is None
    assert "identity policy" in " ".join(verification["errors"])


def test_standalone_verifier_and_cli_match_release_pipeline(tmp_path, capsys):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    pipeline = ReleasePipeline(epubcheck_runner=StaticRunner(_passed_epubcheck()))
    result = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "release",
        signature_provider="none",
    )

    standalone = StandaloneReleaseVerifier()
    verification = standalone.verify(
        result.bundle_path,
        policy=ReleaseVerificationPolicy(),
    )
    assert verification["valid"] is True
    assert verification["release_id"] == result.manifest.release_id

    exit_code = verify_cli_main([str(result.bundle_path), "--json"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["valid"] is True
    assert output["release_id"] == result.manifest.release_id


def test_verifier_accepts_legacy_manifest_v02_release_id(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    pipeline = ReleasePipeline(epubcheck_runner=StaticRunner(_passed_epubcheck()))
    result = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "current",
        signature_provider="none",
    )

    with zipfile.ZipFile(result.bundle_path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    manifest_payload = json.loads(entries["manifest.json"])
    manifest_payload["schema_version"] = "0.2"
    manifest_payload["attestation"].pop("provider", None)
    artifacts = [
        type(result.manifest.artifacts[0]).from_dict(item)
        for item in manifest_payload["artifacts"]
    ]
    manifest_payload["release_id"] = ReleasePipeline._release_id(
        artifacts,
        require_epubcheck=manifest_payload["policy"]["require_epubcheck"],
        require_signature=manifest_payload["policy"]["require_signature"],
        release_ready=manifest_payload["release_ready"],
        epubcheck_status=manifest_payload["external_validation"]["epubcheck"]["status"],
        signed=manifest_payload["attestation"]["signed"],
        signature_provider="none",
        signing_key_id=manifest_payload["attestation"]["key_id"],
        signing_algorithm=manifest_payload["attestation"]["algorithm"],
        schema_version="0.2",
    )
    entries["manifest.json"] = (
        json.dumps(
            manifest_payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")

    legacy = tmp_path / "legacy-v02.release.zip"
    with zipfile.ZipFile(legacy, "w") as archive:
        for name in sorted(entries):
            archive.writestr(name, entries[name])

    verification = pipeline.verify_bundle(legacy)

    assert verification["valid"] is True
    assert verification["release_id"] == manifest_payload["release_id"]


@pytest.mark.skipif(shutil.which("cosign") is None, reason="Cosign is not installed")
def test_real_cosign_native_bundle_with_key(tmp_path, monkeypatch):
    cosign = shutil.which("cosign")
    monkeypatch.setenv("COSIGN_PASSWORD", "ebookai-ci-fixture")
    prefix = tmp_path / "sigstore-ci"
    subprocess.run(
        [
            cosign,
            "generate-key-pair",
            "--output-key-prefix",
            str(prefix),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    signing_config = tmp_path / "signing-config.json"
    subprocess.run(
        [
            cosign,
            "signing-config",
            "create",
            "--no-default-fulcio",
            "--no-default-oidc",
            "--no-default-rekor",
            "--no-default-tsa",
            "--out",
            str(signing_config),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    pipeline = ReleasePipeline(
        epubcheck_runner=StaticRunner(_passed_epubcheck()),
        sigstore_signer=SigstoreBundleSigner(
            command=[cosign],
            key=str(prefix) + ".key",
            extra_args=["--signing-config", str(signing_config)],
        ),
        sigstore_verifier=SigstoreBundleVerifier(
            command=[cosign],
            key=str(prefix) + ".pub",
            extra_args=["--insecure-ignore-tlog"],
        ),
    )

    result = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "cosign-release",
        require_signature=True,
        signature_provider="sigstore",
    )
    verification = pipeline.verify_bundle(result.bundle_path)

    assert verification["valid"] is True
    assert verification["signature"]["provider"] == "sigstore"
    assert verification["signature"]["cryptographically_valid"] is True
    assert verification["signature"]["trusted"] is True
    assert verification["signature"]["mode"] == "key"
    assert verification["signature"]["cosign_version"]


def test_verifier_accepts_legacy_manifest_v01_release_id(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    pipeline = ReleasePipeline(epubcheck_runner=StaticRunner(_passed_epubcheck()))
    result = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "current-v01",
        signature_provider="none",
    )

    with zipfile.ZipFile(result.bundle_path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    manifest_payload = json.loads(entries["manifest.json"])
    manifest_payload["schema_version"] = "0.1"
    manifest_payload["policy"].pop("require_signature", None)
    manifest_payload.pop("attestation", None)
    artifacts = [
        type(result.manifest.artifacts[0]).from_dict(item)
        for item in manifest_payload["artifacts"]
    ]
    manifest_payload["release_id"] = ReleasePipeline._release_id(
        artifacts,
        require_epubcheck=manifest_payload["policy"]["require_epubcheck"],
        require_signature=False,
        release_ready=manifest_payload["release_ready"],
        epubcheck_status=manifest_payload["external_validation"]["epubcheck"]["status"],
        signed=False,
        signature_provider="none",
        signing_key_id="",
        signing_algorithm="",
        schema_version="0.1",
    )
    entries["manifest.json"] = (
        json.dumps(
            manifest_payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")

    legacy = tmp_path / "legacy-v01.release.zip"
    with zipfile.ZipFile(legacy, "w") as archive:
        for name in sorted(entries):
            archive.writestr(name, entries[name])

    verification = pipeline.verify_bundle(legacy)

    assert verification["valid"] is True
    assert verification["release_id"] == manifest_payload["release_id"]
