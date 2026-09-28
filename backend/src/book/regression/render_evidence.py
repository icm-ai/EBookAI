"""Stable render-oriented evidence extracted from compiled EPUB packages."""

from __future__ import annotations

import hashlib
import html
import re
import zipfile
from pathlib import Path
from typing import List
from xml.etree import ElementTree

from book.regression.models import RenderEvidence

_WS = re.compile(r"\s+")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _normalize_text(value: str) -> str:
    return _WS.sub(" ", html.unescape(value)).strip()


class EpubRenderEvidenceCollector:
    """Create stable DOM/text-flow signatures without requiring a browser runtime."""

    def collect(self, epub_path: Path) -> RenderEvidence:
        epub_path = Path(epub_path)
        with zipfile.ZipFile(epub_path, "r") as archive:
            xhtml_names = sorted(
                name
                for name in archive.namelist()
                if name.startswith("EPUB/text/") and name.endswith(".xhtml")
            )
            xhtml_parts: List[str] = []
            flow_parts: List[str] = []

            for name in xhtml_names:
                payload = archive.read(name)
                root = ElementTree.fromstring(payload)
                for element in root.iter():
                    tag = element.tag.rsplit("}", 1)[-1]
                    text = _normalize_text(element.text or "")
                    tail = _normalize_text(element.tail or "")
                    if text:
                        xhtml_parts.append(f"{tag}:{text}")
                    else:
                        xhtml_parts.append(f"{tag}:")
                    if (
                        tag
                        in {
                            "h1",
                            "h2",
                            "h3",
                            "h4",
                            "h5",
                            "h6",
                            "p",
                            "li",
                            "blockquote",
                            "aside",
                        }
                        and text
                    ):
                        flow_parts.append(f"{tag}:{text}")
                    if tail:
                        flow_parts.append(f"tail:{tail}")

            stylesheet = archive.read("EPUB/styles/book.css")

        return RenderEvidence(
            xhtml_digest=_sha256("\n".join(xhtml_parts).encode("utf-8")),
            flow_digest=_sha256("\n".join(flow_parts).encode("utf-8")),
            stylesheet_digest=_sha256(stylesheet),
            section_count=len(xhtml_names),
        )
