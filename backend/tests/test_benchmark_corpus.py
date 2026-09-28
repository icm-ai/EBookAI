import base64
import hashlib
import json
from pathlib import Path

import pytest
from book.benchmark import CorpusIntegrityError, CorpusManifest, CorpusStore

ROOT = Path(__file__).resolve().parents[2]
REAL_MANIFEST = ROOT / "benchmark" / "corpus" / "manifest.json"


def test_real_manifest_has_explicit_rights_and_pinned_digests():
    manifest = CorpusManifest.load(REAL_MANIFEST)

    assert manifest.corpus_id == "ebookai-real-pdf-v1"
    assert len(manifest.documents) >= 2
    for document in manifest.documents:
        assert document.rights_basis
        assert document.license_url.startswith("https://")
        assert len(document.sha256) == 64
        assert document.page_count > 0
        if document.embedded_base64_path:
            assert document.redistributable is True


def test_embedded_real_pdf_materializes_without_network(tmp_path):
    store = CorpusStore(REAL_MANIFEST, tmp_path / "cache")

    result = store.fetch(["nist-ballot-definition-prototype"])[0]
    materialized = Path(result.path)

    assert result.source == "embedded"
    assert result.sha256 == (
        "98649f6216af762aa9ff1290665f42dc7978d90523ae6ddd9e50c460a8e540a0"
    )
    assert result.byte_count == 59416
    assert materialized.read_bytes().startswith(b"%PDF")
    assert store.verify(["nist-ballot-definition-prototype"])[0]["ok"] is True

    cached = store.fetch(["nist-ballot-definition-prototype"])[0]
    assert cached.cached is True
    assert cached.source == "cache"


def test_embedded_asset_digest_mismatch_is_rejected(tmp_path):
    asset = tmp_path / "bad.pdf.b64"
    raw = b"%PDF-1.4\nnot-the-pinned-document\n"
    asset.write_bytes(base64.b64encode(raw))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "corpus_id": "digest-test",
                "documents": [
                    {
                        "id": "bad",
                        "title": "Bad digest",
                        "source_url": "https://example.invalid/bad.pdf",
                        "license_url": "https://example.invalid/license",
                        "rights_basis": "Test-only explicitly redistributable bytes.",
                        "sha256": hashlib.sha256(b"different").hexdigest(),
                        "document_class": "test",
                        "language": "en",
                        "page_count": 1,
                        "redistributable": True,
                        "embedded_base64_path": asset.name,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    store = CorpusStore(manifest_path, tmp_path / "cache")
    with pytest.raises(CorpusIntegrityError, match="SHA-256 mismatch"):
        store.fetch(["bad"])
